"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { IconAlertCircle, IconLanguage, IconLock, IconMoon, IconSun } from "@tabler/icons-react";
import { useApp } from "@/components/AppProvider";
import { SvrBrandMark } from "@/components/SvrBrandMark";
import { api, ApiError } from "@/lib/api";
import { UI_COPY } from "@/lib/i18n";

const AUTH_ASIDE = {
  en: {
    headline: "Egyptian Arabic voicemail in. A prioritized, routed callback ticket out.",
    steps: [
      { title: "Transcribe", desc: "Whisper large-v3 runs on your own server. Audio never leaves it." },
      {
        title: "Classify",
        desc: "MARBERTv2 reads four fields: category, urgency, customer state, churn risk.",
      },
      { title: "Prioritize", desc: "A score from 1 to 6 from a fixed formula you can read." },
      { title: "Route", desc: "First eligible agent by skill, availability, and capacity." },
    ],
  },
  ar: {
    headline: "رسالة صوتية بالعامية المصرية تدخل، وتذكرة معاودة اتصال مرتبة ومحددة الموظف تخرج.",
    steps: [
      { title: "تفريغ الصوت", desc: "Whisper large-v3 شغال على السيرفر بتاعكم والصوت مبيخرجش منه." },
      {
        title: "التصنيف",
        desc: "MARBERTv2 بيقرأ أربع حقول: نوع الشكوى، الاستعجال، حالة العميل، وChurn Risk.",
      },
      { title: "ترتيب الأولوية", desc: "درجة من 1 إلى 6 بمعادلة ثابتة وواضحة." },
      { title: "التوجيه", desc: "أول موظف مؤهل حسب المهارة والتوفر والسعة." },
    ],
  },
} as const;

export default function LoginPage() {
  const { user, authLoading, refreshAuth, locale, setLocale, theme, setTheme } = useApp();
  const router = useRouter();
  const t = UI_COPY[locale];
  const aside = AUTH_ASIDE[locale];

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && user) {
      router.replace(user.role === "agent" ? "/my-tickets" : "/dashboard");
    }
  }, [authLoading, user, router]);

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setError(null);
    if (!email.trim() || !password) {
      setError(
        locale === "ar"
          ? "يرجى إدخال البريد الإلكتروني وكلمة المرور."
          : "Please enter both your email address and password."
      );
      return;
    }
    setSubmitting(true);
    try {
      await api.login(email.trim(), password);
      const me = await refreshAuth();
      if (me) {
        router.replace(me.role === "agent" ? "/my-tickets" : "/dashboard");
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError(
          locale === "ar"
            ? "تعذر الاتصال بخادم المصادقة. حاول مرة أخرى."
            : "Could not reach the authentication server. Please try again."
        );
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-page">
      <aside className="auth-aside">
        <div className="auth-aside-brand">
          <SvrBrandMark size={40} />
          <div className="rail-brand-text">
            <span className="rail-brand-name">SVR</span>
            <span className="rail-brand-sub">Smart Voicemail Router</span>
          </div>
        </div>

        <div>
          <h2>{aside.headline}</h2>
          <ol className="auth-steps">
            {aside.steps.map((step, index) => (
              <li key={step.title} className="auth-step">
                <span className="auth-step-no">{String(index + 1).padStart(2, "0")}</span>
                <strong>{step.title}</strong>
                <span className="auth-step-desc">{step.desc}</span>
              </li>
            ))}
          </ol>
        </div>

        <svg
          className="auth-wave"
          viewBox="0 0 1200 120"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path d="M0 60H440M760 60H1200" stroke="var(--rail-accent)" strokeWidth="4" />
          <g stroke="var(--rail-accent)" strokeWidth="9" strokeLinecap="round">
            <path d="M490 60v-12m28 24V38m28 44V22m28 60V8m28 74V22m28 60V38m28 22V48m28 12V54" />
          </g>
        </svg>
      </aside>

      <div className="auth-main">
      <div className="auth-card">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 8,
            marginBottom: 16,
          }}
        >
          <div className="auth-brand-inline" style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <SvrBrandMark size={30} />
            <div>
              <div className="brand-title">{t.appName}</div>
              <div className="muted" style={{ fontSize: 12 }}>
                {t.orgName}
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 4, marginInlineStart: "auto" }}>
            <button
              type="button"
              className="btn ghost"
              onClick={() => setLocale(locale === "en" ? "ar" : "en")}
              aria-label={locale === "en" ? "Switch to Arabic" : "Switch to English"}
            >
              <IconLanguage size={18} stroke={1.75} aria-hidden="true" />
              <span>{locale === "en" ? "العربية" : "EN"}</span>
            </button>
            <button
              type="button"
              className="btn ghost"
              onClick={() => setTheme(theme === "light" ? "dark" : "light")}
              aria-label={theme === "light" ? "Switch to dark theme" : "Switch to light theme"}
            >
              {theme === "light" ? (
                <IconMoon size={18} stroke={1.75} aria-hidden="true" />
              ) : (
                <IconSun size={18} stroke={1.75} aria-hidden="true" />
              )}
            </button>
          </div>
        </div>

        <h1>{locale === "ar" ? "تسجيل دخول المشغل" : "Operator Sign In"}</h1>
        <p className="sub">
          {locale === "ar"
            ? "أدخل بيانات حسابك للوصول إلى قائمة معاودة الاتصال وإدارة الرسائل الصوتية."
            : "Sign in with your telecom care operator account to access subscriber voicemail queues."}
        </p>

        {error && (
          <div className="alert error" role="alert">
            <IconAlertCircle size={18} stroke={1.8} aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <label className="field" htmlFor="login-email">
            <span>{locale === "ar" ? "البريد الإلكتروني" : "Email Address"}</span>
            <input
              id="login-email"
              name="email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(ev) => setEmail(ev.target.value)}
              placeholder="supervisor@telecom.local"
              disabled={submitting}
            />
          </label>

          <label className="field" htmlFor="login-password">
            <span>{locale === "ar" ? "كلمة المرور" : "Password"}</span>
            <input
              id="login-password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(ev) => setPassword(ev.target.value)}
              disabled={submitting}
            />
          </label>

          <button type="submit" className="btn primary" disabled={submitting}>
            <IconLock size={17} stroke={1.8} aria-hidden="true" />
            <span>
              {submitting
                ? locale === "ar"
                  ? "جاري التحقق..."
                  : "Signing in..."
                : locale === "ar"
                  ? "تسجيل الدخول"
                  : "Sign In"}
            </span>
          </button>
        </form>

        <div
          style={{
            marginTop: 20,
            paddingTop: 14,
            borderTop: "1px solid var(--line)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 12,
            flexWrap: "wrap",
            fontSize: 12,
          }}
        >
          <span className="muted">
            {locale === "ar"
              ? "جلسة محمية تنتهي بعد 8 ساعات من عدم النشاط."
              : "HttpOnly session expires after 8 hours of inactivity."}
          </span>
          <div className="auth-legal">
            <Link href="/privacy">{t.privacy}</Link>
            <Link href="/terms">{t.terms}</Link>
          </div>
        </div>
      </div>
      </div>
    </main>
  );
}
