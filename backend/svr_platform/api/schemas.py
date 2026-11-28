"""Strict Pydantic v2 request and response schemas (extra='forbid' against mass assignment)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..taxonomy import (
    ChurnRisk,
    ComplaintCategory,
    ComplaintUrgency,
    CustomerState,
    TicketStatus,
    UserRole,
)

_UNEXPANDED_PLACEHOLDER_RE = re.compile(r"\{[^{}]+\}")
_ALL_CATEGORIES = frozenset(c.value for c in ComplaintCategory)


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StrictResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


# --- Authentication ---


class LoginRequest(StrictSchema):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=256)


class UserResponse(StrictResponseSchema):
    id: str
    organization_id: str
    email: str
    full_name: str
    role: UserRole
    active: bool
    linked_agent_id: str | None = None
    created_at: datetime


class AuthResponse(StrictResponseSchema):
    user: UserResponse
    csrf_token: str
    message: str = "Authenticated."


class LogoutResponse(StrictResponseSchema):
    message: str = "Logged out."


# --- Voicemail Intake ---


class VoicemailUploadResponse(StrictResponseSchema):
    voicemail_id: str
    ticket_id: str
    status: str
    deduplicated: bool = False
    file_name: str
    format: str
    size_bytes: int
    duration_seconds: float
    recommendation_note: str | None = None
    idempotency_key: str


# --- Audit & AI Interaction Logs ---


class AIInteractionLogResponse(StrictResponseSchema):
    id: str
    ticket_id: str
    stage: str
    model: str
    input_ref: str
    output: dict[str, Any]
    latency_ms: int
    created_at: datetime


class AuditEventResponse(StrictResponseSchema):
    id: str
    organization_id: str
    entity_type: str
    entity_id: str
    action: str
    actor: str
    old_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    created_at: datetime


class AuditLogListResponse(StrictResponseSchema):
    items: list[AuditEventResponse]
    limit: int
    next_cursor: str | None = None
    prev_cursor: str | None = None
    total: int


# --- Tickets ---


class TicketSummary(StrictResponseSchema):
    id: str
    voicemail_id: str
    status: str
    file_name: str
    duration_seconds: float
    summary: str
    customer_request: str
    suggested_script: str
    complaint_category: str | None = None
    complaint_urgency: str | None = None
    customer_state: str | None = None
    churn_risk: str | None = None
    confidence: float
    confidence_threshold_snapshot: float
    priority_score: int | None = None
    queue_priority: str | None = None
    assigned_agent_id: str | None = None
    assigned_agent_name: str | None = None
    route_reason: str
    needs_human_review: bool
    review_reason: str | None = None
    language_mix: str | None = None
    stage_status: dict[str, str]
    processing_ms: float
    created_at: datetime
    updated_at: datetime


class TicketListResponse(StrictResponseSchema):
    items: list[TicketSummary]
    limit: int
    next_cursor: str | None = None
    prev_cursor: str | None = None
    total: int
    counts_by_bucket: dict[str, int]
    counts_by_status: dict[str, int]
    human_review_count: int


class TicketDetail(StrictResponseSchema):
    id: str
    voicemail_id: str
    organization_id: str
    status: str
    file_name: str
    format: str
    size_bytes: int
    duration_seconds: float
    audio_url: str
    transcript: str
    text_norm: str
    language_mix: str | None = None
    stt_v1_json: dict[str, Any] | None = None
    transcript_verification: dict[str, Any] | None = None
    complaint_category: str | None = None
    complaint_urgency: str | None = None
    customer_state: str | None = None
    churn_risk: str | None = None
    label_sources: dict[str, str]
    probabilities: dict[str, dict[str, float]]
    confidence: float
    confidence_threshold_snapshot: float
    priority_score: int | None = None
    queue_priority: str | None = None
    priority_signals: dict[str, Any]
    priority_reason: str
    route_reason: str
    assigned_agent_id: str | None = None
    assigned_agent_name: str | None = None
    summary: str
    customer_request: str
    suggested_script: str
    needs_human_review: bool
    review_reason: str | None = None
    model_version: str
    stage_status: dict[str, str]
    stage_timing_ms: dict[str, float]
    processing_ms: float
    config_snapshot: dict[str, Any]
    ai_logs: list[AIInteractionLogResponse]
    audit_events: list[AuditEventResponse]
    created_at: datetime
    updated_at: datetime


class CorrectionPreviewRequest(StrictSchema):
    complaint_category: ComplaintCategory | None = None
    complaint_urgency: ComplaintUrgency | None = None
    customer_state: CustomerState | None = None
    churn_risk: ChurnRisk | None = None


class CorrectionPreviewResponse(StrictResponseSchema):
    proposed_labels: dict[str, str | None]
    priority_score: int | None = None
    queue_priority: str | None = None
    priority_signals: dict[str, Any]
    priority_reason: str
    recommended_agent_id: str | None = None
    recommended_agent_name: str | None = None
    required_skill: str | None = None
    route_reason: str
    summary: str
    customer_request: str
    suggested_script: str
    needs_human_review: bool
    review_reason: str | None = None


class CorrectionApplyRequest(StrictSchema):
    complaint_category: ComplaintCategory | None = None
    complaint_urgency: ComplaintUrgency | None = None
    customer_state: CustomerState | None = None
    churn_risk: ChurnRisk | None = None
    apply_recommended_route: bool = True
    clear_human_review: bool = True
    note: str | None = Field(default=None, max_length=500)


class PatchTicketRequest(StrictSchema):
    status: TicketStatus | None = None
    assigned_agent_id: str | None = None
    unassign: bool = False
    needs_human_review: bool | None = None
    review_reason: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=500)


# --- Agents & Skills ---


def _clean_skills(skills: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in skills:
        val = raw.strip()
        if not val:
            raise ValueError("Skill names must be non-empty strings.")
        if len(val) > 64:
            raise ValueError("Skill name exceeds 64 character limit.")
        if val not in seen:
            seen.add(val)
            cleaned.append(val)
    if not cleaned:
        raise ValueError("At least one skill is required.")
    return cleaned


class AgentResponse(StrictResponseSchema):
    id: str
    organization_id: str
    name: str
    skills: list[str]
    capacity: int
    current_load: int
    available: bool
    active: bool
    seed_order: int
    created_at: datetime
    updated_at: datetime


class AgentCreateRequest(StrictSchema):
    name: str = Field(..., min_length=2, max_length=160)
    skills: list[str] = Field(..., min_length=1)
    capacity: int = Field(default=5, ge=1, le=100)
    available: bool = True
    seed_order: int = Field(default=100, ge=1, le=10000)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        val = v.strip()
        if len(val) < 2:
            raise ValueError("Agent name must be at least 2 characters.")
        return val

    @field_validator("skills")
    @classmethod
    def _validate_skills(cls, v: list[str]) -> list[str]:
        return _clean_skills(v)


class AgentUpdateRequest(StrictSchema):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    skills: list[str] | None = Field(default=None, min_length=1)
    capacity: int | None = Field(default=None, ge=1, le=100)
    available: bool | None = None
    active: bool | None = None
    seed_order: int | None = Field(default=None, ge=1, le=10000)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        val = v.strip()
        if len(val) < 2:
            raise ValueError("Agent name must be at least 2 characters.")
        return val

    @field_validator("skills")
    @classmethod
    def _validate_skills(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return _clean_skills(v)


class SkillMappingItem(StrictResponseSchema):
    category: str
    skill_name: str
    updated_at: datetime | None = None


class SkillMappingListResponse(StrictResponseSchema):
    mappings: list[SkillMappingItem]


class SkillMappingUpdateRequest(StrictSchema):
    mappings: dict[str, str]

    @field_validator("mappings")
    @classmethod
    def _validate_all_11_categories(cls, v: dict[str, str]) -> dict[str, str]:
        keys = set(v.keys())
        missing = sorted(_ALL_CATEGORIES - keys)
        extra = sorted(keys - _ALL_CATEGORIES)
        if missing:
            raise ValueError(
                f"Skill mapping must cover all 11 complaint categories; missing: {', '.join(missing)}."
            )
        if extra:
            raise ValueError(
                f"Unknown complaint category in skill mapping: {', '.join(extra)}."
            )
        cleaned: dict[str, str] = {}
        for cat, skill in v.items():
            s = (skill or "").strip()
            if not s or len(s) > 64:
                raise ValueError(f"Category '{cat}' must map to a non-empty skill name (max 64 chars).")
            cleaned[cat] = s
        return cleaned


# --- Settings & Script Templates ---


class SettingsResponse(StrictResponseSchema):
    organization_id: str
    confidence_threshold: float
    auto_routing_enabled: bool
    retention_days: int
    weekly_sample_rate: float
    updated_at: datetime


class SettingsUpdateRequest(StrictSchema):
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    auto_routing_enabled: bool | None = None
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    weekly_sample_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class ScriptTemplateResponse(StrictResponseSchema):
    category: str
    template_ar: str
    template_en: str
    customer_request_ar: str
    customer_request_en: str
    version: int
    updated_at: datetime


class ScriptTemplateUpdateRequest(StrictSchema):
    template_ar: str = Field(..., min_length=1, max_length=1000)
    template_en: str = Field(..., min_length=1, max_length=1000)
    customer_request_ar: str = Field(..., min_length=1, max_length=500)
    customer_request_en: str = Field(..., min_length=1, max_length=500)

    @field_validator("template_ar", "template_en", "customer_request_ar", "customer_request_en")
    @classmethod
    def _reject_unexpanded_placeholders(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Template text cannot be blank.")
        if _UNEXPANDED_PLACEHOLDER_RE.search(cleaned):
            raise ValueError("Unexpanded placeholders like '{...}' are forbidden in grounded script templates.")
        return cleaned


# --- Evaluation, Monitoring & Health ---


class EvalRunResponse(StrictResponseSchema):
    id: str
    organization_id: str
    dataset_version: str
    split: str
    model_version: str
    config: dict[str, Any]
    metrics: dict[str, Any]
    guard_claim_id: str | None = None
    created_at: datetime
    created_by: str


class MonitoringAlert(StrictResponseSchema):
    code: str
    severity: str
    message: str
    value: float
    threshold: float


class MonitoringSummaryResponse(StrictResponseSchema):
    total_tickets: int
    tickets_last_24h: int
    tickets_by_status: dict[str, int]
    classification_distribution: dict[str, dict[str, int]]
    confidence_histogram: list[dict[str, Any]]
    human_review_rate: float
    human_review_rate_24h: float
    qa_sampled_count: int = 0
    qa_sample_rate: float = 0.0
    processing_success_rate: float
    end_to_end_latency_ms: dict[str, float]
    end_to_end_latency_24h_ms: dict[str, float]
    stage_latency_ms: dict[str, dict[str, float]]
    alerts: list[MonitoringAlert]
    auto_routing_enabled: bool
    active_ws_connections: int


class HealthResponse(StrictResponseSchema):
    status: str
    environment: str
    database: str
    whisper_model: str
    stt_backend: str = "faster_whisper"
    stt_model: str = ""
    marbert_checkpoints_ready: bool
    active_ws_connections: int
    version: str


class AgentMemoryLessonItem(StrictResponseSchema):
    id: str
    rule_type: str
    trigger_pattern: str
    instruction: str
    support_count: int
    success_count: int
    source: str
    updated_at: datetime


class AgentMemoryStatsResponse(StrictResponseSchema):
    organization_id: str
    memory_enabled: bool
    adjudicator_enabled: bool
    embed_model: str
    episodic_total: int
    episodic_by_source: dict[str, int]
    semantic_entries_count: int
    procedural_rules_active_count: int
    training_feedback_total: int
    training_feedback_by_tier: dict[str, int]
    recent_procedural_lessons: list[AgentMemoryLessonItem]


class CohereRecentResult(StrictResponseSchema):
    ticket_id: str
    file_name: str
    transcript_preview: str
    min_avg_logprob: float | None = None
    max_no_speech_prob: float | None = None
    needs_review: bool
    latency_ms: int
    status: str
    created_at: datetime


class CohereModelTelemetry(StrictResponseSchema):
    name: str
    model_id: str
    backend: str
    device: str
    status: str
    total_runs: int
    success_rate: float
    latency_ms: dict[str, float]
    avg_logprob: float | None = None
    avg_no_speech_prob: float | None = None
    flagged_rate: float
    recent_results: list[CohereRecentResult]


class MarbertRecentResult(StrictResponseSchema):
    ticket_id: str
    file_name: str
    complaint_category: str | None = None
    complaint_urgency: str | None = None
    customer_state: str | None = None
    churn_risk: str | None = None
    confidence: float
    agreed_with_orchestrator: bool
    latency_ms: int
    status: str
    created_at: datetime


class MarbertModelTelemetry(StrictResponseSchema):
    name: str
    model_id: str
    backend: str
    checkpoints_ready: bool
    status: str
    total_runs: int
    avg_confidence: float
    below_threshold_rate: float
    latency_ms: dict[str, float]
    per_head_avg_confidence: dict[str, float]
    category_distribution: dict[str, int]
    recent_results: list[MarbertRecentResult]


class OrchestratorRecentResult(StrictResponseSchema):
    ticket_id: str
    file_name: str
    gate_status: str
    adjudicator_mode: str
    changed_fields: list[str]
    memory_episodes_used: int
    max_episode_similarity: float
    calibrated_confidence: float
    assigned_agent_name: str | None = None
    reasoning_preview: str
    latency_ms: int
    created_at: datetime


class OrchestratorModelTelemetry(StrictResponseSchema):
    name: str
    model_id: str
    embed_model: str
    status: str
    total_runs: int
    fast_path_count: int
    repaired_count: int
    uncertain_count: int
    fast_verified_count: int
    adjudicated_count: int
    override_count: int
    agreement_rate: float
    verify_latency_ms: dict[str, float]
    adjudicate_latency_ms: dict[str, float]
    memory: AgentMemoryStatsResponse
    recent_results: list[OrchestratorRecentResult]


class ModelsTelemetryResponse(StrictResponseSchema):
    generated_at: datetime
    total_tickets: int
    ready_tickets: int
    unassigned_tickets: int
    failed_tickets: int
    escalated_human_review_count: int
    escalated_human_review_rate: float
    qa_sampled_count: int
    qa_sample_rate: float
    avg_confidence: float
    active_ws_connections: int
    e2e_latency_ms: dict[str, float]
    cohere_asr: CohereModelTelemetry
    marbert_v2: MarbertModelTelemetry
    voicegate_orchestrator: OrchestratorModelTelemetry
