"""Pipeline tests: end-to-end mock run, null/review rules, latency."""

import io
import wave

from svr import fixtures
from svr.latency import p95, percentile, summarize_latency
from svr.pipeline import fixture_ticket, run_pipeline
from svr.stages.intake import AudioMeta, validate_and_measure


def make_wav_bytes(duration_s: float = 1.0, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * int(rate * duration_s))
    return buf.getvalue()


def make_meta(
    voicemail_id: str,
    filename: str = "test.wav",
    size_bytes: int = 32044,
    duration_s: float | None = 1.0,
    duration_checked: bool = True,
) -> AudioMeta:
    """Valid upload metadata: 1 s, 16 kHz mono 16-bit WAV (32044 bytes)."""
    return AudioMeta(
        voicemail_id=voicemail_id,
        filename=filename,
        format="wav",
        size_bytes=size_bytes,
        duration_s=duration_s,
        duration_checked=duration_checked,
    )


def test_end_to_end_mock_pipeline_matches_fixture_shape():
    result = run_pipeline(make_meta("voicemail-test-001"), "voicemail-test-001")
    ticket = result.ticket
    assert ticket.ticket_status.value == "completed"
    assert ticket.assignment_status.value == "assigned"
    assert ticket.complaint_category.value == "network_and_connectivity"
    assert ticket.complaint_urgency.value == "medium"
    assert ticket.customer_state_text.value == "frustrated"
    assert ticket.churn_risk.value == "not_at_risk"
    assert ticket.customer_state_final is None  # fusion disabled
    assert ticket.voice_state_candidate is None  # voice stage skipped
    assert ticket.priority_score is None  # formula OPEN
    assert ticket.needs_human_review is False
    assert ticket.cached is False
    assert ticket.schema_version == 1
    assert ticket.label_version == "taxonomy-2026-11-11"
    assert ticket.transcript == fixtures.FIXTURE_TRANSCRIPT
    assert ticket.route_reason == fixtures.FIXTURE_ROUTE_REASON
    assert result.decision is not None
    assert result.decision.assigned_agent_id == "agent-demo-network"
    assert result.text is not None
    assert result.audio is not None
    assert result.voice_evidence is None


def test_stage_status_and_timings_present_on_every_ticket():
    result = run_pipeline(make_meta("voicemail-test-002"), "voicemail-test-002")
    ticket = result.ticket
    assert ticket.stage_status == {
        "intake": "ok",
        "stt": "ok",
        "text_analysis": "ok",
        "voice_evidence": "skipped",
        "triage": "ok",
    }
    for stage in ("intake", "stt", "text_analysis", "voice_evidence", "triage"):
        assert stage in ticket.stage_timing_ms
        assert ticket.stage_timing_ms[stage] >= 0
    assert ticket.processing_ms > 0
    assert ticket.processing_ms < 10_000  # p95 target, mock run is far under


def test_null_category_goes_to_needs_review_not_a_guess():
    result = run_pipeline(
        make_meta("voicemail-test-003"),
        "voicemail-test-003",
        classification_override={"complaint_category": None},
    )
    ticket = result.ticket
    assert ticket.ticket_status.value == "needs_review"
    assert ticket.needs_human_review is True
    assert ticket.complaint_category is None


def test_out_of_enum_label_goes_to_needs_review():
    result = run_pipeline(
        make_meta("voicemail-test-004"),
        "voicemail-test-004",
        classification_override={"complaint_category": "offers_and_packages"},
    )
    ticket = result.ticket
    assert ticket.ticket_status.value == "needs_review"
    assert ticket.needs_human_review is True
    assert "validation" in ticket.route_reason.lower()


def test_invalid_upload_goes_to_needs_review():
    bad_meta = AudioMeta(
        voicemail_id="voicemail-test-005",
        filename="test.txt",
        format="txt",
        size_bytes=15,
        duration_s=None,
        duration_checked=False,
    )
    result = run_pipeline(bad_meta, "voicemail-test-005")
    ticket = result.ticket
    assert ticket.ticket_status.value == "needs_review"
    assert ticket.needs_human_review is True


def test_metadata_only_intake_rejects_oversize_and_overlong():
    too_big = run_pipeline(
        make_meta("voicemail-test-005b", size_bytes=25 * 1024 * 1024 + 1),
        "voicemail-test-005b",
    )
    assert too_big.ticket.ticket_status.value == "needs_review"
    assert too_big.ticket.stage_status["intake"] == "failed"
    too_long = run_pipeline(
        make_meta("voicemail-test-005c", size_bytes=32044 * 61, duration_s=61.0),
        "voicemail-test-005c",
    )
    assert too_long.ticket.ticket_status.value == "needs_review"
    assert too_long.ticket.stage_status["intake"] == "failed"


def test_validate_and_measure_still_measures_wav_duration():
    meta = validate_and_measure(make_wav_bytes(), "test.wav", "voicemail-test-005d")
    assert meta.duration_s == 1.0
    assert meta.duration_checked is True
    assert meta.size_bytes == 32044
    assert meta.format == "wav"


def test_p95_helper():
    assert p95([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]) == 10
    assert p95([5]) == 5
    assert p95([]) is None
    assert percentile([10, 20, 30, 40], 50.0) == 20


def test_latency_summary_reports_hardware_and_slowest_stage():
    report = summarize_latency(
        [100.0, 200.0, 150.0],
        [
            {"intake": 10, "stt": 80, "text_analysis": 5, "voice_evidence": 0, "triage": 5},
            {"intake": 12, "stt": 90, "text_analysis": 6, "voice_evidence": 0, "triage": 4},
            {"intake": 11, "stt": 85, "text_analysis": 5, "voice_evidence": 0, "triage": 5},
        ],
    )
    assert report["runs"] == 3
    assert report["within_target"] is True
    assert report["slowest_stage"] == "stt"
    assert report["hardware"]["cpu_count"] is not None
    assert report["hardware"]["python"]


def test_fixture_ticket_helper():
    assert fixture_ticket().id == fixtures.FIXTURE_TICKET_ID
