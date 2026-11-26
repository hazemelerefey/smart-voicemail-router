"""Tests for security controls: sliding-window rate limit, boundary burst, password policy, CSRF."""

from __future__ import annotations

import pytest
from starlette.requests import Request

from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from svr_platform.api.main import create_app
from svr_platform.config import Settings
from svr_platform.models import Ticket, Voicemail
from svr_platform.security import (
    SlidingWindowRateLimiter,
    extract_client_ip,
    validate_password_strength,
)


def test_sliding_window_blocks_boundary_burst():
    limiter = SlidingWindowRateLimiter()
    # 5 requests near end of minute (t=55..59)
    for t in [55.0, 56.0, 57.0, 58.0, 59.0]:
        ok, _ = limiter.check_and_record("login:1.2.3.4", limit=5, window_seconds=60, now=t)
        assert ok is True

    # 6th request at t=61 (across fixed-window boundary!) MUST still be blocked
    ok, retry = limiter.check_and_record("login:1.2.3.4", limit=5, window_seconds=60, now=61.0)
    assert ok is False
    assert retry > 0

    # Once t=116 (> 55 + 60), oldest entry expires and request succeeds
    ok_after, _ = limiter.check_and_record("login:1.2.3.4", limit=5, window_seconds=60, now=116.0)
    assert ok_after is True


def test_lockout_blocks_attempts():
    limiter = SlidingWindowRateLimiter()
    limiter.set_lockout("acct:admin@telecom.local", duration_seconds=300, now=1000.0)
    ok, retry = limiter.check_and_record("acct:admin@telecom.local", limit=10, window_seconds=60, now=1010.0)
    assert ok is False
    assert retry >= 290


def test_password_strength_and_breach_rejection():
    with pytest.raises(ValueError, match="10 characters"):
        validate_password_strength("Short1!")
    with pytest.raises(ValueError, match="breached"):
        validate_password_strength("Password123!")
    with pytest.raises(ValueError, match="uppercase"):
        validate_password_strength("alllowercase123")
    validate_password_strength("TelecomOps2026#Safe")


def test_extract_client_ip_respects_trust_proxy():
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/auth/login",
        "headers": [(b"x-forwarded-for", b"203.0.113.9, 10.0.0.1")],
        "client": ("10.0.0.5", 44321),
    }
    req = Request(scope)
    assert extract_client_ip(req, trust_proxy=False) == "10.0.0.5"
    assert extract_client_ip(req, trust_proxy=True) == "203.0.113.9"


def test_production_config_rejects_placeholder_secrets(tmp_path):
    with pytest.raises(RuntimeError, match="SVR_SECRET_KEY"):
        Settings(
            SVR_ENV="production",
            SVR_STORAGE_DIR=tmp_path / "st",
            SVR_SECRET_KEY="replace-with-32-byte-random-secret",
            SVR_ENCRYPTION_KEY="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
            SVR_BOOTSTRAP_PASSWORD="UniqueStrongPassword2026!",
        )
    with pytest.raises(RuntimeError, match="SVR_BOOTSTRAP_PASSWORD"):
        Settings(
            SVR_ENV="production",
            SVR_STORAGE_DIR=tmp_path / "st",
            SVR_SECRET_KEY="a" * 32,
            SVR_ENCRYPTION_KEY="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
            SVR_BOOTSTRAP_PASSWORD="SvrTelecom2026!",
        )


def test_metrics_requires_auth_or_scrape_token(test_settings, db_manager):
    app = create_app(settings=test_settings, db_manager=db_manager)
    with TestClient(app) as client:
        unauth = client.get("/api/metrics")
        assert unauth.status_code == 401


def test_retention_purge_deletes_expired_records(test_settings, db_manager):
    from ops.retention_purge import purge_expired_records
    from svr_platform.seed import seed_initial_data

    db_manager.create_all()
    with db_manager.session_factory() as db:
        org = seed_initial_data(db, test_settings)
        old_ts = datetime.now(timezone.utc) - timedelta(days=120)
        blob = test_settings.svr_storage_dir / "voicemails" / "expired.wav.enc"
        blob.write_bytes(b"encrypted-demo")
        vm = Voicemail(
            organization_id=org.id,
            file_name="expired.wav",
            file_path=str(blob),
            format="wav",
            size_bytes=14,
            duration_seconds=3.0,
            status="resolved",
            idempotency_key="exp-key-1",
            content_sha256="b" * 64,
            encrypted=True,
            created_at=old_ts,
            created_by="seed",
        )
        db.add(vm)
        db.flush()
        db.add(
            Ticket(
                voicemail_id=vm.id,
                organization_id=org.id,
                status="resolved",
                needs_human_review=False,
                created_at=old_ts,
            )
        )
        db.commit()

        res = purge_expired_records(db, dry_run=False)
        assert res["purged_tickets"] == 1
        assert res["removed_files"] == 1
        assert not blob.exists()
