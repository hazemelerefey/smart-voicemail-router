"""SVR Contracts v1.0 (schema_version 1, label_version taxonomy-2026-11-11).

Pydantic models for every contract object in
``~/workspace/goals/ai-voicemail-intelligence-competition/files/arafa-contracts-v1.md``
sections 2 and 3. Only the approved enum values are allowed: any other label
is rejected by validation and the ticket goes to human review, never guessed
(contracts section 4, rule 2).

Fusion is DISABLED: ``customer_state_final`` must stay null until the fusion
rules are agreed (contracts section 2 and section 10). The Ticket model
enforces this.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

SCHEMA_VERSION = 1
LABEL_VERSION = "taxonomy-2026-11-11"


class ComplaintCategory(str, Enum):
    """10 approved complaint_category values (contracts section 2)."""

    NETWORK_AND_CONNECTIVITY = "network_and_connectivity"
    BILLING_AND_CHARGES = "billing_and_charges"
    BALANCE_AND_DATA = "balance_and_data"
    APP_AND_ACCOUNT = "app_and_account"
    BRANCH_AND_STAFF = "branch_and_staff"
    NO_REPLY_OR_LONG_WAIT = "no_reply_or_long_wait"
    CANCELLATION_REQUEST = "cancellation_request"
    THANKS_OR_PRAISE = "thanks_or_praise"
    GREETING_ONLY = "greeting_only"
    OTHER = "other"


class ComplaintUrgency(str, Enum):
    """3 approved complaint_urgency values (contracts section 2)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CustomerState(str, Enum):
    """5 approved customer_state_text / voice_state_candidate values."""

    CALM = "calm"
    FRUSTRATED = "frustrated"
    MAD = "mad"
    SATISFIED = "satisfied"
    UNCLEAR = "unclear"


class ChurnRisk(str, Enum):
    """2 approved churn_risk values (contracts section 2)."""

    AT_RISK = "at_risk"
    NOT_AT_RISK = "not_at_risk"


class TicketStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"


class AssignmentStatus(str, Enum):
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"


def utcnow_iso() -> str:
    """ISO-8601 UTC timestamp, e.g. 2026-11-12T00:00:00Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class AudioEvidence(BaseModel):
    """Contracts section 3.1, produced by Sira (mocked in Phase 1)."""

    voicemail_id: str
    audio_path_local: str
    duration_s: float
    format: str
    sample_rate_hz: int = 16000
    channels: int = 1
    transcript: str
    stt_provider: str
    stt_model_version: str
    stt_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    # language_mix values are OPEN (contracts section 2 / section 10):
    # null until Hazem defines the approved list. Never invent a value.
    language_mix: str | None = None
    audio_quality: dict = Field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION
    label_version: str = LABEL_VERSION


class TextAnalysis(BaseModel):
    """Contracts section 3.2, produced by Lama (mocked in Phase 1)."""

    voicemail_id: str
    summary: str
    complaint_category: ComplaintCategory | None = None
    complaint_urgency: ComplaintUrgency | None = None
    customer_state_text: CustomerState | None = None
    churn_risk: ChurnRisk | None = None
    keywords: list[str] = Field(default_factory=list)
    customer_request: str
    # language_mix values OPEN, see AudioEvidence.
    language_mix: str | None = None
    suggested_script: str
    confidence: float = Field(ge=0.0, le=1.0)
    needs_human_review: bool
    schema_version: int = SCHEMA_VERSION
    label_version: str = LABEL_VERSION


class VoiceEvidence(BaseModel):
    """Contracts section 3.3, produced by Sira (mocked in Phase 1).

    Voice evidence is optional until validated. ``voice_state_candidate`` is
    evidence with uncertainty, never a truth label: it must never overwrite
    ``customer_state_text`` and never decide complaint urgency.
    """

    voicemail_id: str
    quality_features: dict = Field(default_factory=dict)
    acoustic_features: dict = Field(default_factory=dict)
    voice_state_candidate: CustomerState | None = None
    voice_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    model_version: str
    schema_version: int = SCHEMA_VERSION


class TriageDecision(BaseModel):
    """Contracts section 3.4, produced by Ibthal (mocked in Phase 1)."""

    voicemail_id: str
    # Priority formula and weights are OPEN (contracts section 10), owned by
    # Ibthal, approved by Hazem. Until agreed, priority_score stays null.
    priority_score: float | None = None
    queue_priority: str | None = None
    assigned_agent_id: str | None = None
    assignment_status: AssignmentStatus
    route_reason: str
    contributing_signals: list[str] = Field(default_factory=list)
    config_version: str
    evaluation: dict | None = None
    schema_version: int = SCHEMA_VERSION


class Ticket(BaseModel):
    """Contracts section 3.5, system level, produced by Arafa."""

    id: str
    voicemail_id: str
    ticket_status: TicketStatus
    assignment_status: AssignmentStatus
    priority_score: float | None = None
    route_reason: str
    summary: str
    customer_request: str
    suggested_script: str
    transcript: str
    complaint_category: ComplaintCategory | None = None
    complaint_urgency: ComplaintUrgency | None = None
    customer_state_text: CustomerState | None = None
    # Fusion DISABLED (contracts section 2): stays null until fusion rules
    # and labels are agreed. Enforced by the validator below.
    customer_state_final: CustomerState | None = None
    voice_state_candidate: CustomerState | None = None
    churn_risk: ChurnRisk | None = None
    needs_human_review: bool
    # True only for the exact preapproved demo file (contracts section 4.6).
    # No preapproved demo file exists in Phase 1, so mocks set False.
    cached: bool = False
    stage_status: dict[str, str] = Field(default_factory=dict)
    stage_timing_ms: dict[str, float] = Field(default_factory=dict)
    processing_ms: float = 0.0
    schema_version: int = SCHEMA_VERSION
    label_version: str = LABEL_VERSION
    created_at: str = Field(default_factory=utcnow_iso)

    @model_validator(mode="after")
    def _fusion_must_stay_disabled(self) -> "Ticket":
        if self.customer_state_final is not None:
            raise ValueError(
                "customer_state_final must stay null: fusion is disabled "
                "until the fusion rules are agreed (contracts section 2)."
            )
        return self


class Agent(BaseModel):
    """Contracts section 3.6, seeded demo agents only. No real people."""

    id: str
    name: str
    skills: list[ComplaintCategory]
    tier: str | None = None
    capacity: int
    current_load: int
    on_shift: bool
    languages: list[str]

    @field_validator("skills", mode="before")
    @classmethod
    def _coerce_skills(cls, value: object) -> object:
        # Accept plain strings as well as enum members.
        if isinstance(value, list):
            return [ComplaintCategory(v) if isinstance(v, str) else v for v in value]
        return value


class TicketEvent(BaseModel):
    """Audit event (contracts section 4.7, entity ticket_events)."""

    id: str
    ticket_id: str
    event: str
    detail: str = ""
    actor: str = "system"
    created_at: str = Field(default_factory=utcnow_iso)


class TicketDetail(Ticket):
    """Ticket plus evidence and audit trail, returned by GET /api/tickets/{id}."""

    audio_evidence: AudioEvidence | None = None
    text_analysis: TextAnalysis | None = None
    voice_evidence: VoiceEvidence | None = None
    triage_decision: TriageDecision | None = None
    events: list[TicketEvent] = Field(default_factory=list)
