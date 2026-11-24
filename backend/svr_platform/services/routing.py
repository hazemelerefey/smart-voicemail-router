"""Deterministic telecom agent routing engine and capacity lifecycle (FR10, FR11, FR20, 10.5)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Agent, Assignment, SkillMapping, Ticket
from ..taxonomy import DEFAULT_SKILL_MAPPING


@dataclass(frozen=True)
class RouteDecision:
    assigned_agent_id: str | None
    assigned_agent_name: str | None
    required_skill: str | None
    route_reason: str
    needs_human_review: bool
    review_reason: str | None = None


def resolve_required_skill(db: Session, organization_id: str, complaint_category: str | None) -> str | None:
    if not complaint_category:
        return None
    mapping = db.scalar(
        select(SkillMapping).where(
            SkillMapping.organization_id == organization_id,
            SkillMapping.category == complaint_category,
        )
    )
    if mapping is not None:
        return mapping.skill_name
    return DEFAULT_SKILL_MAPPING.get(complaint_category)


def recommend_route(
    db: Session,
    *,
    organization_id: str,
    complaint_category: str | None,
    auto_routing_enabled: bool = True,
    human_review_blocker: str | None = None,
) -> RouteDecision:
    """Select the first eligible agent in seed order without mutating state.

    Eligibility: active == True, skill covers complaint_category, available == True,
    current_load < capacity. No tier policy, no language_mix filter (PRD Appendix C).
    """
    if not auto_routing_enabled:
        return RouteDecision(
            assigned_agent_id=None,
            assigned_agent_name=None,
            required_skill=resolve_required_skill(db, organization_id, complaint_category),
            route_reason=(
                "UNASSIGNED: automatic routing kill switch is active. "
                "Ticket routed to the Human Review Queue for manual supervisor assignment."
            ),
            needs_human_review=True,
            review_reason="kill_switch_active",
        )

    if human_review_blocker is not None:
        return RouteDecision(
            assigned_agent_id=None,
            assigned_agent_name=None,
            required_skill=resolve_required_skill(db, organization_id, complaint_category),
            route_reason=(
                f"UNASSIGNED: ticket flagged for Human Review ({human_review_blocker}) "
                "before automatic agent routing."
            ),
            needs_human_review=True,
            review_reason=human_review_blocker,
        )

    if not complaint_category:
        return RouteDecision(
            assigned_agent_id=None,
            assigned_agent_name=None,
            required_skill=None,
            route_reason=(
                "UNASSIGNED: complaint_category is missing, so no telecom skill can be matched. "
                "Entered the Human Routing Queue."
            ),
            needs_human_review=True,
            review_reason="missing_label",
        )

    required_skill = resolve_required_skill(db, organization_id, complaint_category)
    if not required_skill:
        return RouteDecision(
            assigned_agent_id=None,
            assigned_agent_name=None,
            required_skill=None,
            route_reason=(
                f"UNASSIGNED: complaint category '{complaint_category}' has no approved skill mapping. "
                "Entered the Human Routing Queue."
            ),
            needs_human_review=True,
            review_reason="no_eligible_agent",
        )

    agents = db.scalars(
        select(Agent)
        .where(Agent.organization_id == organization_id, Agent.active.is_(True))
        .order_by(Agent.seed_order.asc(), Agent.created_at.asc())
    ).all()

    skill_matched = [
        a for a in agents if required_skill in (a.skills or []) or complaint_category in (a.skills or [])
    ]
    if not skill_matched:
        return RouteDecision(
            assigned_agent_id=None,
            assigned_agent_name=None,
            required_skill=required_skill,
            route_reason=(
                f"UNASSIGNED: no active telecom care agent holds skill '{required_skill}' "
                f"for category '{complaint_category}'. Entered the Human Routing Queue."
            ),
            needs_human_review=True,
            review_reason="no_eligible_agent",
        )

    available_agents = [a for a in skill_matched if a.available]
    if not available_agents:
        return RouteDecision(
            assigned_agent_id=None,
            assigned_agent_name=None,
            required_skill=required_skill,
            route_reason=(
                f"UNASSIGNED: {len(skill_matched)} agent(s) hold skill '{required_skill}' "
                f"for '{complaint_category}', but none are currently available. "
                "Entered the Human Routing Queue."
            ),
            needs_human_review=True,
            review_reason="no_eligible_agent",
        )

    for agent in available_agents:
        if agent.current_load < agent.capacity:
            next_load = agent.current_load + 1
            reason = (
                f"Assigned to {agent.name}: matched skill '{required_skill}' for "
                f"'{complaint_category}', available on shift, concurrent load {next_load}/{agent.capacity} "
                f"(first eligible in seed order)."
            )
            return RouteDecision(
                assigned_agent_id=agent.id,
                assigned_agent_name=agent.name,
                required_skill=required_skill,
                route_reason=reason,
                needs_human_review=False,
                review_reason=None,
            )

    return RouteDecision(
        assigned_agent_id=None,
        assigned_agent_name=None,
        required_skill=required_skill,
        route_reason=(
            f"UNASSIGNED: {len(available_agents)} available agent(s) hold skill '{required_skill}' "
            f"for '{complaint_category}', but all are at full concurrent ticket capacity. "
            "Entered the Human Routing Queue."
        ),
        needs_human_review=True,
        review_reason="no_eligible_agent",
    )


def release_active_assignment(db: Session, ticket: Ticket, *, final_status: str = "released") -> None:
    """Release an active assignment on a ticket and decrement the previous agent's concurrent load."""
    active_assignments = db.scalars(
        select(Assignment).where(
            Assignment.ticket_id == ticket.id,
            Assignment.status == "active",
        )
    ).all()
    for asgn in active_assignments:
        asgn.status = final_status
        prev_agent = db.get(Agent, asgn.agent_id)
        if prev_agent is not None and prev_agent.current_load > 0:
            prev_agent.current_load -= 1


def assign_ticket_to_agent(
    db: Session,
    ticket: Ticket,
    agent_id: str,
    *,
    assigned_by: str,
    route_reason: str,
) -> Agent:
    """Assign ticket to target agent enforcing organization isolation, active status, and capacity."""
    agent = db.get(Agent, agent_id)
    if agent is None or agent.organization_id != ticket.organization_id:
        raise ValueError("Target agent not found in organization.")
    if not agent.active:
        raise ValueError(f"Agent '{agent.name}' is deactivated and cannot receive tickets.")

    # No-op capacity change if already assigned to the same agent with an active assignment
    if ticket.assigned_agent_id == agent.id:
        existing = db.scalar(
            select(Assignment).where(
                Assignment.ticket_id == ticket.id,
                Assignment.agent_id == agent.id,
                Assignment.status == "active",
            )
        )
        if existing is not None:
            existing.route_reason = route_reason
            ticket.route_reason = route_reason
            return agent

    if agent.current_load >= agent.capacity:
        raise ValueError(
            f"Agent '{agent.name}' is at maximum concurrent capacity ({agent.current_load}/{agent.capacity})."
        )

    release_active_assignment(db, ticket, final_status="released")
    agent.current_load += 1
    ticket.assigned_agent_id = agent.id
    ticket.route_reason = route_reason
    db.add(
        Assignment(
            organization_id=ticket.organization_id,
            ticket_id=ticket.id,
            agent_id=agent.id,
            assigned_by=assigned_by,
            route_reason=route_reason,
            status="active",
        )
    )
    return agent
