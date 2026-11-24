"""Authentication, bcrypt password hashing, session lifecycle, and RBAC (FR22-FR24, NFR1, NFR3)."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

import bcrypt
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .models import AuditEvent, User, UserSession
from .taxonomy import UserRole

BCRYPT_ROUNDS = 12


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def hash_session_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def record_audit_event(
    db: Session,
    *,
    organization_id: str,
    entity_type: str,
    entity_id: str,
    action: str,
    actor: str,
    old_value: dict | None = None,
    new_value: dict | None = None,
) -> AuditEvent:
    evt = AuditEvent(
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(evt)
    return evt


def create_user_session(
    db: Session,
    user: User,
    settings: Settings,
    now: datetime | None = None,
) -> tuple[str, UserSession]:
    current = _ensure_utc(now or utcnow())
    raw_token = secrets.token_urlsafe(32)
    expires_at = current + timedelta(hours=settings.session_inactivity_hours)
    sess = UserSession(
        user_id=user.id,
        organization_id=user.organization_id,
        token_hash=hash_session_token(raw_token),
        role_snapshot=user.role,
        token_version_snapshot=user.token_version,
        last_activity_at=current,
        expires_at=expires_at,
        revoked=False,
    )
    db.add(sess)
    return raw_token, sess


def invalidate_user_sessions(db: Session, user: User) -> None:
    """Revoke all active sessions and bump token_version on logout/role/status change (FR22, NFR1)."""
    user.token_version += 1
    sessions = db.scalars(
        select(UserSession).where(
            UserSession.user_id == user.id,
            UserSession.revoked.is_(False),
        )
    ).all()
    for sess in sessions:
        sess.revoked = True


def set_session_cookie(response: Response, raw_token: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.svr_cookie_secure,
        samesite="lax",
        max_age=settings.session_inactivity_hours * 3600,
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.svr_cookie_secure,
        samesite="lax",
        path="/",
    )


@dataclass
class AuthContext:
    user: User
    session: UserSession

    @property
    def organization_id(self) -> str:
        return self.user.organization_id

    @property
    def role(self) -> UserRole:
        return UserRole(self.user.role)


def extract_raw_token(request: Request, settings: Settings) -> str | None:
    cookie_val = request.cookies.get(settings.session_cookie_name)
    if cookie_val:
        return cookie_val
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            return token
    return None


def resolve_auth_context(
    db: Session,
    raw_token: str | None,
    settings: Settings,
    now: datetime | None = None,
) -> AuthContext | None:
    if not raw_token:
        return None
    token_hash = hash_session_token(raw_token)
    sess = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash))
    if sess is None or sess.revoked:
        return None
    user = db.get(User, sess.user_id)
    if user is None or not user.active:
        sess.revoked = True
        db.commit()
        return None
    if user.role != sess.role_snapshot or user.token_version != sess.token_version_snapshot:
        sess.revoked = True
        db.commit()
        return None

    current = _ensure_utc(now or utcnow())
    inactivity_limit = timedelta(hours=settings.session_inactivity_hours)
    last_active = _ensure_utc(sess.last_activity_at)
    expires_at = _ensure_utc(sess.expires_at)
    if current > expires_at or (current - last_active) > inactivity_limit:
        sess.revoked = True
        db.commit()
        return None

    # Sliding 8-hour inactivity window
    sess.last_activity_at = current
    sess.expires_at = current + inactivity_limit
    db.commit()
    return AuthContext(user=user, session=sess)


def get_db_from_app(request: Request):
    db_mgr = request.app.state.db_manager
    yield from db_mgr.session()


def get_current_auth(
    request: Request,
    db: Session = Depends(get_db_from_app),
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    raw_token = extract_raw_token(request, settings)
    ctx = resolve_auth_context(db, raw_token, settings)
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required or session expired.",
        )
    return ctx


def require_roles(*allowed_roles: UserRole) -> Callable[[AuthContext], AuthContext]:
    allowed = {r.value for r in allowed_roles}

    def _checker(ctx: AuthContext = Depends(get_current_auth)) -> AuthContext:
        if ctx.user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{ctx.user.role}' is not permitted for this operation.",
            )
        return ctx

    return _checker
