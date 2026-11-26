"""Scheduled retention purge CLI honoring SystemSetting.retention_days (PRD Q1, DPIA Section 4.4)."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from svr_platform.auth import record_audit_event  # noqa: E402
from svr_platform.config import get_settings  # noqa: E402
from svr_platform.database import DatabaseManager  # noqa: E402
from svr_platform.models import SystemSetting, Ticket, Voicemail  # noqa: E402


def _ensure_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def purge_expired_records(
    db: Session,
    *,
    dry_run: bool = False,
    now: datetime | None = None,
) -> dict[str, int]:
    """Delete encrypted voicemail blobs and linked tickets past each org's retention_days."""
    current = _ensure_utc(now or datetime.now(timezone.utc))
    settings_rows = db.scalars(select(SystemSetting)).all()

    purged_tickets = 0
    removed_files = 0

    for org_setting in settings_rows:
        cutoff = current - timedelta(days=max(1, int(org_setting.retention_days)))
        expired_tickets = db.scalars(
            select(Ticket).where(
                Ticket.organization_id == org_setting.organization_id,
                Ticket.created_at < cutoff,
            )
        ).all()
        if not expired_tickets:
            continue

        vm_ids = [t.voicemail_id for t in expired_tickets]
        voicemails = (
            db.scalars(select(Voicemail).where(Voicemail.id.in_(vm_ids))).all() if vm_ids else []
        )

        if dry_run:
            purged_tickets += len(expired_tickets)
            removed_files += sum(1 for v in voicemails if Path(v.file_path).is_file())
            continue

        for t in expired_tickets:
            db.delete(t)
            purged_tickets += 1
        db.flush()

        for v in voicemails:
            p = Path(v.file_path)
            if p.is_file():
                p.unlink()
                removed_files += 1
            db.delete(v)

        record_audit_event(
            db,
            organization_id=org_setting.organization_id,
            entity_type="setting",
            entity_id=org_setting.organization_id,
            action="retention_purged",
            actor="system:retention-cron",
            old_value=None,
            new_value={
                "retention_days": org_setting.retention_days,
                "purged_tickets": len(expired_tickets),
                "removed_audio_files": len(voicemails),
            },
        )

    if not dry_run and purged_tickets > 0:
        db.commit()

    return {"purged_tickets": purged_tickets, "removed_files": removed_files}


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge SVR voicemails/tickets older than retention_days.")
    parser.add_argument("--dry-run", action="store_true", help="Report counts without deleting records.")
    args = parser.parse_args()

    cfg = get_settings()
    db_mgr = DatabaseManager(cfg.database_url)
    with db_mgr.session_factory() as db:
        summary = purge_expired_records(db, dry_run=args.dry_run)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
