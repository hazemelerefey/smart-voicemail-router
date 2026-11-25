"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  IconAlertCircle,
  IconAlertTriangle,
  IconArrowLeft,
  IconArrowRight,
  IconCheck,
  IconEdit,
  IconRefresh,
  IconUserPlus,
} from "@tabler/icons-react";
import { AppShell } from "@/components/AppShell";
import { useApp } from "@/components/AppProvider";
import { BucketText, TicketStatusText, bucketColorClass } from "@/components/StatusLabel";
import { api, ApiError } from "@/lib/api";
import {
  UI_COPY,
  labelForCategory,
  labelForChurn,
  labelForReviewReason,
  labelForState,
  labelForUrgency,
} from "@/lib/i18n";
import { REVIEW_REASONS, formatPct, formatUtcTimestamp } from "@/lib/taxonomy";
import type { AgentResponse, TicketListResponse } from "@/lib/types";

export default function ReviewQueuePage() {
  const { locale, wsVersion } = useApp();
  const t = UI_COPY[locale];

  const [reasonFilter, setReasonFilter] = useState<string>("");
  const [cursor, setCursor] = useState<string | null>(null);
  const [data, setData] = useState<TicketListResponse | null>(null);
  const [agents, setAgents] = useState<AgentResponse[]>([]);
  const [selectedAgents, setSelectedAgents] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadQueue = useCallback(async () => {
    setError(null);
    try {
      const res = await api.listTickets({
        limit: 20,
        cursor: cursor || undefined,
        needs_human_review: true,
        review_reason: reasonFilter || undefined,
      });
      setData(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load Human Routing Queue.");
    } finally {
      setLoading(false);
    }
  }, [reasonFilter, cursor]);

  useEffect(() => {
    setLoading(true);
    void loadQueue();
  }, [loadQueue]);

  useEffect(() => {
    if (wsVersion > 0) {
      void loadQueue();
    }
  }, [wsVersion, loadQueue]);

  useEffect(() => {
    api
      .listAgents()
      .then((list) => setAgents(list.filter((a) => a.active)))
      .catch((err) => console.warn("Failed to load agents for review queue:", err));
  }, []);

  const handleQuickAssign = async (ticketId: string) => {
    const agentId = selectedAgents[ticketId];
    if (!agentId) {
      setError(
        locale === "ar"
          ? "اختر موظفا أولا لتوجيه التذكرة."
          : "Select an agent first before assigning."
      );
      return;
    }
    setBusyId(ticketId);
    setError(null);
    setNotice(null);
    try {
      await api.patchTicket(ticketId, {
        assigned_agent_id: agentId,
        needs_human_review: false,
      });
      setNotice(
        locale === "ar"
          ? "تم تعيين الموظف وإخراج التذكرة من قائمة المراجعة."
          : "Agent assigned and ticket cleared from Human Routing Queue."
      );
      await loadQueue();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to assign ticket.");
    } finally {
      setBusyId(null);
    }
  };

  const handleResolve = async (ticketId: string) => {
    setBusyId(ticketId);
    setError(null);
    setNotice(null);
    try {
      await api.patchTicket(ticketId, {
        status: "resolved",
        needs_human_review: false,
      });
      setNotice(
        locale === "ar"
          ? "تم حل التذكرة وإغلاق طلب المراجعة."
          : "Ticket marked resolved."
      );
      await loadQueue();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to resolve ticket.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <AppShell
      allowedRoles={["supervisor", "admin"]}
      reviewBadgeCount={data?.human_review_count}
    >
      <div className="page-head">
        <div>
          <h1>{locale === "ar" ? "قائمة المراجعة والتوجيه البشري" : "Human Routing Queue"}</h1>
          <p className="sub" style={{ margin: 0 }}>
            {locale === "ar"
              ? "التذاكر ذات الثقة المنخفضة أو غير المعينة أو عينات الجودة التي تتطلب تدخل المشرف."
              : "Flagged and unassigned subscriber voicemails requiring supervisor verification, correction, or manual assignment."}
          </p>
        </div>
        <div className="page-head-actions">
          <button
            type="button"
            className="btn primary"
            onClick={() => void loadQueue()}
            disabled={loading}
          >
            <IconRefresh size={16} stroke={1.8} aria-hidden="true" />
            <span>{locale === "ar" ? "تحديث القائمة" : "Refresh Queue"}</span>
          </button>
        </div>
      </div>

      <div className="toolbar">
        <label className="field" style={{ minWidth: 260 }}>
          <span>{t.filterReason}</span>
          <select
            value={reasonFilter}
            onChange={(ev) => {
              setReasonFilter(ev.target.value);
              setCursor(null);
            }}
          >
            <option value="">{t.allOption}</option>
            {REVIEW_REASONS.map((r) => (
              <option key={r} value={r}>
                {labelForReviewReason(r, locale)}
              </option>
            ))}
          </select>
        </label>
        <div className="spacer" />
        <span className="muted num" style={{ fontSize: 13 }}>
          {locale === "ar"
            ? `إجمالي قيد المراجعة: ${data?.total ?? 0}`
            : `Flagged tickets: ${data?.total ?? 0}`}
        </span>
      </div>

      {error && (
        <div className="alert error" role="alert">
          <IconAlertCircle size={18} stroke={1.8} aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {notice && (
        <div className="alert ok" role="status">
          <IconCheck size={18} stroke={1.8} aria-hidden="true" />
          <span>{notice}</span>
        </div>
      )}

      {loading && !data ? (
        <p className="loading-state">{t.loading}</p>
      ) : !data || data.items.length === 0 ? (
        <div className="empty-state">
          <p style={{ margin: 0 }}>
            {locale === "ar"
              ? "لا توجد تذاكر في قائمة المراجعة البشرية حاليا."
              : "The Human Routing Queue is clear for the selected filter."}
          </p>
        </div>
      ) : (
        <>
          <div style={{ display: "grid", gap: 12 }}>
            {data.items.map((ticket) => {
              const isBusy = busyId === ticket.id;
              return (
                <article className="card" key={ticket.id} style={{ margin: 0 }}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      justifyContent: "space-between",
                      gap: 12,
                      flexWrap: "wrap",
                    }}
                  >
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                        <span
                          className={`num ${bucketColorClass(ticket.queue_priority)}`}
                          style={{ fontSize: 18, fontWeight: 700 }}
                        >
                          {ticket.priority_score !== null ? `P${ticket.priority_score}` : "P-"}
                        </span>
                        <strong>{labelForCategory(ticket.complaint_category, locale)}</strong>
                        <span className="mono muted">#{ticket.id.slice(0, 8)}</span>
                        <span className="status-inline high-text">
                          <IconAlertTriangle size={15} stroke={2} aria-hidden="true" />
                          {ticket.review_reason
                            ? labelForReviewReason(ticket.review_reason, locale)
                            : locale === "ar"
                              ? "مراجعة بشرية"
                              : "Human Review"}
                        </span>
                      </div>
                      <p className="muted" style={{ margin: "6px 0 4px" }} dir="auto">
                        {ticket.summary || ticket.route_reason || "-"}
                      </p>
                      <div className="ticket-meta">
                        <span>
                          {locale === "ar" ? "الاستعجال:" : "Urgency:"}{" "}
                          <strong>{labelForUrgency(ticket.complaint_urgency, locale)}</strong>
                        </span>
                        <span>
                          {locale === "ar" ? "الحالة:" : "State:"}{" "}
                          <strong>{labelForState(ticket.customer_state, locale)}</strong>
                        </span>
                        <span>
                          {locale === "ar" ? "الإلغاء:" : "Churn:"}{" "}
                          <strong>{labelForChurn(ticket.churn_risk, locale)}</strong>
                        </span>
                        <span>
                          {locale === "ar" ? "الثقة:" : "Conf:"}{" "}
                          <strong className="num">{formatPct(ticket.confidence)}</strong> /{" "}
                          <span className="num">{formatPct(ticket.confidence_threshold_snapshot, 0)}</span>
                        </span>
                        <span className="num">{formatUtcTimestamp(ticket.created_at, locale)}</span>
                      </div>
                      {ticket.route_reason && ticket.summary && (
                        <div className="faint" style={{ fontSize: 12, marginTop: 4 }}>
                          {locale === "ar" ? "سياق خط المعالجة:" : "Pipeline context:"}{" "}
                          {ticket.route_reason}
                        </div>
                      )}
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
                      <TicketStatusText status={ticket.status} locale={locale} />
                      <BucketText bucket={ticket.queue_priority} locale={locale} />
                    </div>
                  </div>

                  <div
                    style={{
                      marginTop: 12,
                      paddingTop: 12,
                      borderTop: "1px solid var(--line)",
                      display: "flex",
                      alignItems: "flex-end",
                      gap: 8,
                      flexWrap: "wrap",
                    }}
                  >
                    <Link href={`/tickets/${ticket.id}`} className="btn">
                      <IconEdit size={16} stroke={1.8} aria-hidden="true" />
                      <span>
                        {locale === "ar" ? "مراجعة وتصحيح التصنيف" : "Review & Correct"}
                      </span>
                    </Link>

                    <label className="field" style={{ flex: "1 1 200px" }}>
                      <span className="sr-only">Select agent</span>
                      <select
                        aria-label={locale === "ar" ? "تعيين موظف" : "Assign agent"}
                        value={selectedAgents[ticket.id] || ""}
                        onChange={(ev) =>
                          setSelectedAgents((prev) => ({ ...prev, [ticket.id]: ev.target.value }))
                        }
                        disabled={isBusy}
                      >
                        <option value="">
                          {locale === "ar" ? "اختر موظف للتعيين..." : "Select agent to assign..."}
                        </option>
                        {agents.map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.name} ({a.current_load}/{a.capacity})
                          </option>
                        ))}
                      </select>
                    </label>

                    <button
                      type="button"
                      className="btn"
                      disabled={isBusy || !selectedAgents[ticket.id]}
                      onClick={() => void handleQuickAssign(ticket.id)}
                    >
                      <IconUserPlus size={16} stroke={1.8} aria-hidden="true" />
                      <span>{locale === "ar" ? "تعيين" : "Assign"}</span>
                    </button>

                    {ticket.status !== "resolved" && ticket.status !== "closed" && (
                      <button
                        type="button"
                        className="btn"
                        disabled={isBusy}
                        onClick={() => void handleResolve(ticket.id)}
                      >
                        <IconCheck size={16} stroke={1.8} aria-hidden="true" />
                        <span>{locale === "ar" ? "تم الحل" : "Resolve"}</span>
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>

          <div className="pager">
            <span>
              {locale === "ar"
                ? `عرض ${data.items.length} من ${data.total}`
                : `Showing ${data.items.length} of ${data.total}`}
            </span>
            <div className="pager-actions">
              <button
                type="button"
                className="btn"
                disabled={!data.prev_cursor}
                onClick={() => setCursor(data.prev_cursor)}
              >
                <IconArrowLeft size={16} stroke={1.8} aria-hidden="true" />
                <span>{t.previous}</span>
              </button>
              <button
                type="button"
                className="btn"
                disabled={!data.next_cursor}
                onClick={() => setCursor(data.next_cursor)}
              >
                <span>{t.next}</span>
                <IconArrowRight size={16} stroke={1.8} aria-hidden="true" />
              </button>
            </div>
          </div>
        </>
      )}
    </AppShell>
  );
}
