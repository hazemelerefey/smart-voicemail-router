"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  IconAlertCircle,
  IconAlertTriangle,
  IconArrowLeft,
  IconCheck,
  IconChevronDown,
  IconCopy,
  IconCpu,
  IconEdit,
  IconPlayerPlay,
  IconRefresh,
  IconUserEdit,
  IconUserPlus,
} from "@tabler/icons-react";
import { AppShell } from "@/components/AppShell";
import { useApp } from "@/components/AppProvider";
import { BucketText, TicketStatusText, bucketColorClass } from "@/components/StatusLabel";
import { api, ApiError, apiUrl } from "@/lib/api";
import {
  FIELD_LABELS,
  UI_COPY,
  labelForBucket,
  labelForCategory,
  labelForChurn,
  labelForLanguageMix,
  labelForReviewReason,
  labelForState,
  labelForStatus,
  labelForUrgency,
} from "@/lib/i18n";
import {
  ALLOWED_TRANSITIONS,
  CHURN_RISKS,
  COMPLAINT_CATEGORIES,
  COMPLAINT_URGENCIES,
  CUSTOMER_STATES,
  formatDuration,
  formatMs,
  formatPct,
  formatUtcTimestamp,
} from "@/lib/taxonomy";
import type {
  AgentResponse,
  CorrectionPreviewResponse,
  TicketDetail,
} from "@/lib/types";

const STT_V1_COLUMNS = [
  "file",
  "model",
  "text",
  "text_norm",
  "min_avg_logprob",
  "max_no_speech_prob",
  "needs_review",
  "review_reasons",
  "dup_text_size",
  "error",
] as const;

export default function TicketDetailPage() {
  const params = useParams<{ id: string }>();
  const ticketId = params?.id || "";
  const { user, locale, wsVersion } = useApp();
  const t = UI_COPY[locale];

  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [agents, setAgents] = useState<AgentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  // WF2 Correction state
  const [editCategory, setEditCategory] = useState<string>("");
  const [editUrgency, setEditUrgency] = useState<string>("");
  const [editState, setEditState] = useState<string>("");
  const [editChurn, setEditChurn] = useState<string>("");
  const [corrNote, setCorrNote] = useState<string>("");
  const [applyRecRoute, setApplyRecRoute] = useState<boolean>(true);
  const [clearReview, setClearReview] = useState<boolean>(true);
  const [preview, setPreview] = useState<CorrectionPreviewResponse | null>(null);
  const [previewing, setPreviewing] = useState(false);

  // Reassignment state
  const [reassignAgentId, setReassignAgentId] = useState<string>("");

  const isSupervisorOrAdmin = user?.role === "supervisor" || user?.role === "admin";

  const loadTicket = useCallback(async () => {
    if (!ticketId) return;
    setError(null);
    try {
      const detail = await api.getTicket(ticketId);
      setTicket(detail);
      setEditCategory(detail.complaint_category || "");
      setEditUrgency(detail.complaint_urgency || "");
      setEditState(detail.customer_state || "");
      setEditChurn(detail.churn_risk || "");
      setReassignAgentId(detail.assigned_agent_id || "");
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Failed to load ticket detail.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [ticketId]);

  useEffect(() => {
    setLoading(true);
    void loadTicket();
  }, [loadTicket]);

  useEffect(() => {
    if (wsVersion > 0) {
      void loadTicket();
    }
  }, [wsVersion, loadTicket]);

  useEffect(() => {
    if (isSupervisorOrAdmin) {
      api
        .listAgents()
        .then(setAgents)
        .catch((err) => console.warn("Failed to load agents list:", err));
    }
  }, [isSupervisorOrAdmin]);

  const handleCopyScript = async () => {
    if (!ticket?.suggested_script) return;
    try {
      await navigator.clipboard.writeText(ticket.suggested_script);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.warn("Clipboard write failed:", err);
      setActionErr(
        locale === "ar"
          ? "تعذر نسخ النص إلى الحافظة."
          : "Could not copy script to clipboard."
      );
    }
  };

  const handleStatusTransition = async (nextStatus: string) => {
    if (!ticket) return;
    setBusy(true);
    setActionErr(null);
    setActionMsg(null);
    try {
      const updated = await api.patchTicket(ticket.id, { status: nextStatus });
      setTicket(updated);
      setActionMsg(
        locale === "ar"
          ? `تم تحديث حالة التذكرة إلى ${labelForStatus(nextStatus, locale)}.`
          : `Ticket status updated to ${labelForStatus(nextStatus, locale)}.`
      );
    } catch (err) {
      setActionErr(err instanceof ApiError ? err.detail : "Failed to update ticket status.");
    } finally {
      setBusy(false);
    }
  };

  const handleReassign = async () => {
    if (!ticket) return;
    setBusy(true);
    setActionErr(null);
    setActionMsg(null);
    try {
      const updated = await api.patchTicket(
        ticket.id,
        reassignAgentId
          ? { assigned_agent_id: reassignAgentId, needs_human_review: false }
          : { unassign: true, needs_human_review: true, review_reason: "supervisor_requested" }
      );
      setTicket(updated);
      setActionMsg(
        reassignAgentId
          ? locale === "ar"
            ? "تمت إعادة توجيه التذكرة بنجاح."
            : "Ticket reassigned successfully."
          : locale === "ar"
            ? "تم تحويل التذكرة إلى غير معين."
            : "Ticket released to unassigned queue."
      );
    } catch (err) {
      setActionErr(err instanceof ApiError ? err.detail : "Reassignment failed.");
    } finally {
      setBusy(false);
    }
  };

  const handlePreviewCorrection = async () => {
    if (!ticket) return;
    setPreviewing(true);
    setActionErr(null);
    setActionMsg(null);
    try {
      const res = await api.previewCorrection(ticket.id, {
        complaint_category: editCategory || null,
        complaint_urgency: editUrgency || null,
        customer_state: editState || null,
        churn_risk: editChurn || null,
      });
      setPreview(res);
    } catch (err) {
      setActionErr(err instanceof ApiError ? err.detail : "Correction preview failed.");
    } finally {
      setPreviewing(false);
    }
  };

  const handleConfirmCorrection = async () => {
    if (!ticket) return;
    setBusy(true);
    setActionErr(null);
    setActionMsg(null);
    try {
      const updated = await api.applyCorrection(ticket.id, {
        complaint_category: editCategory || null,
        complaint_urgency: editUrgency || null,
        customer_state: editState || null,
        churn_risk: editChurn || null,
        apply_recommended_route: applyRecRoute,
        clear_human_review: clearReview,
        note: corrNote.trim() || null,
      });
      setTicket(updated);
      setPreview(null);
      setCorrNote("");
      setReassignAgentId(updated.assigned_agent_id || "");
      setActionMsg(
        locale === "ar"
          ? "تم حفظ التصحيح البشري وإعادة حساب الأولوية والتوجيه وتسجيله في سجل التدقيق."
          : "Human correction confirmed, priority and routing updated, and audit diff recorded."
      );
    } catch (err) {
      setActionErr(err instanceof ApiError ? err.detail : "Failed to apply correction.");
    } finally {
      setBusy(false);
    }
  };

  const backHref = user?.role === "agent" ? "/my-tickets" : "/dashboard";

  const renderLabelValue = (field: string, val: string | null) => {
    if (field === "complaint_category") return labelForCategory(val, locale);
    if (field === "complaint_urgency") return labelForUrgency(val, locale);
    if (field === "customer_state") return labelForState(val, locale);
    if (field === "churn_risk") return labelForChurn(val, locale);
    return val || "-";
  };

  const nextTransitions = ticket
    ? (ALLOWED_TRANSITIONS[ticket.status] || []).filter((st) => {
        if (user?.role === "agent") {
          return st === "in_progress" || st === "resolved";
        }
        return true;
      })
    : [];

  return (
    <AppShell allowedRoles={["admin", "supervisor", "agent"]}>
      <div className="page-head">
        <div>
          <Link href={backHref} className="btn ghost" style={{ paddingInline: 0, marginBottom: 4 }}>
            <IconArrowLeft size={16} stroke={1.8} aria-hidden="true" />
            <span>{t.backToQueue}</span>
          </Link>
          <h1>
            {ticket
              ? `${labelForCategory(ticket.complaint_category, locale)} · #${ticket.id.slice(0, 8)}`
              : locale === "ar"
                ? "تفاصيل التذكرة"
                : "Ticket Detail"}
          </h1>
          {ticket && (
            <p className="sub" style={{ margin: 0 }}>
              <span className="mono">{ticket.file_name}</span> · {formatDuration(ticket.duration_seconds)} ·{" "}
              <span className="num">{formatUtcTimestamp(ticket.created_at, locale)}</span>
            </p>
          )}
        </div>

        {ticket && (
          <div className="page-head-actions">
            <button type="button" className="btn" onClick={() => void loadTicket()} disabled={busy}>
              <IconRefresh size={16} stroke={1.8} aria-hidden="true" />
              <span>{locale === "ar" ? "تحديث" : "Refresh"}</span>
            </button>
            {nextTransitions.map((nextSt, idx) => (
              <button
                key={nextSt}
                type="button"
                className={idx === 0 ? "btn primary" : "btn"}
                disabled={busy}
                onClick={() => void handleStatusTransition(nextSt)}
              >
                {nextSt === "in_progress" ? (
                  <IconPlayerPlay size={16} stroke={1.8} aria-hidden="true" />
                ) : (
                  <IconCheck size={16} stroke={1.8} aria-hidden="true" />
                )}
                <span>
                  {nextSt === "in_progress"
                    ? locale === "ar"
                      ? "بدء معاودة الاتصال"
                      : "Start Callback"
                    : nextSt === "resolved"
                      ? locale === "ar"
                        ? "إنهاء وحل التذكرة"
                        : "Mark Resolved"
                      : labelForStatus(nextSt, locale)}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {error && (
        <div className="alert error" role="alert">
          <IconAlertCircle size={18} stroke={1.8} aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {actionErr && (
        <div className="alert error" role="alert">
          <IconAlertCircle size={18} stroke={1.8} aria-hidden="true" />
          <span>{actionErr}</span>
        </div>
      )}

      {actionMsg && (
        <div className="alert ok" role="status">
          <IconCheck size={18} stroke={1.8} aria-hidden="true" />
          <span>{actionMsg}</span>
        </div>
      )}

      {loading && !ticket ? (
        <p className="loading-state">{t.loading}</p>
      ) : !ticket ? null : (
        <>
          {/* Status bar */}
          <div className="detail-status-bar">
            <span>
              <strong>{locale === "ar" ? "الحالة:" : "Status:"}</strong>
              <TicketStatusText status={ticket.status} locale={locale} />
            </span>
            <span>
              <strong>{locale === "ar" ? "الأولوية:" : "Priority:"}</strong>
              <span className={`num ${bucketColorClass(ticket.queue_priority)}`}>
                {ticket.priority_score !== null ? `${ticket.priority_score} / 6` : "-"}
              </span>{" "}
              <BucketText bucket={ticket.queue_priority} locale={locale} />
            </span>
            <span>
              <strong>{locale === "ar" ? "الثقة:" : "Confidence:"}</strong>
              <span className="num">{formatPct(ticket.confidence)}</span>{" "}
              <span className="faint num">
                ({locale === "ar" ? "الحد:" : "threshold"}{" "}
                {formatPct(ticket.confidence_threshold_snapshot, 0)})
              </span>
            </span>
            <span>
              <strong>{locale === "ar" ? "الموظف:" : "Assigned:"}</strong>
              {ticket.assigned_agent_name || t.unassignedOption}
            </span>
            <span>
              <strong>{locale === "ar" ? "زمن المعالجة:" : "Pipeline:"}</strong>
              <span className="num">{formatMs(ticket.processing_ms)}</span>
            </span>
            <span>
              <strong>{locale === "ar" ? "إصدار النموذج:" : "Model:"}</strong>
              <span className="mono">{ticket.model_version}</span>
            </span>
          </div>

          {ticket.needs_human_review && (
            <div className="alert warn" role="status">
              <IconAlertTriangle size={18} stroke={1.8} aria-hidden="true" />
              <div>
                <strong>
                  {locale === "ar" ? "مطلوب مراجعة بشرية:" : "Flagged for Human Review:"}
                </strong>{" "}
                {ticket.review_reason
                  ? labelForReviewReason(ticket.review_reason, locale)
                  : locale === "ar"
                    ? "تتطلب هذه التذكرة مراجعة المشرف."
                    : "This ticket requires supervisor review."}
              </div>
            </div>
          )}

          {/* Audio Player */}
          <section className="audio-box" aria-label="Voicemail audio playback">
            <div style={{ minWidth: 150 }}>
              <div style={{ fontWeight: 700, fontSize: 13 }}>
                {locale === "ar" ? "التسجيل الصوتي للمشترك" : "Subscriber Voicemail Audio"}
              </div>
              <div className="mono muted num">
                {ticket.format.toUpperCase()} · {formatDuration(ticket.duration_seconds)} ·{" "}
                {(ticket.size_bytes / 1024).toFixed(1)} KB
              </div>
            </div>
            <audio controls preload="none" src={apiUrl(ticket.audio_url)}>
              {locale === "ar"
                ? "متصفحك لا يدعم تشغيل الصوت."
                : "Your browser does not support audio playback."}
            </audio>
          </section>

          {/* Callback Brief + Arabic Transcript */}
          <div className="detail-grid">
            <section className="card" style={{ margin: 0 }}>
              <h2>
                {locale === "ar" ? "ملخص معاودة الاتصال للموظف" : "Subscriber Callback Brief"}
              </h2>
              <dl className="kv">
                <div className="kv-row" style={{ flexDirection: "column", alignItems: "flex-start" }}>
                  <dt>{locale === "ar" ? "طلب المشترك" : "Customer Request"}</dt>
                  <dd style={{ textAlign: "start", fontWeight: 500 }} dir="auto">
                    {ticket.customer_request || "-"}
                  </dd>
                </div>
                <div className="kv-row" style={{ flexDirection: "column", alignItems: "flex-start" }}>
                  <dt>
                    {locale === "ar"
                      ? "ملخص الرسالة (حتى 200 حرف)"
                      : "Summary (up to 200 chars)"}
                  </dt>
                  <dd style={{ textAlign: "start", fontWeight: 500 }} dir="auto">
                    {ticket.summary || "-"}
                  </dd>
                </div>
              </dl>

              <div style={{ marginTop: 14 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 8,
                    marginBottom: 6,
                  }}
                >
                  <strong style={{ fontSize: 12, color: "var(--muted)" }}>
                    {locale === "ar" ? "النص المقترح لبدء المكالمة" : "Suggested Callback Opening Script"}
                  </strong>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => void handleCopyScript()}
                    disabled={!ticket.suggested_script}
                  >
                    {copied ? (
                      <IconCheck size={16} stroke={1.8} aria-hidden="true" />
                    ) : (
                      <IconCopy size={16} stroke={1.8} aria-hidden="true" />
                    )}
                    <span>{copied ? t.copied : t.copyScript}</span>
                  </button>
                </div>
                <div className="card-surface" style={{ margin: 0 }} dir="auto">
                  {ticket.suggested_script || "-"}
                </div>
                <p className="card-note">{t.neverSentAuto}</p>
              </div>
            </section>

            <section className="card" style={{ margin: 0 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 8,
                  flexWrap: "wrap",
                  marginBottom: 10,
                }}
              >
                <h2 style={{ margin: 0 }}>
                  {locale === "ar" ? "التفريغ الصوتي بالعربية" : "Arabic Transcript"}
                </h2>
                {ticket.language_mix && (
                  <span className="mono muted">
                    {labelForLanguageMix(ticket.language_mix, locale)}
                  </span>
                )}
              </div>

              <p className="transcript-ar" dir="rtl" lang="ar">
                {ticket.transcript || (locale === "ar" ? "لا يوجد نص متاح." : "No transcript available.")}
              </p>

              {ticket.text_norm && (
                <div style={{ marginTop: 10 }}>
                  <div className="field-label">
                    {locale === "ar" ? "النص المعالج للنموذج (text_norm)" : "Normalized Model Input (text_norm)"}
                  </div>
                  <p className="muted" dir="rtl" lang="ar" style={{ marginTop: 4, fontSize: 13 }}>
                    {ticket.text_norm}
                  </p>
                </div>
              )}

              <details className="panel">
                <summary>
                  <IconChevronDown size={16} stroke={1.8} aria-hidden="true" />
                  <span>
                    {locale === "ar"
                      ? "جدول مخرجات Whisper STT v1 (10 أعمدة)"
                      : "Whisper STT v1 Metadata (10 Columns)"}
                  </span>
                </summary>
                <div className="panel-body">
                  {ticket.stt_v1_json ? (
                    <div className="table-wrap">
                      <table className="data">
                        <thead>
                          <tr>
                            <th>{locale === "ar" ? "العمود" : "Column"}</th>
                            <th>{locale === "ar" ? "القيمة" : "Value"}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {STT_V1_COLUMNS.map((col) => {
                            const rawVal = ticket.stt_v1_json?.[col];
                            const display =
                              rawVal === null || rawVal === undefined
                                ? "-"
                                : typeof rawVal === "object"
                                  ? JSON.stringify(rawVal)
                                  : String(rawVal);
                            return (
                              <tr key={col}>
                                <td className="mono">{col}</td>
                                <td className="mono num" dir="auto">
                                  {display}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="muted" style={{ margin: 0 }}>
                      {locale === "ar"
                        ? "بيانات STT غير متوفرة بعد."
                        : "STT metadata not recorded yet."}
                    </p>
                  )}
                </div>
              </details>
            </section>
          </div>

          {/* 4 Independent Fields + Probability Distributions */}
          <section className="card">
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 8,
                flexWrap: "wrap",
                marginBottom: 12,
              }}
            >
              <h2 style={{ margin: 0 }}>
                {locale === "ar"
                  ? "الحقول الأربعة المستقلة وتوزيع الاحتمالات"
                  : "Four Independent Classified Fields & Probabilities"}
              </h2>
              <span className="mono num muted">
                {locale === "ar" ? "أقل احتمال (الثقة):" : "Min predicted prob (Confidence):"}{" "}
                <strong>{formatPct(ticket.confidence, 2)}</strong> vs{" "}
                {formatPct(ticket.confidence_threshold_snapshot, 0)}
              </span>
            </div>

            <div className="fields-grid">
              {(
                [
                  ["complaint_category", ticket.complaint_category],
                  ["complaint_urgency", ticket.complaint_urgency],
                  ["customer_state", ticket.customer_state],
                  ["churn_risk", ticket.churn_risk],
                ] as const
              ).map(([fieldKey, fieldVal]) => {
                const source = ticket.label_sources?.[fieldKey] || "model";
                const isHuman = source === "human";
                const probs = ticket.probabilities?.[fieldKey] || {};
                const sortedProbs = Object.entries(probs).sort((a, b) => b[1] - a[1]);

                return (
                  <div className="field-card" key={fieldKey}>
                    <div className="field-label">{FIELD_LABELS[locale][fieldKey]}</div>
                    <div
                      className={`field-value${
                        fieldKey === "churn_risk" && fieldVal === "at_risk" ? " urgent-text" : ""
                      }`}
                    >
                      {renderLabelValue(fieldKey, fieldVal)}
                    </div>
                    <div className="field-provenance">
                      {isHuman ? (
                        <span className="status-inline ok-text">
                          <IconUserEdit size={14} stroke={1.8} aria-hidden="true" />
                          {t.humanCorrection}
                        </span>
                      ) : (
                        <span className="status-inline muted">
                          <IconCpu size={14} stroke={1.8} aria-hidden="true" />
                          {t.modelOutput}
                        </span>
                      )}
                    </div>

                    {sortedProbs.length > 0 ? (
                      <div className="prob-list">
                        {sortedProbs.map(([cls, prob]) => {
                          const isTop = cls === fieldVal;
                          return (
                            <div className="prob-row" key={cls}>
                              <span
                                className="prob-name"
                                title={renderLabelValue(fieldKey, cls)}
                                style={isTop ? { color: "var(--ink)", fontWeight: 700 } : undefined}
                              >
                                {renderLabelValue(fieldKey, cls)}
                              </span>
                              <span className="prob-track" aria-hidden="true">
                                <span
                                  className={`prob-fill${isTop ? "" : " dim"}`}
                                  style={{ width: `${Math.max(0, Math.min(100, prob * 100))}%` }}
                                />
                              </span>
                              <span className="prob-val">{formatPct(prob, 1)}</span>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="muted" style={{ fontSize: 12, margin: 0 }}>
                        {locale === "ar" ? "لا توجد احتمالات مسجلة." : "No probabilities recorded."}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </section>

          {/* Priority Breakdown + Routing Decision */}
          <div className="detail-grid">
            <section className="card" style={{ margin: 0 }}>
              <h2>
                {locale === "ar" ? "تفصيل درجة الأولوية" : "Explainable Priority Breakdown"}
              </h2>
              <dl className="kv">
                <div className="kv-row">
                  <dt>{FIELD_LABELS[locale].complaint_urgency}</dt>
                  <dd className="num">
                    {labelForUrgency(ticket.complaint_urgency, locale)} (+
                    {String(
                      (ticket.priority_signals?.complaint_urgency as { points?: number } | undefined)
                        ?.points ??
                        ticket.priority_signals?.urgency_points ??
                        "-"
                    )}
                    )
                  </dd>
                </div>
                <div className="kv-row">
                  <dt>{FIELD_LABELS[locale].churn_risk}</dt>
                  <dd className="num">
                    {labelForChurn(ticket.churn_risk, locale)} (+
                    {String(
                      (ticket.priority_signals?.churn_risk as { points?: number } | undefined)
                        ?.points ??
                        ticket.priority_signals?.churn_points ??
                        "-"
                    )}
                    )
                  </dd>
                </div>
                <div className="kv-row">
                  <dt>{FIELD_LABELS[locale].customer_state}</dt>
                  <dd className="num">
                    {labelForState(ticket.customer_state, locale)} (+
                    {String(
                      (ticket.priority_signals?.customer_state as { points?: number } | undefined)
                        ?.points ??
                        ticket.priority_signals?.state_points ??
                        "-"
                    )}
                    )
                  </dd>
                </div>
                <div className="kv-row">
                  <dt style={{ fontWeight: 700, color: "var(--ink)" }}>
                    {locale === "ar" ? "المجموع والفئة" : "Total Score & Queue Bucket"}
                  </dt>
                  <dd className={`num ${bucketColorClass(ticket.queue_priority)}`}>
                    {ticket.priority_score !== null ? ticket.priority_score : "-"} ·{" "}
                    {labelForBucket(ticket.queue_priority, locale)}
                  </dd>
                </div>
              </dl>
              <p className="card-note">{ticket.priority_reason || "-"}</p>
            </section>

            <section className="card" style={{ margin: 0 }}>
              <h2>{locale === "ar" ? "قرار التوجيه والموظف" : "Routing Decision & Assignment"}</h2>
              <dl className="kv">
                <div className="kv-row">
                  <dt>{locale === "ar" ? "الموظف المعين" : "Assigned Agent"}</dt>
                  <dd>{ticket.assigned_agent_name || t.unassignedOption}</dd>
                </div>
                <div className="kv-row" style={{ flexDirection: "column", alignItems: "flex-start" }}>
                  <dt>{locale === "ar" ? "سبب التوجيه" : "Route Reason"}</dt>
                  <dd style={{ textAlign: "start", fontWeight: 500 }}>{ticket.route_reason || "-"}</dd>
                </div>
              </dl>

              {isSupervisorOrAdmin && (
                <div style={{ marginTop: 14, display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
                  <label className="field" style={{ flex: "1 1 200px" }}>
                    <span>{locale === "ar" ? "إعادة توجيه يدوية" : "Manual Reassignment"}</span>
                    <select
                      value={reassignAgentId}
                      onChange={(ev) => setReassignAgentId(ev.target.value)}
                      disabled={busy}
                    >
                      <option value="">{t.unassignedOption}</option>
                      {agents
                        .filter((a) => a.active)
                        .map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.name} ({a.current_load}/{a.capacity}{" "}
                            {a.available ? "" : " - unavailable"})
                          </option>
                        ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => void handleReassign()}
                    disabled={busy}
                  >
                    <IconUserPlus size={16} stroke={1.8} aria-hidden="true" />
                    <span>{locale === "ar" ? "تطبيق التعيين" : "Apply Assignment"}</span>
                  </button>
                </div>
              )}
            </section>
          </div>

          {/* WF2 Supervisor Correction Panel */}
          {isSupervisorOrAdmin && (
            <section className="card">
              <h2>
                <IconEdit
                  size={16}
                  stroke={1.8}
                  aria-hidden="true"
                  style={{ verticalAlign: "text-bottom", marginInlineEnd: 6 }}
                />
                {locale === "ar"
                  ? "تصحيح المشرف وإعادة حساب التوجيه"
                  : "Supervisor Label Correction (Preview Before Confirm)"}
              </h2>
              <p className="sub">
                {locale === "ar"
                  ? "عدّل أي حقل ثم اضغط معاينة لرؤية الأولوية والموظف الجديد قبل التأكيد."
                  : "Edit any of the four independent fields, preview the recomputed priority and agent route, then confirm to log the audit diff."}
              </p>

              <div className="fields-grid">
                <label className="field">
                  <span>{FIELD_LABELS[locale].complaint_category}</span>
                  <select
                    value={editCategory}
                    onChange={(ev) => {
                      setEditCategory(ev.target.value);
                      setPreview(null);
                    }}
                  >
                    <option value="">-</option>
                    {COMPLAINT_CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {labelForCategory(c, locale)}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="field">
                  <span>{FIELD_LABELS[locale].complaint_urgency}</span>
                  <select
                    value={editUrgency}
                    onChange={(ev) => {
                      setEditUrgency(ev.target.value);
                      setPreview(null);
                    }}
                  >
                    <option value="">-</option>
                    {COMPLAINT_URGENCIES.map((u) => (
                      <option key={u} value={u}>
                        {labelForUrgency(u, locale)}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="field">
                  <span>{FIELD_LABELS[locale].customer_state}</span>
                  <select
                    value={editState}
                    onChange={(ev) => {
                      setEditState(ev.target.value);
                      setPreview(null);
                    }}
                  >
                    <option value="">-</option>
                    {CUSTOMER_STATES.map((s) => (
                      <option key={s} value={s}>
                        {labelForState(s, locale)}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="field">
                  <span>{FIELD_LABELS[locale].churn_risk}</span>
                  <select
                    value={editChurn}
                    onChange={(ev) => {
                      setEditChurn(ev.target.value);
                      setPreview(null);
                    }}
                  >
                    <option value="">-</option>
                    {CHURN_RISKS.map((r) => (
                      <option key={r} value={r}>
                        {labelForChurn(r, locale)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div style={{ marginTop: 12, display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={applyRecRoute}
                    onChange={(ev) => setApplyRecRoute(ev.target.checked)}
                  />
                  <span>
                    {locale === "ar"
                      ? "تطبيق التوجيه الموصى به تلقائيا"
                      : "Apply recommended agent route"}
                  </span>
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={clearReview}
                    onChange={(ev) => setClearReview(ev.target.checked)}
                  />
                  <span>
                    {locale === "ar"
                      ? "إزالة علامة المراجعة البشرية بعد التأكيد"
                      : "Clear human review flag on confirm"}
                  </span>
                </label>
              </div>

              <label className="field" style={{ marginTop: 10 }}>
                <span>{locale === "ar" ? "ملاحظة التصحيح (اختياري)" : "Correction Note (Optional)"}</span>
                <input
                  type="text"
                  value={corrNote}
                  onChange={(ev) => setCorrNote(ev.target.value)}
                  maxLength={500}
                  placeholder={
                    locale === "ar"
                      ? "سبب تعديل التصنيف..."
                      : "Reason for supervisor correction..."
                  }
                />
              </label>

              <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="btn"
                  onClick={() => void handlePreviewCorrection()}
                  disabled={previewing || busy}
                >
                  {previewing
                    ? locale === "ar"
                      ? "جاري الحساب..."
                      : "Computing Preview..."
                    : t.previewCorrection}
                </button>
              </div>

              {preview && (
                <div className="card-surface" style={{ marginTop: 14, marginBottom: 0 }}>
                  <h3>
                    {locale === "ar"
                      ? "معاينة النتيجة الجديدة (قبل الحفظ)"
                      : "Recomputed Priority & Routing Preview (Not Saved Yet)"}
                  </h3>
                  <dl className="kv">
                    <div className="kv-row">
                      <dt>{locale === "ar" ? "الأولوية الجديدة" : "New Priority"}</dt>
                      <dd className={`num ${bucketColorClass(preview.queue_priority)}`}>
                        {preview.priority_score !== null ? `${preview.priority_score} / 6` : "-"} ·{" "}
                        {labelForBucket(preview.queue_priority, locale)}
                      </dd>
                    </div>
                    <div className="kv-row">
                      <dt>{locale === "ar" ? "الموظف الموصى به" : "Recommended Agent"}</dt>
                      <dd>{preview.recommended_agent_name || t.unassignedOption}</dd>
                    </div>
                    <div className="kv-row">
                      <dt>{locale === "ar" ? "سبب التوجيه الجديد" : "New Route Reason"}</dt>
                      <dd>{preview.route_reason}</dd>
                    </div>
                  </dl>
                  <div style={{ marginTop: 12, display: "flex", gap: 8, justifyContent: "flex-end" }}>
                    <button
                      type="button"
                      className="btn"
                      onClick={() => setPreview(null)}
                      disabled={busy}
                    >
                      {t.cancel}
                    </button>
                    <button
                      type="button"
                      className="btn primary"
                      onClick={() => void handleConfirmCorrection()}
                      disabled={busy}
                    >
                      <IconCheck size={16} stroke={1.8} aria-hidden="true" />
                      <span>{t.confirmCorrection}</span>
                    </button>
                  </div>
                </div>
              )}
            </section>
          )}

          {/* Pipeline Stages + Audit & AI Interaction Timeline */}
          <div className="detail-grid">
            <section className="card" style={{ margin: 0 }}>
              <h2>
                {locale === "ar" ? "سجل مراحل الذكاء الاصطناعي" : "AI Pipeline Interaction Log"}
              </h2>
              {ticket.ai_logs.length === 0 ? (
                <p className="muted" style={{ margin: 0 }}>
                  {locale === "ar" ? "لا توجد مراحل مسجلة بعد." : "No AI stages recorded yet."}
                </p>
              ) : (
                <div className="table-wrap">
                  <table className="data">
                    <thead>
                      <tr>
                        <th>{locale === "ar" ? "المرحلة" : "Stage"}</th>
                        <th>{locale === "ar" ? "النموذج / القاعدة" : "Model / Engine"}</th>
                        <th className="num">{locale === "ar" ? "الزمن" : "Latency"}</th>
                        <th>{locale === "ar" ? "الوقت" : "Time"}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ticket.ai_logs.map((log) => (
                        <tr key={log.id}>
                          <td className="mono">{log.stage}</td>
                          <td className="mono">{log.model}</td>
                          <td className="num">{formatMs(log.latency_ms)}</td>
                          <td className="num muted">{formatUtcTimestamp(log.created_at, locale)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="card" style={{ margin: 0 }}>
              <h2>{locale === "ar" ? "سجل تدقيق التذكرة" : "Ticket Audit Timeline"}</h2>
              {ticket.audit_events.length === 0 ? (
                <p className="muted" style={{ margin: 0 }}>
                  {locale === "ar" ? "لا توجد أحداث تدقيق." : "No audit events recorded."}
                </p>
              ) : (
                <ul className="timeline">
                  {ticket.audit_events.map((ev) => (
                    <li key={ev.id}>
                      <div>
                        <div className="mono" style={{ fontWeight: 700 }}>
                          {ev.action}
                        </div>
                        <div className="faint num" style={{ fontSize: 12 }}>
                          {formatUtcTimestamp(ev.created_at, locale)}
                        </div>
                      </div>
                      <div>
                        <div>
                          <strong>{ev.actor}</strong>
                        </div>
                        {(ev.old_value || ev.new_value) && (
                          <div className="mono muted" style={{ marginTop: 4, wordBreak: "break-word" }}>
                            {ev.old_value ? JSON.stringify(ev.old_value) : "{}"} -&gt;{" "}
                            {ev.new_value ? JSON.stringify(ev.new_value) : "{}"}
                          </div>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </>
      )}
    </AppShell>
  );
}
