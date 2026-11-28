/* Strict TypeScript types aligned with backend/svr_platform/api/schemas.py */

export type UserRole = "admin" | "supervisor" | "agent";

export interface UserResponse {
  id: string;
  organization_id: string;
  email: string;
  full_name: string;
  role: UserRole;
  active: boolean;
  linked_agent_id: string | null;
  created_at: string;
}

export interface AuthResponse {
  user: UserResponse;
  csrf_token: string;
  message: string;
}

export interface VoicemailUploadResponse {
  voicemail_id: string;
  ticket_id: string;
  status: string;
  deduplicated: boolean;
  file_name: string;
  format: string;
  size_bytes: number;
  duration_seconds: number;
  recommendation_note: string | null;
  idempotency_key: string;
}

export interface AIInteractionLogResponse {
  id: string;
  ticket_id: string;
  stage: string;
  model: string;
  input_ref: string;
  output: Record<string, unknown>;
  latency_ms: number;
  created_at: string;
}

export interface AuditEventResponse {
  id: string;
  organization_id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor: string;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditEventResponse[];
  limit: number;
  next_cursor: string | null;
  prev_cursor: string | null;
  total: number;
}

export interface TicketSummary {
  id: string;
  voicemail_id: string;
  status: string;
  file_name: string;
  duration_seconds: number;
  summary: string;
  customer_request: string;
  suggested_script: string;
  complaint_category: string | null;
  complaint_urgency: string | null;
  customer_state: string | null;
  churn_risk: string | null;
  confidence: number;
  confidence_threshold_snapshot: number;
  priority_score: number | null;
  queue_priority: string | null;
  assigned_agent_id: string | null;
  assigned_agent_name: string | null;
  route_reason: string;
  needs_human_review: boolean;
  review_reason: string | null;
  language_mix: string | null;
  stage_status: Record<string, string>;
  processing_ms: number;
  created_at: string;
  updated_at: string;
}

export interface TicketListResponse {
  items: TicketSummary[];
  limit: number;
  next_cursor: string | null;
  prev_cursor: string | null;
  total: number;
  counts_by_bucket: Record<string, number>;
  counts_by_status: Record<string, number>;
  human_review_count: number;
}

export interface TranscriptVerificationChange {
  from: string;
  to: string;
  reason?: string;
}

export interface TranscriptVerificationRound {
  round: number;
  thinking: string;
  input_text: string;
  candidate_text: string;
  confidence: number;
  is_coherent: boolean;
  accepted: boolean;
  critique?: string | null;
  changes?: TranscriptVerificationChange[];
}

export interface OrchestratorAdjudicationSummary {
  mode: string;
  marbert_original_labels: Record<string, string | null>;
  agent_final_labels: Record<string, string | null>;
  label_sources: Record<string, string>;
  changed_fields: string[];
  flagged_fields: string[];
  trigger_reasons: string[];
  calibrated_confidence: number;
  reasoning: string;
  learned_lesson: string;
  memory_episodes_used: number;
  max_episode_similarity: number;
  semantic_rules_used: number;
  procedural_rules_used: number;
  resolved_gate_uncertainty: boolean;
  escalate_to_human: boolean;
  latency_ms: number;
  error?: string;
}

export interface TranscriptVerificationReport {
  agent_name: string;
  model: string;
  backend_used: string;
  status: string;
  raw_text: string;
  corrected_text: string;
  correction_applied: boolean;
  rounds_run: number;
  confidence: number;
  convergence_reason: string;
  needs_human_review: boolean;
  review_reason?: string | null;
  signal_summary?: Record<string, unknown>;
  changes: TranscriptVerificationChange[];
  trace: TranscriptVerificationRound[];
  orchestrator_adjudication?: OrchestratorAdjudicationSummary | null;
  latency_ms: number;
  error?: string;
}

export interface TicketDetail {
  id: string;
  voicemail_id: string;
  organization_id: string;
  status: string;
  file_name: string;
  format: string;
  size_bytes: number;
  duration_seconds: number;
  audio_url: string;
  transcript: string;
  text_norm: string;
  language_mix: string | null;
  stt_v1_json: Record<string, unknown> | null;
  transcript_verification?: TranscriptVerificationReport | null;
  complaint_category: string | null;
  complaint_urgency: string | null;
  customer_state: string | null;
  churn_risk: string | null;
  label_sources: Record<string, string>;
  probabilities: Record<string, Record<string, number>>;
  confidence: number;
  confidence_threshold_snapshot: number;
  priority_score: number | null;
  queue_priority: string | null;
  priority_signals: Record<string, unknown>;
  priority_reason: string;
  route_reason: string;
  assigned_agent_id: string | null;
  assigned_agent_name: string | null;
  summary: string;
  customer_request: string;
  suggested_script: string;
  needs_human_review: boolean;
  review_reason: string | null;
  model_version: string;
  stage_status: Record<string, string>;
  stage_timing_ms: Record<string, number>;
  processing_ms: number;
  config_snapshot: Record<string, unknown>;
  ai_logs: AIInteractionLogResponse[];
  audit_events: AuditEventResponse[];
  created_at: string;
  updated_at: string;
}

export interface CorrectionPreviewRequest {
  complaint_category?: string | null;
  complaint_urgency?: string | null;
  customer_state?: string | null;
  churn_risk?: string | null;
}

export interface CorrectionPreviewResponse {
  proposed_labels: Record<string, string | null>;
  priority_score: number | null;
  queue_priority: string | null;
  priority_signals: Record<string, unknown>;
  priority_reason: string;
  recommended_agent_id: string | null;
  recommended_agent_name: string | null;
  required_skill: string | null;
  route_reason: string;
  summary: string;
  customer_request: string;
  suggested_script: string;
  needs_human_review: boolean;
  review_reason: string | null;
}

export interface CorrectionApplyRequest extends CorrectionPreviewRequest {
  apply_recommended_route?: boolean;
  clear_human_review?: boolean;
  note?: string | null;
}

export interface PatchTicketRequest {
  status?: string | null;
  assigned_agent_id?: string | null;
  unassign?: boolean;
  needs_human_review?: boolean | null;
  review_reason?: string | null;
  note?: string | null;
}

export interface AgentResponse {
  id: string;
  organization_id: string;
  name: string;
  skills: string[];
  capacity: number;
  current_load: number;
  available: boolean;
  active: boolean;
  seed_order: number;
  created_at: string;
  updated_at: string;
}

export interface AgentCreateRequest {
  name: string;
  skills: string[];
  capacity: number;
  available: boolean;
  seed_order: number;
}

export interface AgentUpdateRequest {
  name?: string;
  skills?: string[];
  capacity?: number;
  available?: boolean;
  active?: boolean;
  seed_order?: number;
}

export interface SkillMappingItem {
  category: string;
  skill_name: string;
  updated_at: string | null;
}

export interface SkillMappingListResponse {
  mappings: SkillMappingItem[];
}

export interface SettingsResponse {
  organization_id: string;
  confidence_threshold: number;
  auto_routing_enabled: boolean;
  retention_days: number;
  weekly_sample_rate: number;
  updated_at: string;
}

export interface SettingsUpdateRequest {
  confidence_threshold?: number;
  auto_routing_enabled?: boolean;
  retention_days?: number;
  weekly_sample_rate?: number;
}

export interface ScriptTemplateResponse {
  category: string;
  template_ar: string;
  template_en: string;
  customer_request_ar: string;
  customer_request_en: string;
  version: number;
  updated_at: string;
}

export interface ScriptTemplateUpdateRequest {
  template_ar: string;
  template_en: string;
  customer_request_ar: string;
  customer_request_en: string;
}

export interface EvalRunResponse {
  id: string;
  organization_id: string;
  dataset_version: string;
  split: string;
  model_version: string;
  config: Record<string, unknown>;
  metrics: Record<string, unknown>;
  guard_claim_id: string | null;
  created_at: string;
  created_by: string;
}

export interface MonitoringAlert {
  code: string;
  severity: string;
  message: string;
  value: number;
  threshold: number;
}

export interface MonitoringSummaryResponse {
  total_tickets: number;
  tickets_last_24h: intLike;
  tickets_by_status: Record<string, number>;
  classification_distribution: Record<string, Record<string, number>>;
  confidence_histogram: Array<{ bucket?: string; label?: string; range?: string; count: number }>;
  human_review_rate: number;
  human_review_rate_24h: number;
  qa_sampled_count: number;
  qa_sample_rate: number;
  processing_success_rate: number;
  end_to_end_latency_ms: Record<string, number>;
  end_to_end_latency_24h_ms: Record<string, number>;
  stage_latency_ms: Record<string, Record<string, number>>;
  alerts: MonitoringAlert[];
  auto_routing_enabled: boolean;
  active_ws_connections: number;
}

export interface AgentMemoryLessonItem {
  id: string;
  rule_type: string;
  trigger_pattern: string;
  instruction: string;
  support_count: number;
  success_count: number;
  source: string;
  updated_at: string;
}

export interface AgentMemoryStatsResponse {
  organization_id: string;
  memory_enabled: boolean;
  adjudicator_enabled: boolean;
  embed_model: string;
  episodic_total: number;
  episodic_by_source: Record<string, number>;
  semantic_entries_count: number;
  procedural_rules_active_count: number;
  training_feedback_total: number;
  training_feedback_by_tier: Record<string, number>;
  recent_procedural_lessons: AgentMemoryLessonItem[];
}

export interface CohereRecentResult {
  ticket_id: string;
  file_name: string;
  transcript_preview: string;
  min_avg_logprob: number | null;
  max_no_speech_prob: number | null;
  needs_review: boolean;
  latency_ms: number;
  status: string;
  created_at: string;
}

export interface CohereModelTelemetry {
  name: string;
  model_id: string;
  backend: string;
  device: string;
  status: string;
  total_runs: number;
  success_rate: number;
  latency_ms: Record<string, number>;
  avg_logprob: number | null;
  avg_no_speech_prob: number | null;
  flagged_rate: number;
  recent_results: CohereRecentResult[];
}

export interface MarbertRecentResult {
  ticket_id: string;
  file_name: string;
  complaint_category: string | null;
  complaint_urgency: string | null;
  customer_state: string | null;
  churn_risk: string | null;
  confidence: number;
  agreed_with_orchestrator: boolean;
  latency_ms: number;
  status: string;
  created_at: string;
}

export interface MarbertModelTelemetry {
  name: string;
  model_id: string;
  backend: string;
  checkpoints_ready: boolean;
  status: string;
  total_runs: number;
  avg_confidence: number;
  below_threshold_rate: number;
  latency_ms: Record<string, number>;
  per_head_avg_confidence: Record<string, number>;
  category_distribution: Record<string, number>;
  recent_results: MarbertRecentResult[];
}

export interface OrchestratorRecentResult {
  ticket_id: string;
  file_name: string;
  gate_status: string;
  adjudicator_mode: string;
  changed_fields: string[];
  memory_episodes_used: number;
  max_episode_similarity: number;
  calibrated_confidence: number;
  assigned_agent_name: string | null;
  reasoning_preview: string;
  latency_ms: number;
  created_at: string;
}

export interface OrchestratorModelTelemetry {
  name: string;
  model_id: string;
  embed_model: string;
  status: string;
  total_runs: number;
  fast_path_count: number;
  repaired_count: number;
  uncertain_count: number;
  fast_verified_count: number;
  adjudicated_count: number;
  override_count: number;
  agreement_rate: number;
  verify_latency_ms: Record<string, number>;
  adjudicate_latency_ms: Record<string, number>;
  memory: AgentMemoryStatsResponse;
  recent_results: OrchestratorRecentResult[];
}

export interface ModelsTelemetryResponse {
  generated_at: string;
  total_tickets: number;
  ready_tickets: number;
  unassigned_tickets: number;
  failed_tickets: number;
  escalated_human_review_count: number;
  escalated_human_review_rate: number;
  qa_sampled_count: number;
  qa_sample_rate: number;
  avg_confidence: number;
  active_ws_connections: number;
  e2e_latency_ms: Record<string, number>;
  cohere_asr: CohereModelTelemetry;
  marbert_v2: MarbertModelTelemetry;
  voicegate_orchestrator: OrchestratorModelTelemetry;
}

type intLike = number;

export interface QueueWsEvent {
  type: string;
  ticket_id?: string;
  status?: string;
  stage?: string;
  assigned_agent_id?: string | null;
  auto_routing_enabled?: boolean;
  [key: string]: unknown;
}
