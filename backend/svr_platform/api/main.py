"""Production FastAPI application for Smart Voicemail Router (SVR-PRD-02)."""

from __future__ import annotations

import asyncio
import base64
import csv
import hashlib
import hmac
import io
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
from cryptography.fernet import InvalidToken
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from sqlalchemy import func, nullslast, or_, select, text
from sqlalchemy.orm import Session

from ..auth import (
    AuthContext,
    clear_session_cookie,
    create_user_session,
    get_current_auth,
    get_db_from_app,
    hash_password,
    invalidate_user_sessions,
    record_audit_event,
    require_roles,
    resolve_auth_context,
    set_session_cookie,
    utcnow,
    verify_password,
)
from ..config import Settings, get_settings
from ..crypto import EncryptionService
from ..database import DatabaseManager
from ..models import (
    AIInteractionLog,
    Agent,
    AuditEvent,
    EvalRun,
    ScriptTemplate,
    SkillMapping,
    SystemSetting,
    Ticket,
    User,
    Voicemail,
    new_uuid,
)
from ..security import (
    SecurityHeadersMiddleware,
    SlidingWindowRateLimiter,
    clear_csrf_cookie,
    extract_client_ip,
    generate_csrf_token,
    set_csrf_cookie,
    verify_csrf,
)
from ..seed import seed_initial_data
from ..services.brief import build_callback_brief
from ..services.classification import CLASSIFICATION_FIELDS, MARBERTv2ClassifierService
from ..services.intake import (
    MAX_BYTES,
    IntakeValidationError,
    read_upload_limited,
    validate_and_probe_audio,
)
from ..services.pipeline import run_voicemail_pipeline
from ..services.priority import compute_priority
from ..services.routing import (
    assign_ticket_to_agent,
    recommend_route,
    release_active_assignment,
)
from ..services.stt import WhisperSTTService
from ..services.text_norm import normalize_transcript
from ..services.agentic_gate import AgenticTranscriptGate
from ..services.transcript_gate import TranscriptVerificationGate
from ..taxonomy import (
    ALLOWED_TICKET_TRANSITIONS,
    ComplaintCategory,
    TicketStatus,
    UserRole,
)
from .schemas import (
    AIInteractionLogResponse,
    AgentCreateRequest,
    AgentResponse,
    AgentUpdateRequest,
    AuditEventResponse,
    AuditLogListResponse,
    AuthResponse,
    CorrectionApplyRequest,
    CorrectionPreviewRequest,
    CorrectionPreviewResponse,
    EvalRunResponse,
    HealthResponse,
    LoginRequest,
    LogoutResponse,
    MonitoringAlert,
    MonitoringSummaryResponse,
    PatchTicketRequest,
    ScriptTemplateResponse,
    ScriptTemplateUpdateRequest,
    SettingsResponse,
    SettingsUpdateRequest,
    SkillMappingItem,
    SkillMappingListResponse,
    SkillMappingUpdateRequest,
    TicketDetail,
    TicketListResponse,
    TicketSummary,
    UserResponse,
    VoicemailUploadResponse,
)
from .ws import QueueHub

logger = logging.getLogger("svr_platform.api")

APP_VERSION = "1.0.0"
_DUMMY_BCRYPT_HASH = hash_password("DummyTimingProtection2026!")

_MEDIA_TYPES: dict[str, str] = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
}

_PIPELINE_STAGES = ("transcribe", "verify_transcript", "classify", "priority", "route", "brief")
_STAGE_ORDER = {name: idx for idx, name in enumerate(_PIPELINE_STAGES)}
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _encode_cursor(offset: int) -> str:
    raw = json.dumps({"offset": max(0, int(offset))}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> int:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("offset"), int) or payload["offset"] < 0:
            raise ValueError("Invalid cursor structure")
        return int(payload["offset"])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pagination cursor.",
        ) from exc


def _csv_safe_cell(val: Any) -> str:
    if val is None:
        return ""
    s = json.dumps(val, ensure_ascii=False) if isinstance(val, (dict, list)) else str(val)
    if s and s[0] in _CSV_FORMULA_PREFIXES:
        return "'" + s
    return s


def _latency_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p50": 0.0, "p95": 0.0, "mean": 0.0}
    arr = np.asarray(values, dtype=float)
    return {
        "p50": round(float(np.percentile(arr, 50)), 2),
        "p95": round(float(np.percentile(arr, 95)), 2),
        "mean": round(float(np.mean(arr)), 2),
    }


def _build_prometheus_metrics() -> tuple[CollectorRegistry, dict[str, Any]]:
    registry = CollectorRegistry()
    metrics = {
        "http_requests": Counter(
            "svr_http_requests_total",
            "Total HTTP requests handled by SVR API",
            ["method", "path", "status"],
            registry=registry,
        ),
        "http_duration": Histogram(
            "svr_http_request_duration_seconds",
            "HTTP request latency in seconds",
            ["method", "path"],
            registry=registry,
        ),
        "pipeline_runs": Counter(
            "svr_pipeline_runs_total",
            "Total voicemail AI pipeline runs by terminal status",
            ["status"],
            registry=registry,
        ),
        "pipeline_duration": Histogram(
            "svr_pipeline_duration_seconds",
            "End-to-end voicemail pipeline duration in seconds",
            buckets=(0.25, 0.5, 1.0, 2.0, 4.0, 6.0, 8.0, 10.0, 15.0, 30.0, 60.0),
            registry=registry,
        ),
        "stage_duration": Histogram(
            "svr_pipeline_stage_duration_seconds",
            "Per-stage AI pipeline latency in seconds",
            ["stage"],
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
            registry=registry,
        ),
        "human_review_tickets": Counter(
            "svr_human_review_tickets_total",
            "Tickets flagged for Human Review by reason",
            ["reason"],
            registry=registry,
        ),
        "ws_connections": Gauge(
            "svr_active_websocket_connections",
            "Active WebSocket queue subscribers",
            registry=registry,
        ),
    }
    return registry, metrics


def _require_csrf_dep(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    verify_csrf(request, settings)


def _check_rate_limit(
    request: Request,
    *,
    key: str,
    limit: int,
    window_seconds: int,
    detail: str = "Rate limit exceeded. Please retry later.",
) -> None:
    limiter: SlidingWindowRateLimiter = request.app.state.rate_limiter
    ok, retry_after = limiter.check_and_record(
        key,
        limit=limit,
        window_seconds=window_seconds,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(retry_after)},
        )


def _build_ticket_summary(
    ticket: Ticket,
    vm_map: dict[str, Voicemail],
    agent_map: dict[str, Agent],
) -> TicketSummary:
    vm = vm_map.get(ticket.voicemail_id)
    agent = agent_map.get(ticket.assigned_agent_id) if ticket.assigned_agent_id else None
    return TicketSummary(
        id=ticket.id,
        voicemail_id=ticket.voicemail_id,
        status=ticket.status,
        file_name=vm.file_name if vm else "",
        duration_seconds=vm.duration_seconds if vm else 0.0,
        summary=ticket.summary,
        customer_request=ticket.customer_request,
        suggested_script=ticket.suggested_script,
        complaint_category=ticket.complaint_category,
        complaint_urgency=ticket.complaint_urgency,
        customer_state=ticket.customer_state,
        churn_risk=ticket.churn_risk,
        confidence=ticket.confidence,
        confidence_threshold_snapshot=ticket.confidence_threshold_snapshot,
        priority_score=ticket.priority_score,
        queue_priority=ticket.queue_priority,
        assigned_agent_id=ticket.assigned_agent_id,
        assigned_agent_name=agent.name if agent else None,
        route_reason=ticket.route_reason,
        needs_human_review=ticket.needs_human_review,
        review_reason=ticket.review_reason,
        language_mix=ticket.language_mix,
        stage_status=dict(ticket.stage_status or {}),
        processing_ms=ticket.processing_ms,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def _build_ticket_detail(db: Session, ticket: Ticket) -> TicketDetail:
    vm = db.get(Voicemail, ticket.voicemail_id)
    agent = db.get(Agent, ticket.assigned_agent_id) if ticket.assigned_agent_id else None
    ai_logs = sorted(
        db.scalars(
            select(AIInteractionLog)
            .where(
                AIInteractionLog.organization_id == ticket.organization_id,
                AIInteractionLog.ticket_id == ticket.id,
            )
            .order_by(AIInteractionLog.created_at.asc(), AIInteractionLog.id.asc())
        ).all(),
        key=lambda x: (_ensure_utc(x.created_at), _STAGE_ORDER.get(x.stage, 99)),
    )
    audit_events = db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.organization_id == ticket.organization_id,
            AuditEvent.entity_type == "ticket",
            AuditEvent.entity_id == ticket.id,
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    ).all()

    return TicketDetail(
        id=ticket.id,
        voicemail_id=ticket.voicemail_id,
        organization_id=ticket.organization_id,
        status=ticket.status,
        file_name=vm.file_name if vm else "",
        format=vm.format if vm else "wav",
        size_bytes=vm.size_bytes if vm else 0,
        duration_seconds=vm.duration_seconds if vm else 0.0,
        audio_url=f"/api/voicemails/{ticket.voicemail_id}/audio",
        transcript=ticket.transcript,
        text_norm=ticket.text_norm,
        language_mix=ticket.language_mix,
        stt_v1_json=vm.stt_v1_json if vm else None,
        transcript_verification=(
            dict(ticket.transcript_verification_json)
            if ticket.transcript_verification_json
            else None
        ),
        complaint_category=ticket.complaint_category,
        complaint_urgency=ticket.complaint_urgency,
        customer_state=ticket.customer_state,
        churn_risk=ticket.churn_risk,
        label_sources=dict(ticket.label_sources or {}),
        probabilities=dict(ticket.probabilities or {}),
        confidence=ticket.confidence,
        confidence_threshold_snapshot=ticket.confidence_threshold_snapshot,
        priority_score=ticket.priority_score,
        queue_priority=ticket.queue_priority,
        priority_signals=dict(ticket.priority_signals or {}),
        priority_reason=ticket.priority_reason,
        route_reason=ticket.route_reason,
        assigned_agent_id=ticket.assigned_agent_id,
        assigned_agent_name=agent.name if agent else None,
        summary=ticket.summary,
        customer_request=ticket.customer_request,
        suggested_script=ticket.suggested_script,
        needs_human_review=ticket.needs_human_review,
        review_reason=ticket.review_reason,
        model_version=ticket.model_version,
        stage_status=dict(ticket.stage_status or {}),
        stage_timing_ms=dict(ticket.stage_timing_ms or {}),
        processing_ms=ticket.processing_ms,
        config_snapshot=dict(ticket.config_snapshot or {}),
        ai_logs=[AIInteractionLogResponse.model_validate(x) for x in ai_logs],
        audit_events=[AuditEventResponse.model_validate(x) for x in audit_events],
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def _get_ticket_in_org(db: Session, ticket_id: str, organization_id: str) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")
    return ticket


def _build_ws_snapshot(
    db: Session,
    *,
    organization_id: str,
    role: UserRole,
    linked_agent_id: str | None,
) -> dict[str, Any]:
    stmt = select(Ticket).where(Ticket.organization_id == organization_id)
    if role == UserRole.AGENT:
        if not linked_agent_id:
            tickets: list[Ticket] = []
        else:
            tickets = list(
                db.scalars(
                    stmt.where(Ticket.assigned_agent_id == linked_agent_id)
                    .order_by(nullslast(Ticket.priority_score.desc()), Ticket.created_at.desc())
                    .limit(20)
                ).all()
            )
    else:
        tickets = list(
            db.scalars(
                stmt.order_by(nullslast(Ticket.priority_score.desc()), Ticket.created_at.desc()).limit(20)
            ).all()
        )

    vm_ids = [t.voicemail_id for t in tickets]
    agent_ids = [t.assigned_agent_id for t in tickets if t.assigned_agent_id]
    vm_map = (
        {v.id: v for v in db.scalars(select(Voicemail).where(Voicemail.id.in_(vm_ids))).all()}
        if vm_ids
        else {}
    )
    agent_map = (
        {a.id: a for a in db.scalars(select(Agent).where(Agent.id.in_(agent_ids))).all()}
        if agent_ids
        else {}
    )
    sys_setting = db.get(SystemSetting, organization_id)

    count_stmt = select(func.count(Ticket.id)).where(Ticket.organization_id == organization_id)
    review_stmt = select(func.count(Ticket.id)).where(
        Ticket.organization_id == organization_id,
        Ticket.needs_human_review.is_(True),
    )
    if role == UserRole.AGENT:
        if linked_agent_id:
            count_stmt = count_stmt.where(Ticket.assigned_agent_id == linked_agent_id)
            review_stmt = review_stmt.where(Ticket.assigned_agent_id == linked_agent_id)
        else:
            count_stmt = None
            review_stmt = None

    total_count = int(db.scalar(count_stmt) or 0) if count_stmt is not None else 0
    review_count = int(db.scalar(review_stmt) or 0) if review_stmt is not None else 0

    return {
        "organization_id": organization_id,
        "total_tickets": total_count,
        "human_review_count": review_count,
        "auto_routing_enabled": sys_setting.auto_routing_enabled if sys_setting else True,
        "items": [
            _build_ticket_summary(t, vm_map, agent_map).model_dump(mode="json") for t in tickets
        ],
    }


def _run_pipeline_bg(app: FastAPI, ticket_id: str) -> None:
    """Execute voicemail pipeline in worker thread without blocking HTTP response."""
    db_mgr: DatabaseManager = app.state.db_manager
    crypto: EncryptionService = app.state.crypto
    stt_service: WhisperSTTService = app.state.stt_service
    transcript_gate: TranscriptVerificationGate = app.state.transcript_gate
    classifier_service: MARBERTv2ClassifierService = app.state.classifier_service
    queue_hub: QueueHub = app.state.queue_hub
    prom = app.state.prom_metrics

    with db_mgr.session_factory() as db:
        try:
            ticket = run_voicemail_pipeline(
                db,
                ticket_id=ticket_id,
                crypto=crypto,
                stt_service=stt_service,
                transcript_gate=transcript_gate,
                classifier_service=classifier_service,
                on_update=lambda evt: queue_hub.broadcast_threadsafe(evt["organization_id"], evt),
            )
            prom["pipeline_runs"].labels(status=ticket.status).inc()
            prom["pipeline_duration"].observe(max(0.0, ticket.processing_ms / 1000.0))
            for stage, ms in (ticket.stage_timing_ms or {}).items():
                prom["stage_duration"].labels(stage=stage).observe(max(0.0, float(ms) / 1000.0))
            if ticket.needs_human_review:
                prom["human_review_tickets"].labels(reason=ticket.review_reason or "unspecified").inc()
        except Exception:
            logger.exception("Unhandled pipeline failure for ticket %s", ticket_id)
            prom["pipeline_runs"].labels(status="failed").inc()
            failed_ticket = db.get(Ticket, ticket_id)
            if failed_ticket is not None and failed_ticket.status == TicketStatus.PROCESSING.value:
                failed_ticket.status = TicketStatus.FAILED.value
                failed_ticket.needs_human_review = True
                failed_ticket.review_reason = "processing_error"
                failed_ticket.route_reason = (
                    "FAILED: unexpected background worker error. Ticket escalated to Human Review."
                )
                vm = db.get(Voicemail, failed_ticket.voicemail_id)
                if vm is not None:
                    vm.status = TicketStatus.FAILED.value
                db.commit()
                queue_hub.broadcast_threadsafe(
                    failed_ticket.organization_id,
                    {
                        "type": "ticket_update",
                        "organization_id": failed_ticket.organization_id,
                        "ticket_id": failed_ticket.id,
                        "status": failed_ticket.status,
                        "needs_human_review": True,
                        "review_reason": "processing_error",
                        "assigned_agent_id": None,
                    },
                )


def create_app(
    *,
    settings: Settings | None = None,
    db_manager: DatabaseManager | None = None,
    stt_service: WhisperSTTService | None = None,
    transcript_gate: TranscriptVerificationGate | AgenticTranscriptGate | None = None,
    classifier_service: MARBERTv2ClassifierService | None = None,
) -> FastAPI:
    """Create and configure the production SVR FastAPI application."""
    resolved_settings = settings or get_settings()
    resolved_db = db_manager or DatabaseManager(resolved_settings.database_url)
    resolved_crypto = EncryptionService(resolved_settings.svr_encryption_key)
    resolved_limiter = SlidingWindowRateLimiter(redis_url=resolved_settings.redis_url)
    resolved_hub = QueueHub()
    prom_registry, prom_metrics = _build_prometheus_metrics()

    whisper_cache = str(resolved_settings.repo_root / ".cache" / "huggingface")
    resolved_stt = stt_service or WhisperSTTService(
        model_id=resolved_settings.whisper_model_id,
        device=resolved_settings.whisper_device,
        compute_type=resolved_settings.whisper_compute_type,
        download_root=whisper_cache,
        ffmpeg_bin=resolved_settings.ffmpeg_bin,
    )
    resolved_gate = transcript_gate or (
        AgenticTranscriptGate(
            ollama_url=resolved_settings.ollama_url,
            ollama_model=resolved_settings.qwen_model_id,
            max_iterations=resolved_settings.agentic_gate_max_iterations,
            confidence_threshold=resolved_settings.qwen_confidence_threshold,
            early_stop_confidence=resolved_settings.agentic_gate_early_stop_confidence,
            timeout_s=resolved_settings.qwen_timeout_s,
        )
        if resolved_settings.agentic_gate_enabled
        else TranscriptVerificationGate(
            backend=resolved_settings.qwen_backend,
            ollama_url=resolved_settings.ollama_url,
            ollama_model=resolved_settings.qwen_model_id,
            hf_model_id=resolved_settings.qwen_hf_model_id,
            max_rounds=resolved_settings.qwen_max_rounds,
            confidence_threshold=resolved_settings.qwen_confidence_threshold,
            timeout_s=resolved_settings.qwen_timeout_s,
        )
    )
    resolved_classifier = classifier_service or MARBERTv2ClassifierService(
        models_dir=resolved_settings.svr_models_dir,
        repo_root=resolved_settings.repo_root,
        base_model_id=resolved_settings.marbert_base_model,
        seed=resolved_settings.marbert_checkpoint_seed,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.db_manager.create_all()
        with application.state.db_manager.session_factory() as db:
            seed_initial_data(db, application.state.settings)
        application.state.queue_hub.set_loop(asyncio.get_running_loop())
        yield

    application = FastAPI(
        title="Smart Voicemail Router (SVR) API",
        version=APP_VERSION,
        description=(
            "Production API for Egypt Telecom Care single-speaker Egyptian Arabic voicemail "
            "transcription, four-field MARBERTv2 classification, explainable queue prioritization, "
            "and deterministic telecom agent routing."
        ),
        lifespan=lifespan,
    )

    application.state.settings = resolved_settings
    application.state.db_manager = resolved_db
    application.state.crypto = resolved_crypto
    application.state.rate_limiter = resolved_limiter
    application.state.queue_hub = resolved_hub
    application.state.stt_service = resolved_stt
    application.state.transcript_gate = resolved_gate
    application.state.classifier_service = resolved_classifier
    application.state.prom_registry = prom_registry
    application.state.prom_metrics = prom_metrics

    # Ensure FastAPI dependencies always resolve this app instance's settings
    application.dependency_overrides[get_settings] = lambda: resolved_settings

    # Security headers middleware
    application.add_middleware(SecurityHeadersMiddleware)

    # Restricted CORS middleware (never '*' with allow_credentials=True)
    safe_origins = [origin for origin in resolved_settings.cors_origins_list if origin != "*"]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=safe_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key", "Authorization"],
    )

    @application.middleware("http")
    async def _metrics_middleware(request: Request, call_next):
        t0 = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            elapsed = max(0.0, time.perf_counter() - t0)
            route = request.scope.get("route")
            path_label = getattr(route, "path", request.url.path)
            prom_metrics["http_requests"].labels(
                method=request.method,
                path=path_label,
                status=str(status_code),
            ).inc()
            prom_metrics["http_duration"].labels(
                method=request.method,
                path=path_label,
            ).observe(elapsed)

    @application.exception_handler(Exception)
    async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        error_id = uuid.uuid4().hex[:12]
        logger.exception("Unhandled exception [error_id=%s] on %s %s", error_id, request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error.", "error_id": error_id},
        )

    # ------------------------------------------------------------------
    # Authentication Endpoints
    # ------------------------------------------------------------------

    @application.post("/api/auth/login", response_model=AuthResponse, tags=["Auth"])
    def login(
        body: LoginRequest,
        request: Request,
        response: Response,
        db: Session = Depends(get_db_from_app),
        cfg: Settings = Depends(get_settings),
    ) -> AuthResponse:
        client_ip = extract_client_ip(request, trust_proxy=cfg.svr_trust_proxy)
        _check_rate_limit(
            request,
            key=f"login:ip:{client_ip}",
            limit=10,
            window_seconds=60,
            detail="Too many login attempts from this IP. Please retry shortly.",
        )

        email_norm = body.email.strip().lower()
        limiter: SlidingWindowRateLimiter = request.app.state.rate_limiter
        lock_ok, lock_retry = limiter.check_and_record(
            f"login:lock:{email_norm}",
            limit=1_000_000,
            window_seconds=1,
        )
        if not lock_ok:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Account temporarily locked due to repeated failed login attempts.",
                headers={"Retry-After": str(lock_retry)},
            )

        user = db.scalar(select(User).where(func.lower(User.email) == email_norm))
        password_ok = False
        if user is not None and user.active:
            password_ok = verify_password(body.password, user.password_hash)
        else:
            # Constant-time mitigation against user enumeration
            verify_password(body.password, _DUMMY_BCRYPT_HASH)

        if not password_ok or user is None:
            fail_ok, _ = limiter.check_and_record(
                f"login:fail:{email_norm}",
                limit=4,
                window_seconds=900,
            )
            if not fail_ok:
                limiter.set_lockout(f"login:lock:{email_norm}", duration_seconds=300)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many failed login attempts. Account locked for 5 minutes.",
                    headers={"Retry-After": "300"},
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        limiter.clear_key(f"login:fail:{email_norm}")
        raw_token, sess = create_user_session(db, user, cfg)
        csrf_token = generate_csrf_token()
        set_session_cookie(response, raw_token, cfg)
        set_csrf_cookie(response, csrf_token, cfg)

        record_audit_event(
            db,
            organization_id=user.organization_id,
            entity_type="user",
            entity_id=user.id,
            action="login",
            actor=user.email,
            old_value=None,
            new_value={"session_id": sess.id, "role": user.role, "ip": client_ip},
        )
        db.commit()

        return AuthResponse(
            user=UserResponse.model_validate(user),
            csrf_token=csrf_token,
            message="Authenticated.",
        )

    @application.post(
        "/api/auth/logout",
        response_model=LogoutResponse,
        dependencies=[Depends(_require_csrf_dep)],
        tags=["Auth"],
    )
    def logout(
        response: Response,
        ctx: AuthContext = Depends(get_current_auth),
        db: Session = Depends(get_db_from_app),
        cfg: Settings = Depends(get_settings),
    ) -> LogoutResponse:
        invalidate_user_sessions(db, ctx.user)
        record_audit_event(
            db,
            organization_id=ctx.organization_id,
            entity_type="user",
            entity_id=ctx.user.id,
            action="logout",
            actor=ctx.user.email,
            old_value={"session_id": ctx.session.id},
            new_value={"revoked": True},
        )
        db.commit()
        clear_session_cookie(response, cfg)
        clear_csrf_cookie(response, cfg)
        return LogoutResponse(message="Logged out.")

    @application.get("/api/auth/me", response_model=UserResponse, tags=["Auth"])
    def get_me(ctx: AuthContext = Depends(get_current_auth)) -> UserResponse:
        return UserResponse.model_validate(ctx.user)

    # ------------------------------------------------------------------
    # Voicemail Intake & Audio Streaming
    # ------------------------------------------------------------------

    @application.post(
        "/api/voicemails",
        response_model=VoicemailUploadResponse,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[Depends(_require_csrf_dep)],
        tags=["Voicemails"],
    )
    async def upload_voicemail(
        request: Request,
        response: Response,
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        ctx: AuthContext = Depends(
            require_roles(UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT)
        ),
        db: Session = Depends(get_db_from_app),
        cfg: Settings = Depends(get_settings),
    ) -> VoicemailUploadResponse:
        client_ip = extract_client_ip(request, trust_proxy=cfg.svr_trust_proxy)
        _check_rate_limit(
            request,
            key=f"upload:ip:{client_ip}",
            limit=30,
            window_seconds=60,
            detail="Voicemail upload rate limit exceeded. Please retry shortly.",
        )

        try:
            raw_bytes = await read_upload_limited(file, limit_bytes=MAX_BYTES)
            probe = validate_and_probe_audio(
                raw_bytes,
                file.filename or "voicemail.wav",
                ffprobe_bin=cfg.ffprobe_bin,
            )
        except IntakeValidationError as exc:
            code = (
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
                if exc.problem == "size" and "exceeds" in exc.detail.lower()
                else status.HTTP_400_BAD_REQUEST
            )
            raise HTTPException(status_code=code, detail=exc.detail) from exc
        finally:
            await file.close()

        clean_header_key = (idempotency_key or "").strip()[:128] or None
        existing_vm: Voicemail | None = None
        if clean_header_key:
            existing_vm = db.scalar(
                select(Voicemail).where(
                    Voicemail.organization_id == ctx.organization_id,
                    Voicemail.idempotency_key == clean_header_key,
                )
            )
        if existing_vm is None:
            existing_vm = db.scalar(
                select(Voicemail).where(
                    Voicemail.organization_id == ctx.organization_id,
                    Voicemail.content_sha256 == probe.content_sha256,
                )
            )

        if existing_vm is not None:
            existing_ticket = db.scalar(
                select(Ticket).where(
                    Ticket.organization_id == ctx.organization_id,
                    Ticket.voicemail_id == existing_vm.id,
                )
            )
            if existing_ticket is not None:
                response.status_code = status.HTTP_200_OK
                return VoicemailUploadResponse(
                    voicemail_id=existing_vm.id,
                    ticket_id=existing_ticket.id,
                    status=existing_ticket.status,
                    deduplicated=True,
                    file_name=existing_vm.file_name,
                    format=existing_vm.format,
                    size_bytes=existing_vm.size_bytes,
                    duration_seconds=existing_vm.duration_seconds,
                    recommendation_note=probe.recommendation_note,
                    idempotency_key=existing_vm.idempotency_key,
                )

        effective_key = clean_header_key or f"sha256:{probe.content_sha256}"
        vm_id = new_uuid()
        enc_path = cfg.svr_storage_dir / "voicemails" / f"{vm_id}.{probe.format}.enc"
        crypto: EncryptionService = request.app.state.crypto
        crypto.write_encrypted_file(enc_path, raw_bytes)

        sys_setting = db.get(SystemSetting, ctx.organization_id)
        conf_snapshot = sys_setting.confidence_threshold if sys_setting else 0.5

        vm = Voicemail(
            id=vm_id,
            organization_id=ctx.organization_id,
            file_name=probe.file_name,
            file_path=str(enc_path),
            format=probe.format,
            size_bytes=probe.size_bytes,
            duration_seconds=probe.duration_seconds,
            sample_rate_hz=probe.sample_rate_hz,
            channels=probe.channels,
            status=TicketStatus.PROCESSING.value,
            idempotency_key=effective_key,
            content_sha256=probe.content_sha256,
            encrypted=True,
            created_by=ctx.user.id,
        )
        db.add(vm)
        db.flush()

        ticket = Ticket(
            voicemail_id=vm.id,
            organization_id=ctx.organization_id,
            status=TicketStatus.PROCESSING.value,
            confidence_threshold_snapshot=conf_snapshot,
            needs_human_review=True,
            stage_status={"intake": "ok"},
        )
        db.add(ticket)
        db.flush()

        record_audit_event(
            db,
            organization_id=ctx.organization_id,
            entity_type="ticket",
            entity_id=ticket.id,
            action="created",
            actor=ctx.user.email,
            old_value=None,
            new_value={
                "voicemail_id": vm.id,
                "file_name": probe.file_name,
                "format": probe.format,
                "size_bytes": probe.size_bytes,
                "duration_seconds": probe.duration_seconds,
                "status": TicketStatus.PROCESSING.value,
            },
        )
        db.commit()

        background_tasks.add_task(_run_pipeline_bg, request.app, ticket.id)

        return VoicemailUploadResponse(
            voicemail_id=vm.id,
            ticket_id=ticket.id,
            status=TicketStatus.PROCESSING.value,
            deduplicated=False,
            file_name=probe.file_name,
            format=probe.format,
            size_bytes=probe.size_bytes,
            duration_seconds=probe.duration_seconds,
            recommendation_note=probe.recommendation_note,
            idempotency_key=effective_key,
        )

    @application.get("/api/voicemails/{voicemail_id}/audio", tags=["Voicemails"])
    def stream_voicemail_audio(
        voicemail_id: str,
        request: Request,
        ctx: AuthContext = Depends(get_current_auth),
        db: Session = Depends(get_db_from_app),
    ) -> Response:
        vm = db.get(Voicemail, voicemail_id)
        if vm is None or vm.organization_id != ctx.organization_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voicemail not found.")

        if ctx.role == UserRole.AGENT:
            ticket = db.scalar(
                select(Ticket).where(
                    Ticket.organization_id == ctx.organization_id,
                    Ticket.voicemail_id == vm.id,
                )
            )
            if ticket is None or not ctx.user.linked_agent_id or ticket.assigned_agent_id != ctx.user.linked_agent_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Agents may only access audio for tickets assigned to them.",
                )

        audio_path = Path(vm.file_path)
        if not audio_path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file unavailable.")

        crypto: EncryptionService = request.app.state.crypto
        try:
            raw_audio = crypto.read_encrypted_file(audio_path) if vm.encrypted else audio_path.read_bytes()
        except InvalidToken as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Audio cannot be decrypted with the active encryption key.",
            ) from exc
        media_type = _MEDIA_TYPES.get(vm.format.lower(), "application/octet-stream")
        safe_filename = vm.file_name.replace('"', "").replace("\r", "").replace("\n", "")
        return Response(
            content=raw_audio,
            media_type=media_type,
            headers={
                "Content-Disposition": f'inline; filename="{safe_filename}"',
                "Cache-Control": "private, no-store",
            },
        )

    # ------------------------------------------------------------------
    # Tickets Queue, Detail, Corrections & Lifecycle
    # ------------------------------------------------------------------

    @application.get("/api/tickets", response_model=TicketListResponse, tags=["Tickets"])
    def list_tickets(
        limit: int = Query(default=20, ge=1, le=100),
        cursor: str | None = Query(default=None),
        offset: int = Query(default=0, ge=0),
        bucket: str | None = Query(default=None),
        category: str | None = Query(default=None),
        ticket_status: str | None = Query(default=None, alias="status"),
        assigned_agent_id: str | None = Query(default=None),
        needs_human_review: bool | None = Query(default=None),
        review_reason: str | None = Query(default=None),
        q: str | None = Query(default=None, max_length=200),
        ctx: AuthContext = Depends(get_current_auth),
        db: Session = Depends(get_db_from_app),
    ) -> TicketListResponse:
        effective_offset = _decode_cursor(cursor) if cursor else offset

        # Base scope: organization + strict agent RBAC scoping (FR17, FR23, FR24)
        base_filters = [Ticket.organization_id == ctx.organization_id]
        if ctx.role == UserRole.AGENT:
            if not ctx.user.linked_agent_id:
                return TicketListResponse(
                    items=[],
                    limit=limit,
                    next_cursor=None,
                    prev_cursor=None,
                    total=0,
                    counts_by_bucket={"urgent": 0, "high": 0, "normal": 0, "low": 0, "unranked": 0},
                    counts_by_status={},
                    human_review_count=0,
                )
            base_filters.append(Ticket.assigned_agent_id == ctx.user.linked_agent_id)

        # Compute unscoped (within role/org) KPI counts for dashboard header
        bucket_rows = db.execute(
            select(Ticket.queue_priority, func.count(Ticket.id))
            .where(*base_filters)
            .group_by(Ticket.queue_priority)
        ).all()
        counts_by_bucket = {"urgent": 0, "high": 0, "normal": 0, "low": 0, "unranked": 0}
        for b_val, b_cnt in bucket_rows:
            key = b_val if b_val in counts_by_bucket else "unranked"
            counts_by_bucket[key] += int(b_cnt)

        status_rows = db.execute(
            select(Ticket.status, func.count(Ticket.id))
            .where(*base_filters)
            .group_by(Ticket.status)
        ).all()
        counts_by_status = {str(s_val): int(s_cnt) for s_val, s_cnt in status_rows}
        human_review_count = int(
            db.scalar(
                select(func.count(Ticket.id)).where(
                    *base_filters,
                    Ticket.needs_human_review.is_(True),
                )
            )
            or 0
        )

        # Apply interactive filters
        filters = list(base_filters)
        if bucket:
            if bucket == "unranked":
                filters.append(Ticket.queue_priority.is_(None))
            else:
                filters.append(Ticket.queue_priority == bucket)
        if category:
            filters.append(Ticket.complaint_category == category)
        if ticket_status:
            statuses = [s.strip() for s in ticket_status.split(",") if s.strip()]
            if len(statuses) == 1:
                filters.append(Ticket.status == statuses[0])
            elif statuses:
                filters.append(Ticket.status.in_(statuses))
        if assigned_agent_id and ctx.role != UserRole.AGENT:
            if assigned_agent_id == "unassigned":
                filters.append(Ticket.assigned_agent_id.is_(None))
            else:
                filters.append(Ticket.assigned_agent_id == assigned_agent_id)
        if needs_human_review is not None:
            filters.append(Ticket.needs_human_review.is_(needs_human_review))
        if review_reason:
            filters.append(Ticket.review_reason == review_reason)
        if q and q.strip():
            q_raw = q.strip()
            q_norm = normalize_transcript(q_raw)
            search_clauses = [
                Ticket.transcript.ilike(f"%{q_raw}%"),
                Ticket.summary.ilike(f"%{q_raw}%"),
                Ticket.complaint_category.ilike(f"%{q_raw}%"),
                Ticket.id.ilike(f"%{q_raw}%"),
            ]
            if q_norm:
                search_clauses.append(Ticket.text_norm.ilike(f"%{q_norm}%"))
            filters.append(or_(*search_clauses))

        total = int(db.scalar(select(func.count(Ticket.id)).where(*filters)) or 0)
        tickets = db.scalars(
            select(Ticket)
            .where(*filters)
            .order_by(
                nullslast(Ticket.priority_score.desc()),
                Ticket.created_at.desc(),
                Ticket.id.desc(),
            )
            .offset(effective_offset)
            .limit(limit)
        ).all()

        vm_ids = [t.voicemail_id for t in tickets]
        agent_ids = [t.assigned_agent_id for t in tickets if t.assigned_agent_id]
        vm_map = (
            {v.id: v for v in db.scalars(select(Voicemail).where(Voicemail.id.in_(vm_ids))).all()}
            if vm_ids
            else {}
        )
        agent_map = (
            {a.id: a for a in db.scalars(select(Agent).where(Agent.id.in_(agent_ids))).all()}
            if agent_ids
            else {}
        )

        items = [_build_ticket_summary(t, vm_map, agent_map) for t in tickets]
        next_cursor = _encode_cursor(effective_offset + limit) if (effective_offset + limit) < total else None
        prev_cursor = _encode_cursor(max(0, effective_offset - limit)) if effective_offset > 0 else None

        return TicketListResponse(
            items=items,
            limit=limit,
            next_cursor=next_cursor,
            prev_cursor=prev_cursor,
            total=total,
            counts_by_bucket=counts_by_bucket,
            counts_by_status=counts_by_status,
            human_review_count=human_review_count,
        )

    @application.get("/api/tickets/{ticket_id}", response_model=TicketDetail, tags=["Tickets"])
    def get_ticket(
        ticket_id: str,
        ctx: AuthContext = Depends(get_current_auth),
        db: Session = Depends(get_db_from_app),
    ) -> TicketDetail:
        ticket = _get_ticket_in_org(db, ticket_id, ctx.organization_id)
        if ctx.role == UserRole.AGENT:
            if not ctx.user.linked_agent_id or ticket.assigned_agent_id != ctx.user.linked_agent_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Agents may only view tickets assigned to them.",
                )
        return _build_ticket_detail(db, ticket)

    @application.post(
        "/api/tickets/{ticket_id}/preview-correction",
        response_model=CorrectionPreviewResponse,
        dependencies=[Depends(_require_csrf_dep)],
        tags=["Tickets"],
    )
    def preview_ticket_correction(
        ticket_id: str,
        body: CorrectionPreviewRequest,
        ctx: AuthContext = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)),
        db: Session = Depends(get_db_from_app),
    ) -> CorrectionPreviewResponse:
        """Compute recomputed priority, route, and brief without mutating DB (WF2 step 4)."""
        ticket = _get_ticket_in_org(db, ticket_id, ctx.organization_id)

        proposed = {
            "complaint_category": body.complaint_category.value if body.complaint_category else ticket.complaint_category,
            "complaint_urgency": body.complaint_urgency.value if body.complaint_urgency else ticket.complaint_urgency,
            "customer_state": body.customer_state.value if body.customer_state else ticket.customer_state,
            "churn_risk": body.churn_risk.value if body.churn_risk else ticket.churn_risk,
        }

        prio_res = compute_priority(
            proposed["complaint_urgency"],
            proposed["churn_risk"],
            proposed["customer_state"],
        )
        sys_setting = db.get(SystemSetting, ctx.organization_id)
        auto_routing = sys_setting.auto_routing_enabled if sys_setting else True
        blocker = prio_res.review_reason if prio_res.needs_human_review else None
        route_dec = recommend_route(
            db,
            organization_id=ctx.organization_id,
            complaint_category=proposed["complaint_category"],
            auto_routing_enabled=auto_routing,
            human_review_blocker=blocker,
        )
        brief = build_callback_brief(
            db,
            organization_id=ctx.organization_id,
            transcript=ticket.transcript,
            complaint_category=proposed["complaint_category"],
        )

        needs_review = bool(prio_res.needs_human_review or route_dec.needs_human_review or brief.flagged)
        review_reason = route_dec.review_reason or prio_res.review_reason or brief.flag_reason

        return CorrectionPreviewResponse(
            proposed_labels=proposed,
            priority_score=prio_res.priority_score,
            queue_priority=prio_res.queue_priority,
            priority_signals=prio_res.contributing_signals,
            priority_reason=prio_res.priority_reason,
            recommended_agent_id=route_dec.assigned_agent_id,
            recommended_agent_name=route_dec.assigned_agent_name,
            required_skill=route_dec.required_skill,
            route_reason=route_dec.route_reason,
            summary=brief.summary,
            customer_request=brief.customer_request,
            suggested_script=brief.suggested_script,
            needs_human_review=needs_review,
            review_reason=review_reason,
        )

    @application.post(
        "/api/tickets/{ticket_id}/correct",
        response_model=TicketDetail,
        dependencies=[Depends(_require_csrf_dep)],
        tags=["Tickets"],
    )
    async def apply_ticket_correction(
        ticket_id: str,
        body: CorrectionApplyRequest,
        request: Request,
        ctx: AuthContext = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)),
        db: Session = Depends(get_db_from_app),
    ) -> TicketDetail:
        """Apply supervisor label correction, mark human provenance (S4), recompute priority/brief/route."""
        ticket = _get_ticket_in_org(db, ticket_id, ctx.organization_id)
        previous_agent_id = ticket.assigned_agent_id

        old_snapshot = {
            "complaint_category": ticket.complaint_category,
            "complaint_urgency": ticket.complaint_urgency,
            "customer_state": ticket.customer_state,
            "churn_risk": ticket.churn_risk,
            "label_sources": dict(ticket.label_sources or {}),
            "priority_score": ticket.priority_score,
            "queue_priority": ticket.queue_priority,
            "assigned_agent_id": ticket.assigned_agent_id,
            "status": ticket.status,
            "needs_human_review": ticket.needs_human_review,
        }

        sources = dict(ticket.label_sources or {f: "model" for f in CLASSIFICATION_FIELDS})
        submitted_map = {
            "complaint_category": body.complaint_category.value if body.complaint_category else None,
            "complaint_urgency": body.complaint_urgency.value if body.complaint_urgency else None,
            "customer_state": body.customer_state.value if body.customer_state else None,
            "churn_risk": body.churn_risk.value if body.churn_risk else None,
        }
        for field_name, new_val in submitted_map.items():
            if new_val is not None:
                setattr(ticket, field_name, new_val)
                sources[field_name] = "human"
        ticket.label_sources = sources

        prio_res = compute_priority(
            ticket.complaint_urgency,
            ticket.churn_risk,
            ticket.customer_state,
        )
        ticket.priority_score = prio_res.priority_score
        ticket.queue_priority = prio_res.queue_priority
        ticket.priority_signals = prio_res.contributing_signals
        ticket.priority_reason = prio_res.priority_reason

        brief = build_callback_brief(
            db,
            organization_id=ctx.organization_id,
            transcript=ticket.transcript,
            complaint_category=ticket.complaint_category,
        )
        ticket.summary = brief.summary
        ticket.customer_request = brief.customer_request
        ticket.suggested_script = brief.suggested_script

        vm = db.get(Voicemail, ticket.voicemail_id)
        route_dec = None
        if body.apply_recommended_route and ticket.status not in (
            TicketStatus.RESOLVED.value,
            TicketStatus.CLOSED.value,
        ):
            sys_setting = db.get(SystemSetting, ctx.organization_id)
            auto_routing = sys_setting.auto_routing_enabled if sys_setting else True
            blocker = prio_res.review_reason if prio_res.needs_human_review else None
            route_dec = recommend_route(
                db,
                organization_id=ctx.organization_id,
                complaint_category=ticket.complaint_category,
                auto_routing_enabled=auto_routing,
                human_review_blocker=blocker,
            )
            if route_dec.assigned_agent_id is not None:
                assign_ticket_to_agent(
                    db,
                    ticket,
                    route_dec.assigned_agent_id,
                    assigned_by=ctx.user.email,
                    route_reason=route_dec.route_reason,
                )
                if ticket.status in (TicketStatus.UNASSIGNED.value, TicketStatus.FAILED.value):
                    ticket.status = TicketStatus.READY.value
                    if vm is not None:
                        vm.status = TicketStatus.READY.value
            else:
                release_active_assignment(db, ticket, final_status="released")
                ticket.assigned_agent_id = None
                ticket.route_reason = route_dec.route_reason
                if ticket.status == TicketStatus.READY.value:
                    ticket.status = TicketStatus.UNASSIGNED.value
                    if vm is not None:
                        vm.status = TicketStatus.UNASSIGNED.value

        if prio_res.needs_human_review:
            ticket.needs_human_review = True
            ticket.review_reason = prio_res.review_reason
        elif route_dec is not None and route_dec.needs_human_review:
            ticket.needs_human_review = True
            ticket.review_reason = route_dec.review_reason
        elif brief.flagged:
            ticket.needs_human_review = True
            ticket.review_reason = brief.flag_reason
        elif body.clear_human_review:
            ticket.needs_human_review = False
            ticket.review_reason = None

        new_snapshot = {
            "complaint_category": ticket.complaint_category,
            "complaint_urgency": ticket.complaint_urgency,
            "customer_state": ticket.customer_state,
            "churn_risk": ticket.churn_risk,
            "label_sources": dict(ticket.label_sources),
            "priority_score": ticket.priority_score,
            "queue_priority": ticket.queue_priority,
            "assigned_agent_id": ticket.assigned_agent_id,
            "status": ticket.status,
            "needs_human_review": ticket.needs_human_review,
            "note": body.note,
        }

        record_audit_event(
            db,
            organization_id=ctx.organization_id,
            entity_type="ticket",
            entity_id=ticket.id,
            action="corrected",
            actor=ctx.user.email,
            old_value=old_snapshot,
            new_value=new_snapshot,
        )
        db.commit()
        db.refresh(ticket)

        queue_hub: QueueHub = request.app.state.queue_hub
        await queue_hub.broadcast(
            ctx.organization_id,
            {
                "type": "ticket_update",
                "organization_id": ctx.organization_id,
                "ticket_id": ticket.id,
                "status": ticket.status,
                "priority_score": ticket.priority_score,
                "queue_priority": ticket.queue_priority,
                "assigned_agent_id": ticket.assigned_agent_id,
                "previous_agent_id": previous_agent_id,
                "needs_human_review": ticket.needs_human_review,
                "review_reason": ticket.review_reason,
            },
        )
        return _build_ticket_detail(db, ticket)

    @application.patch(
        "/api/tickets/{ticket_id}",
        response_model=TicketDetail,
        dependencies=[Depends(_require_csrf_dep)],
        tags=["Tickets"],
    )
    async def patch_ticket(
        ticket_id: str,
        body: PatchTicketRequest,
        request: Request,
        ctx: AuthContext = Depends(get_current_auth),
        db: Session = Depends(get_db_from_app),
    ) -> TicketDetail:
        ticket = _get_ticket_in_org(db, ticket_id, ctx.organization_id)
        previous_agent_id = ticket.assigned_agent_id
        vm = db.get(Voicemail, ticket.voicemail_id)

        if ctx.role == UserRole.AGENT:
            if not ctx.user.linked_agent_id or ticket.assigned_agent_id != ctx.user.linked_agent_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Agents may only update tickets assigned to them.",
                )
            if (
                body.assigned_agent_id is not None
                or body.unassign
                or body.needs_human_review is not None
                or body.review_reason is not None
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Agents may only update status to in_progress or resolved on their own tickets.",
                )
            if body.status not in (TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Agents may only transition own tickets to in_progress or resolved.",
                )

        old_value = {
            "status": ticket.status,
            "assigned_agent_id": ticket.assigned_agent_id,
            "needs_human_review": ticket.needs_human_review,
            "review_reason": ticket.review_reason,
        }

        current_status = TicketStatus(ticket.status)
        if body.status is not None and body.status != current_status:
            allowed_next = ALLOWED_TICKET_TRANSITIONS.get(current_status, frozenset())
            if body.status not in allowed_next:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Invalid ticket transition from '{current_status.value}' to '{body.status.value}'.",
                )

        action = "updated"

        if body.unassign:
            release_active_assignment(db, ticket, final_status="released")
            ticket.assigned_agent_id = None
            ticket.route_reason = f"UNASSIGNED manually by {ctx.user.email}."
            ticket.needs_human_review = True
            ticket.review_reason = body.review_reason or "supervisor_requested"
            if body.status is None and ticket.status == TicketStatus.READY.value:
                ticket.status = TicketStatus.UNASSIGNED.value
                if vm is not None:
                    vm.status = TicketStatus.UNASSIGNED.value
            action = "reassigned"
        elif body.assigned_agent_id is not None:
            reason_suffix = f": {body.note}" if body.note else "."
            try:
                assign_ticket_to_agent(
                    db,
                    ticket,
                    body.assigned_agent_id,
                    assigned_by=ctx.user.email,
                    route_reason=f"Manually assigned by {ctx.user.email}{reason_suffix}",
                )
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
            if body.status is None and ticket.status in (
                TicketStatus.UNASSIGNED.value,
                TicketStatus.FAILED.value,
            ):
                ticket.status = TicketStatus.READY.value
                if vm is not None:
                    vm.status = TicketStatus.READY.value
            if body.needs_human_review is None and ticket.review_reason in (
                "no_eligible_agent",
                "kill_switch_active",
            ):
                ticket.needs_human_review = False
                ticket.review_reason = None
            action = "reassigned"

        if body.status is not None and body.status.value != ticket.status:
            if body.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
                release_active_assignment(db, ticket, final_status="completed")
                if body.needs_human_review is None:
                    ticket.needs_human_review = False
                    ticket.review_reason = None
            elif body.status == TicketStatus.UNASSIGNED:
                release_active_assignment(db, ticket, final_status="released")
                ticket.assigned_agent_id = None
                ticket.needs_human_review = True
                if not ticket.review_reason:
                    ticket.review_reason = body.review_reason or "supervisor_requested"

            ticket.status = body.status.value
            if vm is not None:
                vm.status = body.status.value
            action = "status_changed" if action == "updated" else action

        if body.needs_human_review is not None:
            ticket.needs_human_review = body.needs_human_review
            ticket.review_reason = (
                (body.review_reason or ticket.review_reason or "supervisor_requested")
                if body.needs_human_review
                else None
            )

        new_value = {
            "status": ticket.status,
            "assigned_agent_id": ticket.assigned_agent_id,
            "needs_human_review": ticket.needs_human_review,
            "review_reason": ticket.review_reason,
            "note": body.note,
        }
        record_audit_event(
            db,
            organization_id=ctx.organization_id,
            entity_type="ticket",
            entity_id=ticket.id,
            action=action,
            actor=ctx.user.email,
            old_value=old_value,
            new_value=new_value,
        )
        db.commit()
        db.refresh(ticket)

        queue_hub: QueueHub = request.app.state.queue_hub
        await queue_hub.broadcast(
            ctx.organization_id,
            {
                "type": "ticket_update",
                "organization_id": ctx.organization_id,
                "ticket_id": ticket.id,
                "status": ticket.status,
                "priority_score": ticket.priority_score,
                "queue_priority": ticket.queue_priority,
                "assigned_agent_id": ticket.assigned_agent_id,
                "previous_agent_id": previous_agent_id,
                "needs_human_review": ticket.needs_human_review,
                "review_reason": ticket.review_reason,
            },
        )
        return _build_ticket_detail(db, ticket)

    # ------------------------------------------------------------------
    # Agents Management (FR19)
    # ------------------------------------------------------------------

    @application.get("/api/agents", response_model=list[AgentResponse], tags=["Agents"])
    def list_agents(
        ctx: AuthContext = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)),
        db: Session = Depends(get_db_from_app),
    ) -> list[AgentResponse]:
        agents = db.scalars(
            select(Agent)
            .where(Agent.organization_id == ctx.organization_id)
            .order_by(Agent.seed_order.asc(), Agent.created_at.asc())
        ).all()
        return [AgentResponse.model_validate(a) for a in agents]

    @application.post(
        "/api/agents",
        response_model=AgentResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(_require_csrf_dep)],
        tags=["Agents"],
    )
    def create_agent(
        body: AgentCreateRequest,
        ctx: AuthContext = Depends(require_roles(UserRole.ADMIN)),
        db: Session = Depends(get_db_from_app),
    ) -> AgentResponse:
        agent = Agent(
            organization_id=ctx.organization_id,
            name=body.name,
            skills=body.skills,
            capacity=body.capacity,
            current_load=0,
            available=body.available,
            active=True,
            seed_order=body.seed_order,
        )
        db.add(agent)
        db.flush()
        record_audit_event(
            db,
            organization_id=ctx.organization_id,
            entity_type="agent",
            entity_id=agent.id,
            action="created",
            actor=ctx.user.email,
            old_value=None,
            new_value={
                "name": agent.name,
                "skills": agent.skills,
                "capacity": agent.capacity,
                "available": agent.available,
                "seed_order": agent.seed_order,
            },
        )
        db.commit()
        db.refresh(agent)
        return AgentResponse.model_validate(agent)

    @application.patch(
        "/api/agents/{agent_id}",
        response_model=AgentResponse,
        dependencies=[Depends(_require_csrf_dep)],
        tags=["Agents"],
    )
    def update_agent(
        agent_id: str,
        body: AgentUpdateRequest,
        ctx: AuthContext = Depends(require_roles(UserRole.ADMIN)),
        db: Session = Depends(get_db_from_app),
    ) -> AgentResponse:
        agent = db.get(Agent, agent_id)
        if agent is None or agent.organization_id != ctx.organization_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")

        old_value = {
            "name": agent.name,
            "skills": list(agent.skills or []),
            "capacity": agent.capacity,
            "available": agent.available,
            "active": agent.active,
            "seed_order": agent.seed_order,
        }
        if body.name is not None:
            agent.name = body.name
        if body.skills is not None:
            agent.skills = body.skills
        if body.capacity is not None:
            agent.capacity = body.capacity
        if body.available is not None:
            agent.available = body.available
        if body.active is not None:
            agent.active = body.active
            if not body.active:
                agent.available = False
        if body.seed_order is not None:
            agent.seed_order = body.seed_order

        new_value = {
            "name": agent.name,
            "skills": list(agent.skills or []),
            "capacity": agent.capacity,
            "available": agent.available,
            "active": agent.active,
            "seed_order": agent.seed_order,
        }
        record_audit_event(
            db,
            organization_id=ctx.organization_id,
            entity_type="agent",
            entity_id=agent.id,
            action="updated",
            actor=ctx.user.email,
            old_value=old_value,
            new_value=new_value,
        )
        db.commit()
        db.refresh(agent)
        return AgentResponse.model_validate(agent)

    # ------------------------------------------------------------------
    # Settings, Skill Mapping & Script Templates (FR20, FR21, PRD 10.5)
    # ------------------------------------------------------------------

    @application.get("/api/settings", response_model=SettingsResponse, tags=["Settings"])
    def get_system_settings(
        ctx: AuthContext = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)),
        db: Session = Depends(get_db_from_app),
    ) -> SettingsResponse:
        setting = db.get(SystemSetting, ctx.organization_id)
        if setting is None:
            setting = SystemSetting(organization_id=ctx.organization_id)
            db.add(setting)
            db.commit()
            db.refresh(setting)
        return SettingsResponse.model_validate(setting)

    @application.patch(
        "/api/settings",
        response_model=SettingsResponse,
        dependencies=[Depends(_require_csrf_dep)],
        tags=["Settings"],
    )
    async def update_system_settings(
        body: SettingsUpdateRequest,
        request: Request,
        ctx: AuthContext = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)),
        db: Session = Depends(get_db_from_app),
    ) -> SettingsResponse:
        # PRD Section 10.5: Supervisor may toggle auto_routing_enabled kill switch;
        # Admin only for confidence_threshold, retention_days, and weekly_sample_rate.
        if ctx.role == UserRole.SUPERVISOR:
            if (
                body.confidence_threshold is not None
                or body.retention_days is not None
                or body.weekly_sample_rate is not None
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only Admins may modify confidence threshold, retention period, or sampling rate.",
                )

        setting = db.get(SystemSetting, ctx.organization_id)
        if setting is None:
            setting = SystemSetting(organization_id=ctx.organization_id)
            db.add(setting)
            db.flush()

        old_value = {
            "confidence_threshold": setting.confidence_threshold,
            "auto_routing_enabled": setting.auto_routing_enabled,
            "retention_days": setting.retention_days,
            "weekly_sample_rate": setting.weekly_sample_rate,
        }
        if body.confidence_threshold is not None:
            setting.confidence_threshold = body.confidence_threshold
        if body.auto_routing_enabled is not None:
            setting.auto_routing_enabled = body.auto_routing_enabled
        if body.retention_days is not None:
            setting.retention_days = body.retention_days
        if body.weekly_sample_rate is not None:
            setting.weekly_sample_rate = body.weekly_sample_rate

        new_value = {
            "confidence_threshold": setting.confidence_threshold,
            "auto_routing_enabled": setting.auto_routing_enabled,
            "retention_days": setting.retention_days,
            "weekly_sample_rate": setting.weekly_sample_rate,
        }
        record_audit_event(
            db,
            organization_id=ctx.organization_id,
            entity_type="setting",
            entity_id=ctx.organization_id,
            action="setting_changed",
            actor=ctx.user.email,
            old_value=old_value,
            new_value=new_value,
        )
        db.commit()
        db.refresh(setting)

        queue_hub: QueueHub = request.app.state.queue_hub
        await queue_hub.broadcast(
            ctx.organization_id,
            {
                "type": "settings_updated",
                "organization_id": ctx.organization_id,
                "auto_routing_enabled": setting.auto_routing_enabled,
                "confidence_threshold": setting.confidence_threshold,
            },
        )
        return SettingsResponse.model_validate(setting)

    @application.get("/api/settings/skills", response_model=SkillMappingListResponse, tags=["Settings"])
    def get_skill_mappings(
        ctx: AuthContext = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)),
        db: Session = Depends(get_db_from_app),
    ) -> SkillMappingListResponse:
        rows = db.scalars(
            select(SkillMapping)
            .where(SkillMapping.organization_id == ctx.organization_id)
            .order_by(SkillMapping.category.asc())
        ).all()
        return SkillMappingListResponse(
            mappings=[
                SkillMappingItem(
                    category=r.category,
                    skill_name=r.skill_name,
                    updated_at=r.updated_at,
                )
                for r in rows
            ]
        )

    @application.put(
        "/api/settings/skills",
        response_model=SkillMappingListResponse,
        dependencies=[Depends(_require_csrf_dep)],
        tags=["Settings"],
    )
    def update_skill_mappings(
        body: SkillMappingUpdateRequest,
        ctx: AuthContext = Depends(require_roles(UserRole.ADMIN)),
        db: Session = Depends(get_db_from_app),
    ) -> SkillMappingListResponse:
        existing_rows = db.scalars(
            select(SkillMapping).where(SkillMapping.organization_id == ctx.organization_id)
        ).all()
        old_map = {r.category: r.skill_name for r in existing_rows}
        by_cat = {r.category: r for r in existing_rows}

        for cat, skill_name in body.mappings.items():
            if cat in by_cat:
                by_cat[cat].skill_name = skill_name
            else:
                db.add(
                    SkillMapping(
                        organization_id=ctx.organization_id,
                        category=cat,
                        skill_name=skill_name,
                    )
                )

        record_audit_event(
            db,
            organization_id=ctx.organization_id,
            entity_type="setting",
            entity_id="skill_mappings",
            action="setting_changed",
            actor=ctx.user.email,
            old_value=old_map,
            new_value=dict(body.mappings),
        )
        db.commit()

        updated_rows = db.scalars(
            select(SkillMapping)
            .where(SkillMapping.organization_id == ctx.organization_id)
            .order_by(SkillMapping.category.asc())
        ).all()
        return SkillMappingListResponse(
            mappings=[
                SkillMappingItem(
                    category=r.category,
                    skill_name=r.skill_name,
                    updated_at=r.updated_at,
                )
                for r in updated_rows
            ]
        )

    @application.get(
        "/api/settings/templates",
        response_model=list[ScriptTemplateResponse],
        tags=["Settings"],
    )
    def list_script_templates(
        ctx: AuthContext = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)),
        db: Session = Depends(get_db_from_app),
    ) -> list[ScriptTemplateResponse]:
        rows = db.scalars(
            select(ScriptTemplate)
            .where(ScriptTemplate.organization_id == ctx.organization_id)
            .order_by(ScriptTemplate.category.asc())
        ).all()
        return [ScriptTemplateResponse.model_validate(r) for r in rows]

    @application.put(
        "/api/settings/templates/{category}",
        response_model=ScriptTemplateResponse,
        dependencies=[Depends(_require_csrf_dep)],
        tags=["Settings"],
    )
    def update_script_template(
        category: ComplaintCategory,
        body: ScriptTemplateUpdateRequest,
        ctx: AuthContext = Depends(require_roles(UserRole.ADMIN)),
        db: Session = Depends(get_db_from_app),
    ) -> ScriptTemplateResponse:
        tpl = db.scalar(
            select(ScriptTemplate).where(
                ScriptTemplate.organization_id == ctx.organization_id,
                ScriptTemplate.category == category.value,
            )
        )
        old_value: dict[str, Any] | None = None
        if tpl is None:
            tpl = ScriptTemplate(
                organization_id=ctx.organization_id,
                category=category.value,
                template_ar=body.template_ar,
                template_en=body.template_en,
                customer_request_ar=body.customer_request_ar,
                customer_request_en=body.customer_request_en,
                version=1,
            )
            db.add(tpl)
        else:
            old_value = {
                "template_ar": tpl.template_ar,
                "template_en": tpl.template_en,
                "customer_request_ar": tpl.customer_request_ar,
                "customer_request_en": tpl.customer_request_en,
                "version": tpl.version,
            }
            tpl.template_ar = body.template_ar
            tpl.template_en = body.template_en
            tpl.customer_request_ar = body.customer_request_ar
            tpl.customer_request_en = body.customer_request_en
            tpl.version += 1

        record_audit_event(
            db,
            organization_id=ctx.organization_id,
            entity_type="setting",
            entity_id=f"template:{category.value}",
            action="setting_changed",
            actor=ctx.user.email,
            old_value=old_value,
            new_value={
                "template_ar": tpl.template_ar,
                "template_en": tpl.template_en,
                "customer_request_ar": tpl.customer_request_ar,
                "customer_request_en": tpl.customer_request_en,
                "version": tpl.version,
            },
        )
        db.commit()
        db.refresh(tpl)
        return ScriptTemplateResponse.model_validate(tpl)

    # ------------------------------------------------------------------
    # Audit Log & Export (FR18, NFR19)
    # ------------------------------------------------------------------

    @application.get("/api/audit-logs", response_model=AuditLogListResponse, tags=["Audit"])
    def list_audit_logs(
        limit: int = Query(default=20, ge=1, le=100),
        cursor: str | None = Query(default=None),
        offset: int = Query(default=0, ge=0),
        entity_type: str | None = Query(default=None),
        entity_id: str | None = Query(default=None),
        action: str | None = Query(default=None),
        actor: str | None = Query(default=None),
        date_from: datetime | None = Query(default=None),
        date_to: datetime | None = Query(default=None),
        ctx: AuthContext = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)),
        db: Session = Depends(get_db_from_app),
    ) -> AuditLogListResponse:
        effective_offset = _decode_cursor(cursor) if cursor else offset
        filters = [AuditEvent.organization_id == ctx.organization_id]
        if entity_type:
            filters.append(AuditEvent.entity_type == entity_type)
        if entity_id:
            filters.append(AuditEvent.entity_id == entity_id)
        if action:
            filters.append(AuditEvent.action == action)
        if actor:
            filters.append(AuditEvent.actor.ilike(f"%{actor.strip()}%"))
        if date_from:
            filters.append(AuditEvent.created_at >= _ensure_utc(date_from))
        if date_to:
            filters.append(AuditEvent.created_at <= _ensure_utc(date_to))

        total = int(db.scalar(select(func.count(AuditEvent.id)).where(*filters)) or 0)
        rows = db.scalars(
            select(AuditEvent)
            .where(*filters)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .offset(effective_offset)
            .limit(limit)
        ).all()

        next_cursor = _encode_cursor(effective_offset + limit) if (effective_offset + limit) < total else None
        prev_cursor = _encode_cursor(max(0, effective_offset - limit)) if effective_offset > 0 else None

        return AuditLogListResponse(
            items=[AuditEventResponse.model_validate(r) for r in rows],
            limit=limit,
            next_cursor=next_cursor,
            prev_cursor=prev_cursor,
            total=total,
        )

    @application.get("/api/audit-logs/export", tags=["Audit"])
    def export_audit_logs(
        request: Request,
        export_format: str = Query(default="csv", alias="format", pattern="^(csv|json)$"),
        entity_type: str | None = Query(default=None),
        action: str | None = Query(default=None),
        ctx: AuthContext = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)),
        db: Session = Depends(get_db_from_app),
        cfg: Settings = Depends(get_settings),
    ) -> Response:
        client_ip = extract_client_ip(request, trust_proxy=cfg.svr_trust_proxy)
        _check_rate_limit(
            request,
            key=f"audit_export:ip:{client_ip}",
            limit=10,
            window_seconds=60,
            detail="Audit export rate limit exceeded. Please retry shortly.",
        )

        filters = [AuditEvent.organization_id == ctx.organization_id]
        if entity_type:
            filters.append(AuditEvent.entity_type == entity_type)
        if action:
            filters.append(AuditEvent.action == action)

        rows = db.scalars(
            select(AuditEvent)
            .where(*filters)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .limit(10000)
        ).all()

        record_audit_event(
            db,
            organization_id=ctx.organization_id,
            entity_type="audit",
            entity_id=ctx.organization_id,
            action="exported",
            actor=ctx.user.email,
            old_value=None,
            new_value={
                "format": export_format,
                "exported_count": len(rows),
                "filters": {"entity_type": entity_type, "action": action},
            },
        )
        db.commit()

        if export_format == "json":
            payload = [AuditEventResponse.model_validate(r).model_dump(mode="json") for r in rows]
            return Response(
                content=json.dumps(payload, ensure_ascii=False, indent=2),
                media_type="application/json",
                headers={"Content-Disposition": 'attachment; filename="svr-audit-logs.json"'},
            )

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            ["id", "created_at", "entity_type", "entity_id", "action", "actor", "old_value", "new_value"]
        )
        for r in rows:
            writer.writerow(
                [
                    _csv_safe_cell(r.id),
                    _csv_safe_cell(r.created_at.isoformat()),
                    _csv_safe_cell(r.entity_type),
                    _csv_safe_cell(r.entity_id),
                    _csv_safe_cell(r.action),
                    _csv_safe_cell(r.actor),
                    _csv_safe_cell(r.old_value),
                    _csv_safe_cell(r.new_value),
                ]
            )
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="svr-audit-logs.csv"'},
        )

    # ------------------------------------------------------------------
    # Evaluation, Monitoring, Prometheus Metrics & Health
    # ------------------------------------------------------------------

    @application.get(
        "/api/evaluation/runs",
        response_model=list[EvalRunResponse],
        tags=["Evaluation"],
    )
    def list_eval_runs(
        ctx: AuthContext = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)),
        db: Session = Depends(get_db_from_app),
    ) -> list[EvalRunResponse]:
        runs = db.scalars(
            select(EvalRun)
            .where(EvalRun.organization_id == ctx.organization_id)
            .order_by(EvalRun.created_at.desc(), EvalRun.id.desc())
            .limit(100)
        ).all()
        return [EvalRunResponse.model_validate(r) for r in runs]

    @application.get(
        "/api/monitoring/summary",
        response_model=MonitoringSummaryResponse,
        tags=["Monitoring"],
    )
    def get_monitoring_summary(
        request: Request,
        ctx: AuthContext = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)),
        db: Session = Depends(get_db_from_app),
    ) -> MonitoringSummaryResponse:
        now = utcnow()
        cutoff_24h = now - timedelta(hours=24)

        tickets = db.scalars(
            select(Ticket).where(Ticket.organization_id == ctx.organization_id)
        ).all()
        ai_logs = db.scalars(
            select(AIInteractionLog).where(AIInteractionLog.organization_id == ctx.organization_id)
        ).all()
        sys_setting = db.get(SystemSetting, ctx.organization_id)

        total_tickets = len(tickets)
        tickets_24h = [t for t in tickets if _ensure_utc(t.created_at) >= cutoff_24h]

        tickets_by_status: dict[str, int] = {}
        cls_dist: dict[str, dict[str, int]] = {f: {} for f in CLASSIFICATION_FIELDS}
        hist_counts = [0] * 10
        e2e_latencies: list[float] = []
        e2e_latencies_24h: list[float] = []
        flagged_total = 0
        flagged_24h = 0
        succeeded_total = 0

        for t in tickets:
            tickets_by_status[t.status] = tickets_by_status.get(t.status, 0) + 1
            if t.needs_human_review:
                flagged_total += 1
            if (
                t.status
                not in (TicketStatus.FAILED.value, TicketStatus.PROCESSING.value, TicketStatus.RECEIVED.value)
                and t.review_reason != "processing_error"
            ):
                succeeded_total += 1
            if t.processing_ms > 0:
                e2e_latencies.append(float(t.processing_ms))

            for field_name in CLASSIFICATION_FIELDS:
                val = getattr(t, field_name)
                if val:
                    cls_dist[field_name][val] = cls_dist[field_name].get(val, 0) + 1

            if t.confidence > 0 or t.complaint_category is not None:
                bin_idx = min(9, max(0, int(t.confidence * 10)))
                hist_counts[bin_idx] += 1

        for t in tickets_24h:
            if t.needs_human_review:
                flagged_24h += 1
            if t.processing_ms > 0:
                e2e_latencies_24h.append(float(t.processing_ms))

        stage_samples: dict[str, list[float]] = {s: [] for s in _PIPELINE_STAGES}
        for log in ai_logs:
            if log.stage in stage_samples:
                stage_samples[log.stage].append(float(log.latency_ms))

        confidence_histogram = [
            {
                "range": f"{i / 10:.1f}-{(i + 1) / 10:.1f}",
                "min": round(i / 10.0, 1),
                "max": round((i + 1) / 10.0, 1),
                "count": hist_counts[i],
            }
            for i in range(10)
        ]

        review_rate = round(flagged_total / total_tickets, 4) if total_tickets else 0.0
        review_rate_24h = round(flagged_24h / len(tickets_24h), 4) if tickets_24h else 0.0
        completed_count = sum(
            c
            for st, c in tickets_by_status.items()
            if st not in (TicketStatus.PROCESSING.value, TicketStatus.RECEIVED.value)
        )
        success_rate = round(succeeded_total / completed_count, 4) if completed_count else 1.0

        e2e_stats = _latency_stats(e2e_latencies)
        e2e_stats_24h = _latency_stats(e2e_latencies_24h)
        stage_stats = {s: _latency_stats(vals) for s, vals in stage_samples.items()}

        alerts: list[MonitoringAlert] = []
        if tickets_24h and review_rate_24h > 0.20:
            alerts.append(
                MonitoringAlert(
                    code="high_human_review_rate",
                    severity="warning",
                    message=(
                        f"24h human review rate is {review_rate_24h * 100:.1f}%, "
                        "exceeding the 20.0% alert threshold."
                    ),
                    value=review_rate_24h,
                    threshold=0.20,
                )
            )
        if e2e_latencies_24h and e2e_stats_24h["p95"] > 10000.0:
            alerts.append(
                MonitoringAlert(
                    code="high_p95_latency",
                    severity="critical",
                    message=(
                        f"24h p95 end-to-end latency is {e2e_stats_24h['p95']:.0f} ms, "
                        "exceeding the 10,000 ms (10 s) latency target."
                    ),
                    value=e2e_stats_24h["p95"],
                    threshold=10000.0,
                )
            )

        queue_hub: QueueHub = request.app.state.queue_hub
        return MonitoringSummaryResponse(
            total_tickets=total_tickets,
            tickets_last_24h=len(tickets_24h),
            tickets_by_status=tickets_by_status,
            classification_distribution=cls_dist,
            confidence_histogram=confidence_histogram,
            human_review_rate=review_rate,
            human_review_rate_24h=review_rate_24h,
            processing_success_rate=success_rate,
            end_to_end_latency_ms=e2e_stats,
            end_to_end_latency_24h_ms=e2e_stats_24h,
            stage_latency_ms=stage_stats,
            alerts=alerts,
            auto_routing_enabled=sys_setting.auto_routing_enabled if sys_setting else True,
            active_ws_connections=queue_hub.active_count(ctx.organization_id),
        )

    @application.get("/api/metrics", tags=["Monitoring"])
    def prometheus_metrics(
        request: Request,
        db: Session = Depends(get_db_from_app),
        cfg: Settings = Depends(get_settings),
    ) -> Response:
        metrics_token = cfg.svr_metrics_token.strip()
        auth_header = request.headers.get("Authorization", "")
        bearer_val = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else ""
        authorized = bool(metrics_token and bearer_val and hmac.compare_digest(bearer_val, metrics_token))
        if not authorized:
            raw_token = request.cookies.get(cfg.session_cookie_name) or (bearer_val or None)
            ctx = resolve_auth_context(db, raw_token, cfg)
            if ctx is None or ctx.role not in (UserRole.ADMIN, UserRole.SUPERVISOR):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED if ctx is None else status.HTTP_403_FORBIDDEN,
                    detail="Authentication or metrics scrape token required.",
                )
        queue_hub: QueueHub = request.app.state.queue_hub
        request.app.state.prom_metrics["ws_connections"].set(queue_hub.active_count())
        data = generate_latest(request.app.state.prom_registry)
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)

    @application.get("/api/health", response_model=HealthResponse, tags=["Monitoring"])
    def health_check(
        request: Request,
        db: Session = Depends(get_db_from_app),
        cfg: Settings = Depends(get_settings),
    ) -> HealthResponse:
        db.execute(text("SELECT 1"))
        classifier: MARBERTv2ClassifierService = request.app.state.classifier_service
        queue_hub: QueueHub = request.app.state.queue_hub
        return HealthResponse(
            status="ok",
            environment=cfg.svr_env,
            database="connected",
            whisper_model=cfg.whisper_model_id,
            marbert_checkpoints_ready=classifier.has_local_checkpoints(),
            active_ws_connections=queue_hub.active_count(),
            version=APP_VERSION,
        )

    # ------------------------------------------------------------------
    # WebSocket Real-Time Queue Updates (FR3, NFR18)
    # ------------------------------------------------------------------

    @application.websocket("/ws/queue")
    async def ws_queue(websocket: WebSocket) -> None:
        cfg: Settings = websocket.app.state.settings
        db_mgr: DatabaseManager = websocket.app.state.db_manager
        queue_hub: QueueHub = websocket.app.state.queue_hub

        raw_token = websocket.cookies.get(cfg.session_cookie_name)
        if not raw_token:
            auth_header = websocket.headers.get("authorization", "")
            if auth_header.lower().startswith("bearer "):
                raw_token = auth_header[7:].strip() or None

        with db_mgr.session_factory() as db:
            ctx = resolve_auth_context(db, raw_token, cfg)
            if ctx is None:
                await websocket.close(code=4401, reason="Authentication required")
                return
            org_id = ctx.organization_id
            user_id = ctx.user.id
            role = ctx.role
            linked_agent_id = ctx.user.linked_agent_id
            snapshot = _build_ws_snapshot(
                db,
                organization_id=org_id,
                role=role,
                linked_agent_id=linked_agent_id,
            )

        conn = await queue_hub.connect(
            websocket,
            organization_id=org_id,
            user_id=user_id,
            role=role.value,
            linked_agent_id=linked_agent_id,
            snapshot=snapshot,
        )
        try:
            while True:
                msg = await websocket.receive_text()
                if msg.strip().lower() == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            logger.debug("WebSocket disconnected cleanly for user=%s", user_id)
        except Exception as exc:
            logger.warning("WebSocket loop error for user=%s: %s", user_id, exc)
        finally:
            queue_hub.disconnect(conn)

    return application


app = create_app()
