"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  IconAlertCircle,
  IconCheck,
  IconCopy,
  IconExternalLink,
  IconMicrophone,
  IconPlayerPlay,
  IconRefresh,
} from "@tabler/icons-react";
import { AppShell } from "@/components/AppShell";
import { useApp } from "@/components/AppProvider";
import { BucketText, TicketStatusText, bucketColorClass } from "@/components/StatusLabel";
import { VoicemailIntakeDrawer } from "@/components/VoicemailIntakeDrawer";
import { api, ApiError } from "@/lib/api";
import { UI_COPY, labelForCategory } from "@/lib/i18n";
import { formatDuration, formatUtcTimestamp } from "@/lib/taxonomy";
import type { TicketListResponse } from "@/lib/types";

export default function MyTicketsPage() {
  const { locale, wsVersion } = useApp();
  const t = UI_COPY[locale];

  const [data, setData] = useState<TicketListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [intakeOpen, setIntakeOpen] = useState(false);

  const loadMyTickets = useCallback(async () => {
    setError(null);
    try {
      const res = await api.listTickets({ limit: 50 });
      setData(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load your assigned callbacks.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    void loadMyTickets();
  }, [loadMyTickets]);

  useEffect(() => {
    if (wsVersion > 0) {
      void loadMyTickets();
    }
  }, [wsVersion, loadMyTickets]);

  const handleTransition = async (ticketId: string, status: "in_progress" | "resolved") => {
    setBusyId(ticketId);
    setError(null);
    try {
      await api.patchTicket(ticketId, { status });
      await loadMyTickets();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to update ticket status.");
    } finally {
      setBusyId(null);
    }
  };

  const handleCopy = async (ticketId: string, script: string) => {
    try {
      await navigator.clipboard.writeText(script);
      setCopiedId(ticketId);
      setTimeout(() => setCopiedId(null), 1800);
    } catch (err) {
      console.warn("Clipboard copy failed:", err);
    }
  };

  return (
    <AppShell allowedRoles={["agent"]}>
      <div className="page-head">
        <div>
          <h1>{locale === "ar" ? "تذاكري لمعاودة الاتصال" : "My Assigned Callbacks"}</h1>
          <p className="sub" style={{ margin: 0 }}>
            {locale === "ar"
              ? "التذاكر المخصصة لحسابك فقط مع ملخص ونص معاودة الاتصال الجاهز."
              : "Subscriber voicemails assigned to you, ordered by priority with inline callback briefs."}
          </p>
        </div>
        <div className="page-head-actions">
          <button type="button" className="btn" onClick={() => void loadMyTickets()} disabled={loading}>
            <IconRefresh size={16} stroke={1.8} aria-hidden="true" />
            <span>{locale === "ar" ? "تحديث" : "Refresh"}</span>
          </button>
          <button type="button" className="btn primary" onClick={() => setIntakeOpen(true)}>
            <IconMicrophone size={16} stroke={1.8} aria-hidden="true" />
            <span>{t.intakeOpen}</span>
          </button>
        </div>
      </div>

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
          <p style={{ margin: 0 }}>
            {locale === "ar"
              ? "لا توجد تذاكر مخصصة لك حاليا."
              : "No subscriber callback tickets are currently assigned to you."}
          </p>
        </div>
      ) : (
        <div style={{ display: "grid", gap: 14 }}>
          {data.items.map((ticket) => {
            const isBusy = busyId === ticket.id;
            const canStart = ticket.status === "ready";
            const canResolve = ticket.status === "ready" || ticket.status === "in_progress";

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
                        P{ticket.priority_score ?? "-"}
                      </span>
                      <strong style={{ fontSize: 15 }}>
                        {labelForCategory(ticket.complaint_category, locale)}
                      </strong>
                      <span className="mono muted">#{ticket.id.slice(0, 8)}</span>
                      <BucketText bucket={ticket.queue_priority} locale={locale} />
                      <TicketStatusText status={ticket.status} locale={locale} />
                    </div>
                    <div className="muted num" style={{ fontSize: 12, marginTop: 4 }}>
                      {ticket.file_name} · {formatDuration(ticket.duration_seconds)} ·{" "}
                      {formatUtcTimestamp(ticket.created_at, locale)}
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <Link href={`/tickets/${ticket.id}`} className="btn">
                      <IconExternalLink size={16} stroke={1.8} aria-hidden="true" />
                      <span>{locale === "ar" ? "فتح التفاصيل" : "Open Ticket"}</span>
                    </Link>
                    {canStart && (
                      <button
                        type="button"
                        className="btn"
                        disabled={isBusy}
                        onClick={() => void handleTransition(ticket.id, "in_progress")}
                      >
                        <IconPlayerPlay size={16} stroke={1.8} aria-hidden="true" />
                        <span>{locale === "ar" ? "بدء المكالمة" : "Start Callback"}</span>
                      </button>
                    )}
                    {canResolve && (
                      <button
                        type="button"
                        className="btn"
                        disabled={isBusy}
                        onClick={() => void handleTransition(ticket.id, "resolved")}
                      >
                        <IconCheck size={16} stroke={1.8} aria-hidden="true" />
                        <span>{locale === "ar" ? "تم الحل" : "Resolve"}</span>
                      </button>
                    )}
                  </div>
                </div>

                <div className="detail-grid" style={{ marginTop: 14, marginBottom: 0 }}>
                  <div className="card-surface" style={{ margin: 0 }}>
                    <div className="field-label">
                      {locale === "ar" ? "طلب المشترك والملخص" : "Customer Request & Summary"}
                    </div>
                    <p style={{ marginTop: 6, fontWeight: 600 }} dir="auto">
                      {ticket.customer_request || "-"}
                    </p>
                    <p className="muted" style={{ margin: 0 }} dir="auto">
                      {ticket.summary || "-"}
                    </p>
                  </div>

                  <div className="card-surface" style={{ margin: 0 }}>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: 8,
                      }}
                    >
                      <span className="field-label">
                        {locale === "ar" ? "نص معاودة الاتصال" : "Suggested Callback Script"}
                      </span>
                      <button
                        type="button"
                        className="btn ghost"
                        onClick={() => void handleCopy(ticket.id, ticket.suggested_script)}
                        disabled={!ticket.suggested_script}
                      >
                        {copiedId === ticket.id ? (
                          <IconCheck size={15} stroke={1.8} aria-hidden="true" />
                        ) : (
                          <IconCopy size={15} stroke={1.8} aria-hidden="true" />
                        )}
                        <span>{copiedId === ticket.id ? t.copied : t.copyScript}</span>
                      </button>
                    </div>
                    <p style={{ marginTop: 4, marginBottom: 6 }} dir="auto">
                      {ticket.suggested_script || "-"}
                    </p>
                    <p className="card-note" style={{ margin: 0 }}>
                      {t.neverSentAuto}
                    </p>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}

      <VoicemailIntakeDrawer
        open={intakeOpen}
        locale={locale}
        onClose={() => setIntakeOpen(false)}
        onSubmitted={() => void loadMyTickets()}
      />
    </AppShell>
  );
}
