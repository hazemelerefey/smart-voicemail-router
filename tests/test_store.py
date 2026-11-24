"""Store tests: duplicates, deep copies, state machine, ticket assembly."""

import pytest

from svr.pipeline import PipelineResult, run_pipeline
from svr.schemas import TicketStatus
from svr.stages.intake import AudioMeta
from svr.stages.ticket import assemble_ticket
from svr.store import TicketStore


def _make_meta(voicemail_id: str) -> AudioMeta:
    return AudioMeta(
        voicemail_id=voicemail_id,
        filename="test.wav",
        format="wav",
        size_bytes=32044,
        duration_s=1.0,
        duration_checked=True,
    )


def _completed_run(store: TicketStore, ticket_id: str, voicemail_id: str):
    """Run the mock pipeline and store it as a completed ticket."""
    result = run_pipeline(_make_meta(voicemail_id), voicemail_id, ticket_id=ticket_id)
    store.create_placeholder(ticket_id, voicemail_id)
    store.complete(result)
    return result


def test_create_placeholder_rejects_duplicate():
    store = TicketStore()
    store.create_placeholder("ticket-dup-001", "voicemail-dup-001")
    with pytest.raises(ValueError, match="already exists"):
        store.create_placeholder("ticket-dup-001", "voicemail-dup-001")
    assert store.get("ticket-dup-001").ticket_status == TicketStatus.PROCESSING


def test_duplicate_placeholder_cannot_clobber_finished_evidence():
    store = TicketStore()
    result = _completed_run(store, "ticket-dup-002", "voicemail-dup-002")
    with pytest.raises(ValueError, match="already exists"):
        store.create_placeholder("ticket-dup-002", "voicemail-dup-002")
    detail = store.get_detail("ticket-dup-002")
    assert detail.ticket_status == TicketStatus.COMPLETED
    assert detail.audio_evidence is not None
    assert detail.transcript != ""
    assert detail.text_analysis is not None
    assert detail.triage_decision is not None
    assert [e.event for e in detail.events] == ["submitted", "completed"]


def test_complete_rejects_non_terminal_and_double_complete():
    store = TicketStore()
    result = _completed_run(store, "ticket-dup-003", "voicemail-dup-003")
    with pytest.raises(ValueError, match="already finished"):
        store.complete(result)
    placeholder = store.create_placeholder("ticket-dup-004", "voicemail-dup-004")
    with pytest.raises(ValueError, match="cannot complete"):
        store.complete(PipelineResult(placeholder, None, None, None, None))


def test_get_returns_deep_copy():
    """Mutating a ticket returned by get() does not change the stored one."""
    store = TicketStore()
    result = _completed_run(store, "ticket-copy-001", "voicemail-copy-001")
    got = store.get("ticket-copy-001")
    got.complaint_category = None
    got.stage_status["intake"] = "tampered"
    stored = store.get("ticket-copy-001")
    assert stored.complaint_category is not None
    assert stored.stage_status["intake"] == "ok"


def test_get_detail_returns_deep_copies():
    store = TicketStore()
    _completed_run(store, "ticket-copy-002", "voicemail-copy-002")
    detail = store.get_detail("ticket-copy-002")
    detail.audio_evidence.transcript = "tampered"
    detail.events[0].detail = "tampered"
    fresh = store.get_detail("ticket-copy-002")
    assert fresh.audio_evidence.transcript != "tampered"
    assert fresh.events[0].detail != "tampered"


def test_update_rejects_invalid_transitions():
    store = TicketStore()
    result = _completed_run(store, "ticket-sm-001", "voicemail-sm-001")
    with pytest.raises(ValueError, match="invalid status transition"):
        store.update("ticket-sm-001", ticket_status="queued")
    # A processing placeholder has null labels: it cannot be completed.
    store.create_placeholder("ticket-sm-002", "voicemail-sm-002")
    with pytest.raises(ValueError, match="null labels"):
        store.update("ticket-sm-002", ticket_status="completed")
    # A needs_review ticket with null labels cannot be completed either.
    review = run_pipeline(
        _make_meta("voicemail-sm-003"),
        "voicemail-sm-003",
        ticket_id="ticket-sm-003",
        classification_override={"complaint_category": None},
    )
    store.create_placeholder("ticket-sm-003", "voicemail-sm-003")
    store.complete(review)
    with pytest.raises(ValueError, match="null labels"):
        store.update("ticket-sm-003", ticket_status="completed")


def test_update_keeps_review_flag_in_sync():
    store = TicketStore()
    # A processing placeholder sent to review gets the flag.
    store.create_placeholder("ticket-sm-004", "voicemail-sm-004")
    updated = store.update("ticket-sm-004", ticket_status="needs_review")
    assert updated.ticket_status == TicketStatus.NEEDS_REVIEW
    assert updated.needs_human_review is True
    # A needs_review ticket with all labels present can be completed, and
    # the flag flips back to False.
    result = run_pipeline(
        _make_meta("voicemail-sm-005"), "voicemail-sm-005", ticket_id="ticket-sm-005"
    )
    review_ticket = result.ticket.model_copy(
        update={
            "ticket_status": TicketStatus.NEEDS_REVIEW,
            "needs_human_review": True,
        }
    )
    store.create_placeholder("ticket-sm-005", "voicemail-sm-005")
    store.complete(
        PipelineResult(
            review_ticket,
            result.audio,
            result.text,
            result.voice_evidence,
            result.decision,
        )
    )
    updated = store.update("ticket-sm-005", ticket_status="completed")
    assert updated.ticket_status == TicketStatus.COMPLETED
    assert updated.needs_human_review is False
    assert updated.complaint_category is not None


def test_latency_samples_include_zero_duration_runs():
    store = TicketStore()
    result = run_pipeline(
        _make_meta("voicemail-zero-001"),
        "voicemail-zero-001",
        ticket_id="ticket-zero-001",
    )
    zero = result.ticket.model_copy(update={"processing_ms": 0.0})
    store.complete(
        PipelineResult(zero, result.audio, result.text, result.voice_evidence, result.decision)
    )
    processing, _stages = store.latency_samples()
    assert 0.0 in processing


def test_assemble_ticket_derives_status_from_labels():
    result = run_pipeline(
        _make_meta("voicemail-asm-001"), "voicemail-asm-001", ticket_id="ticket-asm-001"
    )
    base = dict(
        ticket_id="ticket-asm-001",
        voicemail_id="voicemail-asm-001",
        audio=result.audio,
        voice_evidence=None,
        decision=result.decision,
        stage_status=dict(result.ticket.stage_status),
        stage_timing_ms=dict(result.ticket.stage_timing_ms),
        processing_ms=1.0,
    )
    # A null label means NEEDS_REVIEW, even though the text flag is set.
    text_null = result.text.model_copy(
        update={"complaint_category": None, "needs_human_review": True}
    )
    ticket = assemble_ticket(text=text_null, **base)
    assert ticket.ticket_status == TicketStatus.NEEDS_REVIEW
    assert ticket.needs_human_review is True
    assert ticket.complaint_category is None
    # All labels present means COMPLETED.
    ticket = assemble_ticket(text=result.text, **base)
    assert ticket.ticket_status == TicketStatus.COMPLETED
    assert ticket.needs_human_review is False


def test_assemble_ticket_rejects_mismatched_voicemail_ids():
    result = run_pipeline(
        _make_meta("voicemail-asm-002"), "voicemail-asm-002", ticket_id="ticket-asm-002"
    )
    audio_other = result.audio.model_copy(update={"voicemail_id": "voicemail-other"})
    with pytest.raises(ValueError, match="different voicemails"):
        assemble_ticket(
            ticket_id="ticket-asm-002",
            voicemail_id="voicemail-asm-002",
            audio=audio_other,
            text=result.text,
            voice_evidence=None,
            decision=result.decision,
            stage_status=dict(result.ticket.stage_status),
            stage_timing_ms=dict(result.ticket.stage_timing_ms),
            processing_ms=1.0,
        )


def test_assemble_ticket_refuses_failed_stage():
    result = run_pipeline(
        _make_meta("voicemail-asm-003"), "voicemail-asm-003", ticket_id="ticket-asm-003"
    )
    failed_status = dict(result.ticket.stage_status)
    failed_status["triage"] = "failed"
    with pytest.raises(ValueError, match="failed stages"):
        assemble_ticket(
            ticket_id="ticket-asm-003",
            voicemail_id="voicemail-asm-003",
            audio=result.audio,
            text=result.text,
            voice_evidence=None,
            decision=result.decision,
            stage_status=failed_status,
            stage_timing_ms=dict(result.ticket.stage_timing_ms),
            processing_ms=1.0,
        )
