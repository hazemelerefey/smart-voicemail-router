"""Stage 5: triage and routing (owner: Ibthal, mock in Phase 1).

Phase 1 mock: fixed route reason from the contracts section 9 fixture and
assignment to the first seeded demo agent whose approved skill matches the
complaint category, who is on shift, and who has capacity. If no eligible
agent exists the ticket stays ``unassigned`` with the reason, it does not
pick an unqualified agent (contracts section 3.4).

``priority_score`` stays null: the priority formula and weights are OPEN
(contracts section 10), owned by Ibthal, approved by Hazem.
"""

from __future__ import annotations

from .. import fixtures
from ..agents import assign_agent
from ..schemas import AssignmentStatus, TextAnalysis, TriageDecision, VoiceEvidence

MOCK_TRIAGE_CONFIG_VERSION = "mock-triage-0.1"


def triage_mock(
    text: TextAnalysis, voice_evidence: VoiceEvidence | None
) -> TriageDecision:
    """Mock triage: fixture route reason, seeded-agent assignment.

    Assignment consumes one unit of the chosen agent's capacity
    (``assign_agent``); the unit is released when the run finishes or the
    ticket is reassigned (see ``agents``).
    """
    agent = None
    if text.complaint_category is not None:
        agent = assign_agent(text.complaint_category)
    if agent is not None:
        assignment_status = AssignmentStatus.ASSIGNED
        assigned_agent_id: str | None = agent.id
        route_reason = fixtures.FIXTURE_ROUTE_REASON
    else:
        assignment_status = AssignmentStatus.UNASSIGNED
        assigned_agent_id = None
        route_reason = (
            "No eligible agent is on shift with capacity for this complaint "
            "category, so the ticket stays unassigned for human routing."
        )
    signals = []
    if text.complaint_category is not None:
        signals.append(f"complaint_category={text.complaint_category.value}")
    if text.complaint_urgency is not None:
        signals.append(f"complaint_urgency={text.complaint_urgency.value}")
    if text.churn_risk is not None:
        signals.append(f"churn_risk={text.churn_risk.value}")
    return TriageDecision(
        voicemail_id=text.voicemail_id,
        priority_score=None,  # formula OPEN, contracts section 10
        queue_priority=None,
        assigned_agent_id=assigned_agent_id,
        assignment_status=assignment_status,
        route_reason=route_reason,
        contributing_signals=signals,
        config_version=MOCK_TRIAGE_CONFIG_VERSION,
        evaluation=None,
    )
