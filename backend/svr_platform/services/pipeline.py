"""Async voicemail-to-ticket AI pipeline orchestrator (WF1, AI2, AI3, AI4, AI10, NFR14)."""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import record_audit_event
from ..crypto import EncryptionService
from ..models import (
    AIInteractionLog,
    SystemSetting,
    Ticket,
    Voicemail,
)
from ..taxonomy import TicketStatus
from .brief import build_callback_brief
from .classification import CLASSIFICATION_FIELDS, MARBERTv2ClassifierService
from .priority import compute_priority
from .routing import assign_ticket_to_agent, recommend_route, release_active_assignment
from .stt import WhisperSTTService

logger = logging.getLogger("svr_platform.pipeline")


def _is_weekly_quality_sample(ticket_id: str, sample_rate: float) -> bool:
    """Deterministic >=5% ticket sampling for weekly supervisor review (AI10)."""
    if sample_rate <= 0.0:
        return False
    bucket = int(hashlib.sha256(ticket_id.encode("utf-8")).hexdigest()[:8], 16) % 1000
    return bucket < int(round(sample_rate * 1000))


def _log_ai_stage(
    db: Session,
    *,
    organization_id: str,
    ticket_id: str,
    stage: str,
    model: str,
    input_ref: str,
    output: dict,
    latency_ms: int,
) -> None:
    db.add(
        AIInteractionLog(
            organization_id=organization_id,
            ticket_id=ticket_id,
            stage=stage,
            model=model,
            input_ref=input_ref,
            output=output,
            latency_ms=max(0, int(latency_ms)),
        )
    )


def run_voicemail_pipeline(
    db: Session,
    *,
    ticket_id: str,
    crypto: EncryptionService,
    stt_service: WhisperSTTService,
    classifier_service: MARBERTv2ClassifierService,
    on_update: Callable[[dict], None] | None = None,
) -> Ticket:
    """Execute WF1 stages in order: transcribe -> classify -> priority -> route -> brief.

    Each stage records latency, AIInteractionLog, and AuditEvent. Failures never leave
    a ticket stuck in 'processing' and never fail silently (WF1, NFR14).
    """
    pipeline_t0 = time.perf_counter()
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise ValueError(f"Ticket {ticket_id} not found")
    voicemail = db.get(Voicemail, ticket.voicemail_id)
    if voicemail is None:
        raise ValueError(f"Voicemail {ticket.voicemail_id} not found")

    org_id = ticket.organization_id
    sys_setting = db.get(SystemSetting, org_id)
    conf_threshold = sys_setting.confidence_threshold if sys_setting else 0.5
    auto_routing = sys_setting.auto_routing_enabled if sys_setting else True
    sample_rate = sys_setting.weekly_sample_rate if sys_setting else 0.05

    # FR21: snapshot active settings onto the ticket so future admin changes affect new tickets only
    ticket.confidence_threshold_snapshot = conf_threshold
    ticket.config_snapshot = {
        "confidence_threshold": conf_threshold,
        "auto_routing_enabled": auto_routing,
        "weekly_sample_rate": sample_rate,
    }
    ticket.status = TicketStatus.PROCESSING.value
    voicemail.status = TicketStatus.PROCESSING.value
    stage_status: dict[str, str] = {"intake": "ok"}
    stage_timing_ms: dict[str, float] = {}
    ticket.stage_status = dict(stage_status)
    db.commit()

    def _emit(event_type: str) -> None:
        if on_update is None:
            return
        try:
            on_update(
                {
                    "type": event_type,
                    "organization_id": org_id,
                    "ticket_id": ticket.id,
                    "status": ticket.status,
                    "stage_status": dict(ticket.stage_status or {}),
                    "priority_score": ticket.priority_score,
                    "queue_priority": ticket.queue_priority,
                    "assigned_agent_id": ticket.assigned_agent_id,
                    "needs_human_review": ticket.needs_human_review,
                    "review_reason": ticket.review_reason,
                }
            )
        except Exception as exc:
            logger.warning("WebSocket update dispatch failed for ticket %s: %s", ticket.id, exc)

    _emit("ticket_stage_update")

    # 1. Stage: STT (Whisper large-v3)
    t_stt = time.perf_counter()
    try:
        audio_path = Path(voicemail.file_path)
        raw_audio = (
            crypto.read_encrypted_file(audio_path) if voicemail.encrypted else audio_path.read_bytes()
        )
        stt_res = stt_service.transcribe(
            raw_audio,
            voicemail.format,
            file_label=voicemail.file_name,
            dup_count_fn=lambda tn: int(
                db.scalar(
                    select(func.count(Ticket.id)).where(
                        Ticket.organization_id == org_id,
                        Ticket.text_norm == tn,
                    )
                )
                or 0
            )
            + 1,
        )
    except Exception as exc:
        logger.exception("Unexpected STT storage/runtime error for ticket %s", ticket.id)
        stt_ms = round((time.perf_counter() - t_stt) * 1000.0, 2)
        stage_status["transcribe"] = "failed"
        stage_timing_ms["transcribe"] = stt_ms
        ticket.status = TicketStatus.UNASSIGNED.value
        voicemail.status = TicketStatus.UNASSIGNED.value
        ticket.needs_human_review = True
        ticket.review_reason = "processing_error"
        ticket.route_reason = f"UNASSIGNED: transcription failed ({exc}). Ticket sent to Human Review."
        ticket.stage_status = dict(stage_status)
        ticket.stage_timing_ms = dict(stage_timing_ms)
        ticket.processing_ms = round((time.perf_counter() - pipeline_t0) * 1000.0, 2)
        _log_ai_stage(
            db,
            organization_id=org_id,
            ticket_id=ticket.id,
            stage="transcribe",
            model=stt_service.canonical_model_name,
            input_ref=f"voicemail:{voicemail.id}",
            output={"error": str(exc)},
            latency_ms=int(stt_ms),
        )
        record_audit_event(
            db,
            organization_id=org_id,
            entity_type="ticket",
            entity_id=ticket.id,
            action="status_changed",
            actor="system",
            old_value={"status": "processing"},
            new_value={"status": "unassigned", "review_reason": "processing_error"},
        )
        db.commit()
        _emit("ticket_update")
        return ticket

    stt_ms = round((time.perf_counter() - t_stt) * 1000.0, 2)
    stage_timing_ms["transcribe"] = stt_ms
    voicemail.stt_v1_json = stt_res.to_v1_dict()
    ticket.transcript = stt_res.text
    ticket.text_norm = stt_res.text_norm
    ticket.language_mix = stt_res.language_mix

    _log_ai_stage(
        db,
        organization_id=org_id,
        ticket_id=ticket.id,
        stage="transcribe",
        model=stt_res.model,
        input_ref=f"voicemail:{voicemail.id}",
        output={
            "min_avg_logprob": stt_res.min_avg_logprob,
            "max_no_speech_prob": stt_res.max_no_speech_prob,
            "needs_review": stt_res.needs_review,
            "review_reasons": stt_res.review_reasons,
            "dup_text_size": stt_res.dup_text_size,
            "error": stt_res.error,
        },
        latency_ms=int(stt_ms),
    )

    if stt_res.error:
        stage_status["transcribe"] = "failed"
        ticket.status = TicketStatus.UNASSIGNED.value
        voicemail.status = TicketStatus.UNASSIGNED.value
        ticket.needs_human_review = True
        ticket.review_reason = "processing_error"
        ticket.route_reason = f"UNASSIGNED: {stt_res.error}. Routed to Human Review."
        ticket.stage_status = dict(stage_status)
        ticket.stage_timing_ms = dict(stage_timing_ms)
        ticket.processing_ms = round((time.perf_counter() - pipeline_t0) * 1000.0, 2)
        record_audit_event(
            db,
            organization_id=org_id,
            entity_type="ticket",
            entity_id=ticket.id,
            action="status_changed",
            actor="system",
            old_value={"status": "processing"},
            new_value={"status": "unassigned", "review_reason": "processing_error", "error": stt_res.error},
        )
        db.commit()
        _emit("ticket_update")
        return ticket

    stage_status["transcribe"] = "ok"
    ticket.stage_status = dict(stage_status)
    ticket.stage_timing_ms = dict(stage_timing_ms)
    db.commit()
    _emit("ticket_stage_update")

    # 2. Stage: Classification (MARBERTv2 single-task x4)
    t_cls = time.perf_counter()
    cls_res = classifier_service.classify(
        ticket.text_norm,
        confidence_threshold=conf_threshold,
        file_name=voicemail.file_name,
    )
    cls_ms = round((time.perf_counter() - t_cls) * 1000.0, 2)
    stage_timing_ms["classify"] = cls_ms
    stage_status["classify"] = "failed" if cls_res.error else "ok"

    ticket.complaint_category = cls_res.labels["complaint_category"]
    ticket.complaint_urgency = cls_res.labels["complaint_urgency"]
    ticket.customer_state = cls_res.labels["customer_state"]
    ticket.churn_risk = cls_res.labels["churn_risk"]
    ticket.probabilities = cls_res.probabilities
    ticket.confidence = cls_res.confidence
    ticket.label_sources = dict(cls_res.label_sources)
    ticket.model_version = cls_res.model_version

    _log_ai_stage(
        db,
        organization_id=org_id,
        ticket_id=ticket.id,
        stage="classify",
        model=cls_res.model_version,
        input_ref=f"ticket:{ticket.id}:text_norm",
        output={
            "labels": cls_res.labels,
            "confidence": cls_res.confidence,
            "rejected_labels": cls_res.rejected_labels,
            "needs_human_review": cls_res.needs_human_review,
            "review_reason": cls_res.review_reason,
            "error": cls_res.error,
        },
        latency_ms=int(cls_ms),
    )
    record_audit_event(
        db,
        organization_id=org_id,
        entity_type="ticket",
        entity_id=ticket.id,
        action="classified",
        actor="system",
        old_value=None,
        new_value={
            "labels": cls_res.labels,
            "confidence": cls_res.confidence,
            "model_version": cls_res.model_version,
            "source": "model",
        },
    )

    # 3. Stage: Priority computation (fixed formula)
    t_prio = time.perf_counter()
    prio_res = compute_priority(
        ticket.complaint_urgency,
        ticket.churn_risk,
        ticket.customer_state,
    )
    prio_ms = round((time.perf_counter() - t_prio) * 1000.0, 2)
    stage_timing_ms["priority"] = prio_ms
    stage_status["priority"] = "ok"

    ticket.priority_score = prio_res.priority_score
    ticket.queue_priority = prio_res.queue_priority
    ticket.priority_signals = prio_res.contributing_signals
    ticket.priority_reason = prio_res.priority_reason

    _log_ai_stage(
        db,
        organization_id=org_id,
        ticket_id=ticket.id,
        stage="priority",
        model="rules",
        input_ref=f"ticket:{ticket.id}:labels",
        output={
            "priority_score": prio_res.priority_score,
            "queue_priority": prio_res.queue_priority,
            "reason": prio_res.priority_reason,
        },
        latency_ms=int(prio_ms),
    )
    record_audit_event(
        db,
        organization_id=org_id,
        entity_type="ticket",
        entity_id=ticket.id,
        action="priority_computed",
        actor="system",
        old_value=None,
        new_value={
            "priority_score": prio_res.priority_score,
            "queue_priority": prio_res.queue_priority,
            "signals": prio_res.contributing_signals,
        },
    )

    # 4. Stage: Routing (fixed telecom skill + availability + capacity rules)
    t_route = time.perf_counter()
    blocker: str | None = None
    if cls_res.error:
        blocker = "processing_error"
    elif cls_res.review_reason in ("invalid_label", "missing_label", "low_confidence"):
        blocker = cls_res.review_reason
    elif prio_res.needs_human_review:
        blocker = prio_res.review_reason or "missing_label"

    route_dec = recommend_route(
        db,
        organization_id=org_id,
        complaint_category=ticket.complaint_category,
        auto_routing_enabled=auto_routing,
        human_review_blocker=blocker,
    )
    if route_dec.assigned_agent_id is not None:
        assign_ticket_to_agent(
            db,
            ticket,
            route_dec.assigned_agent_id,
            assigned_by="system",
            route_reason=route_dec.route_reason,
        )
    else:
        ticket.assigned_agent_id = None
        ticket.route_reason = route_dec.route_reason

    route_ms = round((time.perf_counter() - t_route) * 1000.0, 2)
    stage_timing_ms["route"] = route_ms
    stage_status["route"] = "ok"

    _log_ai_stage(
        db,
        organization_id=org_id,
        ticket_id=ticket.id,
        stage="route",
        model="rules",
        input_ref=f"ticket:{ticket.id}:category",
        output={
            "assigned_agent_id": ticket.assigned_agent_id,
            "required_skill": route_dec.required_skill,
            "route_reason": ticket.route_reason,
        },
        latency_ms=int(route_ms),
    )
    record_audit_event(
        db,
        organization_id=org_id,
        entity_type="ticket",
        entity_id=ticket.id,
        action="routed",
        actor="system",
        old_value=None,
        new_value={
            "assigned_agent_id": ticket.assigned_agent_id,
            "route_reason": ticket.route_reason,
        },
    )

    # 5. Stage: Callback brief (rule-based summary + category template script)
    t_brief = time.perf_counter()
    brief = build_callback_brief(
        db,
        organization_id=org_id,
        transcript=ticket.transcript,
        complaint_category=ticket.complaint_category,
    )
    brief_ms = round((time.perf_counter() - t_brief) * 1000.0, 2)
    stage_timing_ms["brief"] = brief_ms
    stage_status["brief"] = "flagged" if brief.flagged else "ok"

    ticket.summary = brief.summary
    ticket.customer_request = brief.customer_request
    ticket.suggested_script = brief.suggested_script

    _log_ai_stage(
        db,
        organization_id=org_id,
        ticket_id=ticket.id,
        stage="brief",
        model="rules",
        input_ref=f"ticket:{ticket.id}:transcript",
        output={"flagged": brief.flagged, "flag_reason": brief.flag_reason},
        latency_ms=int(brief_ms),
    )

    # Finalize lifecycle status and Human Review flags
    needs_review = bool(route_dec.needs_human_review or cls_res.needs_human_review or prio_res.needs_human_review or brief.flagged)
    review_reason = route_dec.review_reason or cls_res.review_reason or prio_res.review_reason or brief.flag_reason

    if ticket.assigned_agent_id is not None and not (
        route_dec.needs_human_review or cls_res.needs_human_review or prio_res.needs_human_review
    ):
        ticket.status = TicketStatus.READY.value
        voicemail.status = TicketStatus.READY.value
        if not needs_review and _is_weekly_quality_sample(ticket.id, sample_rate):
            needs_review = True
            review_reason = "weekly_quality_sample"
    else:
        if ticket.assigned_agent_id is not None:
            release_active_assignment(db, ticket, final_status="released")
            ticket.assigned_agent_id = None
        ticket.status = TicketStatus.UNASSIGNED.value
        voicemail.status = TicketStatus.UNASSIGNED.value
        needs_review = True

    ticket.needs_human_review = needs_review
    ticket.review_reason = review_reason
    ticket.stage_status = dict(stage_status)
    ticket.stage_timing_ms = dict(stage_timing_ms)
    ticket.processing_ms = round((time.perf_counter() - pipeline_t0) * 1000.0, 2)

    record_audit_event(
        db,
        organization_id=org_id,
        entity_type="ticket",
        entity_id=ticket.id,
        action="status_changed",
        actor="system",
        old_value={"status": "processing"},
        new_value={
            "status": ticket.status,
            "needs_human_review": ticket.needs_human_review,
            "review_reason": ticket.review_reason,
            "processing_ms": ticket.processing_ms,
        },
    )
    db.commit()
    db.refresh(ticket)
    _emit("ticket_update")
    return ticket
