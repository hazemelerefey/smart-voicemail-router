"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  IconAlertCircle,
  IconAlertTriangle,
  IconArrowRight,
  IconBellRinging,
  IconCircleCheck,
  IconMicrophone,
  IconRefresh,
} from "@tabler/icons-react";
import { AppShell } from "@/components/AppShell";
import { useApp } from "@/components/AppProvider";
import { BucketText, TicketStatusText } from "@/components/StatusLabel";
import { VoicemailIntakeDrawer } from "@/components/VoicemailIntakeDrawer";
import { api, ApiError } from "@/lib/api";
import { UI_COPY, labelForBucket, labelForCategory } from "@/lib/i18n";
import { QUEUE_BUCKETS, formatPct, formatUtcTimestamp } from "@/lib/taxonomy";
import type {
  AgentResponse,
  MonitoringSummaryResponse,
  TicketListResponse,
} from "@/lib/types";

const SEGMENT_CLASS: Record<string, string> = {
  urgent: "seg-urgent",
  high: "seg-high",
  normal: "seg-normal",
  low: "seg-low",
};

const STATE_ORDER = ["mad", "frustrated", "calm", "satisfied"] as const;
const STATE_SEG: Record<string, string> = {
  mad: "seg-urgent",
  frustrated: "seg-high",
  calm: "seg-normal",
  satisfied: "seg-low",
};
const STATE_LABEL: Record<string, { en: string; ar: string }> = {
  mad: { en: "Mad", ar: "غاضب" },
  frustrated: { en: "Frustrated", ar: "منزعج" },
  calm: { en: "Calm", ar: "هادئ" },
  satisfied: { en: "Satisfied", ar: "راضي" },
};
const CHURN_ORDER = ["at_risk", "not_at_risk"] as const;
const CHURN_SEG: Record<string, string> = { at_risk: "seg-urgent", not_at_risk: "seg-low" };
const CHURN_LABEL: Record<string, { en: string; ar: string }> = {
  at_risk: { en: "At risk", ar: "معرض للفقد" },
  not_at_risk: { en: "Not at risk", ar: "مش معرض للفقد" },
};

const REVIEW_RATE_TARGET = 0.2;
const LATENCY_TARGET_MS = 10000;

function seconds(ms: number | undefined): string {
  if (ms === undefined || !Number.isFinite(ms) || ms <= 0) return "-";
  return `${(ms / 1000).toFixed(1)}s`;
}

function prettyStage(key: string): string {
  return key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export default function OverviewPage() {
  const { locale, wsVersion, settings } = useApp();
  const t = UI_COPY[locale];
  const isAr = locale === "ar";
  const L = (en: string, ar: string) => (isAr ? ar : en);

  const [summary, setSummary] = useState<MonitoringSummaryResponse | null>(null);
  const [queue, setQueue] = useState<TicketListResponse | null>(null);
  const [agents, setAgents] = useState<AgentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [intakeOpen, setIntakeOpen] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, q, a] = await Promise.all([
        api.getMonitoringSummary(),
        api.listTickets({ limit: 6 }),
        api.listAgents(),
      ]);
      setSummary(s);
      setQueue(q);
      setAgents(a);
      setUpdatedAt(new Date());
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load the operations overview.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (wsVersion > 0) void load();
  }, [wsVersion, load]);

  const counts = queue?.counts_by_bucket ?? {};
  const urgent = counts.urgent ?? 0;
  const unassigned = queue?.counts_by_status?.unassigned ?? 0;
  const humanReview = queue?.human_review_count ?? 0;

  const categoryDist = Object.entries(summary?.classification_distribution?.complaint_category ?? {})
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1]);
  const categoryMax = categoryDist.length ? categoryDist[0][1] : 0;

  const stateDist = summary?.classification_distribution?.customer_state ?? {};
  const churnDist = summary?.classification_distribution?.churn_risk ?? {};
  const stateTotal = STATE_ORDER.reduce((n, k) => n + (stateDist[k] ?? 0), 0);
  const churnTotal = CHURN_ORDER.reduce((n, k) => n + (churnDist[k] ?? 0), 0);

  const hist = summary?.confidence_histogram ?? [];
  const histMax = hist.reduce((m, h) => Math.max(m, h.count), 0);
  const threshold = settings?.confidence_threshold ?? 0.5;

  const has24h = (summary?.tickets_last_24h ?? 0) > 0;
  const reviewRate24h = summary?.human_review_rate_24h ?? 0;
  const p95_24h = summary?.end_to_end_latency_24h_ms?.p95;
  const reviewOk = reviewRate24h <= REVIEW_RATE_TARGET;
  const latencyOk = (p95_24h ?? 0) <= LATENCY_TARGET_MS;

  const stageRows = Object.entries(summary?.stage_latency_ms ?? {}).filter(
    ([, v]) => (v?.p50 ?? 0) > 0 || (v?.p95 ?? 0) > 0
  );

  return (
    <AppShell allowedRoles={["supervisor", "admin"]} reviewBadgeCount={queue?.human_review_count}>
      <div className="page-head">
        <div>
          <h1>{L("Operations Overview", "نظرة عامة على التشغيل")}</h1>
          <p className="sub" style={{ margin: 0 }}>
            {L(
              "Live view of the voicemail pipeline, the callback queue, and agent capacity.",
              "متابعة مباشرة لمسار الرسائل الصوتية وقائمة معاودة الاتصال وسعة الموظفين."
            )}
            {updatedAt && (
              <span className="num faint">
                {" "}
                {L("Updated", "آخر تحديث")} {updatedAt.toLocaleTimeString(isAr ? "ar-EG" : "en-GB")}
              </span>
            )}
          </p>
        </div>
        <div className="page-head-actions">
          <button type="button" className="btn" onClick={() => void load()} disabled={loading}>
            <IconRefresh size={17} stroke={1.8} aria-hidden="true" />
            <span>{L("Refresh", "تحديث")}</span>
          </button>
          <button type="button" className="btn primary" onClick={() => setIntakeOpen(true)}>
            <IconMicrophone size={17} stroke={1.8} aria-hidden="true" />
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

      {summary?.alerts?.map((a) => (
        <div key={a.code} className={`alert ${a.severity === "critical" ? "error" : "warn"}`} role="alert">
          <IconAlertTriangle size={18} stroke={1.8} aria-hidden="true" />
          <span>{a.message}</span>
        </div>
      ))}

      {loading && !summary ? (
        <p className="loading-state">{t.loading}</p>
      ) : (
        <div className="ov-grid">
          {/* Attention hero */}
          <section className="hero-tile ov-span-5" aria-label={L("Needs attention", "يحتاج متابعة")}>
            <div className="hero-label">
              <IconBellRinging size={16} stroke={1.9} aria-hidden="true" />
              <span>{L("Urgent now", "عاجل الآن")}</span>
            </div>
            <div className="hero-number num">{queue ? urgent : "-"}</div>
            <p className="hero-note">
              {L(
                `${humanReview} in the Human Routing Queue and ${unassigned} without an eligible agent.`,
                `${humanReview} في قائمة المراجعة والتوجيه البشري و${unassigned} بدون موظف مؤهل.`
              )}
            </p>
            <div className="dist-bar" role="img" aria-label={L("Tickets by priority bucket", "التذاكر حسب الأولوية")}>
              {QUEUE_BUCKETS.map((b) =>
                (counts[b] ?? 0) > 0 ? (
                  <span key={b} className={`dist-seg ${SEGMENT_CLASS[b]}`} style={{ flexGrow: counts[b] }} />
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
            <Link href="/dashboard" className="hero-link">
              <span>{L("Open callback queue", "فتح قائمة معاودة الاتصال")}</span>
              <IconArrowRight size={16} stroke={1.9} aria-hidden="true" />
            </Link>
          </section>

          {/* Last 24 hours */}
          <section className="ledger ov-span-7" aria-label={L("Last 24 hours", "آخر 24 ساعة")}>
            <div className="ledger-row">
              <div className="ledger-label">{L("Voicemails received, 24 hours", "رسائل صوتية وردت خلال 24 ساعة")}</div>
              <div className="ledger-sub">
                {L(`${summary?.total_tickets ?? 0} tickets in total`, `${summary?.total_tickets ?? 0} تذكرة إجمالا`)}
              </div>
              <div className="ledger-value num">{summary?.tickets_last_24h ?? 0}</div>
            </div>

            <div className="ledger-row">
              <div className="ledger-label">{L("Human review rate, 24 hours", "نسبة المراجعة البشرية خلال 24 ساعة")}</div>
              <div className="ledger-sub">
                {has24h ? (
                  reviewOk ? (
                    <span className="status-inline ok-text">
                      <IconCircleCheck size={14} stroke={1.9} aria-hidden="true" />
                      {L("Within the 20% target", "ضمن الحد المستهدف 20%")}
                    </span>
                  ) : (
                    <span className="status-inline urgent-text">
                      <IconAlertTriangle size={14} stroke={1.9} aria-hidden="true" />
                      {L("Above the 20% target", "أعلى من الحد المستهدف 20%")}
                    </span>
                  )
                ) : (
                  L("No tickets in the last 24 hours", "لا توجد تذاكر خلال 24 ساعة")
                )}
              </div>
              <div className="ledger-value num">{has24h ? formatPct(reviewRate24h, 1) : "-"}</div>
              {has24h && (
                <div className="gauge" role="img" aria-label={L("Human review rate against the 20% target", "نسبة المراجعة مقابل الحد 20%")}>
                  <span className="gauge-fill" style={{ inlineSize: `${Math.min(100, reviewRate24h * 100)}%` }} />
                  <span className="gauge-tick" style={{ insetInlineStart: `${REVIEW_RATE_TARGET * 100}%` }} />
                </div>
              )}
            </div>

            <div className="ledger-row">
              <div className="ledger-label">{L("Processing success rate", "نسبة نجاح المعالجة")}</div>
              <div className="ledger-sub">
                {L("Tickets that finished without a pipeline error", "تذاكر اكتملت بدون خطأ في المعالجة")}
              </div>
              <div className="ledger-value num">{formatPct(summary?.processing_success_rate ?? 0, 1)}</div>
            </div>

            <div className="ledger-row">
              <div className="ledger-label">{L("End to end p95, 24 hours", "زمن المعالجة p95 خلال 24 ساعة")}</div>
              <div className="ledger-sub">
                {has24h && p95_24h ? (
                  latencyOk ? (
                    <span className="status-inline ok-text">
                      <IconCircleCheck size={14} stroke={1.9} aria-hidden="true" />
                      {L("Within the 10s target", "ضمن الحد المستهدف 10 ثواني")}
                    </span>
                  ) : (
                    <span className="status-inline urgent-text">
                      <IconAlertTriangle size={14} stroke={1.9} aria-hidden="true" />
                      {L("Above the 10s target", "أعلى من الحد المستهدف 10 ثواني")}
                    </span>
                  )
                ) : (
                  L("No timed tickets in the last 24 hours", "لا توجد تذاكر مقاسة خلال 24 ساعة")
                )}
              </div>
              <div className="ledger-value num">{has24h ? seconds(p95_24h) : "-"}</div>
            </div>
          </section>

          {/* Complaint categories */}
          <section className="panel ov-span-7" aria-labelledby="ov-cat">
            <div className="panel-head">
              <h2 id="ov-cat">{L("Complaint categories", "أنواع الشكاوى")}</h2>
              <span className="panel-meta num">
                {L(
                  `${categoryDist.reduce((n, [, c]) => n + c, 0)} classified of ${summary?.total_tickets ?? 0}`,
                  `${categoryDist.reduce((n, [, c]) => n + c, 0)} مصنفة من ${summary?.total_tickets ?? 0}`
                )}
              </span>
            </div>
            {categoryDist.length === 0 ? (
              <p className="muted">{L("No classified tickets yet.", "لا توجد تذاكر مصنفة بعد.")}</p>
            ) : (
              <ul className="bar-list">
                {categoryDist.map(([cat, n], i) => (
                  <li key={cat} className={`bar-row${i === 0 ? " top" : ""}`}>
                    <span className="bar-name">{labelForCategory(cat, locale)}</span>
                    <span className="bar-track">
                      <span className="bar-fill" style={{ inlineSize: `${(n / categoryMax) * 100}%` }} />
                    </span>
                    <span className="bar-val num">{n}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Agent workload */}
          <section className="panel ov-span-5" aria-labelledby="ov-agents">
            <div className="panel-head">
              <h2 id="ov-agents">{L("Agent workload", "حمل الموظفين")}</h2>
              <Link href="/admin/agents" className="panel-link">
                {L("Manage agents", "إدارة الموظفين")}
              </Link>
            </div>
            <ul className="load-list">
              {agents
                .filter((a) => a.active)
                .sort((a, b) => a.seed_order - b.seed_order)
                .map((a) => {
                  const full = a.current_load >= a.capacity;
                  return (
                    <li key={a.id} className="load-row">
                      <div className="load-top">
                        <span className="load-name">{a.name}</span>
                        <span className="num load-count" dir="ltr">
                          {a.current_load} / {a.capacity}
                        </span>
                      </div>
                      <span className="bar-track">
                        <span
                          className={`bar-fill${full ? " full" : ""}`}
                          style={{ inlineSize: `${Math.min(100, (a.current_load / Math.max(1, a.capacity)) * 100)}%` }}
                        />
                      </span>
                      <span className="load-sub">
                        {a.skills.join(", ")} ·{" "}
                        {a.available ? (
                          <span className="ok-text">{L("Available", "متاح")}</span>
                        ) : (
                          <span className="high-text">{L("Off shift", "خارج الوردية")}</span>
                        )}
                        {full && <span className="urgent-text"> · {L("At capacity", "اكتملت السعة")}</span>}
                      </span>
                    </li>
                  );
                })}
            </ul>
          </section>

          {/* Confidence histogram */}
          <section className="panel ov-span-7" aria-labelledby="ov-conf">
            <div className="panel-head">
              <h2 id="ov-conf">{L("Classification confidence", "ثقة التصنيف")}</h2>
              <span className="panel-meta">
                {L(`Review threshold ${formatPct(threshold, 0)}`, `حد المراجعة ${formatPct(threshold, 0)}`)}
              </span>
            </div>
            <div className="hist" role="img" aria-label={L("Tickets by confidence range", "التذاكر حسب نطاق الثقة")}>
              {hist.map((h, i) => {
                const lo = (h as { min?: number }).min ?? i / 10;
                const below = lo + 0.1 <= threshold + 1e-9;
                return (
                  <div key={i} className="hist-col">
                    <div className="hist-plot">
                      <span
                        className={`hist-bar${below ? " below" : ""}`}
                        style={{ blockSize: histMax ? `${(h.count / histMax) * 100}%` : "0%" }}
                      />
                    </div>
                    <span className="hist-count num">{h.count}</span>
                    <span className="hist-label num">{lo.toFixed(1)}</span>
                  </div>
                );
              })}
            </div>
            <p className="card-note">
              {L(
                "Amber bars fall below the review threshold and are flagged for human review.",
                "الأعمدة البرتقالية أقل من حد المراجعة ويتم تحويلها للمراجعة البشرية."
              )}
            </p>
          </section>

          {/* Customer signals */}
          <section className="panel ov-span-5" aria-labelledby="ov-signals">
            <div className="panel-head">
              <h2 id="ov-signals">{L("Customer signals", "إشارات العملاء")}</h2>
            </div>
            <div className="mix">
              <div className="mix-title">{L("Customer state", "حالة العميل")}</div>
              <div className="mix-bar" role="img" aria-label={L("Customer state mix", "توزيع حالة العميل")}>
                {STATE_ORDER.map((k) =>
                  (stateDist[k] ?? 0) > 0 ? (
                    <span key={k} className={`mix-seg ${STATE_SEG[k]}`} style={{ flexGrow: stateDist[k] }} />
                  ) : null
                )}
              </div>
              <dl className="mix-legend">
                {STATE_ORDER.map((k) => (
                  <div key={k} className={`mix-item ${STATE_SEG[k]}`}>
                    <dd className="num">{stateDist[k] ?? 0}</dd>
                    <dt>{STATE_LABEL[k][locale]}</dt>
                  </div>
                ))}
              </dl>
              <span className="sr-only">{stateTotal}</span>
            </div>
            <div className="mix">
              <div className="mix-title">{L("Churn risk", "خطر فقد العميل")}</div>
              <div className="mix-bar" role="img" aria-label={L("Churn risk mix", "توزيع خطر الفقد")}>
                {CHURN_ORDER.map((k) =>
                  (churnDist[k] ?? 0) > 0 ? (
                    <span key={k} className={`mix-seg ${CHURN_SEG[k]}`} style={{ flexGrow: churnDist[k] }} />
                  ) : null
                )}
              </div>
              <dl className="mix-legend two">
                {CHURN_ORDER.map((k) => (
                  <div key={k} className={`mix-item ${CHURN_SEG[k]}`}>
                    <dd className="num">{churnDist[k] ?? 0}</dd>
                    <dt>{CHURN_LABEL[k][locale]}</dt>
                  </div>
                ))}
              </dl>
              <span className="sr-only">{churnTotal}</span>
            </div>
          </section>

          {/* Top of the queue */}
          <section className="panel ov-span-7" aria-labelledby="ov-top">
            <div className="panel-head">
              <h2 id="ov-top">{L("Top of the queue", "أعلى القائمة")}</h2>
              <Link href="/dashboard" className="panel-link">
                {L("Open full queue", "فتح القائمة كاملة")}
              </Link>
            </div>
            {!queue || queue.items.length === 0 ? (
              <p className="muted">{t.noTickets}</p>
            ) : (
              <ul className="ticket-list top-list" aria-label={L("Highest priority tickets", "التذاكر الأعلى أولوية")}>
                {queue.items.map((ticket) => (
                  <li key={ticket.id}>
                    <Link href={`/tickets/${ticket.id}`} className="ticket-row">
                      <div className={`q-score ${ticket.queue_priority ?? "none"}`}>
                        {ticket.priority_score !== null ? ticket.priority_score : "-"}
                      </div>
                      <div className="q-main">
                        <div className="q-title">
                          <span>{labelForCategory(ticket.complaint_category, locale)}</span>
                          <span className="mono muted">#{ticket.id.slice(0, 8)}</span>
                        </div>
                        <div className="q-excerpt" dir="auto">
                          {ticket.summary || ticket.customer_request || ticket.route_reason || "-"}
                        </div>
                      </div>
                      <div className="q-agent">
                        {ticket.assigned_agent_name ?? (
                          <span className="faint" aria-label={t.unassignedOption}>
                            -
                          </span>
                        )}
                      </div>
                      <div className="q-when num">
                        <span>{formatUtcTimestamp(ticket.created_at, locale)}</span>
                      </div>
                      <div className="q-status">
                        <TicketStatusText status={ticket.status} locale={locale} />
                        <BucketText bucket={ticket.queue_priority} locale={locale} />
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Stage latency */}
          <section className="panel ov-span-5" aria-labelledby="ov-lat">
            <div className="panel-head">
              <h2 id="ov-lat">{L("Pipeline latency", "زمن مراحل المعالجة")}</h2>
              <span className="panel-meta">{L("All tickets", "كل التذاكر")}</span>
            </div>
            <div className="table-wrap flat">
              <table className="data">
                <thead>
                  <tr>
                    <th>{L("Stage", "المرحلة")}</th>
                    <th className="num">p50</th>
                    <th className="num">p95</th>
                  </tr>
                </thead>
                <tbody>
                  {stageRows.map(([stage, v]) => (
                    <tr key={stage}>
                      <td>{prettyStage(stage)}</td>
                      <td className="num">{seconds(v.p50)}</td>
                      <td className="num">{seconds(v.p95)}</td>
                    </tr>
                  ))}
                  <tr>
                    <td>
                      <strong>{L("End to end", "من البداية للنهاية")}</strong>
                    </td>
                    <td className="num">{seconds(summary?.end_to_end_latency_ms?.p50)}</td>
                    <td className="num">{seconds(summary?.end_to_end_latency_ms?.p95)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}

      <VoicemailIntakeDrawer
        open={intakeOpen}
        locale={locale}
        onClose={() => setIntakeOpen(false)}
        onSubmitted={() => void load()}
      />
    </AppShell>
  );
}
