"""Stage 6: ticket assembly (owner: Arafa).

Builds the contracts section 3.5 Ticket from the stage outputs. Fusion
stays disabled: ``customer_state_final`` is always null. ``cached`` is
always False in Phase 1: cached output is allowed only for the exact
preapproved demo file (contracts section 4.6) and no such file exists yet.
"""

from __future__ import annotations

from ..schemas import (
    AssignmentStatus,
    AudioEvidence,
    TextAnalysis,
    Ticket,
    TicketStatus,
    TriageDecision,
    VoiceEvidence,
    utcnow_iso,
)


def assemble_ticket(
    *,
    ticket_id: str,
    voicemail_id: str,
    audio: AudioEvidence,
    text: TextAnalysis,
    voice_evidence: VoiceEvidence | None,
    decision: TriageDecision,
    stage_status: dict[str, str],
    stage_timing_ms: dict[str, float],
    processing_ms: float,
    created_at: str | None = None,
) -> Ticket:
    """Assemble a completed ticket from the stage outputs."""
    return Ticket(
        id=ticket_id,
        voicemail_id=voicemail_id,
        ticket_status=TicketStatus.COMPLETED,
        assignment_status=decision.assignment_status,
        priority_score=decision.priority_score,
        route_reason=decision.route_reason,
        summary=text.summary,
        customer_request=text.customer_request,
        suggested_script=text.suggested_script,
        transcript=audio.transcript,
        complaint_category=text.complaint_category,
        complaint_urgency=text.complaint_urgency,
        customer_state_text=text.customer_state_text,
        customer_state_final=None,  # fusion disabled
        voice_state_candidate=(
            voice_evidence.voice_state_candidate if voice_evidence else None
        ),
        churn_risk=text.churn_risk,
        needs_human_review=text.needs_human_review,
        cached=False,
        stage_status=dict(stage_status),
        stage_timing_ms=dict(stage_timing_ms),
        processing_ms=processing_ms,
        created_at=created_at or utcnow_iso(),
    )


def build_review_ticket(
    *,
    ticket_id: str,
    voicemail_id: str,
    route_reason: str,
    stage_status: dict[str, str],
    stage_timing_ms: dict[str, float],
    processing_ms: float,
    created_at: str | None = None,
) -> Ticket:
    """A failed run never produces a silent normal ticket (section 4.3):
    labels stay null, the ticket is ``needs_review`` with the reason."""
    return Ticket(
        id=ticket_id,
        voicemail_id=voicemail_id,
        ticket_status=TicketStatus.NEEDS_REVIEW,
        assignment_status=AssignmentStatus.UNASSIGNED,
        priority_score=None,
        route_reason=route_reason,
        summary="",
        customer_request="",
        suggested_script="",
        transcript="",
        complaint_category=None,
        complaint_urgency=None,
        customer_state_text=None,
        customer_state_final=None,
        voice_state_candidate=None,
        churn_risk=None,
        needs_human_review=True,
        cached=False,
        stage_status=dict(stage_status),
        stage_timing_ms=dict(stage_timing_ms),
        processing_ms=processing_ms,
        created_at=created_at or utcnow_iso(),
    )
