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


# Status state machine (issue #7): processing or queued may go to
# completed or needs_review, needs_review may go to completed only, and
# completed is terminal. The same status is always allowed (idempotent).
_ALLOWED_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    TicketStatus.QUEUED: frozenset(
        {
            TicketStatus.PROCESSING,
            TicketStatus.COMPLETED,
            TicketStatus.NEEDS_REVIEW,
        }
    ),
    TicketStatus.PROCESSING: frozenset(
        {TicketStatus.COMPLETED, TicketStatus.NEEDS_REVIEW}
    ),
    TicketStatus.NEEDS_REVIEW: frozenset({TicketStatus.COMPLETED}),
    TicketStatus.COMPLETED: frozenset(),
}


class TicketStore:
    """Thread-safe in-memory store for tickets, evidence and audit events.

    Reads return deep copies: callers can never mutate a stored ticket,
    its evidence, or its events in place. Status changes go through the
    state machine in :meth:`update`.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tickets: dict[str, Ticket] = {}
        self._details: dict[str, PipelineResult] = {}
        self._events: dict[str, list[TicketEvent]] = {}

    def clear(self) -> None:
        """Empty the store. Tests use this for isolation (issue #9)."""
        with self._lock:
            self._tickets.clear()
            self._details.clear()
            self._events.clear()

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
            if ticket_id in self._tickets:
                # Re-creating an id used to overwrite the ticket while
                # leaving the old evidence behind (issue #7): reject it.
                raise ValueError(f"ticket {ticket_id} already exists")
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
        return ticket.model_copy(deep=True)

    def complete(self, result: PipelineResult) -> Ticket:
        """Store a finished pipeline run and audit its completion.

        Only a terminal ticket (completed or needs_review) may be stored:
        a non-terminal run is a caller bug, and a ticket that is already
        finished cannot be completed twice. The run is finished, so the
        unit of agent capacity its routing consumed is released
        (concurrent-load accounting, issue #6)."""
        ticket = result.ticket
        if ticket.ticket_status not in (
            TicketStatus.COMPLETED,
            TicketStatus.NEEDS_REVIEW,
        ):
            raise ValueError(
                f"cannot complete a ticket with status "
                f"{ticket.ticket_status.value}: only completed or "
                f"needs_review are terminal"
            )
        with self._lock:
            existing = self._tickets.get(ticket.id)
            if existing is not None and existing.ticket_status in (
                TicketStatus.COMPLETED,
                TicketStatus.NEEDS_REVIEW,
            ):
                raise ValueError(f"ticket {ticket.id} is already finished")
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
        return ticket.model_copy(deep=True)

    def get(self, ticket_id: str) -> Ticket | None:
        """A deep copy of the stored ticket: mutating it never corrupts
        the store."""
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            return ticket.model_copy(deep=True) if ticket is not None else None

    def get_detail(self, ticket_id: str) -> TicketDetail | None:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                return None
            result = self._details.get(ticket_id)
            events = [
                event.model_copy(deep=True)
                for event in self._events.get(ticket_id, [])
            ]
        return TicketDetail(
            **ticket.model_dump(),
            audio_evidence=result.audio.model_copy(deep=True)
            if result is not None and result.audio is not None
            else None,
            text_analysis=result.text.model_copy(deep=True)
            if result is not None and result.text is not None
            else None,
            voice_evidence=result.voice_evidence.model_copy(deep=True)
            if result is not None and result.voice_evidence is not None
            else None,
            triage_decision=result.decision.model_copy(deep=True)
            if result is not None and result.decision is not None
            else None,
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

        Status changes go through a state machine: processing or queued
        may go to completed or needs_review, needs_review may go to
        completed only, and completed is terminal. The same status is
        always allowed (an idempotent no-op). Completing a ticket
        requires all four labels present. ``needs_human_review`` is kept
        in sync with the status (True for needs_review, False for
        completed), and the updated ticket is re-validated, so no
        invariant can be bypassed through ``model_copy``.

        Raises ValueError on an invalid transition, an invalid status,
        an uncompletable ticket, or an invalid assignment (unknown agent,
        agent at capacity, contradictory assignment fields): the API
        turns it into a 400 and nothing is stored.
        """
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                return None
            changes: dict = {}
            if ticket_status is not None:
                try:
                    new_status = TicketStatus(ticket_status)
                except ValueError:
                    raise ValueError(
                        f"invalid ticket_status: {ticket_status!r}"
                    ) from None
                if (
                    new_status != ticket.ticket_status
                    and new_status not in _ALLOWED_TRANSITIONS[ticket.ticket_status]
                ):
                    raise ValueError(
                        f"invalid status transition "
                        f"{ticket.ticket_status.value} -> {new_status.value}"
                    )
                if new_status == TicketStatus.COMPLETED and any(
                    value is None
                    for value in (
                        ticket.complaint_category,
                        ticket.complaint_urgency,
                        ticket.customer_state_text,
                        ticket.churn_risk,
                    )
                ):
                    raise ValueError(
                        "cannot complete a ticket with null labels: "
                        "it must stay in needs_review until reviewed"
                    )
                changes["ticket_status"] = new_status
                changes["needs_human_review"] = (
                    new_status == TicketStatus.NEEDS_REVIEW
                )
            if assignment_status is not None:
                try:
                    new_assignment = AssignmentStatus(assignment_status)
                except ValueError:
                    raise ValueError(
                        f"invalid assignment_status: {assignment_status!r}"
                    ) from None
                changes["assignment_status"] = new_assignment
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
            # Re-validate: model_copy skips validators, so an invariant
            # (fusion disabled, null label forces review) must be
            # re-checked on the updated ticket.
            updated = Ticket.model_validate(updated.model_dump())
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
            return updated.model_copy(deep=True)

    def list_tickets(self) -> list[Ticket]:
        """Deep copies: mutating a listed ticket never corrupts the store."""
        with self._lock:
            return [ticket.model_copy(deep=True) for ticket in self._tickets.values()]

    def latency_samples(self) -> tuple[list[float], list[dict[str, float]]]:
        """processing_ms and stage timings of finished runs, for p95.

        Zero-duration finished runs are included: a 0 ms run is a real
        run, and excluding it would undercount p95 silently."""
        with self._lock:
            done = [
                t
                for t in self._tickets.values()
                if t.ticket_status.value in ("completed", "needs_review")
                and t.processing_ms >= 0
            ]
        return (
            [t.processing_ms for t in done],
            [dict(t.stage_timing_ms) for t in done],
        )


# One process-wide store for the Phase 1 API and demo.
STORE = TicketStore()
