"""SVR Phase 1 pipeline skeleton (Role 6, Arafa).

Mock stages only. No model is loaded, no network call is made, no real
audio or transcript is read.
"""

from __future__ import annotations

import copy
from typing import Callable

from .latency import Timer
from .schemas import (
    AudioEvidence,
    TextAnalysis,
    Ticket,
    TicketStatus,
    TriageDecision,
    VoiceEvidence,
    utcnow_iso,
)
from .stages import classification, intake, stt, ticket as ticket_stage, triage, voice
from .stages.intake import AudioMeta


class PipelineResult:
    """Everything one pipeline run produces, for the API and the demo."""

    def __init__(
        self,
        ticket: Ticket,
        audio: AudioEvidence | None,
        text: TextAnalysis | None,
        voice_evidence: VoiceEvidence | None,
        decision: TriageDecision | None,
    ) -> None:
        self.ticket = ticket
        self.audio = audio
        self.text = text
        self.voice_evidence = voice_evidence
        self.decision = decision


def run_pipeline(
    audio_meta: AudioMeta,
    voicemail_id: str,
    ticket_id: str | None = None,
    *,
    classification_override: dict | None = None,
    now: Callable[[], str] = utcnow_iso,
) -> PipelineResult:
    """Run intake -> STT -> text analysis -> voice evidence -> triage -> ticket.

    Runs on upload metadata only (filename, size, duration). Audio bytes
    never enter this function: the endpoint measures them first with
    ``validate_and_measure`` and discards them, and the background task
    carries only the AudioMeta. All stages are mocks returning the contracts
    section 9 fixture values. ``classification_override`` lets tests (and
    only tests) feed a different TextAnalysis payload, e.g. a null category,
    to prove the null/review rules. A failed stage never produces a silent
    normal ticket: the run ends as ``needs_review`` with the failed stage
    recorded.
    """
    timer = Timer()
    stage_status: dict[str, str] = {}
    stage_timing_ms: dict[str, float] = {}
    audio: AudioEvidence | None = None
    text: TextAnalysis | None = None
    voice_evidence: VoiceEvidence | None = None
    decision: TriageDecision | None = None

    def fail(reason: str, failed_stage: str) -> PipelineResult:
        stage_status[failed_stage] = "failed"
        ticket = ticket_stage.build_review_ticket(
            ticket_id=ticket_id or f"ticket-{voicemail_id}",
            voicemail_id=voicemail_id,
            route_reason=reason,
            stage_status=stage_status,
            stage_timing_ms=stage_timing_ms,
            processing_ms=timer.elapsed_ms(),
            created_at=now(),
        )
        return PipelineResult(ticket, audio, text, voice_evidence, decision)

    # 1. Intake: re-validate the metadata; record audio metadata.
    # No bytes here: validate_metadata checks format, size and duration
    # from the AudioMeta the endpoint measured.
    with timer.stage("intake") as elapsed:
        try:
            audio_meta = intake.validate_metadata(
                audio_meta.filename,
                audio_meta.size_bytes,
                audio_meta.duration_s,
                audio_meta.duration_checked,
                voicemail_id,
                audio_meta.sample_rate_hz,
                audio_meta.channels,
            )
        except ValueError as exc:
            stage_timing_ms["intake"] = elapsed()
            return fail(f"Intake rejected the upload: {exc}", "intake")
    stage_status["intake"] = "ok"
    stage_timing_ms["intake"] = elapsed()

    # 2. STT (mock): fixed fixture transcript.
    with timer.stage("stt") as elapsed:
        try:
            audio = stt.transcribe_mock(audio_meta)
        except ValueError as exc:
            stage_timing_ms["stt"] = elapsed()
            return fail(f"STT failed: {exc}", "stt")
    stage_status["stt"] = "ok"
    stage_timing_ms["stt"] = elapsed()

    # 3. Text analysis (mock): fixed fixture fields.
    with timer.stage("text_analysis") as elapsed:
        try:
            text = classification.classify_mock(audio, override=classification_override)
        except ValueError as exc:
            # Out-of-enum label: rejected by schema validation, ticket goes
            # to human review, never stored as a valid label (section 4.2).
            stage_timing_ms["text_analysis"] = elapsed()
            return fail(
                f"Text analysis output failed schema validation: {exc}",
                "text_analysis",
            )
    stage_status["text_analysis"] = "ok"
    stage_timing_ms["text_analysis"] = elapsed()

    # 4. Voice evidence (mock): skipped in Phase 1. The audio model lands
    # with Sira in Phase 2; until then there is no voice_state_candidate.
    with timer.stage("voice_evidence") as elapsed:
        try:
            voice_evidence = voice.voice_evidence_mock(audio)
        except Exception as exc:
            # Any stage failure ends the run as needs_review, never as a
            # silent normal ticket (see the module docstring guarantee).
            stage_timing_ms["voice_evidence"] = elapsed()
            return fail(f"Voice evidence failed: {exc}", "voice_evidence")
    stage_status["voice_evidence"] = "skipped" if voice_evidence is None else "ok"
    stage_timing_ms["voice_evidence"] = elapsed()

    # 5. Triage (mock): fixed route reason, seeded-agent assignment.
    with timer.stage("triage") as elapsed:
        try:
            decision = triage.triage_mock(text, voice_evidence)
        except Exception as exc:
            stage_timing_ms["triage"] = elapsed()
            return fail(f"Triage failed: {exc}", "triage")
    stage_status["triage"] = "ok"
    stage_timing_ms["triage"] = elapsed()

    # 6. Ticket assembly. The status is derived by assemble_ticket
    # itself (null label or review flag means NEEDS_REVIEW); a failure
    # here ends the run as needs_review with the stage recorded.
    try:
        ticket = ticket_stage.assemble_ticket(
            ticket_id=ticket_id or f"ticket-{voicemail_id}",
            voicemail_id=voicemail_id,
            audio=audio,
            text=text,
            voice_evidence=voice_evidence,
            decision=decision,
            stage_status=stage_status,
            stage_timing_ms=stage_timing_ms,
            processing_ms=timer.elapsed_ms(),
            created_at=now(),
        )
    except Exception as exc:
        return fail(f"Ticket assembly failed: {exc}", "ticket")
    return PipelineResult(ticket, audio, text, voice_evidence, decision)


def fixture_ticket() -> Ticket:
    """The contracts section 9 fixture ticket, as a validated Ticket."""
    from . import fixtures

    return Ticket.model_validate(copy.deepcopy(fixtures.FIXTURE_TICKET))
