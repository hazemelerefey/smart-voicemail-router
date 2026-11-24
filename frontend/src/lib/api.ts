/* Secure cookie-authenticated API client with double-submit X-CSRF-Token */
/* Cookie-only session auth; zero browser web-storage token writes; zero secrets */

import type {
  AgentCreateRequest,
  AgentResponse,
  AgentUpdateRequest,
  AuditLogListResponse,
  AuthResponse,
  CorrectionApplyRequest,
  CorrectionPreviewRequest,
  CorrectionPreviewResponse,
  EvalRunResponse,
  MonitoringSummaryResponse,
  PatchTicketRequest,
  ScriptTemplateResponse,
  ScriptTemplateUpdateRequest,
  SettingsResponse,
  SettingsUpdateRequest,
  SkillMappingListResponse,
  TicketDetail,
  TicketListResponse,
  UserResponse,
  VoicemailUploadResponse,
} from "./types";

const CONFIGURED_BASE = (process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/+$/, "");

/** Build API URL: defaults to same-origin /api proxy via Next.js rewrites. */
export function apiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  if (CONFIGURED_BASE) {
    return `${CONFIGURED_BASE}${normalized}`;
  }
  return normalized;
}

/** Build WebSocket URL for /ws/queue. */
export function queueWsUrl(): string {
  if (CONFIGURED_BASE) {
    const wsBase = CONFIGURED_BASE.replace(/^http/, "ws");
    return `${wsBase}/ws/queue`;
  }
  if (typeof window === "undefined") {
    return "ws://127.0.0.1:8000/ws/queue";
  }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.hostname || "127.0.0.1";
  const port = window.location.port === "3000" ? "8000" : window.location.port;
  return `${proto}//${host}${port ? `:${port}` : ""}/ws/queue`;
}

/** Read a non-HttpOnly cookie by name (used for svr_csrf). */
export function readCookie(name: string): string {
  if (typeof document === "undefined") return "";
  const prefix = `${name}=`;
  const parts = document.cookie.split(";");
  for (const part of parts) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length));
    }
  }
  return "";
}

let inMemoryCsrfToken = "";

export function setCsrfTokenMemory(token: string): void {
  inMemoryCsrfToken = token;
}

function getCsrfToken(): string {
  return readCookie("svr_csrf") || inMemoryCsrfToken;
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) {
      return data.detail
        .map((item: { msg?: string; loc?: unknown[] }) => item?.msg || "Validation error")
        .join("; ");
    }
    if (typeof data?.message === "string") return data.message;
  } catch (err) {
    console.warn("Failed to parse JSON error body:", err);
  }
  return `Request failed with status ${res.status}`;
}

async function request<T>(
  path: string,
  options: {
    method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
    body?: unknown;
    formData?: FormData;
    headers?: Record<string, string>;
  } = {}
): Promise<T> {
  const method = options.method || "GET";
  const headers: Record<string, string> = { ...(options.headers || {}) };

  if (method !== "GET") {
    const csrf = getCsrfToken();
    if (csrf) {
      headers["X-CSRF-Token"] = csrf;
    }
  }

  let fetchBody: BodyInit | undefined;
  if (options.formData) {
    fetchBody = options.formData;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    fetchBody = JSON.stringify(options.body);
  }

  const res = await fetch(apiUrl(path), {
    method,
    headers,
    body: fetchBody,
    credentials: "include",
    cache: "no-store",
  });

  if (!res.ok) {
    const detail = await parseErrorDetail(res);
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

function buildQuery(params: Record<string, string | number | boolean | null | undefined>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") {
      usp.set(k, String(v));
    }
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export const api = {
  // Auth
  async login(email: string, password: string): Promise<AuthResponse> {
    const res = await request<AuthResponse>("/api/auth/login", {
      method: "POST",
      body: { email, password },
    });
    if (res.csrf_token) {
      setCsrfTokenMemory(res.csrf_token);
    }
    return res;
  },

  async logout(): Promise<{ message: string }> {
    const res = await request<{ message: string }>("/api/auth/logout", { method: "POST" });
    setCsrfTokenMemory("");
    return res;
  },

  me(): Promise<UserResponse> {
    return request<UserResponse>("/api/auth/me");
  },

  // Voicemails
  uploadVoicemail(file: File, idempotencyKey?: string): Promise<VoicemailUploadResponse> {
    const formData = new FormData();
    formData.append("file", file, file.name);
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers["Idempotency-Key"] = idempotencyKey;
    }
    return request<VoicemailUploadResponse>("/api/voicemails", {
      method: "POST",
      formData,
      headers,
    });
  },

  // Tickets
  listTickets(params: {
    limit?: number;
    cursor?: string | null;
    bucket?: string;
    category?: string;
    status?: string;
    assigned_agent_id?: string;
    needs_human_review?: boolean;
    review_reason?: string;
    q?: string;
  } = {}): Promise<TicketListResponse> {
    return request<TicketListResponse>(`/api/tickets${buildQuery(params)}`);
  },

  getTicket(ticketId: string): Promise<TicketDetail> {
    return request<TicketDetail>(`/api/tickets/${encodeURIComponent(ticketId)}`);
  },

  previewCorrection(
    ticketId: string,
    payload: CorrectionPreviewRequest
  ): Promise<CorrectionPreviewResponse> {
    return request<CorrectionPreviewResponse>(
      `/api/tickets/${encodeURIComponent(ticketId)}/preview-correction`,
      { method: "POST", body: payload }
    );
  },

  applyCorrection(ticketId: string, payload: CorrectionApplyRequest): Promise<TicketDetail> {
    return request<TicketDetail>(`/api/tickets/${encodeURIComponent(ticketId)}/correct`, {
      method: "POST",
      body: payload,
    });
  },

  patchTicket(ticketId: string, payload: PatchTicketRequest): Promise<TicketDetail> {
    return request<TicketDetail>(`/api/tickets/${encodeURIComponent(ticketId)}`, {
      method: "PATCH",
      body: payload,
    });
  },

  // Agents
  listAgents(): Promise<AgentResponse[]> {
    return request<AgentResponse[]>("/api/agents");
  },

  createAgent(payload: AgentCreateRequest): Promise<AgentResponse> {
    return request<AgentResponse>("/api/agents", { method: "POST", body: payload });
  },

  updateAgent(agentId: string, payload: AgentUpdateRequest): Promise<AgentResponse> {
    return request<AgentResponse>(`/api/agents/${encodeURIComponent(agentId)}`, {
      method: "PATCH",
      body: payload,
    });
  },

  // Settings, Skills, Templates
  getSettings(): Promise<SettingsResponse> {
    return request<SettingsResponse>("/api/settings");
  },

  updateSettings(payload: SettingsUpdateRequest): Promise<SettingsResponse> {
    return request<SettingsResponse>("/api/settings", { method: "PATCH", body: payload });
  },

  getSkillMappings(): Promise<SkillMappingListResponse> {
    return request<SkillMappingListResponse>("/api/settings/skills");
  },

  updateSkillMappings(mappings: Record<string, string>): Promise<SkillMappingListResponse> {
    return request<SkillMappingListResponse>("/api/settings/skills", {
      method: "PUT",
      body: { mappings },
    });
  },

  getTemplates(): Promise<ScriptTemplateResponse[]> {
    return request<ScriptTemplateResponse[]>("/api/settings/templates");
  },

  updateTemplate(
    category: string,
    payload: ScriptTemplateUpdateRequest
  ): Promise<ScriptTemplateResponse> {
    return request<ScriptTemplateResponse>(
      `/api/settings/templates/${encodeURIComponent(category)}`,
      { method: "PUT", body: payload }
    );
  },

  // Evaluation & Monitoring
  getEvalRuns(): Promise<EvalRunResponse[]> {
    return request<EvalRunResponse[]>("/api/evaluation/runs");
  },

  getMonitoringSummary(): Promise<MonitoringSummaryResponse> {
    return request<MonitoringSummaryResponse>("/api/monitoring/summary");
  },

  // Audit Log
  listAuditLogs(params: {
    limit?: number;
    cursor?: string | null;
    entity_type?: string;
    entity_id?: string;
    action?: string;
    actor?: string;
  } = {}): Promise<AuditLogListResponse> {
    return request<AuditLogListResponse>(`/api/audit-logs${buildQuery(params)}`);
  },

  auditExportUrl(format: "csv" | "json"): string {
    return apiUrl(`/api/audit-logs/export?format=${format}`);
  },
};
