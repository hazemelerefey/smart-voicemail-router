"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  IconAdjustmentsHorizontal,
  IconAlertTriangle,
  IconChartBar,
  IconHistory,
  IconInbox,
  IconLanguage,
  IconLogout,
  IconMenu2,
  IconMoon,
  IconPhoneCall,
  IconPlugConnected,
  IconPlugConnectedX,
  IconRefresh,
  IconShieldOff,
  IconSun,
  IconUsersGroup,
  IconX,
} from "@tabler/icons-react";
import { useApp } from "./AppProvider";
import { SvrBrandMark } from "./SvrBrandMark";
import { UI_COPY } from "@/lib/i18n";
import type { UserRole } from "@/lib/types";

interface AppShellProps {
  children: React.ReactNode;
  allowedRoles?: UserRole[];
  reviewBadgeCount?: number;
}

export function AppShell({ children, allowedRoles, reviewBadgeCount }: AppShellProps) {
  const { user, authLoading, logout, locale, setLocale, theme, setTheme, settings, wsStatus } =
    useApp();
  const pathname = usePathname();
  const router = useRouter();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const t = UI_COPY[locale];

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
    }
  }, [authLoading, user, router]);

  useEffect(() => {
    setDrawerOpen(false);
  }, [pathname]);

  if (authLoading) {
    return (
      <div className="main-content">
        <p className="loading-state">{t.loading}</p>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    const fallbackPath = user.role === "agent" ? "/my-tickets" : "/dashboard";
    return (
      <div className="main-content">
        <div className="card" style={{ maxWidth: 520, margin: "40px auto" }}>
          <h1>{locale === "ar" ? "غير مصرح بالوصول" : "Access Restricted"}</h1>
          <p className="muted">
            {locale === "ar"
              ? "حسابك لا يمتلك صلاحية فتح هذه الصفحة."
              : "Your current operator role does not have permission to open this page."}
          </p>
          <Link href={fallbackPath} className="btn primary">
            {locale === "ar" ? "الانتقال إلى صفحتك الرئيسية" : "Go to Your Workspace"}
          </Link>
        </div>
      </div>
    );
  }

  const isSupervisorOrAdmin = user.role === "supervisor" || user.role === "admin";
  const isAdmin = user.role === "admin";

  const opsNav = [
    ...(isSupervisorOrAdmin
      ? [{ href: "/dashboard", label: t.navQueue, icon: IconInbox }]
      : []),
    ...(user.role === "agent"
      ? [{ href: "/my-tickets", label: t.navMyTickets, icon: IconPhoneCall }]
      : []),
    ...(isSupervisorOrAdmin
      ? [
          {
            href: "/review-queue",
            label: t.navReviewQueue,
            icon: IconAlertTriangle,
            count: reviewBadgeCount,
          },
          { href: "/evaluation", label: t.navEvaluation, icon: IconChartBar },
          { href: "/audit-log", label: t.navAuditLog, icon: IconHistory },
        ]
      : []),
  ];

  const adminNav = isAdmin
    ? [
        { href: "/admin/agents", label: t.navAgents, icon: IconUsersGroup },
        { href: "/admin/settings", label: t.navSettings, icon: IconAdjustmentsHorizontal },
      ]
    : [];

  const renderNavLinks = () => (
    <>
      <div className="rail-section-label">{t.navSectionOps}</div>
      <nav aria-label={t.navSectionOps}>
        {opsNav.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`rail-link${active ? " current" : ""}`}
              aria-current={active ? "page" : undefined}
            >
              <Icon size={18} stroke={1.75} aria-hidden="true" />
              <span>{item.label}</span>
              {typeof item.count === "number" && item.count > 0 && (
                <span className="rail-count">{item.count}</span>
              )}
            </Link>
          );
        })}
      </nav>

      {adminNav.length > 0 && (
        <>
          <div className="rail-section-label">{t.navSectionAdmin}</div>
          <nav aria-label={t.navSectionAdmin}>
            {adminNav.map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`rail-link${active ? " current" : ""}`}
                  aria-current={active ? "page" : undefined}
                >
                  <Icon size={18} stroke={1.75} aria-hidden="true" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </>
      )}

      <div className="rail-foot">
        <div className="rail-user-name">{user.full_name}</div>
        <div className="mono">{user.email}</div>
        <div className="muted" style={{ textTransform: "uppercase", fontSize: 11, fontWeight: 700 }}>
          {user.role}
        </div>
        <div className="rail-legal">
          <Link href="/privacy">{t.privacy}</Link>
          <Link href="/terms">{t.terms}</Link>
        </div>
      </div>
    </>
  );

  const wsIndicator =
    wsStatus === "connected" ? (
      <span className="status-inline ok-text" title={t.wsConnected}>
        <IconPlugConnected size={16} stroke={1.8} aria-hidden="true" />
        <span className="ws-label-text">{t.wsConnected}</span>
      </span>
    ) : wsStatus === "reconnecting" ? (
      <span className="status-inline high-text" title={t.wsReconnecting}>
        <IconRefresh size={16} stroke={1.8} aria-hidden="true" />
        <span className="ws-label-text">{t.wsReconnecting}</span>
      </span>
    ) : (
      <span className="status-inline muted" title={t.wsOffline}>
        <IconPlugConnectedX size={16} stroke={1.8} aria-hidden="true" />
        <span className="ws-label-text">{t.wsOffline}</span>
      </span>
    );

  const handleSignOut = async () => {
    await logout();
    router.replace("/login");
  };

  const homeHref = user.role === "agent" ? "/my-tickets" : "/dashboard";

  return (
    <div className="app-shell">
      <a href="#main-workspace" className="skip-link">
        {t.skipToMain}
      </a>

      <header className="topbar">
        <button
          type="button"
          className="btn ghost mobile-menu-btn"
          aria-label={locale === "ar" ? "فتح القائمة" : "Open navigation menu"}
          onClick={() => setDrawerOpen(true)}
        >
          <IconMenu2 size={20} stroke={1.8} aria-hidden="true" />
        </button>

        <Link href={homeHref} className="brand-link">
          <SvrBrandMark size={28} />
          <span className="brand-title">{t.appName}</span>
          <span className="brand-title-compact" aria-hidden="true">SVR</span>
        </Link>
        <span className="brand-org">{t.orgName}</span>

        <div className="topbar-right">
          {wsIndicator}

          <button
            type="button"
            className="btn ghost topbar-btn"
            onClick={() => setLocale(locale === "en" ? "ar" : "en")}
            aria-label={locale === "en" ? "Switch to Arabic" : "Switch to English"}
          >
            <IconLanguage size={18} stroke={1.75} aria-hidden="true" />
            <span className="topbar-lang-label">{locale === "en" ? "العربية" : "EN"}</span>
          </button>

          <button
            type="button"
            className="btn ghost topbar-btn"
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
            aria-label={
              theme === "light" ? "Switch to dark theme" : "Switch to light theme"
            }
          >
            {theme === "light" ? (
              <IconMoon size={18} stroke={1.75} aria-hidden="true" />
            ) : (
              <IconSun size={18} stroke={1.75} aria-hidden="true" />
            )}
            <span className="topbar-btn-label">
              {theme === "light" ? t.themeDark : t.themeLight}
            </span>
          </button>

          <button
            type="button"
            className="btn topbar-btn"
            onClick={handleSignOut}
            aria-label={t.signOut}
          >
            <IconLogout size={17} stroke={1.75} aria-hidden="true" />
            <span className="topbar-btn-label">{t.signOut}</span>
          </button>
        </div>
      </header>

      {settings && !settings.auto_routing_enabled && (
        <div className="kill-banner" role="alert">
          <div className="kill-banner-left">
            <IconShieldOff size={18} stroke={2} aria-hidden="true" />
            <span>{t.killSwitchBanner}</span>
          </div>
          {isAdmin && (
            <Link href="/admin/settings" className="btn danger">
              {t.manageKillSwitch}
            </Link>
          )}
        </div>
      )}

      <aside className="rail" aria-label="Sidebar navigation">
        {renderNavLinks()}
      </aside>

      {drawerOpen && (
        <div
          className="mobile-drawer-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="Mobile navigation"
          onClick={(ev) => {
            if (ev.target === ev.currentTarget) setDrawerOpen(false);
          }}
        >
          <div className="mobile-drawer">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span className="brand-title">{t.appName}</span>
              <button
                type="button"
                className="btn ghost"
                aria-label={locale === "ar" ? "إغلاق القائمة" : "Close navigation menu"}
                onClick={() => setDrawerOpen(false)}
              >
                <IconX size={20} stroke={1.8} aria-hidden="true" />
              </button>
            </div>
            {renderNavLinks()}
          </div>
        </div>
      )}

      <main id="main-workspace" className="main-content">
        {children}
      </main>
    </div>
  );
}
