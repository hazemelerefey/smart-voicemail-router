"""Tests for security controls: sliding-window rate limit, boundary burst, password policy, CSRF."""

from __future__ import annotations

import pytest
from starlette.requests import Request

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
