"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  IconAlertCircle,
  IconCheck,
  IconShieldCheck,
  IconShieldOff,
} from "@tabler/icons-react";
import { AppShell } from "@/components/AppShell";
import { useApp } from "@/components/AppProvider";
import { ConfirmModal } from "@/components/ConfirmModal";
import { api, ApiError } from "@/lib/api";
import { UI_COPY, labelForCategory } from "@/lib/i18n";
import { COMPLAINT_CATEGORIES, formatUtcTimestamp } from "@/lib/taxonomy";
import type { ScriptTemplateResponse, SettingsResponse } from "@/lib/types";

export default function AdminSettingsPage() {
  const { locale, refreshSettings } = useApp();
  const t = UI_COPY[locale];

  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [templates, setTemplates] = useState<Record<string, ScriptTemplateResponse>>({});
  const [selectedCat, setSelectedCat] = useState<string>(COMPLAINT_CATEGORIES[0]);

  const [thresholdInput, setThresholdInput] = useState<string>("0.5");
  const [retentionInput, setRetentionInput] = useState<string>("90");
  const [sampleRateInput, setSampleRateInput] = useState<string>("5");

  // Template editor state
  const [tplAr, setTplAr] = useState("");
  const [tplEn, setTplEn] = useState("");
  const [reqAr, setReqAr] = useState("");
  const [reqEn, setReqEn] = useState("");

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [confirmMode, setConfirmMode] = useState<"threshold" | "kill_switch" | null>(null);

  const syncTemplateFields = (cat: string, map: Record<string, ScriptTemplateResponse>) => {
    const item = map[cat];
    if (item) {
      setTplAr(item.template_ar);
      setTplEn(item.template_en);
      setReqAr(item.customer_request_ar);
      setReqEn(item.customer_request_en);
    }
  };

  const loadAll = useCallback(async () => {
    setError(null);
    try {
      const [s, tplList] = await Promise.all([api.getSettings(), api.getTemplates()]);
      setSettings(s);
      setThresholdInput(String(s.confidence_threshold));
      setRetentionInput(String(s.retention_days));
      setSampleRateInput(String(Math.round(s.weekly_sample_rate * 1000) / 10));
      const map: Record<string, ScriptTemplateResponse> = {};
      for (const item of tplList) {
        map[item.category] = item;
      }
      setTemplates(map);
      syncTemplateFields(selectedCat, map);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load routing settings.");
    } finally {
      setLoading(false);
    }
  }, [selectedCat]);

  useEffect(() => {
    setLoading(true);
    void loadAll();
  }, [loadAll]);

  const handleSelectCategory = (cat: string) => {
    setSelectedCat(cat);
    syncTemplateFields(cat, templates);
    setError(null);
    setNotice(null);
  };

  const handleConfirmThreshold = async () => {
    const parsed = Number(thresholdInput);
    if (Number.isNaN(parsed) || parsed < 0 || parsed > 1) {
      setError(
        locale === "ar"
          ? "حد الثقة يجب أن يكون بين 0.0 و 1.0."
          : "Confidence threshold must be between 0.0 and 1.0."
      );
      setConfirmMode(null);
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await api.updateSettings({ confidence_threshold: parsed });
      setSettings(updated);
      await refreshSettings();
      setNotice(
        locale === "ar"
          ? `تم تحديث حد الثقة إلى ${parsed.toFixed(2)} (ينطبق على التذاكر الجديدة فقط).`
          : `Confidence threshold updated to ${parsed.toFixed(2)} (applies to new tickets only).`
      );
      setConfirmMode(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to update threshold.");
    } finally {
      setBusy(false);
    }
  };

  const handleConfirmKillSwitch = async () => {
    if (!settings) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const nextVal = !settings.auto_routing_enabled;
      const updated = await api.updateSettings({ auto_routing_enabled: nextVal });
      setSettings(updated);
      await refreshSettings();
      setNotice(
        nextVal
          ? locale === "ar"
            ? "تم استئناف التوجيه التلقائي للموظفين."
            : "Automatic routing resumed."
          : locale === "ar"
            ? "تم تفعيل مفتاح الإيقاف الطارئ. كل التذاكر الجديدة ستحول للمراجعة البشرية."
            : "Kill Switch enabled. All new tickets will route to the Human Routing Queue."
      );
      setConfirmMode(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to toggle Kill Switch.");
    } finally {
      setBusy(false);
    }
  };

  const handleSaveRetentionAndSampling = async (ev: React.FormEvent) => {
    ev.preventDefault();
    const days = parseInt(retentionInput, 10);
    const pct = Number(sampleRateInput);
    if (Number.isNaN(days) || days < 1 || days > 3650) {
      setError("Retention days must be between 1 and 3650.");
      return;
    }
    if (Number.isNaN(pct) || pct < 0 || pct > 100) {
      setError("Weekly sampling rate must be between 0% and 100%.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await api.updateSettings({
        retention_days: days,
        weekly_sample_rate: pct / 100,
      });
      setSettings(updated);
      await refreshSettings();
      setNotice(
        locale === "ar"
          ? "تم حفظ إعدادات الاحتفاظ والعينة الأسبوعية."
          : "Retention and weekly quality sampling settings saved."
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to update retention settings.");
    } finally {
      setBusy(false);
    }
  };

  const handleSaveTemplate = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await api.updateTemplate(selectedCat, {
        template_ar: tplAr,
        template_en: tplEn,
        customer_request_ar: reqAr,
        customer_request_en: reqEn,
      });
      setTemplates((prev) => ({ ...prev, [selectedCat]: updated }));
      setNotice(
        locale === "ar"
          ? `تم حفظ قالب معاودة الاتصال لفئة ${labelForCategory(selectedCat, locale)} (الإصدار ${updated.version}).`
          : `Saved callback template for ${labelForCategory(selectedCat, locale)} (v${updated.version}).`
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to save callback script template.");
    } finally {
      setBusy(false);
    }
  };

  const activeTemplate = templates[selectedCat];

  return (
    <AppShell allowedRoles={["admin"]}>
      <div className="page-head">
        <div>
          <h1>{locale === "ar" ? "إعدادات التوجيه والقوالب" : "Routing Settings & Script Templates"}</h1>
          <p className="sub" style={{ margin: 0 }}>
            {locale === "ar"
              ? "التحكم في حد الثقة، مفتاح إيقاف التوجيه التلقائي، سياسة الاحتفاظ، ونصوص معاودة الاتصال المعتمدة."
              : "Configure confidence handoff threshold, automatic routing Kill Switch, retention, quality sampling, and grounded 11-category callback scripts."}
          </p>
        </div>
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

      {loading || !settings ? (
        <p className="loading-state">{t.loading}</p>
      ) : (
        <>
          <div className="detail-grid">
            {/* Confidence Threshold */}
            <section className="card" style={{ margin: 0 }}>
              <h2>
                {locale === "ar"
                  ? "حد الثقة للتوجيه التلقائي (FR21)"
                  : "Confidence Handoff Threshold (FR21)"}
              </h2>
              <p className="sub">
                {locale === "ar"
                  ? "أي تذكرة تقل ثقة النموذج فيها عن هذا الحد تحول تلقائيا إلى قائمة المراجعة البشرية. ينطبق التعديل على التذاكر الجديدة فقط."
                  : "Tickets with min predicted probability below this threshold route to the Human Routing Queue. Applies to new tickets only."}
              </p>

              <div style={{ display: "flex", gap: 10, alignItems: "flex-end", flexWrap: "wrap" }}>
                <label className="field" style={{ flex: "1 1 160px" }}>
                  <span>
                    {locale === "ar" ? "حد الثقة (0.00 إلى 1.00)" : "Threshold (0.00 to 1.00)"}
                  </span>
                  <input
                    type="number"
                    step="0.05"
                    min={0}
                    max={1}
                    value={thresholdInput}
                    onChange={(ev) => setThresholdInput(ev.target.value)}
                    disabled={busy}
                  />
                </label>
                <button
                  type="button"
                  className="btn primary"
                  onClick={() => setConfirmMode("threshold")}
                  disabled={busy}
                >
                  <span>{locale === "ar" ? "تحديث الحد" : "Update Threshold"}</span>
                </button>
              </div>
              <p className="card-note num">
                {locale === "ar" ? "القيمة الحالية:" : "Current active threshold:"}{" "}
                <strong>{settings.confidence_threshold.toFixed(2)}</strong> ·{" "}
                {locale === "ar"
                  ? "التذاكر السابقة تحتفظ بقيمة الحد التي أنشئت عليها."
                  : "Existing tickets retain their creation-time threshold snapshot."}
              </p>
            </section>

            {/* Automatic Routing Kill Switch */}
            <section className="card" style={{ margin: 0 }}>
              <h2>
                {locale === "ar"
                  ? "مفتاح إيقاف التوجيه التلقائي (Kill Switch)"
                  : "Automatic Routing Kill Switch (PRD 10.5)"}
              </h2>
              <p className="sub">
                {locale === "ar"
                  ? "عند إيقاف التوجيه التلقائي، تذهب جميع الرسائل الصوتية الجديدة فورا إلى قائمة المراجعة البشرية دون تعيين تلقائي."
                  : "Immediately pause automatic agent assignment. While paused, every new voicemail enters the Human Routing Queue."}
              </p>

              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 12,
                  flexWrap: "wrap",
                  padding: "12px 14px",
                  border: "1px solid var(--line)",
                  backgroundColor: "var(--surface)",
                }}
              >
                <div>
                  <div className="field-label">
                    {locale === "ar" ? "الحالة الحالية" : "Current State"}
                  </div>
                  <div style={{ marginTop: 4 }}>
                    {settings.auto_routing_enabled ? (
                      <span className="status-inline ok-text">
                        <IconShieldCheck size={17} stroke={1.8} aria-hidden="true" />
                        {locale === "ar" ? "التوجيه التلقائي يعمل" : "Automatic Routing Enabled"}
                      </span>
                    ) : (
                      <span className="status-inline urgent-text">
                        <IconShieldOff size={17} stroke={1.8} aria-hidden="true" />
                        {locale === "ar"
                          ? "التوجيه التلقائي متوقف (Kill Switch)"
                          : "Automatic Routing Paused (Kill Switch Active)"}
                      </span>
                    )}
                  </div>
                </div>

                <button
                  type="button"
                  className={settings.auto_routing_enabled ? "btn danger" : "btn"}
                  onClick={() => setConfirmMode("kill_switch")}
                  disabled={busy}
                >
                  {settings.auto_routing_enabled
                    ? locale === "ar"
                      ? "إيقاف التوجيه التلقائي"
                      : "Pause Auto-Routing"
                    : locale === "ar"
                      ? "استئناف التوجيه التلقائي"
                      : "Resume Auto-Routing"}
                </button>
              </div>
            </section>
          </div>

          {/* Retention & Weekly 5% Quality Sampling */}
          <section className="card">
            <h2>
              {locale === "ar"
                ? "الاحتفاظ بالبيانات وعينة الجودة الأسبوعية"
                : "Data Retention & Weekly Quality Sampling (AI10)"}
            </h2>
            <form
              onSubmit={handleSaveRetentionAndSampling}
              style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}
            >
              <label className="field" style={{ minWidth: 200 }}>
                <span>
                  {locale === "ar" ? "مدة الاحتفاظ بالتسجيلات (بالأيام)" : "Retention Window (Days)"}
                </span>
                <input
                  type="number"
                  min={1}
                  max={3650}
                  value={retentionInput}
                  onChange={(ev) => setRetentionInput(ev.target.value)}
                  disabled={busy}
                />
              </label>

              <label className="field" style={{ minWidth: 220 }}>
                <span>
                  {locale === "ar"
                    ? "نسبة عينة المراجعة الأسبوعية (%)"
                    : "Weekly Human Quality Sample (%)"}
                </span>
                <input
                  type="number"
                  step="0.5"
                  min={0}
                  max={100}
                  value={sampleRateInput}
                  onChange={(ev) => setSampleRateInput(ev.target.value)}
                  disabled={busy}
                />
              </label>

              <button type="submit" className="btn" disabled={busy}>
                <IconCheck size={16} stroke={1.8} aria-hidden="true" />
                <span>{t.saveChanges}</span>
              </button>
            </form>
            <p className="card-note">
              {locale === "ar"
                ? "الافتراضي المعتمد: 90 يوما للاحتفاظ، و 5% على الأقل لعينة الجودة الأسبوعية."
                : "PRD baseline: 90-day retention default and at least 5% weekly human review sampling."}
            </p>
          </section>

          {/* 11-Category Bilingual Script Template Editor */}
          <section className="card">
            <h2>
              {locale === "ar"
                ? "محرر قوالب نصوص معاودة الاتصال (11 فئة)"
                : "11-Category Bilingual Callback Script Templates (FR14 / S3)"}
            </h2>
            <p className="sub">
              {locale === "ar"
                ? "قوالب ثابتة معتمدة على بيانات التذكرة فقط (يُمنع استخدام رموز مثل {name}). لا تُرسل للمشترك تلقائيا أبدا."
                : "Grounded opening templates only (no unexpanded {...} placeholders). Used by agents during callbacks and never sent automatically."}
            </p>

            <div className="toolbar">
              <label className="field" style={{ minWidth: 280 }}>
                <span>{locale === "ar" ? "اختر فئة الشكوى" : "Select Complaint Category"}</span>
                <select
                  value={selectedCat}
                  onChange={(ev) => handleSelectCategory(ev.target.value)}
                >
                  {COMPLAINT_CATEGORIES.map((cat) => (
                    <option key={cat} value={cat}>
                      {labelForCategory(cat, locale)} ({cat})
                    </option>
                  ))}
                </select>
              </label>
              {activeTemplate && (
                <span className="mono muted num">
                  v{activeTemplate.version} · {formatUtcTimestamp(activeTemplate.updated_at, locale)}
                </span>
              )}
            </div>

            <form onSubmit={handleSaveTemplate} style={{ display: "grid", gap: 14 }}>
              <div className="detail-grid" style={{ marginBottom: 0 }}>
                <label className="field">
                  <span>
                    {locale === "ar"
                      ? "جملة طلب المشترك (عربي)"
                      : "Customer Request Sentence (Arabic)"}
                  </span>
                  <textarea
                    dir="rtl"
                    lang="ar"
                    value={reqAr}
                    onChange={(ev) => setReqAr(ev.target.value)}
                    required
                    maxLength={500}
                  />
                </label>
                <label className="field">
                  <span>
                    {locale === "ar"
                      ? "جملة طلب المشترك (إنجليزي)"
                      : "Customer Request Sentence (English)"}
                  </span>
                  <textarea
                    dir="ltr"
                    lang="en"
                    value={reqEn}
                    onChange={(ev) => setReqEn(ev.target.value)}
                    required
                    maxLength={500}
                  />
                </label>
              </div>

              <div className="detail-grid" style={{ marginBottom: 0 }}>
                <label className="field">
                  <span>
                    {locale === "ar"
                      ? "نص معاودة الاتصال المقترح (عربي)"
                      : "Suggested Callback Script (Arabic)"}
                  </span>
                  <textarea
                    dir="rtl"
                    lang="ar"
                    value={tplAr}
                    onChange={(ev) => setTplAr(ev.target.value)}
                    required
                    maxLength={1000}
                  />
                </label>
                <label className="field">
                  <span>
                    {locale === "ar"
                      ? "نص معاودة الاتصال المقترح (إنجليزي)"
                      : "Suggested Callback Script (English)"}
                  </span>
                  <textarea
                    dir="ltr"
                    lang="en"
                    value={tplEn}
                    onChange={(ev) => setTplEn(ev.target.value)}
                    required
                    maxLength={1000}
                  />
                </label>
              </div>

              <div>
                <button type="submit" className="btn" disabled={busy}>
                  <IconCheck size={16} stroke={1.8} aria-hidden="true" />
                  <span>
                    {locale === "ar" ? "حفظ القالب لهذه الفئة" : "Save Category Template"}
                  </span>
                </button>
              </div>
            </form>
          </section>
        </>
      )}

      <ConfirmModal
        open={confirmMode === "threshold"}
        title={
          locale === "ar"
            ? "تأكيد تغيير حد الثقة"
            : "Confirm Confidence Threshold Change"
        }
        description={
          locale === "ar"
            ? `سيتم تغيير حد الثقة من ${settings?.confidence_threshold.toFixed(2)} إلى ${Number(thresholdInput).toFixed(2)}. ينطبق هذا التغيير على التذاكر الجديدة فقط ولن يعدّل التذاكر السابقة، وسيُسجل في سجل التدقيق.`
            : `Change confidence threshold from ${settings?.confidence_threshold.toFixed(2)} to ${Number(thresholdInput).toFixed(2)}? This applies to new tickets only; existing tickets keep their creation-time threshold, and this change is logged in the Audit Log.`
        }
        confirmLabel={locale === "ar" ? "تأكيد التحديث" : "Confirm Threshold Update"}
        cancelLabel={t.cancel}
        busy={busy}
        onCancel={() => setConfirmMode(null)}
        onConfirm={() => void handleConfirmThreshold()}
      />

      <ConfirmModal
        open={confirmMode === "kill_switch"}
        title={
          settings?.auto_routing_enabled
            ? locale === "ar"
              ? "تأكيد إيقاف التوجيه التلقائي"
              : "Confirm Automatic Routing Kill Switch"
            : locale === "ar"
              ? "تأكيد استئناف التوجيه التلقائي"
              : "Confirm Resume Automatic Routing"
        }
        description={
          settings?.auto_routing_enabled
            ? locale === "ar"
              ? "سيتم إيقاف التوجيه التلقائي فورا، وستتحول كل الرسائل الصوتية الجديدة إلى قائمة المراجعة البشرية."
              : "Automatic agent routing will pause immediately. Every new subscriber voicemail will enter the Human Routing Queue until resumed."
            : locale === "ar"
              ? "سيستأنف النظام التوجيه التلقائي للرسائل الصوتية الجديدة وفقا للمهارات والسعة وحد الثقة."
              : "The system will resume automatic agent routing for new subscriber voicemails based on skills, capacity, and confidence threshold."
        }
        confirmLabel={
          settings?.auto_routing_enabled
            ? locale === "ar"
              ? "نعم، إيقاف فوري"
              : "Pause Auto-Routing Now"
            : locale === "ar"
              ? "نعم، استئناف"
              : "Resume Auto-Routing"
        }
        cancelLabel={t.cancel}
        danger={Boolean(settings?.auto_routing_enabled)}
        busy={busy}
        onCancel={() => setConfirmMode(null)}
        onConfirm={() => void handleConfirmKillSwitch()}
      />
    </AppShell>
  );
}
