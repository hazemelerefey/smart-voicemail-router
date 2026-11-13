"""Schema tests: contracts v1.0 enums, null rules, fusion disabled."""

import pytest
from pydantic import ValidationError

from svr import fixtures
from svr.schemas import (
    ComplaintCategory,
    ComplaintUrgency,
    CustomerState,
    ChurnRisk,
    TextAnalysis,
    Ticket,
)


def test_enum_counts_match_contracts_section_2():
    assert len(ComplaintCategory) == 10
    assert len(ComplaintUrgency) == 3
    assert len(CustomerState) == 5
    assert len(ChurnRisk) == 2


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
