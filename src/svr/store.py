"""In-memory ticket store (Phase 1).

Holds tickets, their evidence, and audit events for the life of the
process. No database yet: storage choice is an open decision (contracts
section 10), SQLite is a candidate for the local demo. Nothing here is
persisted to disk and no real customer data ever enters it.
"""

from __future__ import annotations

import threading
import uuid

from . import agents as agents_module
from .pipeline import PipelineResult
from .schemas import (
    AssignmentStatus,
    Ticket,
    TicketDetail,
    TicketEvent,
    TicketStatus,
    utcnow_iso,
)


class TicketStore:
    """Thread-safe in-memory store for tickets, evidence and audit events."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tickets: dict[str, Ticket] = {}
        self._details: dict[str, PipelineResult] = {}
        self._events: dict[str, list[TicketEvent]] = {}

    def create_placeholder(self, ticket_id: str, voicemail_id: str) -> Ticket:
        """Ticket visible as queued/processing within 2 seconds of submit
        (contracts section 5), before analysis begins. It carries no labels
        and needs_human_review True until its run finishes, so a queued
        record can never be mistaken for an answer."""
        ticket = Ticket(
            id=ticket_id,
            voicemail_id=voicemail_id,
            ticket_status=TicketStatus.PROCESSING,
            assignment_status=AssignmentStatus.UNASSIGNED,
            route_reason="Processing: pipeline run started.",
            summary="",
            customer_request="",
            suggested_script="",
            transcript="",
            needs_human_review=True,
            cached=False,
            stage_status={"intake": "pending"},
            stage_timing_ms={},
            processing_ms=0.0,
        )
        with self._lock:
            self._tickets[ticket_id] = ticket
            self._events.setdefault(ticket_id, []).append(
                TicketEvent(
                    id=f"evt-{uuid.uuid4().hex[:8]}",
                    ticket_id=ticket_id,
                    event="submitted",
                    detail="Voicemail submitted, pipeline run started.",
                    actor="demo-user",
                )
            )
        return ticket

    def complete(self, result: PipelineResult) -> Ticket:
        """Store a finished pipeline run and audit its completion.

        The run is finished, so the unit of agent capacity its routing
        consumed is released (concurrent-load accounting, issue #6)."""
        ticket = result.ticket
        with self._lock:
            self._tickets[ticket.id] = ticket
            self._details[ticket.id] = result
            self._events.setdefault(ticket.id, []).append(
                TicketEvent(
                    id=f"evt-{uuid.uuid4().hex[:8]}",
                    ticket_id=ticket.id,
                    event="completed" if ticket.ticket_status.value == "completed" else "needs_review",
                    detail=f"Pipeline finished in {ticket.processing_ms} ms.",
                    actor="system",
                )
            )
        if result.decision is not None and result.decision.assigned_agent_id:
            agents_module.release(result.decision.assigned_agent_id)
        return ticket

    def get(self, ticket_id: str) -> Ticket | None:
        with self._lock:
            return self._tickets.get(ticket_id)

    def get_detail(self, ticket_id: str) -> TicketDetail | None:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                return None
            result = self._details.get(ticket_id)
            events = list(self._events.get(ticket_id, []))
        return TicketDetail(
            **ticket.model_dump(),
            audio_evidence=result.audio if result else None,
            text_analysis=result.text if result else None,
            voice_evidence=result.voice_evidence if result else None,
            triage_decision=result.decision if result else None,
            events=events,
        )

    def update(
        self,
        ticket_id: str,
        *,
        ticket_status: str | None = None,
        assignment_status: str | None = None,
        assigned_agent_id: str | None = None,
        actor: str = "demo-user",
    ) -> Ticket | None:
        """Manual status / reassignment action, with an audit event
        (contracts section 6, PATCH /api/tickets/{id}).

        Raises ValueError on an invalid assignment (unknown agent, agent
        at capacity, contradictory assignment fields): the API turns it
        into a 400 and nothing is stored.
        """
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                return None
            changes: dict = {}
            if ticket_status is not None:
                changes["ticket_status"] = TicketStatus(ticket_status)
            if assignment_status is not None:
                changes["assignment_status"] = AssignmentStatus(assignment_status)
            # Capacity accounting (issue #6) happens before anything is
            # stored, so a failed consume leaves the old assignment intact.
            # A reassignment releases the old agent and consumes the new
            # one; unassigning releases the old agent.
            result = self._details.get(ticket_id)
            old_agent_id = (
                result.decision.assigned_agent_id
                if result is not None and result.decision is not None
                else None
            )
            if assigned_agent_id is not None and assigned_agent_id != old_agent_id:
                if not agents_module.consume(assigned_agent_id):
                    raise ValueError(f"agent {assigned_agent_id} is at capacity")
                if old_agent_id is not None:
                    agents_module.release(old_agent_id)
            elif (
                assignment_status is not None
                and AssignmentStatus(assignment_status) == AssignmentStatus.UNASSIGNED
                and old_agent_id is not None
            ):
                agents_module.release(old_agent_id)
            updated = ticket.model_copy(update=changes)
            self._tickets[ticket_id] = updated
            # Keep the stored detail in sync.
            if result is not None:
                result.ticket = updated
                # Persist the reassignment on the stored triage decision as
                # structured data, so GET shows the new agent (issue #4).
                # It is never recorded only as free text in the audit event.
                if result.decision is not None and (
                    assigned_agent_id is not None or assignment_status is not None
                ):
                    decision_changes: dict = {}
                    if assignment_status is not None:
                        new_status = AssignmentStatus(assignment_status)
                        decision_changes["assignment_status"] = new_status
                        if new_status == AssignmentStatus.UNASSIGNED:
                            decision_changes["assigned_agent_id"] = None
                    if assigned_agent_id is not None:
                        decision_changes["assigned_agent_id"] = assigned_agent_id
                        decision_changes["assignment_status"] = AssignmentStatus.ASSIGNED
                    if decision_changes:
                        result.decision = result.decision.model_copy(
                            update=decision_changes
                        )
            detail = ", ".join(f"{k}={v}" for k, v in changes.items())
            if assigned_agent_id is not None:
                detail += f", assigned_agent_id={assigned_agent_id}"
            self._events.setdefault(ticket_id, []).append(
                TicketEvent(
                    id=f"evt-{uuid.uuid4().hex[:8]}",
                    ticket_id=ticket_id,
                    event="manual_update",
                    detail=detail or "no change",
                    actor=actor,
                )
            )
            return updated

    def list_tickets(self) -> list[Ticket]:
        with self._lock:
            return list(self._tickets.values())

    def latency_samples(self) -> tuple[list[float], list[dict[str, float]]]:
        """processing_ms and stage timings of finished runs, for p95."""
        with self._lock:
            done = [
                t
                for t in self._tickets.values()
                if t.ticket_status.value in ("completed", "needs_review")
                and t.processing_ms > 0
            ]
        return (
            [t.processing_ms for t in done],
            [dict(t.stage_timing_ms) for t in done],
        )


# One process-wide store for the Phase 1 API and demo.
STORE = TicketStore()
