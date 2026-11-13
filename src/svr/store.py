"""In-memory ticket store (Phase 1).

Holds tickets, their evidence, and audit events for the life of the
process. No database yet: storage choice is an open decision (contracts
section 10), SQLite is a candidate for the local demo. Nothing here is
persisted to disk and no real customer data ever enters it.
"""

from __future__ import annotations

import threading
import uuid

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
        """Store a finished pipeline run and audit its completion."""
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
        (contracts section 6, PATCH /api/tickets/{id})."""
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                return None
            changes: dict = {}
            if ticket_status is not None:
                changes["ticket_status"] = TicketStatus(ticket_status)
            if assignment_status is not None:
                changes["assignment_status"] = AssignmentStatus(assignment_status)
            updated = ticket.model_copy(update=changes)
            self._tickets[ticket_id] = updated
            # Keep the stored detail in sync.
            result = self._details.get(ticket_id)
            if result is not None:
                result.ticket = updated
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
