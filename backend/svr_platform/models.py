"""SQLAlchemy 2.0 ORM data model matching SVR-PRD-02 Section 11.4."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_users_org_email"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # admin | supervisor | agent
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    token_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    linked_agent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    role_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    token_version_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        Index("ix_agents_org_seed_order", "organization_id", "seed_order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    current_load: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    seed_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Voicemail(Base):
    __tablename__ = "voicemails"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_voicemails_org_idempotency"),
        Index("ix_voicemails_org_created", "organization_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)  # wav, mp3, m4a
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    sample_rate_hz: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="received")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    encrypted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    stt_v1_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_org_status_prio", "organization_id", "status", "priority_score", "created_at"),
        Index("ix_tickets_org_agent", "organization_id", "assigned_agent_id"),
        Index("ix_tickets_org_review", "organization_id", "needs_human_review"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    voicemail_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("voicemails.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="received")
    transcript: Mapped[str] = mapped_column(Text, nullable=False, default="")
    text_norm: Mapped[str] = mapped_column(Text, nullable=False, default="")
    language_mix: Mapped[str | None] = mapped_column(String(32), nullable=True)
    transcript_verification_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    complaint_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    complaint_urgency: Mapped[str | None] = mapped_column(String(32), nullable=True)
    customer_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    churn_risk: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # S4: track provenance ("model" or "human") per field
    label_sources: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    probabilities: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence_threshold_snapshot: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    priority_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queue_priority: Mapped[str | None] = mapped_column(String(32), nullable=True)
    priority_signals: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    priority_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")

    route_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    assigned_agent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )

    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    customer_request: Mapped[str] = mapped_column(Text, nullable=False, default="")
    suggested_script: Mapped[str] = mapped_column(Text, nullable=False, default="")

    needs_human_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    review_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_version: Mapped[str] = mapped_column(String(160), nullable=False, default="pending")

    stage_status: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    stage_timing_ms: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    processing_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        Index("ix_assignments_ticket", "ticket_id", "assigned_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    assigned_by: Mapped[str] = mapped_column(String(64), nullable=False)  # "system" or user id
    route_reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")  # active|released|completed


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_org_created", "organization_id", "created_at"),
        Index("ix_audit_entity", "entity_type", "entity_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)  # ticket|agent|user|setting|eval
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)  # "system" or user id/email
    old_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AIInteractionLog(Base):
    __tablename__ = "ai_interaction_logs"
    __table_args__ = (
        Index("ix_ai_logs_ticket", "ticket_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False)  # transcribe|verify_transcript|classify|priority|route|brief
    model: Mapped[str] = mapped_column(String(160), nullable=False)  # model name+version or "rules"
    input_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    output: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    split: Mapped[str] = mapped_column(String(32), nullable=False)  # validation | test
    model_version: Mapped[str] = mapped_column(String(160), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    guard_claim_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)


class SkillMapping(Base):
    __tablename__ = "skill_mappings"
    __table_args__ = (
        UniqueConstraint("organization_id", "category", name="uq_skill_mapping_org_cat"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    skill_name: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class ScriptTemplate(Base):
    __tablename__ = "script_templates"
    __table_args__ = (
        UniqueConstraint("organization_id", "category", name="uq_script_tpl_org_cat"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    template_ar: Mapped[str] = mapped_column(Text, nullable=False)
    template_en: Mapped[str] = mapped_column(Text, nullable=False)
    customer_request_ar: Mapped[str] = mapped_column(Text, nullable=False)
    customer_request_en: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    auto_routing_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    weekly_sample_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class MemoryEpisode(Base):
    """Layer 2 Episodic Memory storing verified/corrected voicemail episodes & embeddings."""

    __tablename__ = "memory_episodes"
    __table_args__ = (
        Index("ix_mem_episodes_org_source", "organization_id", "source"),
        Index("ix_mem_episodes_org_ticket", "organization_id", "ticket_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticket_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # train_seed | human_correction | agent_adjudicated | high_conf_verified
    trust_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    transcript: Mapped[str] = mapped_column(Text, nullable=False, default="")
    text_norm: Mapped[str] = mapped_column(Text, nullable=False, default="")
    embedding_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    marbert_labels: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    final_labels: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    adjudication_rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    was_corrected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class MemorySemanticEntry(Base):
    """Layer 3 Semantic Memory storing telecom taxonomy boundaries, dialect lexicon, and ASR confusions."""

    __tablename__ = "memory_semantic_entries"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_mem_semantic_org_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # taxonomy_boundary | dialect_lexicon | asr_confusion | routing_domain
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    related_categories: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.9)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class MemoryProceduralRule(Base):
    """Layer 4 Procedural Memory storing Reflexion rules and learned adjudication lessons."""

    __tablename__ = "memory_procedural_rules"
    __table_args__ = (
        Index("ix_mem_proc_org_active", "organization_id", "active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # adjudication_lesson | confusion_override | calibration_stat | stt_repair_rule
    trigger_pattern: Mapped[str] = mapped_column(String(160), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    support_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="seeded"
    )  # seeded | reflection | supervisor_feedback
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class TrainingFeedbackSample(Base):
    """Self-training data curator storing curated gold/silver/bronze labeled samples for continual tuning."""

    __tablename__ = "training_feedback_samples"
    __table_args__ = (
        Index("ix_train_feedback_org_tier", "organization_id", "quality_tier"),
        Index("ix_train_feedback_org_ticket", "organization_id", "ticket_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticket_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # human_correction | agent_adjudicated | high_conf_verified
    quality_tier: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # gold_human | silver_agent | bronze_high_conf
    transcript: Mapped[str] = mapped_column(Text, nullable=False, default="")
    text_norm: Mapped[str] = mapped_column(Text, nullable=False, default="")
    complaint_category: Mapped[str] = mapped_column(String(64), nullable=False)
    complaint_urgency: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_state: Mapped[str] = mapped_column(String(32), nullable=False)
    churn_risk: Mapped[str] = mapped_column(String(32), nullable=False)
    marbert_agreed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
