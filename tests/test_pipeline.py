"""Pipeline tests: end-to-end mock run, null/review rules, latency."""

import io
import wave

from svr import fixtures
from svr.latency import p95, percentile, summarize_latency
from svr.pipeline import fixture_ticket, run_pipeline
from svr.stages.intake import AudioMeta, validate_and_measure


def make_wav_bytes(duration_s: float = 1.0, rate: int = 16000, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * channels * int(rate * duration_s))
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


def test_validate_and_measure_reads_wav_header_values():
    meta = validate_and_measure(
        make_wav_bytes(duration_s=1.0, rate=44100, channels=2),
        "stereo.wav",
        "voicemail-test-005e",
    )
    assert meta.duration_s == 1.0
    assert meta.sample_rate_hz == 44100
    assert meta.channels == 2
    assert meta.duration_checked is True


def test_validate_and_measure_leaves_mp3_values_null():
    meta = validate_and_measure(
        b"ID3" + b"\x00" * 100, "test.mp3", "voicemail-test-005f"
    )
    assert meta.duration_s is None
    assert meta.sample_rate_hz is None
    assert meta.channels is None
    assert meta.duration_checked is False


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


def _boom(*args, **kwargs):
    raise ValueError("forced stage failure for the test")


def test_voice_failure_goes_to_needs_review(monkeypatch):
    monkeypatch.setattr("svr.stages.voice.voice_evidence_mock", _boom)
    result = run_pipeline(make_meta("voicemail-test-006"), "voicemail-test-006")
    ticket = result.ticket
    assert ticket.ticket_status.value == "needs_review"
    assert ticket.needs_human_review is True
    assert ticket.stage_status["voice_evidence"] == "failed"
    assert "voice evidence failed" in ticket.route_reason.lower()


def test_triage_failure_goes_to_needs_review(monkeypatch):
    monkeypatch.setattr("svr.stages.triage.triage_mock", _boom)
    result = run_pipeline(make_meta("voicemail-test-007"), "voicemail-test-007")
    ticket = result.ticket
    assert ticket.ticket_status.value == "needs_review"
    assert ticket.needs_human_review is True
    assert ticket.stage_status["triage"] == "failed"
    assert "triage failed" in ticket.route_reason.lower()


def test_ticket_assembly_failure_goes_to_needs_review(monkeypatch):
    monkeypatch.setattr("svr.stages.ticket.assemble_ticket", _boom)
    result = run_pipeline(make_meta("voicemail-test-008"), "voicemail-test-008")
    ticket = result.ticket
    assert ticket.ticket_status.value == "needs_review"
    assert ticket.needs_human_review is True
    assert ticket.stage_status["ticket"] == "failed"
    assert "ticket assembly failed" in ticket.route_reason.lower()


def test_classification_override_rejects_forbidden_keys():
    """The override allowlist: only the four label fields may be injected.
    Forging voicemail_id or needs_human_review is rejected, and the forged
    value never lands in a ticket."""
    import pytest

    from svr.stages.classification import classify_mock
    from svr.stages.intake import validate_and_measure
    from svr.stages.stt import transcribe_mock

    audio = transcribe_mock(
        validate_and_measure(make_wav_bytes(), "test.wav", "voicemail-test-009")
    )
    with pytest.raises(ValueError, match="not allowed"):
        classify_mock(audio, override={"voicemail_id": "voicemail-forged"})
    with pytest.raises(ValueError, match="not allowed"):
        classify_mock(audio, override={"needs_human_review": False})
    with pytest.raises(ValueError, match="not allowed"):
        classify_mock(audio, override={"schema_version": 999})
    # The four label fields are still overridable.
    assert (
        classify_mock(audio, override={"complaint_category": None}).complaint_category
        is None
    )
    # Through the pipeline a forbidden key ends the run as needs_review,
    # with the forged value nowhere in the ticket.
    result = run_pipeline(
        make_meta("voicemail-test-009b"),
        "voicemail-test-009b",
        classification_override={"voicemail_id": "voicemail-forged"},
    )
    assert result.ticket.ticket_status.value == "needs_review"
    assert result.ticket.voicemail_id == "voicemail-test-009b"


def test_assign_agent_consumes_capacity_and_returns_none_when_full():
    """Assigning two tickets to the same agent increases its reported load,
    and when the agent is at capacity routing finds no eligible agent."""
    from svr import agents as agents_module
    from svr.schemas import ComplaintCategory

    category = ComplaintCategory.NETWORK_AND_CONNECTIVITY
    first = agents_module.assign_agent(category)
    second = agents_module.assign_agent(category)
    assert first is not None and first.id == "agent-demo-network"
    assert second is not None and second.id == "agent-demo-network"
    loads = {a.id: a.current_load for a in agents_module.list_agents()}
    assert loads["agent-demo-network"] == 3  # seeded 1 + two assignments
    # Fill it: two more assignments reach capacity 5.
    assert agents_module.assign_agent(category) is not None
    assert agents_module.assign_agent(category) is not None
    assert loads["agent-demo-network"] == 3  # list_agents copies, not live
    assert {a.id: a.current_load for a in agents_module.list_agents()}[
        "agent-demo-network"
    ] == 5
    # At capacity, and no other agent has the network skill: unassigned.
    assert agents_module.assign_agent(category) is None


def test_list_agents_returns_deep_copies():
    """Mutating an agent returned by list_agents never mutates the seed."""
    from svr import agents as agents_module

    listed = agents_module.list_agents()
    listed[0].current_load = 999
    listed[0].skills.clear()
    stored = agents_module.list_agents()[0]
    assert stored.current_load == 1
    assert len(stored.skills) == 2


def test_pipeline_run_consumes_and_complete_releases_capacity():
    """A routed run consumes one unit of the agent's capacity, and the
    unit is released when the run finishes and is stored."""
    from svr import agents as agents_module
    from svr.store import TicketStore

    def _load(agent_id: str) -> int:
        return {
            a.id: a.current_load for a in agents_module.list_agents()
        }[agent_id]

    assert _load("agent-demo-network") == 1
    result = run_pipeline(make_meta("voicemail-test-010"), "voicemail-test-010")
    assert result.decision is not None
    assert result.decision.assigned_agent_id == "agent-demo-network"
    assert _load("agent-demo-network") == 2
    TicketStore().complete(result)
    assert _load("agent-demo-network") == 1
