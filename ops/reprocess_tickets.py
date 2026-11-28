"""Admin-only targeted ticket reprocessing CLI with pre-run snapshot and rollback.

Requires explicit ticket IDs (--ticket-ids ...). Refuses empty or wildcard selectors
so unaffected tickets in storage/svr.db remain completely untouched.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, text

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from svr_platform.config import get_settings
from svr_platform.crypto import EncryptionService
from svr_platform.database import DatabaseManager
from svr_platform.models import (
    AIInteractionLog,
    Agent,
    Assignment,
    AuditEvent,
    Base,
    Ticket,
    Voicemail,
)
from svr_platform.services.classification import MARBERTv2ClassifierService
from svr_platform.services.factories import (
    build_adjudicator,
    build_memory_service,
    build_stt_service,
    build_transcript_gate,
)
from svr_platform.services.pipeline import run_voicemail_pipeline
from svr_platform.services.routing import release_active_assignment
from svr_platform.taxonomy import TicketStatus

_WILDCARD_TOKENS = frozenset({"*", "all", "ALL", "%", "?"})


def _serialize_value(val: Any) -> Any:
    if isinstance(val, datetime):
        return {"__datetime__": val.isoformat()}
    return val


def _deserialize_value(col_type: Any, val: Any) -> Any:
    if isinstance(val, dict) and "__datetime__" in val:
        return datetime.fromisoformat(val["__datetime__"])
    return val


def _dump_rows(db: Any, model: Any, predicate: Any) -> list[dict[str, Any]]:
    rows = db.scalars(select(model).where(predicate)).all()
    cols = [c.name for c in model.__table__.columns]
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append({col: _serialize_value(getattr(row, col)) for col in cols})
    return result


def _other_ticket_fingerprints(db: Any, target_ids: list[str]) -> list[dict[str, Any]]:
    rows = db.execute(
        select(
            Ticket.id,
            Ticket.status,
            Ticket.assigned_agent_id,
            Ticket.updated_at,
            Ticket.needs_human_review,
            Ticket.review_reason,
        )
        .where(Ticket.id.not_in(target_ids))
        .order_by(Ticket.id.asc())
    ).all()
    return [
        {
            "id": r.id,
            "status": r.status,
            "assigned_agent_id": r.assigned_agent_id,
            "updated_at": r.updated_at.isoformat() if isinstance(r.updated_at, datetime) else str(r.updated_at),
            "needs_human_review": bool(r.needs_human_review),
            "review_reason": r.review_reason,
        }
        for r in rows
    ]


def _brief_ticket_state(db: Any, target_ids: list[str]) -> dict[str, dict[str, Any]]:
    agents = {a.id: a.name for a in db.scalars(select(Agent)).all()}
    out: dict[str, dict[str, Any]] = {}
    for tid in target_ids:
        t = db.get(Ticket, tid)
        if t is None:
            continue
        tv = t.transcript_verification_json if isinstance(t.transcript_verification_json, dict) else {}
        adj = tv.get("orchestrator_adjudication") if isinstance(tv.get("orchestrator_adjudication"), dict) else {}
        out[tid] = {
            "status": t.status,
            "assigned_agent_id": t.assigned_agent_id,
            "assigned_agent_name": agents.get(t.assigned_agent_id) if t.assigned_agent_id else None,
            "complaint_category": t.complaint_category,
            "confidence": t.confidence,
            "needs_human_review": bool(t.needs_human_review),
            "review_reason": t.review_reason,
            "route_reason": t.route_reason,
            "verify_status": tv.get("status"),
            "adjudicator_mode": adj.get("mode"),
        }
    return out


def capture_snapshot(db_mgr: DatabaseManager, target_ids: list[str]) -> dict[str, Any]:
    with db_mgr.session_factory() as db:
        tickets = _dump_rows(db, Ticket, Ticket.id.in_(target_ids))
        found_ids = {row["id"] for row in tickets}
        missing = [tid for tid in target_ids if tid not in found_ids]
        if missing:
            raise ValueError(f"Target ticket ID(s) not found: {missing}")

        vm_ids = [row["voicemail_id"] for row in tickets]
        voicemails = _dump_rows(db, Voicemail, Voicemail.id.in_(vm_ids))
        assignments = _dump_rows(db, Assignment, Assignment.ticket_id.in_(target_ids))
        audit_events = _dump_rows(db, AuditEvent, AuditEvent.entity_id.in_(target_ids))
        ai_logs = _dump_rows(db, AIInteractionLog, AIInteractionLog.ticket_id.in_(target_ids))
        agents = _dump_rows(db, Agent, Agent.id.is_not(None))
        untouched = _other_ticket_fingerprints(db, target_ids)

    return {
        "target_ids": list(target_ids),
        "tickets": tickets,
        "voicemails": voicemails,
        "assignments": assignments,
        "audit_events": audit_events,
        "ai_logs": ai_logs,
        "agents": agents,
        "untouched_fingerprints": untouched,
    }


def restore_snapshot(db_mgr: DatabaseManager, snapshot_path: Path) -> dict[str, Any]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    target_ids: list[str] = list(snapshot["target_ids"])

    model_map = {
        "tickets": (Ticket, "id"),
        "voicemails": (Voicemail, "id"),
        "assignments": (Assignment, "ticket_id"),
        "audit_events": (AuditEvent, "entity_id"),
        "ai_logs": (AIInteractionLog, "ticket_id"),
        "agents": (Agent, "id"),
    }

    with db_mgr.engine.begin() as conn:
        # Remove any new rows generated during the reprocess run for target tickets
        conn.execute(Assignment.__table__.delete().where(Assignment.ticket_id.in_(target_ids)))
        conn.execute(AuditEvent.__table__.delete().where(AuditEvent.entity_id.in_(target_ids)))
        conn.execute(AIInteractionLog.__table__.delete().where(AIInteractionLog.ticket_id.in_(target_ids)))
        conn.execute(Ticket.__table__.delete().where(Ticket.id.in_(target_ids)))

        vm_ids = [row["id"] for row in snapshot.get("voicemails", [])]
        if vm_ids:
            conn.execute(Voicemail.__table__.delete().where(Voicemail.id.in_(vm_ids)))

        # Re-insert voicemails first, then tickets and child records
        for key in ("voicemails", "tickets", "assignments", "audit_events", "ai_logs"):
            model, _ = model_map[key]
            rows = snapshot.get(key, [])
            if not rows:
                continue
            cols = {c.name: c.type for c in model.__table__.columns}
            decoded = [
                {k: _deserialize_value(cols[k], v) for k, v in row.items() if k in cols}
                for row in rows
            ]
            conn.execute(model.__table__.insert(), decoded)

        for agent_row in snapshot.get("agents", []):
            cols = {c.name: c.type for c in Agent.__table__.columns}
            conn.execute(
                Agent.__table__.update()
                .where(Agent.id == agent_row["id"])
                .values(
                    current_load=agent_row["current_load"],
                    updated_at=_deserialize_value(cols["updated_at"], agent_row["updated_at"]),
                )
            )

    return {"restored_target_ids": target_ids, "snapshot_path": str(snapshot_path)}


def _validate_explicit_ticket_ids(raw_ids: list[str] | None) -> list[str]:
    if not raw_ids:
        raise ValueError("--ticket-ids requires at least one explicit ticket UUID.")
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw_ids:
        token = (item or "").strip()
        if not token or token in _WILDCARD_TOKENS or "*" in token or "%" in token:
            raise ValueError(f"Invalid or wildcard ticket ID rejected: {item!r}")
        if token not in seen:
            seen.add(token)
            cleaned.append(token)
    if not cleaned:
        raise ValueError("--ticket-ids requires at least one explicit ticket UUID.")
    return cleaned


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely reprocess explicit SVR ticket IDs with pre-run snapshot and isolation verification."
    )
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--ticket-ids",
        nargs="+",
        help="Explicit ticket UUIDs to reprocess. Wildcards and empty lists are rejected.",
    )
    mode_group.add_argument(
        "--restore-snapshot",
        type=Path,
        help="Rollback target tickets and agent loads from a saved JSON snapshot.",
    )
    parser.add_argument(
        "--snapshot-out",
        type=Path,
        help="Optional path to save full pre-run JSON snapshot before mutating target tickets.",
    )
    parser.add_argument(
        "--database-url",
        default="",
        help="Optional database URL override (defaults to configured DATABASE_URL).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    settings = get_settings()
    db_url = args.database_url.strip() or settings.database_url
    db_mgr = DatabaseManager(db_url)

    if args.restore_snapshot is not None:
        result = restore_snapshot(db_mgr, args.restore_snapshot)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    try:
        target_ids = _validate_explicit_ticket_ids(args.ticket_ids)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        snapshot = capture_snapshot(db_mgr, target_ids)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.snapshot_out is not None:
        args.snapshot_out.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot_out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    with db_mgr.session_factory() as db:
        before_states = _brief_ticket_state(db, target_ids)

    crypto = EncryptionService(settings.svr_encryption_key)
    stt_service = build_stt_service(settings)
    transcript_gate = build_transcript_gate(settings)
    memory_service = build_memory_service(settings)
    adjudicator = build_adjudicator(settings, memory_service)
    classifier_service = MARBERTv2ClassifierService(
        models_dir=settings.svr_models_dir,
        repo_root=settings.repo_root,
        base_model_id=settings.marbert_base_model,
        seed=settings.marbert_checkpoint_seed,
        max_resident_onnx_heads=settings.onnx_max_resident_heads,
    )

    try:
        for tid in target_ids:
            with db_mgr.session_factory() as db:
                ticket = db.get(Ticket, tid)
                if ticket is None:
                    raise RuntimeError(f"Target ticket disappeared: {tid}")
                voicemail = db.get(Voicemail, ticket.voicemail_id)
                release_active_assignment(db, ticket, final_status="released")
                ticket.assigned_agent_id = None
                ticket.status = TicketStatus.RECEIVED.value
                ticket.needs_human_review = False
                ticket.review_reason = None
                ticket.route_reason = ""
                if voicemail is not None:
                    voicemail.status = TicketStatus.RECEIVED.value
                db.commit()

                run_voicemail_pipeline(
                    db,
                    ticket_id=tid,
                    crypto=crypto,
                    stt_service=stt_service,
                    transcript_gate=transcript_gate,
                    classifier_service=classifier_service,
                    adjudicator=adjudicator,
                    memory_service=memory_service,
                    adaptive_reaudit_enabled=settings.adaptive_reaudit_enabled,
                    adaptive_reaudit_category_threshold=settings.adaptive_reaudit_category_threshold,
                    allow_transcript_edits=settings.transcript_edit_enabled,
                )
    finally:
        if hasattr(classifier_service, "unload"):
            classifier_service.unload()
        if hasattr(stt_service, "unload"):
            stt_service.unload()

    with db_mgr.session_factory() as db:
        after_states = _brief_ticket_state(db, target_ids)
        after_untouched = _other_ticket_fingerprints(db, target_ids)

    pre_untouched = snapshot["untouched_fingerprints"]
    diffs = [
        {"before": b, "after": a}
        for b, a in zip(pre_untouched, after_untouched)
        if b != a
    ]
    if len(pre_untouched) != len(after_untouched) or diffs:
        print(
            json.dumps(
                {
                    "error": "Non-target tickets changed unexpectedly!",
                    "untouched_count_before": len(pre_untouched),
                    "untouched_count_after": len(after_untouched),
                    "diffs": diffs,
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    print(
        json.dumps(
            {
                "reprocessed_ids": target_ids,
                "untouched_tickets_verified": len(after_untouched),
                "untouched_diffs": 0,
                "before": before_states,
                "after": after_states,
                "snapshot_path": str(args.snapshot_out) if args.snapshot_out else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
