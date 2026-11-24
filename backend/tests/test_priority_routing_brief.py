"""Unit tests for deterministic priority formula, FR20 routing, and callback brief guardrails."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from svr_platform.models import Agent, Organization, ScriptTemplate, Ticket, Voicemail
from svr_platform.services.brief import build_callback_brief
from svr_platform.services.priority import compute_priority
from svr_platform.services.routing import (
    assign_ticket_to_agent,
    recommend_route,
    release_active_assignment,
)
from svr_platform.taxonomy import DEFAULT_SKILL_MAPPING


# All 12 combinations: 3 urgency x 2 churn x 2 state-point buckets (mad/frustrated=1 vs calm/satisfied/unclear=0)
@pytest.mark.parametrize(
    ("urgency", "churn", "state", "expected_score", "expected_bucket"),
    [
        ("high", "at_risk", "mad", 6, "urgent"),
        ("high", "at_risk", "calm", 5, "high"),
        ("high", "not_at_risk", "frustrated", 4, "normal"),
        ("high", "not_at_risk", "satisfied", 3, "normal"),
        ("medium", "at_risk", "frustrated", 5, "high"),
        ("medium", "at_risk", "calm", 4, "normal"),
        ("medium", "not_at_risk", "mad", 3, "normal"),
        ("medium", "not_at_risk", "unclear", 2, "low"),
        ("low", "at_risk", "mad", 4, "normal"),
        ("low", "at_risk", "satisfied", 3, "normal"),
        ("low", "not_at_risk", "frustrated", 2, "low"),
        ("low", "not_at_risk", "calm", 1, "low"),
    ],
)
def test_priority_all_12_combinations(urgency, churn, state, expected_score, expected_bucket):
    res = compute_priority(urgency, churn, state)
    assert res.priority_score == expected_score
    assert res.queue_priority == expected_bucket
    assert res.needs_human_review is False
    assert res.review_reason is None
    assert res.contributing_signals["total_score"] == expected_score
    assert res.contributing_signals["bucket"] == expected_bucket
    assert f"{expected_score}/6" in res.priority_reason


@pytest.mark.parametrize(
    ("urgency", "churn", "state", "missing_field"),
    [
        (None, "at_risk", "mad", "complaint_urgency"),
        ("high", None, "calm", "churn_risk"),
        ("low", "not_at_risk", None, "customer_state"),
        ("extreme", "not_at_risk", "calm", "complaint_urgency"),
        (None, None, None, "complaint_urgency"),
    ],
)
def test_priority_null_or_invalid_inputs_go_to_human_review(urgency, churn, state, missing_field):
    res = compute_priority(urgency, churn, state)
    assert res.priority_score is None
    assert res.queue_priority is None
    assert res.needs_human_review is True
    assert res.review_reason == "missing_label"
    assert missing_field in res.contributing_signals["missing_inputs"]


def test_fr20_skill_routing_covers_all_11_categories(db_manager):
    expected_agent_by_skill = {
        "Network": "Network Care Specialist",
        "Billing": "Billing & Bundles Specialist",
        "General": "Subscriber Care Specialist",
    }
    assert len(DEFAULT_SKILL_MAPPING) == 11

    with db_manager.session_factory() as db:
        org = db.scalar(select(Organization))
        assert org is not None
        for category, expected_skill in DEFAULT_SKILL_MAPPING.items():
            dec = recommend_route(
                db,
                organization_id=org.id,
                complaint_category=category,
                auto_routing_enabled=True,
            )
            assert dec.needs_human_review is False
            assert dec.required_skill == expected_skill
            assert dec.assigned_agent_name == expected_agent_by_skill[expected_skill]
            assert expected_skill in dec.route_reason


def test_routing_seed_order_and_capacity_exhaustion_and_release(db_manager):
    with db_manager.session_factory() as db:
        org = db.scalar(select(Organization))
        assert org is not None

        # Add a second Network agent with higher seed_order=50 (comes after seed_order=1)
        backup_net = Agent(
            organization_id=org.id,
            name="Backup Network Specialist",
            skills=["Network"],
            capacity=1,
            current_load=0,
            available=True,
            active=True,
            seed_order=50,
        )
        db.add(backup_net)
        db.flush()

        primary_net = db.scalar(
            select(Agent).where(Agent.organization_id == org.id, Agent.name == "Network Care Specialist")
        )
        assert primary_net is not None

        # Seed order selects primary first
        dec1 = recommend_route(db, organization_id=org.id, complaint_category="sim_services")
        assert dec1.assigned_agent_id == primary_net.id

        # Fill primary agent capacity -> spills over to backup agent
        primary_net.current_load = primary_net.capacity
        db.flush()
        dec2 = recommend_route(db, organization_id=org.id, complaint_category="sim_services")
        assert dec2.assigned_agent_id == backup_net.id

        # Create a ticket and assign to backup_net (capacity=1 -> now full)
        vm = Voicemail(
            organization_id=org.id,
            file_name="cap_test.wav",
            file_path="storage/voicemails/cap_test.wav.enc",
            format="wav",
            size_bytes=1024,
            duration_seconds=5.0,
            status="processing",
            idempotency_key="cap-test-key",
            content_sha256="a" * 64,
            encrypted=True,
            created_by="test",
        )
        db.add(vm)
        db.flush()
        ticket = Ticket(voicemail_id=vm.id, organization_id=org.id, status="processing")
        db.add(ticket)
        db.flush()

        assign_ticket_to_agent(
            db,
            ticket,
            backup_net.id,
            assigned_by="system",
            route_reason="Assigned to backup",
        )
        db.flush()
        assert backup_net.current_load == 1

        # All Network agents now at capacity -> UNASSIGNED
        dec3 = recommend_route(db, organization_id=org.id, complaint_category="sim_services")
        assert dec3.assigned_agent_id is None
        assert dec3.needs_human_review is True
        assert dec3.review_reason == "no_eligible_agent"
        assert "UNASSIGNED" in dec3.route_reason

        # Releasing active assignment frees capacity and restores eligibility
        release_active_assignment(db, ticket, final_status="completed")
        db.flush()
        assert backup_net.current_load == 0
        dec4 = recommend_route(db, organization_id=org.id, complaint_category="sim_services")
        assert dec4.assigned_agent_id == backup_net.id


def test_routing_kill_switch_sends_all_tickets_to_human_review(db_manager):
    with db_manager.session_factory() as db:
        org = db.scalar(select(Organization))
        assert org is not None
        dec = recommend_route(
            db,
            organization_id=org.id,
            complaint_category="billing_and_charges",
            auto_routing_enabled=False,
        )
        assert dec.assigned_agent_id is None
        assert dec.needs_human_review is True
        assert dec.review_reason == "kill_switch_active"
        assert "kill switch" in dec.route_reason.lower()


def test_callback_brief_truncation_and_s3_placeholder_guardrail(db_manager):
    with db_manager.session_factory() as db:
        org = db.scalar(select(Organization))
        assert org is not None

        long_transcript = "الشبكة عندي فيها مشكلة كبيرة جدا في البيت " * 15
        assert len(long_transcript) > 200
        brief = build_callback_brief(
            db,
            organization_id=org.id,
            transcript=long_transcript,
            complaint_category="network_and_connectivity",
        )
        assert brief.flagged is False
        assert len(brief.summary) == 200
        assert brief.summary == long_transcript.strip()[:200]
        assert brief.customer_request != ""
        assert brief.suggested_script != ""

        # Missing category flags brief
        missing_brief = build_callback_brief(
            db,
            organization_id=org.id,
            transcript="مرحبا",
            complaint_category=None,
        )
        assert missing_brief.flagged is True
        assert missing_brief.suggested_script == ""

        # S3 guardrail blocks any unexpanded placeholder in a category template
        tpl = db.scalar(
            select(ScriptTemplate).where(
                ScriptTemplate.organization_id == org.id,
                ScriptTemplate.category == "billing_and_charges",
            )
        )
        assert tpl is not None
        tpl.template_ar = "أهلا يا {customer_name}، فاتورتك {amount} جنيه."
        db.commit()

        blocked = build_callback_brief(
            db,
            organization_id=org.id,
            transcript="عندي مشكلة في الفاتورة",
            complaint_category="billing_and_charges",
        )
        assert blocked.flagged is True
        assert blocked.flag_reason == "ungrounded_script_blocked"
        assert blocked.suggested_script == ""
