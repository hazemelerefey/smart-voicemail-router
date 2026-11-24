"""Pipeline tests: end-to-end mock run, null/review rules, latency."""

import pytest
from pydantic import ValidationError

from conftest import make_wav_bytes
from svr import fixtures
from svr.latency import Timer, p95, percentile, summarize_latency
from svr.pipeline import fixture_ticket, run_pipeline
from svr.stages.intake import AudioMeta, validate_and_measure, validate_metadata


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


def test_end_to_end_pipeline_preserves_contract_and_routes():
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
    assert ticket.priority_score == 3.0
    assert ticket.needs_human_review is False
    assert ticket.cached is False
    assert ticket.schema_version == 1
    assert ticket.label_version == "taxonomy-2026-11-15"
    assert ticket.transcript == fixtures.FIXTURE_TRANSCRIPT
    assert "agent-demo-network" in ticket.route_reason
    assert "network_and_connectivity" in ticket.route_reason
    assert "Priority calculation: 2 + 0 + 1 = 3" in ticket.route_reason
    assert "queue_priority=normal" in ticket.route_reason
    assert result.decision is not None
    assert result.decision.priority_score == 3.0
    assert result.decision.queue_priority.value == "normal"
    assert result.decision.label_version == "taxonomy-2026-11-15"
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
    assert ticket.priority_score == 3.0
    assert result.decision is not None
    assert result.decision.queue_priority.value == "normal"


@pytest.mark.parametrize(
    ("category", "expected_agent"),
    [
        ("offers_and_packages", "agent-demo-billing"),
        ("sim_services", "agent-demo-network"),
    ],
)
def test_new_categories_route_to_the_approved_demo_agents(category, expected_agent):
    from svr import agents as agents_module

    loads_before = {a.id: a.current_load for a in agents_module.list_agents()}
    result = None
    try:
        result = run_pipeline(
            make_meta(f"voicemail-{category}"),
            f"voicemail-{category}",
            classification_override={"complaint_category": category},
        )
        assert result.ticket.complaint_category.value == category
        assert result.ticket.label_version == "taxonomy-2026-11-15"
        assert result.ticket.assignment_status.value == "assigned"
        assert result.ticket.ticket_status.value == "completed"
        assert result.ticket.needs_human_review is False
        assert result.decision is not None
        assert result.decision.assignment_status.value == "assigned"
        assert result.decision.assigned_agent_id == expected_agent
        assert result.decision.label_version == "taxonomy-2026-11-15"
        assert result.decision.priority_score == 3.0
        assert result.decision.queue_priority.value == "normal"
        assert category in result.decision.route_reason
        assert "listed skill matches" in result.decision.route_reason
        loads_during_run = {
            a.id: a.current_load for a in agents_module.list_agents()
        }
        assert loads_during_run[expected_agent] == loads_before[expected_agent] + 1
    finally:
        if result is not None and result.decision is not None:
            if result.decision.assigned_agent_id is not None:
                agents_module.release(result.decision.assigned_agent_id)
    assert {a.id: a.current_load for a in agents_module.list_agents()} == loads_before


@pytest.mark.parametrize(
    ("urgency", "urgency_points"),
    [("high", 3), ("medium", 2), ("low", 1)],
)
@pytest.mark.parametrize(
    ("churn", "churn_points"), [("at_risk", 2), ("not_at_risk", 0)]
)
@pytest.mark.parametrize(
    ("state", "state_points"),
    [
        ("calm", 0),
        ("frustrated", 1),
        ("mad", 1),
        ("satisfied", 0),
        ("unclear", 0),
    ],
)
def test_approved_priority_formula_for_every_complete_signal(
    urgency, urgency_points, churn, churn_points, state, state_points
):
    expected_score = urgency_points + churn_points + state_points
    expected_bucket = {
        1: "low",
        2: "low",
        3: "normal",
        4: "normal",
        5: "high",
        6: "urgent",
    }[expected_score]
    result = run_pipeline(
        make_meta(f"priority-{urgency}-{churn}-{state}"),
        f"priority-{urgency}-{churn}-{state}",
        classification_override={
            "complaint_urgency": urgency,
            "churn_risk": churn,
            "customer_state_text": state,
        },
    )
    assert result.ticket.ticket_status.value == "completed"
    assert result.ticket.needs_human_review is False
    assert result.ticket.priority_score == expected_score
    assert result.decision is not None
    assert result.decision.priority_score == expected_score
    assert result.decision.queue_priority.value == expected_bucket
    assert f"priority_score={expected_score}" in result.decision.contributing_signals
    assert f"queue_priority={expected_bucket}" in result.decision.contributing_signals


@pytest.mark.parametrize(
    "missing_fields",
    [
        ("complaint_urgency",),
        ("churn_risk",),
        ("customer_state_text",),
        ("complaint_urgency", "churn_risk"),
        ("complaint_urgency", "customer_state_text"),
        ("churn_risk", "customer_state_text"),
        ("complaint_urgency", "churn_risk", "customer_state_text"),
    ],
)
def test_missing_priority_input_keeps_priority_null_and_requires_review(
    missing_fields,
):
    missing = [
        field
        for field in ("complaint_urgency", "churn_risk", "customer_state_text")
        if field in missing_fields
    ]
    result = run_pipeline(
        make_meta(f"missing-priority-{len(missing)}"),
        f"missing-priority-{len(missing)}",
        classification_override={field: None for field in missing},
    )
    assert result.ticket.ticket_status.value == "needs_review"
    assert result.ticket.needs_human_review is True
    assert result.ticket.priority_score is None
    assert result.decision is not None
    assert result.decision.priority_score is None
    assert result.decision.queue_priority is None
    assert result.decision.assigned_agent_id == "agent-demo-network"
    assert f"priority_missing={','.join(missing)}" in result.decision.contributing_signals
    assert "Priority inputs missing: " + ", ".join(missing) in result.decision.route_reason
    assert "approved missing-input policy" in result.decision.route_reason


def test_triage_revalidates_mutated_text_before_reserving():
    from svr import agents as agents_module
    from svr.schemas import TextAnalysis
    from svr.stages.triage import triage_phase1

    text = TextAnalysis.model_validate(fixtures.FIXTURE_TEXT_ANALYSIS).model_copy(
        update={"complaint_category": "not-a-category"}
    )
    loads_before = {a.id: a.current_load for a in agents_module.list_agents()}
    with pytest.warns(UserWarning, match="Pydantic serializer warnings"):
        with pytest.raises(ValidationError):
            triage_phase1(text)
    assert {a.id: a.current_load for a in agents_module.list_agents()} == loads_before


def test_triage_rejects_mismatched_voice_before_reserving():
    from svr import agents as agents_module
    from svr.schemas import TextAnalysis, VoiceEvidence
    from svr.stages.triage import triage_phase1

    text = TextAnalysis.model_validate(fixtures.FIXTURE_TEXT_ANALYSIS)
    voice_evidence = VoiceEvidence(
        voicemail_id="voicemail-other", model_version="synthetic-voice-0.1"
    )
    loads_before = {a.id: a.current_load for a in agents_module.list_agents()}
    with pytest.raises(ValueError, match="same voicemail"):
        triage_phase1(text, voice_evidence)
    assert {a.id: a.current_load for a in agents_module.list_agents()} == loads_before


def test_triage_releases_reservation_if_decision_construction_fails(monkeypatch):
    from svr import agents as agents_module
    from svr.schemas import TextAnalysis
    import svr.stages.triage as triage_module

    text = TextAnalysis.model_validate(fixtures.FIXTURE_TEXT_ANALYSIS)
    loads_before = {a.id: a.current_load for a in agents_module.list_agents()}

    def _boom(*args, **kwargs):
        raise RuntimeError("forced decision construction failure")

    monkeypatch.setattr(triage_module, "TriageDecision", _boom)
    with pytest.raises(RuntimeError, match="decision construction failure"):
        triage_module.triage_phase1(text)
    assert {a.id: a.current_load for a in agents_module.list_agents()} == loads_before


def test_out_of_enum_label_goes_to_needs_review():
    result = run_pipeline(
        make_meta("voicemail-test-004"),
        "voicemail-test-004",
        classification_override={"complaint_category": "greeting_only"},
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


def test_validate_metadata_boundaries():
    """Boundary values: exactly 25 MiB and exactly 60.0 s pass; one byte
    or a tenth of a second over rejects."""
    assert (
        validate_metadata("test.wav", 25 * 1024 * 1024, 60.0, True, "voicemail-b-001").size_bytes
        == 25 * 1024 * 1024
    )
    with pytest.raises(ValueError, match="25 MB"):
        validate_metadata("test.wav", 25 * 1024 * 1024 + 1, None, False, "voicemail-b-002")
    with pytest.raises(ValueError, match="60 second"):
        validate_metadata("test.wav", 100, 60.1, True, "voicemail-b-003")


def test_audio_meta_rejects_bad_voicemail_id():
    """voicemail_id shape: no slashes, no whitespace, at most 64 chars."""
    with pytest.raises(ValueError, match="voicemail_id"):
        AudioMeta(
            voicemail_id="voicemail/bad id",
            filename="test.wav",
            format="wav",
            size_bytes=100,
            duration_s=1.0,
            duration_checked=True,
        )
    with pytest.raises(ValueError, match="voicemail_id"):
        AudioMeta(
            voicemail_id="x" * 65,
            filename="test.wav",
            format="wav",
            size_bytes=100,
            duration_s=1.0,
            duration_checked=True,
        )


def test_timer_stage_freezes_elapsed_on_exit():
    """Timer.stage records the name and freezes the elapsed value when the
    block exits: calling it later never inflates the stage time."""
    import time

    timer = Timer()
    with timer.stage("intake") as elapsed:
        time.sleep(0.01)
    first = elapsed()
    assert first >= 10
    time.sleep(0.02)
    assert elapsed() == first
    assert timer.stage_timings["intake"] == first


def test_percentile_rejects_out_of_range():
    with pytest.raises(ValueError):
        percentile([1, 2, 3], 101.0)
    with pytest.raises(ValueError):
        percentile([1, 2, 3], -1.0)
    assert percentile([10, 20, 30, 40], 50.0) == 20


def test_summarize_latency_rejects_mismatched_inputs():
    with pytest.raises(ValueError, match="same length"):
        summarize_latency([100.0], [{"intake": 10}, {"intake": 12}])
    report = summarize_latency([], [])
    assert report["runs"] == 0
    assert report["p95_processing_ms"] is None
    assert report["within_target"] is None
    assert report["slowest_stage"] is None


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
    monkeypatch.setattr("svr.stages.triage.triage_phase1", _boom)
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
    assert len(stored.skills) == 3


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


def test_manual_retry_after_ticket_failure_does_not_leak_capacity(monkeypatch):
    """A failed assembly is stored for review and releases its assignment;
    a later rerun can use capacity without accumulating a leaked load."""
    from svr import agents as agents_module
    from svr.stages import ticket as ticket_stage
    from svr.store import TicketStore

    store = TicketStore()
    voicemail_id = "voicemail-retry-cleanup"
    failed_ticket_id = "ticket-retry-failed"
    original_assemble = ticket_stage.assemble_ticket
    monkeypatch.setattr("svr.stages.ticket.assemble_ticket", _boom)

    failed = run_pipeline(
        make_meta(voicemail_id), voicemail_id, ticket_id=failed_ticket_id
    )
    assert failed.ticket.ticket_status.value == "needs_review"
    assert failed.decision is not None
    assert failed.decision.assigned_agent_id == "agent-demo-network"
    assert agents_module.get_agent("agent-demo-network").current_load == 2

    store.create_placeholder(failed_ticket_id, voicemail_id)
    store.complete(failed)
    assert agents_module.get_agent("agent-demo-network").current_load == 1

    monkeypatch.setattr("svr.stages.ticket.assemble_ticket", original_assemble)
    retry = run_pipeline(
        make_meta(voicemail_id), voicemail_id, ticket_id="ticket-retry-success"
    )
    assert retry.ticket.ticket_status.value == "completed"
    assert agents_module.get_agent("agent-demo-network").current_load == 2
    store.create_placeholder("ticket-retry-success", voicemail_id)
    store.complete(retry)
    assert agents_module.get_agent("agent-demo-network").current_load == 1
