"""VoiceGate Orchestrator: stateful AI pipeline brain coordinating Whisper, Qwen, MARBERTv2, and routing."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

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
from .adjudicator import ClassificationAdjudicator
from .brief import build_callback_brief
from .classification import CLASSIFICATION_FIELDS, ClassificationResult, MARBERTv2ClassifierService
from .memory import AgentMemoryService
from .priority import compute_priority
from .routing import assign_ticket_to_agent, recommend_route, release_active_assignment
from .stt import BaseSTTService, STTResult
from .text_norm import detect_language_mix, normalize_transcript
from .transcript_gate import GateResult, TranscriptVerificationGate, analyze_stt_signals

try:
    from .agentic_gate import AgenticTranscriptGate as _AgenticGateType
    _AnyGateType = TranscriptVerificationGate | _AgenticGateType
except ImportError:
    _AnyGateType = TranscriptVerificationGate  # type: ignore[assignment,misc]

logger = logging.getLogger("svr_platform.orchestrator")

AGENT_NAME = "VoiceGate Orchestrator"


@dataclass
class VoiceGatePlan:
    ticket_id: str
    organization_id: str
    confidence_threshold: float
    auto_routing_enabled: bool
    weekly_sample_rate: float
    low_memory_mode: bool
    completed_steps: list[str] = field(default_factory=list)


def is_weekly_quality_sample(ticket_id: str, sample_rate: float) -> bool:
    """Deterministic >=5% ticket sampling for weekly supervisor review (AI10)."""
    if sample_rate <= 0.0:
        return False
    bucket = int(hashlib.sha256(ticket_id.encode("utf-8")).hexdigest()[:8], 16) % 1000
    return bucket < int(round(sample_rate * 1000))


def log_ai_stage(
    db: Session,
    *,
    organization_id: str,
    ticket_id: str,
    stage: str,
    model: str,
    input_ref: str,
    output: dict[str, Any],
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


class VoiceGateOrchestrator:
    """Stateful pipeline orchestrator executing Plan -> STT -> Qwen Gate -> Classify -> Priority/Route/Brief.

    Coordinates memory release between heavy CPU models, validates intermediate outputs,
    preserves raw Whisper STT v1 evidence alongside Qwen-corrected text, and escalates
    uncertain transcripts safely to Human Review.
    """

    def __init__(
        self,
        *,
        crypto: EncryptionService,
        stt_service: BaseSTTService,
        transcript_gate: TranscriptVerificationGate | _AnyGateType,
        classifier_service: MARBERTv2ClassifierService,
        adjudicator: ClassificationAdjudicator | None = None,
        memory_service: AgentMemoryService | None = None,
        adaptive_reaudit_enabled: bool = True,
        adaptive_reaudit_category_threshold: float = 0.60,
        allow_transcript_edits: bool = False,
    ) -> None:
        self.agent_name = AGENT_NAME
        self.crypto = crypto
        self.stt_service = stt_service
        self.transcript_gate = transcript_gate
        self.classifier_service = classifier_service
        self.adjudicator = adjudicator
        self.memory_service = memory_service
        self.adaptive_reaudit_enabled = bool(adaptive_reaudit_enabled)
        self.adaptive_reaudit_category_threshold = float(adaptive_reaudit_category_threshold)
        self.allow_transcript_edits = bool(allow_transcript_edits)

    def _analyze_transcript_readonly(self, stt_res: STTResult) -> GateResult:
        """Analyze STT transcript quality without altering Cohere ASR output."""
        t0 = time.perf_counter()
        raw_clean = " ".join((stt_res.text or "").strip().split())
        min_lp = stt_res.min_avg_logprob
        max_nsp = stt_res.max_no_speech_prob
        conf_src = getattr(stt_res, "stt_confidence_source", "logprob")
        signals = analyze_stt_signals(
            raw_clean,
            min_avg_logprob=min_lp,
            max_no_speech_prob=max_nsp,
            stt_review_reasons=stt_res.review_reasons or "",
            stt_confidence_source=conf_src,
        )
        sig_dict = asdict(signals)
        sig_dict["min_avg_logprob"] = min_lp
        sig_dict["max_no_speech_prob"] = max_nsp

        if not raw_clean:
            return GateResult(
                agent_name=self.agent_name,
                model=stt_res.model,
                backend_used="analyze_only",
                status="skipped_empty",
                raw_text=stt_res.text,
                final_text="",
                final_text_norm="",
                language_mix="arabic",
                correction_applied=False,
                rounds_run=0,
                confidence=0.0,
                convergence_reason="empty_transcript",
                needs_human_review=True,
                review_reason="uncertain_transcript",
                signal_summary=sig_dict,
                changes=[],
                trace=[],
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                error="Raw ASR transcript was empty.",
            )

        final_norm = (stt_res.text_norm or "").strip() or normalize_transcript(raw_clean)
        lang_mix = detect_language_mix(raw_clean)
        words = raw_clean.split()
        severe_failure = (
            len(words) < 2
            or (min_lp is not None and float(min_lp) < -0.75)
            or (max_nsp is not None and float(max_nsp) > 0.80)
            or ("repetition_loop" in signals.lexical_flags)
        )
        return GateResult(
            agent_name=self.agent_name,
            model=stt_res.model,
            backend_used="analyze_only",
            status="uncertain" if severe_failure else "verified",
            raw_text=stt_res.text,
            final_text=raw_clean,
            final_text_norm=final_norm,
            language_mix=lang_mix,
            correction_applied=False,
            rounds_run=0,
            confidence=0.35 if severe_failure else 0.92,
            convergence_reason=(
                "read_only_severe_acoustic_or_loop" if severe_failure else "read_only_cohere_authoritative"
            ),
            needs_human_review=bool(severe_failure),
            review_reason="uncertain_transcript" if severe_failure else None,
            signal_summary=sig_dict,
            changes=[],
            trace=[],
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
            error="",
        )

    def _emit_event(
        self,
        on_update: Callable[[dict[str, Any]], None] | None,
        *,
        event_type: str,
        ticket: Ticket,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if on_update is None:
            return
        payload: dict[str, Any] = {
            "type": event_type,
            "organization_id": ticket.organization_id,
            "ticket_id": ticket.id,
            "status": ticket.status,
            "stage_status": dict(ticket.stage_status or {}),
            "priority_score": ticket.priority_score,
            "queue_priority": ticket.queue_priority,
            "assigned_agent_id": ticket.assigned_agent_id,
            "needs_human_review": ticket.needs_human_review,
            "review_reason": ticket.review_reason,
            "orchestrator": self.agent_name,
        }
        if extra:
            payload.update(extra)
        try:
            on_update(payload)
        except Exception as exc:
            logger.warning("WebSocket update dispatch failed for ticket %s: %s", ticket.id, exc)

    def _fail_early_on_stt(
        self,
        db: Session,
        *,
        ticket: Ticket,
        voicemail: Voicemail,
        stage_status: dict[str, str],
        stage_timing_ms: dict[str, float],
        stt_ms: float,
        pipeline_t0: float,
        error_message: str,
        audit_new_value: dict[str, Any],
        on_update: Callable[[dict[str, Any]], None] | None,
    ) -> Ticket:
        stage_status["transcribe"] = "failed"
        stage_timing_ms["transcribe"] = stt_ms
        ticket.status = TicketStatus.UNASSIGNED.value
        voicemail.status = TicketStatus.UNASSIGNED.value
        ticket.needs_human_review = True
        ticket.review_reason = "processing_error"
        ticket.route_reason = f"UNASSIGNED: {error_message} Escalated by {self.agent_name}."
        ticket.stage_status = dict(stage_status)
        ticket.stage_timing_ms = dict(stage_timing_ms)
        ticket.processing_ms = round((time.perf_counter() - pipeline_t0) * 1000.0, 2)
        record_audit_event(
            db,
            organization_id=ticket.organization_id,
            entity_type="ticket",
            entity_id=ticket.id,
            action="status_changed",
            actor=self.agent_name,
            old_value={"status": "processing"},
            new_value=audit_new_value,
        )
        db.commit()
        self._emit_event(on_update, event_type="ticket_update", ticket=ticket)
        return ticket

    def run(
        self,
        db: Session,
        *,
        ticket_id: str,
        on_update: Callable[[dict[str, Any]], None] | None = None,
    ) -> Ticket:
        pipeline_t0 = time.perf_counter()
        ticket = db.get(Ticket, ticket_id)
        if ticket is None:
            raise ValueError(f"Ticket {ticket_id} not found")
        voicemail = db.get(Voicemail, ticket.voicemail_id)
        if voicemail is None:
            raise ValueError(f"Voicemail {ticket.voicemail_id} not found")

        org_id = ticket.organization_id
        sys_setting = db.get(SystemSetting, org_id)
        plan = VoiceGatePlan(
            ticket_id=ticket.id,
            organization_id=org_id,
            confidence_threshold=sys_setting.confidence_threshold if sys_setting else 0.5,
            auto_routing_enabled=sys_setting.auto_routing_enabled if sys_setting else True,
            weekly_sample_rate=sys_setting.weekly_sample_rate if sys_setting else 0.05,
            low_memory_mode=bool(
                getattr(self.stt_service, "low_memory_mode", False)
                or getattr(self.transcript_gate, "low_memory_mode", False)
            ),
        )

        # FR21: snapshot active settings so future admin changes affect new tickets only
        ticket.confidence_threshold_snapshot = plan.confidence_threshold
        ticket.config_snapshot = {
            "confidence_threshold": plan.confidence_threshold,
            "auto_routing_enabled": plan.auto_routing_enabled,
            "weekly_sample_rate": plan.weekly_sample_rate,
            "orchestrator": self.agent_name,
        }
        ticket.status = TicketStatus.PROCESSING.value
        voicemail.status = TicketStatus.PROCESSING.value
        stage_status: dict[str, str] = {"intake": "ok"}
        stage_timing_ms: dict[str, float] = {}
        ticket.stage_status = dict(stage_status)
        db.commit()
        self._emit_event(on_update, event_type="ticket_stage_update", ticket=ticket, extra={"stage": "intake"})

        # 1. Stage: STT (Whisper large-v3) with immediate memory release
        t_stt = time.perf_counter()
        try:
            audio_path = Path(voicemail.file_path)
            raw_audio = (
                self.crypto.read_encrypted_file(audio_path)
                if voicemail.encrypted
                else audio_path.read_bytes()
            )
            stt_res = self.stt_service.transcribe(
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
            log_ai_stage(
                db,
                organization_id=org_id,
                ticket_id=ticket.id,
                stage="transcribe",
                model=self.stt_service.canonical_model_name,
                input_ref=f"voicemail:{voicemail.id}",
                output={"error": str(exc)},
                latency_ms=int(stt_ms),
            )
            return self._fail_early_on_stt(
                db,
                ticket=ticket,
                voicemail=voicemail,
                stage_status=stage_status,
                stage_timing_ms=stage_timing_ms,
                stt_ms=stt_ms,
                pipeline_t0=pipeline_t0,
                error_message=f"transcription failed ({exc}).",
                audit_new_value={"status": "unassigned", "review_reason": "processing_error"},
                on_update=on_update,
            )
        finally:
            if getattr(self.stt_service, "low_memory_mode", False) and hasattr(self.stt_service, "unload"):
                self.stt_service.unload()

        stt_ms = round((time.perf_counter() - t_stt) * 1000.0, 2)
        stage_timing_ms["transcribe"] = stt_ms
        # Preserve locked 10-column raw Whisper evidence untouched
        voicemail.stt_v1_json = stt_res.to_v1_dict()

        log_ai_stage(
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
            return self._fail_early_on_stt(
                db,
                ticket=ticket,
                voicemail=voicemail,
                stage_status=stage_status,
                stage_timing_ms=stage_timing_ms,
                stt_ms=stt_ms,
                pipeline_t0=pipeline_t0,
                error_message=f"{stt_res.error}.",
                audit_new_value={"status": "unassigned", "review_reason": "processing_error", "error": stt_res.error},
                on_update=on_update,
            )

        stage_status["transcribe"] = "ok"
        plan.completed_steps.append("transcribe")
        ticket.stage_status = dict(stage_status)
        ticket.stage_timing_ms = dict(stage_timing_ms)
        db.commit()
        self._emit_event(on_update, event_type="ticket_stage_update", ticket=ticket, extra={"stage": "transcribe"})

        # 2. Stage: Transcript Analysis (Cohere ASR is authoritative unless edits are explicitly enabled)
        if self.allow_transcript_edits:
            verify_kwargs: dict[str, Any] = {
                "min_avg_logprob": stt_res.min_avg_logprob,
                "max_no_speech_prob": stt_res.max_no_speech_prob,
                "stt_review_reasons": stt_res.review_reasons,
            }
            if hasattr(self.transcript_gate, "verify"):
                import inspect

                sig_params = inspect.signature(self.transcript_gate.verify).parameters
                if "stt_confidence_source" in sig_params:
                    verify_kwargs["stt_confidence_source"] = getattr(stt_res, "stt_confidence_source", "logprob")
            gate_res: GateResult = self.transcript_gate.verify(
                stt_res.text,
                **verify_kwargs,
            )
        else:
            verify_kwargs = {}
            gate_res = self._analyze_transcript_readonly(stt_res)
        gate_ms = round(float(gate_res.latency_ms), 2)
        stage_timing_ms["verify_transcript"] = gate_ms
        stage_status["verify_transcript"] = "flagged" if gate_res.needs_human_review else "ok"
        plan.completed_steps.append("verify_transcript")

        ticket.transcript = gate_res.final_text
        ticket.text_norm = gate_res.final_text_norm
        ticket.language_mix = gate_res.language_mix
        ticket.transcript_verification_json = gate_res.to_report_dict()

        log_ai_stage(
            db,
            organization_id=org_id,
            ticket_id=ticket.id,
            stage="verify_transcript",
            model=f"{gate_res.model} ({self.agent_name})",
            input_ref=f"voicemail:{voicemail.id}:stt_v1",
            output={
                "agent_name": self.agent_name,
                "status": gate_res.status,
                "backend_used": gate_res.backend_used,
                "correction_applied": gate_res.correction_applied,
                "rounds_run": gate_res.rounds_run,
                "confidence": gate_res.confidence,
                "convergence_reason": gate_res.convergence_reason,
                "needs_human_review": gate_res.needs_human_review,
                "review_reason": gate_res.review_reason,
                "changes_count": len(gate_res.changes),
                "error": gate_res.error,
            },
            latency_ms=int(gate_ms),
        )
        if gate_res.correction_applied or gate_res.needs_human_review:
            record_audit_event(
                db,
                organization_id=org_id,
                entity_type="ticket",
                entity_id=ticket.id,
                action="transcript_verified",
                actor=self.agent_name,
                old_value={"raw_transcript": stt_res.text},
                new_value={
                    "corrected_transcript": gate_res.final_text,
                    "status": gate_res.status,
                    "confidence": gate_res.confidence,
                    "rounds_run": gate_res.rounds_run,
                    "changes": [c.to_dict() for c in gate_res.changes],
                },
            )

        ticket.stage_status = dict(stage_status)
        ticket.stage_timing_ms = dict(stage_timing_ms)
        db.commit()
        self._emit_event(
            on_update,
            event_type="ticket_stage_update",
            ticket=ticket,
            extra={"stage": "verify_transcript"},
        )

        # 3. Stage: Classification (MARBERTv2 single-task x4) consuming verified text_norm
        t_cls = time.perf_counter()
        if gate_res.status == "skipped_empty" or not (ticket.text_norm or "").strip():
            cls_res = ClassificationResult(
                labels={f: None for f in CLASSIFICATION_FIELDS},
                probabilities={f: {} for f in CLASSIFICATION_FIELDS},
                confidence=0.0,
                needs_human_review=True,
                review_reason="uncertain_transcript",
                model_version=f"{self.classifier_service.base_model_id}:skipped-empty",
                label_sources={f: "model" for f in CLASSIFICATION_FIELDS},
                error="",
            )
            cls_ms = round((time.perf_counter() - t_cls) * 1000.0, 2)
            stage_timing_ms["classify"] = cls_ms
            stage_status["classify"] = "skipped"
        else:
            cls_res = self.classifier_service.classify(
                ticket.text_norm,
                confidence_threshold=plan.confidence_threshold,
                file_name=voicemail.file_name,
            )
            # VG-10: max-1 adaptive VoiceGate re-audit ONLY when fast-path skipped (rounds_run == 0)
            # and complaint_category head probability is below threshold.
            cat_label = cls_res.labels.get("complaint_category")
            cat_conf = (
                float((cls_res.probabilities.get("complaint_category") or {}).get(cat_label, 0.0))
                if cat_label
                else 0.0
            )
            if (
                self.allow_transcript_edits
                and self.adaptive_reaudit_enabled
                and gate_res.rounds_run == 0
                and not cls_res.error
                and cat_conf < self.adaptive_reaudit_category_threshold
            ):
                import inspect

                reaudit_kwargs = dict(verify_kwargs)
                if "force_audit" in inspect.signature(self.transcript_gate.verify).parameters:
                    reaudit_kwargs["force_audit"] = True
                reaudit_res: GateResult = self.transcript_gate.verify(
                    stt_res.text,
                    **reaudit_kwargs,
                )
                reaudit_ms = round(float(reaudit_res.latency_ms), 2)
                stage_timing_ms["verify_transcript_reaudit"] = reaudit_ms
                plan.completed_steps.append("verify_transcript_reaudit")
                log_ai_stage(
                    db,
                    organization_id=org_id,
                    ticket_id=ticket.id,
                    stage="verify_transcript_reaudit",
                    model=f"{reaudit_res.model} ({self.agent_name})",
                    input_ref=f"ticket:{ticket.id}:category_conf={cat_conf:.3f}",
                    output={
                        "trigger_category_confidence": round(cat_conf, 4),
                        "status": reaudit_res.status,
                        "correction_applied": reaudit_res.correction_applied,
                        "rounds_run": reaudit_res.rounds_run,
                        "confidence": reaudit_res.confidence,
                    },
                    latency_ms=int(reaudit_ms),
                )
                # Preserve an already-verified clean acoustic result if re-audit rejected all rounds with zero edits.
                reaudit_failed_zero_accept = (
                    gate_res.status == "verified"
                    and not gate_res.needs_human_review
                    and not reaudit_res.correction_applied
                    and reaudit_res.needs_human_review
                    and reaudit_res.confidence <= 0.0
                )
                if not reaudit_failed_zero_accept:
                    gate_res = reaudit_res
                    stage_status["verify_transcript"] = "flagged" if gate_res.needs_human_review else "ok"
                    ticket.transcript_verification_json = gate_res.to_report_dict()
                    if normalize_transcript(gate_res.final_text) != ticket.text_norm:
                        ticket.transcript = gate_res.final_text
                        ticket.text_norm = gate_res.final_text_norm
                        ticket.language_mix = gate_res.language_mix
                        cls_res = self.classifier_service.classify(
                            ticket.text_norm,
                            confidence_threshold=plan.confidence_threshold,
                            file_name=voicemail.file_name,
                        )

            cls_ms = round((time.perf_counter() - t_cls) * 1000.0, 2)
            stage_timing_ms["classify"] = cls_ms
            stage_status["classify"] = "failed" if cls_res.error else "ok"
        plan.completed_steps.append("classify")

        marbert_raw_labels = dict(cls_res.labels)
        adj_res = None
        if (
            self.adjudicator is not None
            and self.adjudicator.enabled
            and gate_res.status != "skipped_empty"
            and not cls_res.error
        ):
            adj_res = self.adjudicator.review_and_adjudicate(
                db,
                organization_id=org_id,
                ticket_id=ticket.id,
                transcript=ticket.transcript,
                text_norm=ticket.text_norm,
                marbert_result=cls_res,
                gate_result=gate_res,
                confidence_threshold=plan.confidence_threshold,
            )
            cls_res = adj_res.classification_result
            stage_timing_ms["adjudicate"] = round(float(adj_res.latency_ms), 2)
            stage_status["adjudicate"] = "overridden" if adj_res.changed_fields else "ok"
            plan.completed_steps.append("adjudicate")

            tv_report = dict(ticket.transcript_verification_json or {})
            tv_report["orchestrator_adjudication"] = adj_res.to_report_dict()
            if adj_res.resolved_gate_uncertainty:
                tv_report["needs_human_review"] = False
                tv_report["review_reason"] = None
                tv_report["status"] = "verified"
                stage_status["verify_transcript"] = "ok"
                gate_res.needs_human_review = False
                gate_res.review_reason = None
            ticket.transcript_verification_json = tv_report

            log_ai_stage(
                db,
                organization_id=org_id,
                ticket_id=ticket.id,
                stage="adjudicate",
                model=f"{self.adjudicator.ollama_model} ({self.agent_name})",
                input_ref=f"ticket:{ticket.id}:marbert_plus_memory",
                output=adj_res.to_report_dict(),
                latency_ms=int(adj_res.latency_ms),
            )
            if adj_res.changed_fields:
                record_audit_event(
                    db,
                    organization_id=org_id,
                    entity_type="ticket",
                    entity_id=ticket.id,
                    action="classification_adjudicated",
                    actor=self.agent_name,
                    old_value={"marbert_labels": marbert_raw_labels},
                    new_value={
                        "agent_labels": dict(cls_res.labels),
                        "changed_fields": adj_res.changed_fields,
                        "reasoning": adj_res.reasoning,
                    },
                )

        ticket.complaint_category = cls_res.labels["complaint_category"]
        ticket.complaint_urgency = cls_res.labels["complaint_urgency"]
        ticket.customer_state = cls_res.labels["customer_state"]
        ticket.churn_risk = cls_res.labels["churn_risk"]
        ticket.probabilities = cls_res.probabilities
        ticket.confidence = cls_res.confidence
        ticket.label_sources = dict(cls_res.label_sources)
        ticket.model_version = cls_res.model_version

        log_ai_stage(
            db,
            organization_id=org_id,
            ticket_id=ticket.id,
            stage="classify",
            model=cls_res.model_version,
            input_ref=f"ticket:{ticket.id}:verified_text_norm",
            output={
                "labels": cls_res.labels,
                "confidence": cls_res.confidence,
                "rejected_labels": cls_res.rejected_labels,
                "needs_human_review": cls_res.needs_human_review,
                "review_reason": cls_res.review_reason,
                "gate_corrected": gate_res.correction_applied,
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
            actor=self.agent_name,
            old_value=None,
            new_value={
                "labels": cls_res.labels,
                "confidence": cls_res.confidence,
                "model_version": cls_res.model_version,
                "gate_status": gate_res.status,
                "source": "model",
            },
        )

        # 4. Stage: Priority computation (fixed formula)
        t_prio = time.perf_counter()
        prio_res = compute_priority(
            ticket.complaint_urgency,
            ticket.churn_risk,
            ticket.customer_state,
        )
        prio_ms = round((time.perf_counter() - t_prio) * 1000.0, 2)
        stage_timing_ms["priority"] = prio_ms
        stage_status["priority"] = "ok"
        plan.completed_steps.append("priority")

        ticket.priority_score = prio_res.priority_score
        ticket.queue_priority = prio_res.queue_priority
        ticket.priority_signals = prio_res.contributing_signals
        ticket.priority_reason = prio_res.priority_reason

        log_ai_stage(
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
            actor=self.agent_name,
            old_value=None,
            new_value={
                "priority_score": prio_res.priority_score,
                "queue_priority": prio_res.queue_priority,
                "signals": prio_res.contributing_signals,
            },
        )

        # 5. Stage: Routing with cross-stage blocker resolution
        t_route = time.perf_counter()
        blocker: str | None = None
        if cls_res.error:
            blocker = "processing_error"
        elif gate_res.status == "skipped_empty":
            blocker = gate_res.review_reason or "uncertain_transcript"
        elif cls_res.review_reason in ("invalid_label", "missing_label", "low_confidence"):
            blocker = cls_res.review_reason
        elif gate_res.needs_human_review:
            blocker = gate_res.review_reason or "uncertain_transcript"
        elif prio_res.needs_human_review:
            blocker = prio_res.review_reason or "missing_label"

        route_dec = recommend_route(
            db,
            organization_id=org_id,
            complaint_category=ticket.complaint_category,
            auto_routing_enabled=plan.auto_routing_enabled,
            human_review_blocker=blocker,
        )
        if route_dec.assigned_agent_id is not None:
            route_reason = route_dec.route_reason
            if adj_res is not None:
                route_reason = f"{route_reason} Verified by {self.agent_name} ({adj_res.mode})."
            assign_ticket_to_agent(
                db,
                ticket,
                route_dec.assigned_agent_id,
                assigned_by=self.agent_name if adj_res is not None else "system",
                route_reason=route_reason,
            )
        else:
            ticket.assigned_agent_id = None
            ticket.route_reason = route_dec.route_reason

        route_ms = round((time.perf_counter() - t_route) * 1000.0, 2)
        stage_timing_ms["route"] = route_ms
        stage_status["route"] = "ok"
        plan.completed_steps.append("route")

        log_ai_stage(
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
            actor=self.agent_name,
            old_value=None,
            new_value={
                "assigned_agent_id": ticket.assigned_agent_id,
                "route_reason": ticket.route_reason,
            },
        )

        # 6. Stage: Callback brief on verified transcript
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
        plan.completed_steps.append("brief")

        ticket.summary = brief.summary
        ticket.customer_request = brief.customer_request
        ticket.suggested_script = brief.suggested_script

        log_ai_stage(
            db,
            organization_id=org_id,
            ticket_id=ticket.id,
            stage="brief",
            model="rules",
            input_ref=f"ticket:{ticket.id}:transcript",
            output={"flagged": brief.flagged, "flag_reason": brief.flag_reason},
            latency_ms=int(brief_ms),
        )

        # Finalize lifecycle status and Human Review flags across all pipeline stages
        needs_review = bool(
            route_dec.needs_human_review
            or cls_res.needs_human_review
            or gate_res.needs_human_review
            or prio_res.needs_human_review
            or brief.flagged
        )
        review_reason = (
            (gate_res.review_reason or "uncertain_transcript")
            if gate_res.status == "skipped_empty"
            else (
                route_dec.review_reason
                or cls_res.review_reason
                or gate_res.review_reason
                or prio_res.review_reason
                or brief.flag_reason
            )
        )

        if ticket.assigned_agent_id is not None and not (
            route_dec.needs_human_review
            or cls_res.needs_human_review
            or gate_res.needs_human_review
            or prio_res.needs_human_review
        ):
            ticket.status = TicketStatus.READY.value
            voicemail.status = TicketStatus.READY.value
            # Track proactive 5% QA sampling separately so clean routed tickets do not inflate escalations
            qa_sampled = bool(
                not needs_review and is_weekly_quality_sample(ticket.id, plan.weekly_sample_rate)
            )
            cfg_snap = dict(ticket.config_snapshot or {})
            cfg_snap["qa_sampled"] = qa_sampled
            cfg_snap["qa_sample_reason"] = "weekly_quality_sample" if qa_sampled else None
            ticket.config_snapshot = cfg_snap
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

        # 7. Stage: Self-improving memory consolidation (Episodic + Procedural + Self-Training Curator)
        if (
            self.memory_service is not None
            and self.memory_service.enabled
            and not cls_res.error
            and gate_res.status != "skipped_empty"
            and all(cls_res.labels.get(f) for f in CLASSIFICATION_FIELDS)
        ):
            mem_source = (
                "agent_adjudicated"
                if (adj_res is not None and adj_res.changed_fields)
                else "high_conf_verified"
            )
            try:
                self.memory_service.consolidate_ticket_outcome(
                    db,
                    organization_id=org_id,
                    ticket_id=ticket.id,
                    transcript=ticket.transcript,
                    text_norm=ticket.text_norm,
                    marbert_labels=marbert_raw_labels,
                    final_labels=cls_res.labels,
                    confidence=cls_res.confidence,
                    rationale=(adj_res.reasoning if adj_res else "MARBERTv2 verified clean output"),
                    source=mem_source,
                    was_corrected=bool(adj_res is not None and adj_res.changed_fields),
                    learned_lesson=(adj_res.learned_lesson if adj_res else ""),
                    add_to_episodic=bool(
                        cls_res.confidence >= 0.75
                        or (adj_res is not None and adj_res.mode == "fast_verified")
                    ),
                )
                plan.completed_steps.append("consolidate_memory")
            except Exception as exc:
                logger.warning("Memory consolidation failed for ticket %s: %s", ticket.id, exc)
            finally:
                if plan.low_memory_mode:
                    self.memory_service.embed_client.unload()

        record_audit_event(
            db,
            organization_id=org_id,
            entity_type="ticket",
            entity_id=ticket.id,
            action="status_changed",
            actor=self.agent_name,
            old_value={"status": "processing"},
            new_value={
                "status": ticket.status,
                "needs_human_review": ticket.needs_human_review,
                "review_reason": ticket.review_reason,
                "processing_ms": ticket.processing_ms,
                "completed_steps": plan.completed_steps,
            },
        )
        db.commit()
        db.refresh(ticket)
        self._emit_event(on_update, event_type="ticket_update", ticket=ticket)
        return ticket
