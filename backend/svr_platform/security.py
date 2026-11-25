"""Security controls: sliding-window rate limiting, CSRF, password policy, security headers."""

from __future__ import annotations

import hmac
import logging
import secrets
import threading
import time
from collections import deque
from urllib.parse import urlparse

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from .config import Settings

logger = logging.getLogger("svr_platform.security")

# Curated high-frequency breached / weak passwords rejected regardless of complexity
COMMON_BREACHED_PASSWORDS = frozenset(
    {
        "password",
        "password123",
        "password123!",
        "12345678",
        "123456789",
        "1234567890",
        "qwerty123",
        "admin123",
        "admin1234",
        "welcome1",
        "welcome123",
        "letmein123",
        "iloveyou",
        "football1",
        "monkey123",
        "dragon123",
        "abc123456",
        "passw0rd",
        "p@ssw0rd",
        "p@ssword1",
        "changeme1",
        "telecom123",
        "vodafone123",
        "orange123",
        "etisalat123",
    }
)


def validate_password_strength(password: str) -> None:
    """Enforce password length, character classes, and common-breach denylist."""
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters long.")
    if password.lower() in COMMON_BREACHED_PASSWORDS:
        raise ValueError("Password appears in a known weak/breached password list.")
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_upper and has_lower and has_digit):
        raise ValueError(
            "Password must include uppercase letters, lowercase letters, and at least one digit."
        )


def extract_client_ip(request: Request, trust_proxy: bool = False) -> str:
    """Extract client IP safely; trust X-Forwarded-For only when behind a configured proxy."""
    if trust_proxy:
        xff = request.headers.get("X-Forwarded-For", "").strip()
        if xff:
            first_hop = xff.split(",")[0].strip()
            if first_hop:
                return first_hop
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window rate limiter with lockout support (no boundary burst flaw)."""

    def __init__(self, redis_url: str = "") -> None:
        self._lock = threading.Lock()
        self._windows: dict[str, deque[float]] = {}
        self._lockouts: dict[str, float] = {}
        self._redis = None
        if redis_url:
            try:
                import redis

                client = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=1.0)
                client.ping()
                self._redis = client
            except Exception as exc:
                logger.warning("Redis rate limiter unavailable (%s); falling back to local sliding window.", exc)

    def check_and_record(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
        now: float | None = None,
    ) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds) using an exact sliding time window."""
        ts = time.time() if now is None else now
        if self._redis is not None and now is None:
            return self._check_redis(key, limit=limit, window_seconds=window_seconds, ts=ts)
        return self._check_memory(key, limit=limit, window_seconds=window_seconds, ts=ts)

    def _check_memory(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
        ts: float,
    ) -> tuple[bool, int]:
        with self._lock:
            locked_until = self._lockouts.get(key, 0.0)
            if ts < locked_until:
                return False, max(1, int(locked_until - ts) + 1)

            bucket = self._windows.setdefault(key, deque())
            cutoff = ts - window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                retry_after = max(1, int(bucket[0] + window_seconds - ts) + 1)
                return False, retry_after

            bucket.append(ts)
            return True, 0

    def _check_redis(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
        ts: float,
    ) -> tuple[bool, int]:
        try:
            lock_key = f"svr:rl:lock:{key}"
            ttl = self._redis.ttl(lock_key)
            if ttl and ttl > 0:
                return False, int(ttl)

            zkey = f"svr:rl:win:{key}"
            cutoff = ts - window_seconds
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(zkey, 0, cutoff)
            pipe.zcard(zkey)
            _, count = pipe.execute()
            if int(count) >= limit:
                oldest = self._redis.zrange(zkey, 0, 0, withscores=True)
                retry_after = max(1, int(oldest[0][1] + window_seconds - ts) + 1) if oldest else window_seconds
                return False, retry_after

            member = f"{ts}:{secrets.token_hex(4)}"
            pipe = self._redis.pipeline()
            pipe.zadd(zkey, {member: ts})
            pipe.expire(zkey, window_seconds + 5)
            pipe.execute()
            return True, 0
        except Exception as exc:
            logger.warning("Redis rate limiter error (%s); falling back to memory window.", exc)
            return self._check_memory(key, limit=limit, window_seconds=window_seconds, ts=ts)

    def set_lockout(self, key: str, duration_seconds: int, now: float | None = None) -> None:
        ts = time.time() if now is None else now
        if self._redis is not None and now is None:
            try:
                self._redis.setex(f"svr:rl:lock:{key}", duration_seconds, "1")
                return
            except Exception as exc:
                logger.warning("Redis lockout write failed (%s); storing in memory.", exc)
        with self._lock:
            self._lockouts[key] = ts + duration_seconds

    def clear_key(self, key: str) -> None:
        with self._lock:
            self._windows.pop(key, None)
            self._lockouts.pop(key, None)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        httponly=False,  # JS reads cookie and echoes in X-CSRF-Token header
        secure=settings.svr_cookie_secure,
        samesite="lax",
        max_age=settings.session_inactivity_hours * 3600,
        path="/",
    )


def clear_csrf_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        httponly=False,
        secure=settings.svr_cookie_secure,
        samesite="lax",
        path="/",
    )


def verify_csrf(request: Request, settings: Settings) -> None:
    """Verify double-submit CSRF token and Origin/Referer on cookie-authenticated mutations."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    # Only enforce cookie CSRF when request uses cookie auth (not explicit Bearer API token)
    has_session_cookie = settings.session_cookie_name in request.cookies
    if not has_session_cookie:
        return

    origin = request.headers.get("Origin")
    if origin and origin not in settings.cors_origins_list:
        parsed_req = f"{request.url.scheme}://{request.url.netloc}"
        if origin != parsed_req:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-origin state-changing request rejected.",
            )

    referer = request.headers.get("Referer")
    if referer and not origin:
        ref_parsed = urlparse(referer)
        ref_origin = f"{ref_parsed.scheme}://{ref_parsed.netloc}"
        parsed_req = f"{request.url.scheme}://{request.url.netloc}"
        if ref_origin not in settings.cors_origins_list and ref_origin != parsed_req:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-site referer rejected.",
            )

    cookie_token = request.cookies.get(settings.csrf_cookie_name, "")
    header_token = request.headers.get("X-CSRF-Token", "")
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid CSRF token.",
        )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline security headers (CSP, X-Content-Type-Options, X-Frame-Options) on every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(), microphone=(self)")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; media-src 'self' blob:; connect-src 'self' ws: wss:; frame-ancestors 'none';",
        )
        return response
