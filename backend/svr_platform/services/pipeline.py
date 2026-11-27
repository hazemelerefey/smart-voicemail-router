"""Async voicemail-to-ticket AI pipeline entrypoint delegating to VoiceGate Orchestrator."""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy.orm import Session

from ..crypto import EncryptionService
from ..models import Ticket
from .adjudicator import ClassificationAdjudicator
from .classification import MARBERTv2ClassifierService
from .memory import AgentMemoryService
from .orchestrator import VoiceGateOrchestrator, is_weekly_quality_sample, log_ai_stage
from .stt import BaseSTTService
from .transcript_gate import TranscriptVerificationGate

_is_weekly_quality_sample = is_weekly_quality_sample
_log_ai_stage = log_ai_stage


def run_voicemail_pipeline(
    db: Session,
    *,
    ticket_id: str,
    crypto: EncryptionService,
    stt_service: BaseSTTService,
    classifier_service: MARBERTv2ClassifierService,
    transcript_gate: TranscriptVerificationGate | Any | None = None,
    adjudicator: ClassificationAdjudicator | None = None,
    memory_service: AgentMemoryService | None = None,
    on_update: Callable[[dict[str, Any]], None] | None = None,
    adaptive_reaudit_enabled: bool = True,
    adaptive_reaudit_category_threshold: float = 0.60,
) -> Ticket:
    """Execute full local voicemail pipeline via VoiceGate Orchestrator."""
    gate = transcript_gate or TranscriptVerificationGate()
    orchestrator = VoiceGateOrchestrator(
        crypto=crypto,
        stt_service=stt_service,
        transcript_gate=gate,
        classifier_service=classifier_service,
        adjudicator=adjudicator,
        memory_service=memory_service,
        adaptive_reaudit_enabled=adaptive_reaudit_enabled,
        adaptive_reaudit_category_threshold=adaptive_reaudit_category_threshold,
    )
    return orchestrator.run(db, ticket_id=ticket_id, on_update=on_update)
