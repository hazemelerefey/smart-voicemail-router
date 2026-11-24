"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  IconAlertCircle,
  IconAlertTriangle,
  IconCheck,
  IconRefresh,
} from "@tabler/icons-react";
import { AppShell } from "@/components/AppShell";
import { useApp } from "@/components/AppProvider";
import { api, ApiError } from "@/lib/api";
import { FIELD_LABELS, UI_COPY } from "@/lib/i18n";
import { AI9_THRESHOLDS, formatMs, formatPct, formatUtcTimestamp } from "@/lib/taxonomy";
import type { EvalRunResponse, MonitoringSummaryResponse } from "@/lib/types";

function extractFieldMacroF1(metrics: Record<string, unknown>, field: string): number | null {
  const perField = metrics.per_field_macro_f1 as Record<string, number> | undefined;
  if (perField && typeof perField[field] === "number") return perField[field];
  const fields = metrics.fields as Record<string, { macro_f1?: number }> | undefined;
  if (fields && typeof fields[field]?.macro_f1 === "number") return fields[field].macro_f1!;
  const direct = metrics[`${field}_macro_f1`];
  if (typeof direct === "number") return direct;
  if (field === "combined") {
    if (typeof metrics.combined_macro_f1 === "number") return metrics.combined_macro_f1;
    if (typeof metrics.mean_macro_f1 === "number") return metrics.mean_macro_f1;
  }
  return null;
}

function extractRoutingAgreement(metrics: Record<string, unknown>): number | null {
  if (typeof metrics.routing_agreement === "number") return metrics.routing_agreement;
  if (typeof metrics.routing_agreement_rate === "number") return metrics.routing_agreement_rate;
  const routing = metrics.routing as { agreement_rate?: number; agreement?: number } | undefined;
  if (typeof routing?.agreement_rate === "number") return routing.agreement_rate;
  if (typeof routing?.agreement === "number") return routing.agreement;
  return null;
}

function extractChurnDetails(metrics: Record<string, unknown>): {
  atRiskCount: number | null;
  perSeed: Record<string, number>;
} {
  let atRiskCount: number | null = null;
  let perSeed: Record<string, number> = {};

  if (typeof metrics.churn_at_risk_true_count === "number") {
    atRiskCount = metrics.churn_at_risk_true_count;
  } else if (typeof metrics.churn_at_risk_count === "number") {
    atRiskCount = metrics.churn_at_risk_count;
  }
  const churnAnalysis = metrics.churn_at_risk_analysis as
    | { true_at_risk_count?: number }
    | undefined;
  if (churnAnalysis && typeof churnAnalysis.true_at_risk_count === "number") {
    atRiskCount = churnAnalysis.true_at_risk_count;
  }
  const churnMeta = metrics.churn_details as
    | { at_risk_count?: number; per_seed_macro_f1?: Record<string, number> }
    | undefined;
  if (churnMeta) {
    if (typeof churnMeta.at_risk_count === "number") atRiskCount = churnMeta.at_risk_count;
    if (churnMeta.per_seed_macro_f1) perSeed = churnMeta.per_seed_macro_f1;
  }
  if (metrics.churn_per_seed && typeof metrics.churn_per_seed === "object") {
    perSeed = metrics.churn_per_seed as Record<string, number>;
  }
  const fairRerun = metrics.fair_rerun_5seed as
    | { per_seed?: Array<{ seed?: number | string; churn_risk_macro_f1?: number }> }
    | undefined;
  if (fairRerun?.per_seed && Array.isArray(fairRerun.per_seed) && Object.keys(perSeed).length === 0) {
    const mapped: Record<string, number> = {};
    for (const item of fairRerun.per_seed) {
      if (item.seed !== undefined && typeof item.churn_risk_macro_f1 === "number") {
        mapped[String(item.seed)] = item.churn_risk_macro_f1;
      }
    }
    perSeed = mapped;
  }
  const fiveSeed = metrics.five_seed_churn_macro_f1 as Record<string, number> | undefined;
  if (fiveSeed && Object.keys(perSeed).length === 0) {
    perSeed = fiveSeed;
  }
  return { atRiskCount, perSeed };
}

export default function EvaluationPage() {
  const { locale } = useApp();
  const t = UI_COPY[locale];

  const [runs, setRuns] = useState<EvalRunResponse[]>([]);
  const [summary, setSummary] = useState<MonitoringSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setError(null);
    try {
      const [evalRuns, mon] = await Promise.all([
        api.getEvalRuns(),
        api.getMonitoringSummary(),
      ]);
      setRuns(evalRuns);
      setSummary(mon);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load evaluation & monitoring data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    void loadAll();
  }, [loadAll]);

  const latestValRun = runs.find((r) => r.split === "validation") || runs[0] || null;
  const latestMetrics = latestValRun?.metrics || {};
  const routingAgreement = extractRoutingAgreement(latestMetrics);
  const churnDetails = extractChurnDetails(latestMetrics);

  const gateRows = [
    "complaint_category",
    "complaint_urgency",
    "customer_state",
    "churn_risk",
    "combined",
  ] as const;

  return (
    <AppShell allowedRoles={["supervisor", "admin"]}>
      <div className="page-head">
        <div>
          <h1>
            {locale === "ar"
              ? "تقييم النماذج ومراقبة الجودة (AI9 / AI10)"
              : "Model Evaluation & Production Monitoring"}
          </h1>
          <p className="sub" style={{ margin: 0 }}>
            {locale === "ar"
              ? "مقاييس التحقق على 1,003 عينة مقابل بوابات الإطلاق ومعدل المراجعة وزمن المعالجة p50/p95."
              : "Validation Macro-F1 vs AI9 release gates (1,003 rows), routing agreement, human review rate, latency, and active 24h alerts."}
          </p>
        </div>
        <div className="page-head-actions">
          <button
            type="button"
            className="btn primary"
            onClick={() => void loadAll()}
            disabled={loading}
          >
            <IconRefresh size={16} stroke={1.8} aria-hidden="true" />
            <span>{locale === "ar" ? "تحديث المقاييس" : "Refresh Metrics"}</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="alert error" role="alert">
          <IconAlertCircle size={18} stroke={1.8} aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {loading && !summary ? (
        <p className="loading-state">{t.loading}</p>
      ) : (
        <>
          {/* Active 24h Alerts (AI10 / NFR20) */}
          {summary && summary.alerts.length > 0 && (
            <section style={{ marginBottom: 14 }}>
              {summary.alerts.map((al, idx) => (
                <div className="alert warn" key={`${al.code}-${idx}`} role="alert">
                  <IconAlertTriangle size={18} stroke={1.8} aria-hidden="true" />
                  <div>
                    <strong>{al.code}</strong>: {al.message}{" "}
                    <span className="mono num">
                      ({al.value.toFixed(2)} vs {al.threshold.toFixed(2)})
                    </span>
                  </div>
                </div>
              ))}
            </section>
          )}

          {/* KPI Strip */}
          <div className="kpi-strip">
            <div className="kpi-box">
              <div className="kpi-label">
                {locale === "ar" ? "توافق التوجيه (الهدف >=80%)" : "Routing Agreement (Gate >=80%)"}
              </div>
              <div
                className={`kpi-value num ${
                  routingAgreement !== null && routingAgreement >= 0.8 ? "ok-text" : ""
                }`}
              >
                {routingAgreement !== null ? formatPct(routingAgreement, 1) : "-"}
              </div>
              <div className="kpi-sub">
                {locale === "ar" ? "مجموعة التحقق 1,003 عينة" : "Validation split (1,003 rows)"}
              </div>
            </div>

            <div className="kpi-box">
              <div className="kpi-label">
                {locale === "ar" ? "معدل المراجعة البشرية" : "Human Review Rate"}
              </div>
              <div
                className={`kpi-value num ${
                  summary && summary.human_review_rate_24h > 0.2 ? "urgent-text" : ""
                }`}
              >
                {summary ? formatPct(summary.human_review_rate, 1) : "-"}
              </div>
              <div className="kpi-sub">
                {locale === "ar" ? "آخر 24 ساعة:" : "Last 24h:"}{" "}
                {summary ? formatPct(summary.human_review_rate_24h, 1) : "-"} (alert &gt; 20%)
              </div>
            </div>

            <div className="kpi-box">
              <div className="kpi-label">
                {locale === "ar" ? "زمن المعالجة p50 / p95" : "End-to-End Latency p50 / p95"}
              </div>
              <div className="kpi-value num">
                {summary
                  ? `${formatMs(summary.end_to_end_latency_ms?.p50)} / ${formatMs(
                      summary.end_to_end_latency_ms?.p95
                    )}`
                  : "-"}
              </div>
              <div className="kpi-sub">
                {locale === "ar" ? "آخر 24 ساعة p95:" : "24h p95:"}{" "}
                {summary ? formatMs(summary.end_to_end_latency_24h_ms?.p95) : "-"} (target &lt;=10s GPU)
              </div>
            </div>

            <div className="kpi-box">
              <div className="kpi-label">
                {locale === "ar" ? "إجمالي التذاكر المعالجة" : "Total Processed Tickets"}
              </div>
              <div className="kpi-value num">{summary?.total_tickets ?? 0}</div>
              <div className="kpi-sub">
                {locale === "ar" ? "آخر 24 ساعة:" : "Last 24h:"} {summary?.tickets_last_24h ?? 0} ·{" "}
                {locale === "ar" ? "نسبة النجاح:" : "Success:"}{" "}
                {summary ? formatPct(summary.processing_success_rate, 1) : "-"}
              </div>
            </div>
          </div>

          {/* AI9 Per-Field Validation Macro-F1 vs Release Gates */}
          <section className="card">
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
                {locale === "ar"
                  ? "نتائج التحقق مقابل بوابات الإطلاق AI9"
                  : "Per-Field Validation Macro-F1 vs AI9 Release Gates"}
              </h2>
              {latestValRun && (
                <span className="mono muted">
                  {latestValRun.model_version} · {latestValRun.dataset_version} ({latestValRun.split})
                </span>
              )}
            </div>

            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>{locale === "ar" ? "الحقل / القدرة" : "Capability / Field"}</th>
                    <th className="num">{locale === "ar" ? "حد البوابة (AI9)" : "AI9 Gate"}</th>
                    <th className="num">{locale === "ar" ? "المرجع المعتمد" : "PRD Validated"}</th>
                    <th className="num">{locale === "ar" ? "القياس الحالي" : "Measured Macro-F1"}</th>
                    <th>{locale === "ar" ? "الحالة" : "Gate Status"}</th>
                  </tr>
                </thead>
                <tbody>
                  {gateRows.map((key) => {
                    const spec = AI9_THRESHOLDS[key];
                    const score = latestValRun ? extractFieldMacroF1(latestMetrics, key) : null;
                    const pass = score !== null && score >= spec.threshold;
                    const label =
                      key === "combined"
                        ? locale === "ar"
                          ? "المتوسط المجمّع للحقول الأربعة"
                          : "Combined Mean (4 Fields)"
                        : FIELD_LABELS[locale][key];
                    return (
                      <tr key={key}>
                        <td>
                          <strong>{label}</strong>
                        </td>
                        <td className="num mono">&gt;= {spec.threshold.toFixed(2)}</td>
                        <td className="num mono muted">{spec.validated.toFixed(4)}</td>
                        <td className="num mono">
                          <strong>{score !== null ? score.toFixed(4) : "-"}</strong>
                        </td>
                        <td>
                          {score === null ? (
                            <span className="muted">
                              {locale === "ar" ? "لا يوجد تقييم بعد" : "Pending eval run"}
                            </span>
                          ) : pass ? (
                            <span className="status-inline ok-text">
                              <IconCheck size={15} stroke={2} aria-hidden="true" />
                              {locale === "ar" ? "ناجح" : "PASS"}
                            </span>
                          ) : (
                            <span className="status-inline urgent-text">
                              <IconAlertCircle size={15} stroke={2} aria-hidden="true" />
                              {locale === "ar" ? "دون الحد" : "BELOW GATE"}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Churn fragility disclosure (PRD AI9 / L6) */}
            <div className="card-surface" style={{ marginTop: 12, marginBottom: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 13 }}>
                {locale === "ar"
                  ? "ملاحظة حساسية خطر فقدان المشترك (AI9 / L6)"
                  : "Churn Risk Sample-Size & Per-Seed Disclosure (AI9 / L6)"}
              </div>
              <p className="muted" style={{ marginTop: 4, marginBottom: 6 }}>
                {locale === "ar"
                  ? `يعتمد قياس خطر فقدان المشترك على ${churnDetails.atRiskCount ?? 7} حالات فقط (at_risk) في مجموعة التحقق، لذا فإن حالة واحدة تغير الدرجة بشكل ملحوظ.`
                  : `Churn validation rests on ${churnDetails.atRiskCount ?? 7} at_risk rows out of 1,003 validation samples, so a single misclassification shifts Macro-F1 materially.`}
              </p>
              {Object.keys(churnDetails.perSeed).length > 0 && (
                <div className="mono num" style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                  {Object.entries(churnDetails.perSeed).map(([seed, val]) => (
                    <span key={seed}>
                      seed {seed}: <strong>{Number(val).toFixed(4)}</strong>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* Stage Latency + Confidence Histogram */}
          {summary && (
            <div className="detail-grid">
              <section className="card" style={{ margin: 0 }}>
                <h2>{locale === "ar" ? "زمن المراحل (p50 / p95)" : "Per-Stage Latency (p50 / p95)"}</h2>
                {Object.keys(summary.stage_latency_ms || {}).length === 0 ? (
                  <p className="muted" style={{ margin: 0 }}>
                    {locale === "ar" ? "لا توجد قياسات مراحل بعد." : "No stage latency logs recorded yet."}
                  </p>
                ) : (
                  <div className="table-wrap">
                    <table className="data">
                      <thead>
                        <tr>
                          <th>{locale === "ar" ? "المرحلة" : "Stage"}</th>
                          <th className="num">p50</th>
                          <th className="num">p95</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(summary.stage_latency_ms).map(([stage, stats]) => (
                          <tr key={stage}>
                            <td className="mono">{stage}</td>
                            <td className="num">{formatMs(stats.p50)}</td>
                            <td className="num">{formatMs(stats.p95)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              <section className="card" style={{ margin: 0 }}>
                <h2>
                  {locale === "ar" ? "توزيع ثقة النموذج" : "Confidence Score Distribution"}
                </h2>
                {summary.confidence_histogram.length === 0 ? (
                  <p className="muted" style={{ margin: 0 }}>
                    {locale === "ar" ? "لا توجد بيانات ثقة بعد." : "No confidence distribution data yet."}
                  </p>
                ) : (
                  <div className="prob-list">
                    {(() => {
                      const maxCount = Math.max(
                        1,
                        ...summary.confidence_histogram.map((b) => b.count || 0)
                      );
                      return summary.confidence_histogram.map((bin, idx) => {
                        const binLabel = bin.bucket || bin.range || bin.label || `Bin ${idx + 1}`;
                        return (
                          <div className="prob-row" key={binLabel}>
                            <span className="prob-name mono">{binLabel}</span>
                            <span className="prob-track" aria-hidden="true">
                              <span
                                className="prob-fill"
                                style={{ width: `${(bin.count / maxCount) * 100}%` }}
                              />
                            </span>
                            <span className="prob-val">{bin.count}</span>
                          </div>
                        );
                      });
                    })()}
                  </div>
                )}
              </section>
            </div>
          )}

          {/* Classification Distributions */}
          {summary && Object.keys(summary.classification_distribution || {}).length > 0 && (
            <section className="card">
              <h2>
                {locale === "ar"
                  ? "توزيع التصنيفات في التشغيل الفعلي"
                  : "Live Classification Distributions"}
              </h2>
              <div className="fields-grid">
                {Object.entries(summary.classification_distribution).map(([field, counts]) => {
                  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
                  const maxC = Math.max(1, ...entries.map((e) => e[1]));
                  return (
                    <div className="field-card" key={field}>
                      <div className="field-label" style={{ marginBottom: 8 }}>
                        {FIELD_LABELS[locale][field] || field}
                      </div>
                      {entries.length === 0 ? (
                        <p className="muted" style={{ margin: 0, fontSize: 12 }}>
                          -
                        </p>
                      ) : (
                        <div className="prob-list">
                          {entries.map(([cls, count]) => (
                            <div className="prob-row" key={cls}>
                              <span className="prob-name" title={cls}>
                                {cls}
                              </span>
                              <span className="prob-track" aria-hidden="true">
                                <span
                                  className="prob-fill"
                                  style={{ width: `${(count / maxC) * 100}%` }}
                                />
                              </span>
                              <span className="prob-val">{count}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* EvalRun History Table */}
          <section className="card">
            <h2>{locale === "ar" ? "سجل تشغيلات التقييم (EvalRun)" : "Evaluation Run History"}</h2>
            {runs.length === 0 ? (
              <p className="muted" style={{ margin: 0 }}>
                {locale === "ar"
                  ? "لم يتم تسجيل أي تشغيل تقييم بعد."
                  : "No EvalRun records stored yet."}
              </p>
            ) : (
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>{locale === "ar" ? "المجموعة" : "Split"}</th>
                      <th>{locale === "ar" ? "إصدار البيانات" : "Dataset"}</th>
                      <th>{locale === "ar" ? "إصدار النموذج" : "Model Version"}</th>
                      <th className="num">Combined F1</th>
                      <th className="num">Routing</th>
                      <th>Guard Claim</th>
                      <th>{locale === "ar" ? "المنفذ" : "Run By"}</th>
                      <th>{locale === "ar" ? "التوقيت" : "Created At"}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => {
                      const comb = extractFieldMacroF1(run.metrics, "combined");
                      const rAgree = extractRoutingAgreement(run.metrics);
                      return (
                        <tr key={run.id}>
                          <td className="mono">{run.split}</td>
                          <td className="mono">{run.dataset_version}</td>
                          <td className="mono">{run.model_version}</td>
                          <td className="num mono">{comb !== null ? comb.toFixed(4) : "-"}</td>
                          <td className="num mono">{rAgree !== null ? formatPct(rAgree, 1) : "-"}</td>
                          <td className="mono muted">{run.guard_claim_id || "-"}</td>
                          <td>{run.created_by}</td>
                          <td className="num muted">{formatUtcTimestamp(run.created_at, locale)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </AppShell>
  );
}
