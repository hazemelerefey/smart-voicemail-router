"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { IconAlertCircle, IconLanguage, IconLock, IconMoon, IconSun } from "@tabler/icons-react";
import { useApp } from "@/components/AppProvider";
import { SvrBrandMark } from "@/components/SvrBrandMark";
import { api, ApiError } from "@/lib/api";
import { UI_COPY } from "@/lib/i18n";

export default function LoginPage() {
  const { user, authLoading, refreshAuth, locale, setLocale, theme, setTheme } = useApp();
  const router = useRouter();
  const t = UI_COPY[locale];

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
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <SvrBrandMark size={30} />
            <div>
              <div className="brand-title">{t.appName}</div>
              <div className="muted" style={{ fontSize: 12 }}>
                {t.orgName}
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 4 }}>
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
    </main>
  );
}
