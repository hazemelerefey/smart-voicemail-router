"""Seeded demo agents (contracts section 3.6).

Fictional demo agents ONLY. No real people, no real names, no real
availability. Routing uses only the skills listed here and says so in
``route_reason`` until the skill-to-category mapping and tier policy are
agreed (contracts section 10).
"""

from __future__ import annotations

from .schemas import Agent, ComplaintCategory

SEEDED_AGENTS: list[Agent] = [
    Agent(
        id="agent-demo-network",
        name="Demo Agent - Network",
        skills=[
            ComplaintCategory.NETWORK_AND_CONNECTIVITY,
            ComplaintCategory.NO_REPLY_OR_LONG_WAIT,
        ],
        tier="L1",
        capacity=5,
        current_load=1,
        on_shift=True,
        languages=["Arabic", "English"],
    ),
    Agent(
        id="agent-demo-billing",
        name="Demo Agent - Billing",
        skills=[
            ComplaintCategory.BILLING_AND_CHARGES,
            ComplaintCategory.BALANCE_AND_DATA,
        ],
        tier="L1",
        capacity=5,
        current_load=2,
        on_shift=True,
        languages=["Arabic", "English"],
    ),
    Agent(
        id="agent-demo-general",
        name="Demo Agent - General",
        skills=[
            ComplaintCategory.APP_AND_ACCOUNT,
            ComplaintCategory.BRANCH_AND_STAFF,
            ComplaintCategory.CANCELLATION_REQUEST,
            ComplaintCategory.THANKS_OR_PRAISE,
            ComplaintCategory.GREETING_ONLY,
            ComplaintCategory.OTHER,
        ],
        tier="L2",
        capacity=3,
        current_load=0,
        on_shift=True,
        languages=["Arabic", "English"],
    ),
]


def list_agents() -> list[Agent]:
    """All seeded demo agents."""
    return list(SEEDED_AGENTS)


def find_eligible_agent(category: ComplaintCategory) -> Agent | None:
    """First seeded agent approved for the category, on shift, with capacity."""
    for agent in SEEDED_AGENTS:
        if (
            category in agent.skills
            and agent.on_shift
            and agent.current_load < agent.capacity
        ):
            return agent
    return None


def get_agent(agent_id: str) -> Agent | None:
    """Seeded agent by id, or None."""
    for agent in SEEDED_AGENTS:
        if agent.id == agent_id:
            return agent
    return None
