"""Mock fixture only (contracts section 9).

This is a fixture, not a real voicemail. No real audio, transcript, or
customer content is used here. Every mock stage returns these fixed values
until the real components land in Phase 2.
"""

from __future__ import annotations

# Fixed mock transcript. The real transcript comes from Sira's Whisper
# large-v3 STT in Phase 2; until then the STT stage returns this string.
FIXTURE_TRANSCRIPT = "[fixture transcript]"

FIXTURE_VOICEMAIL_ID = "voicemail-fixture-001"
FIXTURE_TICKET_ID = "ticket-fixture-001"

FIXTURE_TEXT_ANALYSIS: dict = {
    "voicemail_id": FIXTURE_VOICEMAIL_ID,
    "summary": "Customer reports a service problem and requests a callback.",
    "complaint_category": "network_and_connectivity",
    "complaint_urgency": "medium",
    "customer_state_text": "frustrated",
    "churn_risk": "not_at_risk",
    "keywords": ["service problem", "callback"],
    "customer_request": "Customer asks for a callback about the service problem.",
    "language_mix": None,  # values OPEN, contracts section 2 / section 10
    "suggested_script": (
        "Hello, thank you for your message, I am calling back "
        "about the service problem you reported."
    ),
    "confidence": 0.9,
    "needs_human_review": False,
    "schema_version": 1,
    "label_version": "taxonomy-2026-11-11",
}

FIXTURE_ROUTE_REASON = (
    "Assigned because the complaint category matches the agent approved "
    "skill and the agent is on shift with capacity. Priority score is null "
    "because the priority formula is not agreed yet, see contracts section 10."
)

# Contracts section 9 fixture ticket, verbatim values. The pipeline builds a
# ticket in exactly this shape; ids and created_at are set per run.
FIXTURE_TICKET: dict = {
    "id": FIXTURE_TICKET_ID,
    "voicemail_id": FIXTURE_VOICEMAIL_ID,
    "ticket_status": "completed",
    "assignment_status": "assigned",
    "priority_score": None,
    "route_reason": FIXTURE_ROUTE_REASON,
    "summary": "Customer reports a service problem and requests a callback.",
    "customer_request": "Customer asks for a callback about the service problem.",
    "suggested_script": (
        "Hello, thank you for your message, I am calling back "
        "about the service problem you reported."
    ),
    "transcript": FIXTURE_TRANSCRIPT,
    "complaint_category": "network_and_connectivity",
    "complaint_urgency": "medium",
    "customer_state_text": "frustrated",
    "customer_state_final": None,  # fusion disabled, contracts section 2
    "voice_state_candidate": None,
    "churn_risk": "not_at_risk",
    "needs_human_review": False,
    "cached": False,
    "stage_status": {
        "intake": "ok",
        "stt": "ok",
        "text_analysis": "ok",
        "voice_evidence": "skipped",
        "triage": "ok",
    },
    "stage_timing_ms": {
        "intake": 120,
        "stt": 1800,
        "text_analysis": 900,
        "voice_evidence": 0,
        "triage": 80,
    },
    "processing_ms": 2900,
    "schema_version": 1,
    "label_version": "taxonomy-2026-11-11",
    "created_at": "2026-11-12T00:00:00Z",
}
