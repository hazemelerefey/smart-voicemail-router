"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  IconAlertCircle,
  IconAlertTriangle,
  IconArrowLeft,
  IconArrowRight,
  IconBellRinging,
  IconMicrophone,
  IconRefresh,
  IconSearch,
} from "@tabler/icons-react";
import { AppShell } from "@/components/AppShell";
import { useApp } from "@/components/AppProvider";
import { BucketText, TicketStatusText } from "@/components/StatusLabel";
import { VoicemailIntakeDrawer } from "@/components/VoicemailIntakeDrawer";
import { api, ApiError } from "@/lib/api";
import {
  UI_COPY,
  labelForBucket,
  labelForCategory,
  labelForReviewReason,
  labelForStatus,
} from "@/lib/i18n";
import {
  COMPLAINT_CATEGORIES,
  QUEUE_BUCKETS,
  TICKET_STATUSES,
  formatDuration,
  formatPct,
  formatUtcTimestamp,
} from "@/lib/taxonomy";
import type { AgentResponse, TicketListResponse } from "@/lib/types";

const SEGMENT_CLASS: Record<string, string> = {
  urgent: "seg-urgent",
  high: "seg-high",
  normal: "seg-normal",
  low: "seg-low",
};

export default function DashboardPage() {
  const { locale, wsVersion } = useApp();
  const t = UI_COPY[locale];
  const isAr = locale === "ar";

  const [bucket, setBucket] = useState<string>("");
  const [category, setCategory] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [agentId, setAgentId] = useState<string>("");
  const [searchInput, setSearchInput] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [cursor, setCursor] = useState<string | null>(null);

  const [data, setData] = useState<TicketListResponse | null>(null);
  const [agents, setAgents] = useState<AgentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [intakeOpen, setIntakeOpen] = useState(false);

  const fetchQueue = useCallback(async () => {
    setError(null);
    try {
      const res = await api.listTickets({
        limit: 20,
        cursor: cursor || undefined,
        bucket: bucket || undefined,
        category: category || undefined,
        status: statusFilter || undefined,
        assigned_agent_id: agentId || undefined,
        q: searchQuery || undefined,
      });
      setData(res);
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : "Failed to load callback queue.";
      setError(detail);
    } finally {
      setLoading(false);
    }
  }, [bucket, category, statusFilter, agentId, searchQuery, cursor]);

  useEffect(() => {
    setLoading(true);
    void fetchQueue();
  }, [fetchQueue]);

  // Real-time queue refresh when WebSocket pushes ticket/stage updates
  useEffect(() => {
    if (wsVersion > 0) {
      void fetchQueue();
    }
  }, [wsVersion, fetchQueue]);

  useEffect(() => {
    api
      .listAgents()
      .then(setAgents)
      .catch((err) => console.warn("Failed to load agents for filter:", err));
  }, []);

  const handleSearchSubmit = (ev: React.FormEvent) => {
    ev.preventDefault();
    setCursor(null);
    setSearchQuery(searchInput.trim());
  };

  const resetFilters = () => {
    setBucket("");
    setCategory("");
    setStatusFilter("");
    setAgentId("");
    setSearchInput("");
    setSearchQuery("");
    setCursor(null);
  };

  const counts = data?.counts_by_bucket || {};
  const totalAll = Object.values(counts).reduce((a, b) => a + b, 0);
  const urgentCount = counts.urgent ?? 0;
  const inPipeline =
    (data?.counts_by_status?.processing ?? 0) + (data?.counts_by_status?.received ?? 0);
  const unassignedCount = data?.counts_by_status?.unassigned ?? 0;

  return (
    <AppShell allowedRoles={["supervisor", "admin"]} reviewBadgeCount={data?.human_review_count}>
      <div className="page-head">
        <div>
          <h1>{isAr ? "قائمة معاودة الاتصال" : "Subscriber Callback Queue"}</h1>
          <p className="sub" style={{ margin: 0 }}>
            {isAr
              ? "الرسائل الصوتية مرتبة حسب الأولوية (العاجل أولا) مع تحديث مباشر لحالة المعالجة."
              : "Prioritized subscriber voicemails ordered urgent-first with real-time pipeline status."}
          </p>
        </div>

        <div className="page-head-actions">
          <button type="button" className="btn" onClick={() => void fetchQueue()} disabled={loading}>
            <IconRefresh size={17} stroke={1.8} aria-hidden="true" />
            <span>{isAr ? "تحديث" : "Refresh"}</span>
          </button>
          <button type="button" className="btn primary" onClick={() => setIntakeOpen(true)}>
            <IconMicrophone size={17} stroke={1.8} aria-hidden="true" />
            <span>{t.intakeOpen}</span>
          </button>
        </div>
      </div>

      {/* Overview: one hero, one ledger */}
      <section className="overview" aria-label={isAr ? "ملخص القائمة" : "Queue overview"}>
        <div className="hero-tile">
          <div className="hero-label">
            <IconBellRinging size={16} stroke={1.9} aria-hidden="true" />
            <span>{isAr ? "عاجل الآن" : "Urgent now"}</span>
          </div>
          <div className="hero-number num">{data ? urgentCount : "-"}</div>
          <p className="hero-note">
            {isAr
              ? "درجة الأولوية 6: استعجال عالي، خطر فقد العميل، وحالة العميل غاضب أو منزعج."
              : "Priority score 6: high urgency, churn at risk, and customer state mad or frustrated."}
          </p>

          <div
            className="dist-bar"
            role="img"
            aria-label={
              isAr ? "توزيع التذاكر حسب درجة الأولوية" : "Ticket distribution by priority bucket"
            }
          >
            {QUEUE_BUCKETS.map((b) =>
              (counts[b] ?? 0) > 0 ? (
                <span
                  key={b}
                  className={`dist-seg ${SEGMENT_CLASS[b]}`}
                  style={{ flexGrow: counts[b] }}
                />
              ) : null
            )}
          </div>
          <dl className="dist-legend">
            {QUEUE_BUCKETS.map((b) => (
              <div key={b} className={`dist-item ${SEGMENT_CLASS[b]}`}>
                <dd className="num">{counts[b] ?? 0}</dd>
                <dt>{labelForBucket(b, locale)}</dt>
              </div>
            ))}
          </dl>
        </div>

        <div className="ledger">
          <div className="ledger-row">
            <div className="ledger-label">{isAr ? "إجمالي القائمة" : "Total tickets"}</div>
            <div className="ledger-sub">
              {isAr ? "مطابق للتصفية الحالية" : "Matching the active filters"}
            </div>
            <div className="ledger-value num">{data ? data.total : "-"}</div>
          </div>
          <div className="ledger-row">
            <div className="ledger-label">
              {isAr ? "المراجعة والتوجيه البشري" : "Human Routing Queue"}
            </div>
            <div className="ledger-sub">
              <Link href="/review-queue">{isAr ? "فتح قائمة المراجعة" : "Open review queue"}</Link>
            </div>
            <div className="ledger-value num high-text">{data?.human_review_count ?? 0}</div>
          </div>
          <div className="ledger-row">
            <div className="ledger-label">{isAr ? "قيد المعالجة" : "In pipeline"}</div>
            <div className="ledger-sub">
              {isAr ? "تفريغ وتصنيف جاري الآن" : "Transcription and classification running"}
            </div>
            <div className="ledger-value num">{inPipeline}</div>
          </div>
          <div className="ledger-row">
            <div className="ledger-label">{isAr ? "بدون موظف" : "Unassigned"}</div>
            <div className="ledger-sub">
              {isAr
                ? "مفيش موظف مؤهل، في انتظار التوجيه البشري"
                : "No eligible agent, waiting for human routing"}
            </div>
            <div className="ledger-value num">{unassignedCount}</div>
          </div>
        </div>
      </section>

      {/* Bucket Tabs */}
      <div className="tabs" role="tablist" aria-label="Queue priority buckets">
        <button
          type="button"
          role="tab"
          className="tab"
          aria-selected={bucket === ""}
          onClick={() => {
            setBucket("");
            setCursor(null);
          }}
        >
          <span>{t.allBuckets}</span>
          <span className="num tab-count">{totalAll}</span>
        </button>
        {QUEUE_BUCKETS.map((b) => (
          <button
            key={b}
            type="button"
            role="tab"
            className="tab"
            aria-selected={bucket === b}
            onClick={() => {
              setBucket(b);
              setCursor(null);
            }}
          >
            <span>{labelForBucket(b, locale)}</span>
            <span className="num tab-count">{counts[b] ?? 0}</span>
          </button>
        ))}
      </div>

      {/* Filters Toolbar */}
      <form className="toolbar" onSubmit={handleSearchSubmit}>
        <label className="field" style={{ flex: "1 1 240px" }}>
          <span>{isAr ? "بحث في النص الصوتي" : "Transcript search"}</span>
          <div style={{ display: "flex", gap: 6 }}>
            <input
              type="search"
              value={searchInput}
              onChange={(ev) => setSearchInput(ev.target.value)}
              placeholder={t.searchPlaceholder}
              style={{ flex: 1, minWidth: 0 }}
            />
            <button type="submit" className="btn" aria-label={isAr ? "بحث" : "Search"}>
              <IconSearch size={17} stroke={1.8} aria-hidden="true" />
            </button>
          </div>
        </label>

        <label className="field">
          <span>{t.filterCategory}</span>
          <select
            value={category}
            onChange={(ev) => {
              setCategory(ev.target.value);
              setCursor(null);
            }}
          >
            <option value="">{t.allOption}</option>
            {COMPLAINT_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {labelForCategory(c, locale)}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>{t.filterStatus}</span>
          <select
            value={statusFilter}
            onChange={(ev) => {
              setStatusFilter(ev.target.value);
              setCursor(null);
            }}
          >
            <option value="">{t.allOption}</option>
            {TICKET_STATUSES.map((s) => (
              <option key={s} value={s}>
                {labelForStatus(s, locale)}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>{t.filterAgent}</span>
          <select
            value={agentId}
            onChange={(ev) => {
              setAgentId(ev.target.value);
              setCursor(null);
            }}
          >
            <option value="">{t.allOption}</option>
            <option value="unassigned">{t.unassignedOption}</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>

        {(bucket || category || statusFilter || agentId || searchQuery) && (
          <button type="button" className="btn ghost" onClick={resetFilters}>
            {isAr ? "مسح التصفية" : "Clear filters"}
          </button>
        )}
      </form>

      {error && (
        <div className="alert error" role="alert">
          <IconAlertCircle size={18} stroke={1.8} aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {loading && !data ? (
        <p className="loading-state">{t.loading}</p>
      ) : !data || data.items.length === 0 ? (
        <div className="empty-state">
          <p style={{ marginBottom: 12 }}>{t.noTickets}</p>
          <button type="button" className="btn" onClick={() => setIntakeOpen(true)}>
            <IconMicrophone size={16} stroke={1.8} aria-hidden="true" />
            <span>{t.intakeOpen}</span>
          </button>
        </div>
      ) : (
        <>
          <div className="queue">
            <div className="queue-head" aria-hidden="true">
              <span>{isAr ? "الأولوية" : "Score"}</span>
              <span>{isAr ? "التذكرة" : "Ticket"}</span>
              <span className="q-agent-col">{isAr ? "الموظف" : "Agent"}</span>
              <span className="q-conf">{isAr ? "الثقة" : "Confidence"}</span>
              <span className="q-when">{isAr ? "الاستلام" : "Received"}</span>
              <span>{isAr ? "الحالة" : "Status"}</span>
            </div>

            <ul className="ticket-list" aria-label="Prioritized callback tickets">
              {data.items.map((ticket) => (
                <li key={ticket.id}>
                  <Link href={`/tickets/${ticket.id}`} className="ticket-row">
                    <div className={`q-score ${ticket.queue_priority ?? "none"}`}>
                      {ticket.priority_score !== null ? ticket.priority_score : "-"}
                    </div>

                    <div className="q-main">
                      <div className="q-title">
                        <span>{labelForCategory(ticket.complaint_category, locale)}</span>
                        <span className="mono muted">#{ticket.id.slice(0, 8)}</span>
                        {ticket.needs_human_review && (
                          <span className="status-inline high-text">
                            <IconAlertTriangle size={14} stroke={2} aria-hidden="true" />
                            {ticket.review_reason
                              ? labelForReviewReason(ticket.review_reason, locale)
                              : isAr
                                ? "مراجعة بشرية"
                                : "Human Review"}
                          </span>
                        )}
                      </div>
                      <div className="q-excerpt" dir="auto">
                        {ticket.summary || ticket.customer_request || ticket.route_reason || "-"}
                      </div>
                    </div>

                    <div className="q-agent">
                      {ticket.assigned_agent_name ? (
                        ticket.assigned_agent_name
                      ) : (
                        <span className="faint" aria-label={t.unassignedOption}>
                          -
                        </span>
                      )}
                    </div>

                    <div className="q-conf num">
                      <strong>{formatPct(ticket.confidence)}</strong>
                      <span className="faint">
                        {" "}
                        / {formatPct(ticket.confidence_threshold_snapshot, 0)}
                      </span>
                    </div>

                    <div className="q-when num">
                      <span>{formatUtcTimestamp(ticket.created_at, locale)}</span>
                      <span className="faint">{formatDuration(ticket.duration_seconds)}</span>
                    </div>

                    <div className="q-status">
                      <TicketStatusText status={ticket.status} locale={locale} />
                      <BucketText bucket={ticket.queue_priority} locale={locale} />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div className="pager">
            <span>
              {isAr
                ? `عرض ${data.items.length} من أصل ${data.total} تذكرة`
                : `Showing ${data.items.length} of ${data.total} tickets`}
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

      <VoicemailIntakeDrawer
        open={intakeOpen}
        locale={locale}
        onClose={() => setIntakeOpen(false)}
        onSubmitted={() => {
          setCursor(null);
          void fetchQueue();
        }}
      />
    </AppShell>
  );
}
