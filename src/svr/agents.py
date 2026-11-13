"""Seeded demo agents (contracts section 3.6).

Fictional demo agents ONLY. No real people, no real names, no real
availability. Routing uses only the skills listed here and says so in
``route_reason`` until the skill-to-category mapping and tier policy are
agreed (contracts section 10).

Capacity is concurrent load (issue #6): assigning a run to an agent
consumes one unit of its capacity, and the unit is released when the run
finishes (``store.complete``) or the ticket is reassigned / unassigned.
The check is real: an agent at capacity is skipped by routing. Loads are
per-process; restarting the API (or ``reset_loads`` in tests) restores
the seeded loads.
"""

from __future__ import annotations

import threading

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

_LOCK = threading.Lock()
_INITIAL_LOADS = {agent.id: agent.current_load for agent in SEEDED_AGENTS}


def _find(agent_id: str) -> Agent | None:
    for agent in SEEDED_AGENTS:
        if agent.id == agent_id:
            return agent
    return None


def list_agents() -> list[Agent]:
    """All seeded demo agents. Deep copies: mutating a returned agent
    never mutates the stored seed."""
    with _LOCK:
        return [agent.model_copy(deep=True) for agent in SEEDED_AGENTS]


def find_eligible_agent(category: ComplaintCategory) -> Agent | None:
    """First seeded agent approved for the category, on shift, with
    capacity. Read-only: it does not consume capacity (use
    ``assign_agent`` for routing). Returns a copy."""
    with _LOCK:
        for agent in SEEDED_AGENTS:
            if (
                category in agent.skills
                and agent.on_shift
                and agent.current_load < agent.capacity
            ):
                return agent.model_copy(deep=True)
    return None


def assign_agent(category: ComplaintCategory) -> Agent | None:
    """Route to the first eligible agent and consume one unit of its
    capacity, atomically under the lock. Returns a copy of the assigned
    agent, or None when no eligible agent has capacity left."""
    with _LOCK:
        for agent in SEEDED_AGENTS:
            if (
                category in agent.skills
                and agent.on_shift
                and agent.current_load < agent.capacity
            ):
                agent.current_load += 1
                return agent.model_copy(deep=True)
    return None


def consume(agent_id: str) -> bool:
    """Consume one unit of the named agent's capacity. False when the
    agent does not exist or is already at capacity."""
    with _LOCK:
        agent = _find(agent_id)
        if agent is None or agent.current_load >= agent.capacity:
            return False
        agent.current_load += 1
        return True


def release(agent_id: str) -> None:
    """Release one unit of the named agent's capacity (never below 0).
    No-op for an unknown agent."""
    with _LOCK:
        agent = _find(agent_id)
        if agent is not None and agent.current_load > 0:
            agent.current_load -= 1


def reset_loads() -> None:
    """Restore the seeded loads. Tests use this for isolation; the API
    restarts with the seeded loads anyway (per-process store)."""
    with _LOCK:
        for agent in SEEDED_AGENTS:
            agent.current_load = _INITIAL_LOADS[agent.id]


def get_agent(agent_id: str) -> Agent | None:
    """Seeded agent by id, or None. Returns a copy."""
    with _LOCK:
        agent = _find(agent_id)
        return agent.model_copy(deep=True) if agent is not None else None
