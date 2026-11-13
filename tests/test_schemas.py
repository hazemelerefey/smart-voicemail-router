"""Schema tests: contracts v1.0 enums, null rules, fusion disabled."""

import pytest
from pydantic import ValidationError

from svr import fixtures
from svr.schemas import (
    Agent,
    AudioEvidence,
    ComplaintCategory,
    ComplaintUrgency,
    CustomerState,
    ChurnRisk,
    TextAnalysis,
    Ticket,
    TriageDecision,
    VoiceEvidence,
)


def _audio_payload(**overrides) -> dict:
    payload = {
        "voicemail_id": "voicemail-test-001",
        "audio_path_local": None,
        "duration_s": 1.0,
        "format": "wav",
        "sample_rate_hz": 16000,
        "channels": 1,
        "transcript": "[fixture transcript]",
        "stt_provider": "mock",
        "stt_model_version": "mock-stt-0.1",
        "stt_confidence": None,
        "language_mix": None,
        "audio_quality": {},
        "schema_version": 1,
        "label_version": "taxonomy-2026-11-11",
    }
    payload.update(overrides)
    return payload


def _decision_payload(**overrides) -> dict:
    payload = {
        "voicemail_id": "voicemail-test-001",
        "priority_score": None,
        "queue_priority": None,
        "assigned_agent_id": None,
        "assignment_status": "assigned",
        "route_reason": "fixture reason",
        "contributing_signals": [],
        "config_version": "mock-triage-0.1",
        "evaluation": None,
        "schema_version": 1,
        "label_version": "taxonomy-2026-11-11",
    }
    payload.update(overrides)
    return payload


def test_enum_counts_match_contracts_section_2():
    assert len(ComplaintCategory) == 10
    assert len(ComplaintUrgency) == 3
    assert len(CustomerState) == 5
    assert len(ChurnRisk) == 2
    # Membership, not just counts: the exact approved value sets.
    assert {c.value for c in ComplaintCategory} == {
        "network_and_connectivity",
        "billing_and_charges",
        "balance_and_data",
        "app_and_account",
        "branch_and_staff",
        "no_reply_or_long_wait",
        "cancellation_request",
        "thanks_or_praise",
        "greeting_only",
        "other",
    }
    assert {u.value for u in ComplaintUrgency} == {"high", "medium", "low"}
    assert {s.value for s in CustomerState} == {
        "calm",
        "frustrated",
        "mad",
        "satisfied",
        "unclear",
    }
    assert {c.value for c in ChurnRisk} == {"at_risk", "not_at_risk"}


def test_fixture_ticket_validates():
    ticket = Ticket.model_validate(fixtures.FIXTURE_TICKET)
    assert ticket.schema_version == 1
    assert ticket.label_version == "taxonomy-2026-11-11"
    assert ticket.complaint_category == ComplaintCategory.NETWORK_AND_CONNECTIVITY
    assert ticket.complaint_urgency == ComplaintUrgency.MEDIUM
    assert ticket.customer_state_text == CustomerState.FRUSTRATED
    assert ticket.churn_risk == ChurnRisk.NOT_AT_RISK
    assert ticket.customer_state_final is None  # fusion disabled
    assert ticket.cached is False


def test_out_of_enum_category_is_rejected():
    payload = dict(fixtures.FIXTURE_TEXT_ANALYSIS)
    payload["complaint_category"] = "offers_and_packages"  # NOT an approved value
    with pytest.raises(ValidationError):
        TextAnalysis.model_validate(payload)


def test_out_of_enum_state_is_rejected():
    payload = dict(fixtures.FIXTURE_TEXT_ANALYSIS)
    payload["customer_state_text"] = "furious"  # NOT an approved value
    with pytest.raises(ValidationError):
        TextAnalysis.model_validate(payload)


def test_null_label_is_valid_not_a_guess():
    """Null + needs_human_review is a correct output (section 4, rule 1)."""
    payload = dict(fixtures.FIXTURE_TEXT_ANALYSIS)
    payload["complaint_category"] = None
    payload["needs_human_review"] = True
    analysis = TextAnalysis.model_validate(payload)
    assert analysis.complaint_category is None
    assert analysis.needs_human_review is True


def test_fusion_field_must_stay_null():
    """customer_state_final must stay null until fusion rules are agreed."""
    payload = dict(fixtures.FIXTURE_TICKET)
    payload["customer_state_final"] = "frustrated"
    with pytest.raises(ValidationError, match="fusion is disabled"):
        Ticket.model_validate(payload)


def test_language_mix_null_until_values_agreed():
    payload = dict(fixtures.FIXTURE_TEXT_ANALYSIS)
    assert payload["language_mix"] is None
    analysis = TextAnalysis.model_validate(payload)
    assert analysis.language_mix is None
    # A non-null mix is rejected until Hazem defines the approved list.
    payload["language_mix"] = "arabic-english"
    with pytest.raises(ValidationError, match="language_mix"):
        TextAnalysis.model_validate(payload)
    with pytest.raises(ValidationError, match="language_mix"):
        AudioEvidence.model_validate(_audio_payload(language_mix="arabic"))


def test_null_label_with_review_off_is_rejected():
    """The null/review rule is enforced by schema validation itself: a
    null label with needs_human_review False is rejected, never stored."""
    payload = dict(fixtures.FIXTURE_TEXT_ANALYSIS)
    payload["complaint_category"] = None
    payload["needs_human_review"] = False
    with pytest.raises(ValidationError, match="null label"):
        TextAnalysis.model_validate(payload)
    ticket_payload = dict(fixtures.FIXTURE_TICKET)
    ticket_payload["complaint_urgency"] = None
    ticket_payload["needs_human_review"] = False
    with pytest.raises(ValidationError, match="null label"):
        Ticket.model_validate(ticket_payload)


def test_wrong_version_is_rejected():
    payload = dict(fixtures.FIXTURE_TEXT_ANALYSIS)
    payload["schema_version"] = 999
    with pytest.raises(ValidationError):
        TextAnalysis.model_validate(payload)
    payload["schema_version"] = 1
    payload["label_version"] = "anything"
    with pytest.raises(ValidationError):
        TextAnalysis.model_validate(payload)
    ticket_payload = dict(fixtures.FIXTURE_TICKET)
    ticket_payload["label_version"] = "taxonomy-2099-01-01"
    with pytest.raises(ValidationError):
        Ticket.model_validate(ticket_payload)


def test_unknown_field_is_rejected():
    """extra=forbid: a misspelled or unknown field is rejected instead of
    being silently dropped (and silently nulling a label)."""
    payload = dict(fixtures.FIXTURE_TEXT_ANALYSIS)
    payload["complaint_categoy"] = "network_and_connectivity"
    with pytest.raises(ValidationError):
        TextAnalysis.model_validate(payload)
    ticket_payload = dict(fixtures.FIXTURE_TICKET)
    ticket_payload["bogus_field"] = "x"
    with pytest.raises(ValidationError):
        Ticket.model_validate(ticket_payload)


def test_impossible_audio_is_rejected():
    with pytest.raises(ValidationError):
        AudioEvidence.model_validate(_audio_payload(duration_s=-1.0))
    with pytest.raises(ValidationError):
        AudioEvidence.model_validate(_audio_payload(format="ogg"))
    with pytest.raises(ValidationError):
        AudioEvidence.model_validate(_audio_payload(sample_rate_hz=0))
    with pytest.raises(ValidationError):
        AudioEvidence.model_validate(_audio_payload(channels=-1))
    # Measured values still pass.
    assert AudioEvidence.model_validate(_audio_payload()).duration_s == 1.0


def test_audio_path_local_must_live_under_uploads():
    assert (
        AudioEvidence.model_validate(_audio_payload(audio_path_local=None)).audio_path_local
        is None
    )
    assert (
        AudioEvidence.model_validate(
            _audio_payload(audio_path_local="uploads/voicemail-001.wav")
        ).audio_path_local
        == "uploads/voicemail-001.wav"
    )
    with pytest.raises(ValidationError):
        AudioEvidence.model_validate(_audio_payload(audio_path_local="/etc/passwd"))
    with pytest.raises(ValidationError):
        AudioEvidence.model_validate(
            _audio_payload(audio_path_local="uploads/../../etc/passwd")
        )


def test_every_contract_object_carries_label_version():
    assert AudioEvidence.model_validate(_audio_payload()).label_version == (
        "taxonomy-2026-11-11"
    )
    assert (
        TextAnalysis.model_validate(fixtures.FIXTURE_TEXT_ANALYSIS).label_version
        == "taxonomy-2026-11-11"
    )
    voice = VoiceEvidence.model_validate(
        {
            "voicemail_id": "voicemail-test-001",
            "model_version": "mock-voice-0.1",
        }
    )
    assert voice.label_version == "taxonomy-2026-11-11"
    decision = TriageDecision.model_validate(_decision_payload())
    assert decision.label_version == "taxonomy-2026-11-11"
    assert Ticket.model_validate(fixtures.FIXTURE_TICKET).label_version == (
        "taxonomy-2026-11-11"
    )


def test_queue_priority_is_constrained():
    decision = TriageDecision.model_validate(_decision_payload(queue_priority="high"))
    assert decision.queue_priority.value == "high"
    with pytest.raises(ValidationError):
        TriageDecision.model_validate(_decision_payload(queue_priority="banana"))


def test_agent_capacity_and_load_bounds():
    base = {
        "id": "agent-test-001",
        "name": "Test Agent",
        "skills": ["network_and_connectivity"],
        "tier": "L1",
        "capacity": 5,
        "current_load": 1,
        "on_shift": True,
        "languages": ["Arabic"],
    }
    assert Agent.model_validate(base).current_load == 1
    with pytest.raises(ValidationError):
        Agent.model_validate({**base, "current_load": 6})
    with pytest.raises(ValidationError):
        Agent.model_validate({**base, "capacity": -1})
    with pytest.raises(ValidationError):
        Agent.model_validate({**base, "skills": "network_and_connectivity"})
