/* Fixed SVR telecom taxonomy and priority helpers (SVR-PRD-02) */

export const COMPLAINT_CATEGORIES = [
  "network_and_connectivity",
  "billing_and_charges",
  "balance_and_data",
  "app_and_account",
  "branch_and_staff",
  "no_reply_or_long_wait",
  "cancellation_request",
  "thanks_or_praise",
  "other",
  "offers_and_packages",
  "sim_services",
] as const;

export type ComplaintCategory = (typeof COMPLAINT_CATEGORIES)[number];

export const COMPLAINT_URGENCIES = ["high", "medium", "low"] as const;
export type ComplaintUrgency = (typeof COMPLAINT_URGENCIES)[number];

export const CUSTOMER_STATES = [
  "calm",
  "frustrated",
  "mad",
  "satisfied",
  "unclear",
] as const;
export type CustomerState = (typeof CUSTOMER_STATES)[number];

export const CHURN_RISKS = ["at_risk", "not_at_risk"] as const;
export type ChurnRisk = (typeof CHURN_RISKS)[number];

export const QUEUE_BUCKETS = ["urgent", "high", "normal", "low"] as const;
export type QueueBucket = (typeof QUEUE_BUCKETS)[number];

export const TICKET_STATUSES = [
  "received",
  "processing",
  "ready",
  "unassigned",
  "in_progress",
  "resolved",
  "closed",
  "failed",
] as const;
export type TicketStatus = (typeof TICKET_STATUSES)[number];

export const REVIEW_REASONS = [
  "low_confidence",
  "uncertain_transcript",
  "missing_label",
  "invalid_label",
  "no_eligible_agent",
  "processing_error",
  "kill_switch_active",
  "supervisor_requested",
  "weekly_quality_sample",
] as const;
export type ReviewReason = (typeof REVIEW_REASONS)[number];

export const TELECOM_SKILLS = ["Network", "Billing", "General"] as const;
export type TelecomSkill = (typeof TELECOM_SKILLS)[number];

export const AI9_THRESHOLDS: Record<string, { threshold: number; validated: number }> = {
  complaint_category: { threshold: 0.75, validated: 0.7872 },
  complaint_urgency: { threshold: 0.70, validated: 0.7211 },
  customer_state: { threshold: 0.70, validated: 0.7471 },
  churn_risk: { threshold: 0.80, validated: 0.8277 },
  combined: { threshold: 0.75, validated: 0.7708 },
};

export const ALLOWED_TRANSITIONS: Record<string, readonly string[]> = {
  received: ["processing", "failed"],
  processing: ["ready", "unassigned", "failed"],
  ready: ["in_progress", "resolved", "unassigned"],
  unassigned: ["ready", "in_progress", "resolved"],
  in_progress: ["resolved"],
  resolved: ["closed"],
  closed: [],
  failed: ["unassigned"],
};

export function formatUtcTimestamp(iso: string | null | undefined, locale: "en" | "ar"): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(locale === "ar" ? "ar-EG" : "en-GB", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

export function formatPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "-";
  return `${seconds.toFixed(1)}s`;
}

export function formatMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return "-";
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`;
  return `${Math.round(ms)}ms`;
}
