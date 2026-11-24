"""Tests for Module 1: bcrypt cost >= 10, 8h inactivity expiry, revocation, and RBAC."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from svr_platform.auth import (
    create_user_session,
    hash_password,
    invalidate_user_sessions,
    resolve_auth_context,
    utcnow,
    verify_password,
)
from svr_platform.models import User


def test_bcrypt_cost_at_least_10():
    hashed = hash_password("SecureTelecom99!")
    assert hashed.startswith("$2b$12$")
    assert verify_password("SecureTelecom99!", hashed)
    assert not verify_password("WrongPassword", hashed)


def test_session_expires_after_8h_inactivity(db_manager, test_settings):
    t0 = utcnow()
    with db_manager.session_factory() as db:
        supervisor = db.scalar(select(User).where(User.email == "supervisor@telecom.local"))
        assert supervisor is not None
        raw_token, _ = create_user_session(db, supervisor, test_settings, now=t0)
        db.commit()

        # Active at 7h59m
        ctx_valid = resolve_auth_context(db, raw_token, test_settings, now=t0 + timedelta(hours=7, minutes=59))
        assert ctx_valid is not None
        assert ctx_valid.user.email == "supervisor@telecom.local"

        # Expired after > 8h inactivity from last activity
        ctx_expired = resolve_auth_context(
            db, raw_token, test_settings, now=t0 + timedelta(hours=16, minutes=1)
        )
        assert ctx_expired is None


def test_session_invalidated_on_role_or_status_change(db_manager, test_settings):
    t0 = utcnow()
    with db_manager.session_factory() as db:
        agent_user = db.scalar(select(User).where(User.email == "network.agent@telecom.local"))
        assert agent_user is not None
        token1, _ = create_user_session(db, agent_user, test_settings, now=t0)
        db.commit()

        # Role change invalidates existing token
        agent_user.role = "supervisor"
        invalidate_user_sessions(db, agent_user)
        db.commit()
        assert resolve_auth_context(db, token1, test_settings, now=t0 + timedelta(minutes=5)) is None

        # New session works until deactivation
        token2, _ = create_user_session(db, agent_user, test_settings, now=t0 + timedelta(minutes=6))
        db.commit()
        assert resolve_auth_context(db, token2, test_settings, now=t0 + timedelta(minutes=7)) is not None

        agent_user.active = False
        invalidate_user_sessions(db, agent_user)
        db.commit()
        assert resolve_auth_context(db, token2, test_settings, now=t0 + timedelta(minutes=8)) is None
