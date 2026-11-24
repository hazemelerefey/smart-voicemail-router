"use client";

import Link from "next/link";
import { IconArrowLeft, IconShieldLock } from "@tabler/icons-react";
import { useApp } from "@/components/AppProvider";
import { SvrBrandMark } from "@/components/SvrBrandMark";
import { UI_COPY } from "@/lib/i18n";

export default function PrivacyPage() {
  const { locale, user } = useApp();
  const t = UI_COPY[locale];
  const backHref = user ? (user.role === "agent" ? "/my-tickets" : "/dashboard") : "/login";

  return (
    <main className="main-content" style={{ maxWidth: 820, margin: "0 auto" }}>
      <div className="page-head">
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <SvrBrandMark size={28} />
          <div>
            <h1>
              {locale === "ar"
                ? "سياسة الخصوصية وحماية البيانات"
                : "Privacy & Data Residency Notice"}
            </h1>
            <p className="sub" style={{ margin: 0 }}>
              {t.orgName} · SVR Operations
            </p>
          </div>
        </div>
        <Link href={backHref} className="btn">
          <IconArrowLeft size={16} stroke={1.8} aria-hidden="true" />
          <span>{locale === "ar" ? "رجوع" : "Back"}</span>
        </Link>
      </div>

      <section className="card">
        <h2>
          <IconShieldLock
            size={16}
            stroke={1.8}
            aria-hidden="true"
            style={{ verticalAlign: "text-bottom", marginInlineEnd: 6 }}
          />
          {locale === "ar" ? "المعالجة المحلية وسيادة البيانات" : "Local-First Processing & Data Residency"}
        </h2>
        <p>
          {locale === "ar"
            ? "يتم تشغيل نماذج التفريغ الصوتي والتصنيف بالكامل على الخادم الذي يديره مشغل الاتصالات. لا يتم إرسال أي تسجيل صوتي أو نص رسالة صوتية إلى أي مزود ذكاء اصطناعي خارجي بشكل افتراضي."
            : "Speech-to-text (Whisper large-v3) and classification (single-task MARBERTv2) run locally on operator-controlled infrastructure. Raw voicemail audio and transcripts are never transferred to third-party AI APIs by default."}
        </p>
        <p>
          {locale === "ar"
            ? "تخزن الملفات الصوتية مشفرة أثناء السكون، وتخضع بيانات المشغل لسياسات قانون حماية البيانات الشخصية المصري وعزل المؤسسة."
            : "Voicemail audio is encrypted at rest and scoped strictly by organization_id in alignment with Egyptian data protection requirements."}
        </p>
      </section>

      <section className="card">
        <h2>{locale === "ar" ? "فترة الاحتفاظ والتتبع" : "Retention & Telemetry Policy"}</h2>
        <ul style={{ margin: 0, paddingInlineStart: 20, display: "grid", gap: 8 }}>
          <li>
            {locale === "ar"
              ? "فترة الاحتفاظ الافتراضية بالتسجيلات الصوتية وبيانات التذاكر هي 90 يوما (قابلة للضبط من قبل مدير النظام)."
              : "Default retention for voicemail audio, transcripts, and ticket records is 90 days (configurable by an Admin)."}
          </li>
          <li>
            {locale === "ar"
              ? "لا يستخدم النظام أي تسجيل صامت للجلسات أو أدوات تتبع إعلانية من أطراف ثالثة."
              : "SVR uses zero silent session replay scripts, zero advertising trackers, and zero browser token storage (sessions use HttpOnly cookies)."}
          </li>
          <li>
            {locale === "ar"
              ? "مجموعة بيانات التقييم الأولية عبارة عن رسائل صوتية محاكاة مسجلة لأغراض التدريب والتقييم ولا تحتوي على بيانات عملاء حقيقيين."
              : "Simulated Corpus Notice: The initial SVR Voicemail Corpus consists of simulated recordings created for evaluation and validation, with no real subscriber personal data."}
          </li>
          <li>
            {locale === "ar"
              ? "يتم تسجيل جميع عمليات الدخول والتصحيح وإعادة التوجيه والتصدير في سجل التدقيق لضمان المساءلة."
              : "All logins, label corrections, routing reassignments, settings changes, and audit exports are recorded in the Audit Log."}
          </li>
        </ul>
      </section>
    </main>
  );
}
