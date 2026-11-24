"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  IconAlertCircle,
  IconArrowLeft,
  IconArrowRight,
  IconDownload,
  IconRefresh,
} from "@tabler/icons-react";
import { AppShell } from "@/components/AppShell";
import { useApp } from "@/components/AppProvider";
import { api, ApiError } from "@/lib/api";
import { UI_COPY } from "@/lib/i18n";
import { formatUtcTimestamp } from "@/lib/taxonomy";
import type { AuditLogListResponse } from "@/lib/types";

const ENTITY_TYPES = ["ticket", "agent", "user", "setting", "eval"] as const;
const AUDIT_ACTIONS = [
  "login",
  "logout",
  "created",
  "classified",
  "routed",
  "corrected",
  "reassigned",
  "status_changed",
  "setting_changed",
  "exported",
] as const;

export default function AuditLogPage() {
  const { locale } = useApp();
  const t = UI_COPY[locale];

  const [entityType, setEntityType] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [actorFilter, setActorFilter] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);

  const [data, setData] = useState<AuditLogListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadLogs = useCallback(async () => {
    setError(null);
    try {
      const res = await api.listAuditLogs({
        limit: 25,
        cursor: cursor || undefined,
        entity_type: entityType || undefined,
        action: actionFilter || undefined,
        actor: actorFilter.trim() || undefined,
      });
      setData(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load audit log.");
    } finally {
      setLoading(false);
    }
  }, [entityType, actionFilter, actorFilter, cursor]);

  useEffect(() => {
    setLoading(true);
    void loadLogs();
  }, [loadLogs]);

  return (
    <AppShell allowedRoles={["supervisor", "admin"]}>
      <div className="page-head">
        <div>
          <h1>{locale === "ar" ? "سجل التدقيق والمساءلة" : "Operations Audit Log"}</h1>
          <p className="sub" style={{ margin: 0 }}>
            {locale === "ar"
              ? "سجل كامل لكل عمليات الدخول والتصنيف والتصحيح وإعادة التوجيه وتغيير الإعدادات."
              : "Immutable trail of logins, pipeline decisions, supervisor corrections, reassignments, settings updates, and exports."}
          </p>
        </div>

        <div className="page-head-actions">
          <a href={api.auditExportUrl("csv")} className="btn" download>
            <IconDownload size={16} stroke={1.8} aria-hidden="true" />
            <span>{locale === "ar" ? "تصدير CSV" : "Export CSV"}</span>
          </a>
          <a href={api.auditExportUrl("json")} className="btn" download>
            <IconDownload size={16} stroke={1.8} aria-hidden="true" />
            <span>{locale === "ar" ? "تصدير JSON" : "Export JSON"}</span>
          </a>
          <button
            type="button"
            className="btn primary"
            onClick={() => void loadLogs()}
            disabled={loading}
          >
            <IconRefresh size={16} stroke={1.8} aria-hidden="true" />
            <span>{locale === "ar" ? "تحديث" : "Refresh"}</span>
          </button>
        </div>
      </div>

      <div className="toolbar">
        <label className="field">
          <span>{locale === "ar" ? "نوع الكيان" : "Entity Type"}</span>
          <select
            value={entityType}
            onChange={(ev) => {
              setEntityType(ev.target.value);
              setCursor(null);
            }}
          >
            <option value="">{t.allOption}</option>
            {ENTITY_TYPES.map((et) => (
              <option key={et} value={et}>
                {et}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>{locale === "ar" ? "الإجراء" : "Action"}</span>
          <select
            value={actionFilter}
            onChange={(ev) => {
              setActionFilter(ev.target.value);
              setCursor(null);
            }}
          >
            <option value="">{t.allOption}</option>
            {AUDIT_ACTIONS.map((ac) => (
              <option key={ac} value={ac}>
                {ac}
              </option>
            ))}
          </select>
        </label>

        <label className="field" style={{ flex: "1 1 200px" }}>
          <span>{locale === "ar" ? "الفاعل (بريد أو system)" : "Actor (email or system)"}</span>
          <input
            type="text"
            value={actorFilter}
            onChange={(ev) => {
              setActorFilter(ev.target.value);
              setCursor(null);
            }}
            placeholder="system / supervisor@telecom.local"
          />
        </label>
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
              ? "لا توجد أحداث تدقيق مطابقة للتصفية الحالية."
              : "No audit events match the active filters."}
          </p>
        </div>
      ) : (
        <>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>{locale === "ar" ? "الوقت" : "Timestamp"}</th>
                  <th>{locale === "ar" ? "الفاعل" : "Actor"}</th>
                  <th>{locale === "ar" ? "الكيان" : "Entity"}</th>
                  <th>{locale === "ar" ? "الإجراء" : "Action"}</th>
                  <th>{locale === "ar" ? "التغيير (قديم -> جديد)" : "Diff (old_value -> new_value)"}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((ev) => (
                  <tr key={ev.id}>
                    <td className="num mono muted" style={{ whiteSpace: "nowrap" }}>
                      {formatUtcTimestamp(ev.created_at, locale)}
                    </td>
                    <td>
                      <strong>{ev.actor}</strong>
                    </td>
                    <td className="mono">
                      {ev.entity_type} · {ev.entity_id.slice(0, 8)}
                    </td>
                    <td className="mono">{ev.action}</td>
                    <td className="mono muted" style={{ maxWidth: 460, wordBreak: "break-word" }}>
                      {ev.old_value || ev.new_value ? (
                        <>
                          <span>{ev.old_value ? JSON.stringify(ev.old_value) : "{}"}</span>
                          {" -> "}
                          <span style={{ color: "var(--ink)" }}>
                            {ev.new_value ? JSON.stringify(ev.new_value) : "{}"}
                          </span>
                        </>
                      ) : (
                        "-"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="pager">
            <span>
              {locale === "ar"
                ? `عرض ${data.items.length} من ${data.total} حدث`
                : `Showing ${data.items.length} of ${data.total} events`}
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
    </AppShell>
  );
}
