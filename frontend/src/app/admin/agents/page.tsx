"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  IconAlertCircle,
  IconCheck,
  IconEdit,
  IconPlus,
  IconUserCheck,
  IconUserOff,
} from "@tabler/icons-react";
import { AppShell } from "@/components/AppShell";
import { useApp } from "@/components/AppProvider";
import { ConfirmModal } from "@/components/ConfirmModal";
import { api, ApiError } from "@/lib/api";
import { UI_COPY, labelForCategory, labelForSkill } from "@/lib/i18n";
import { COMPLAINT_CATEGORIES, TELECOM_SKILLS } from "@/lib/taxonomy";
import type { AgentResponse } from "@/lib/types";

export default function AdminAgentsPage() {
  const { locale } = useApp();
  const t = UI_COPY[locale];

  const [agents, setAgents] = useState<AgentResponse[]>([]);
  const [skillMap, setSkillMap] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Create / Edit agent form
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [skills, setSkills] = useState<string[]>(["Network"]);
  const [capacity, setCapacity] = useState<number>(5);
  const [available, setAvailable] = useState<boolean>(true);
  const [seedOrder, setSeedOrder] = useState<number>(10);

  // Deactivation confirmation modal
  const [confirmAgent, setConfirmAgent] = useState<AgentResponse | null>(null);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const [agentList, mappingRes] = await Promise.all([
        api.listAgents(),
        api.getSkillMappings(),
      ]);
      setAgents(agentList);
      const mapObj: Record<string, string> = {};
      for (const item of mappingRes.mappings) {
        mapObj[item.category] = item.skill_name;
      }
      setSkillMap(mapObj);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load agents and skill mappings.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    void loadData();
  }, [loadData]);

  const toggleSkillCheckbox = (skill: string) => {
    setSkills((prev) =>
      prev.includes(skill) ? prev.filter((s) => s !== skill) : [...prev, skill]
    );
  };

  const resetForm = () => {
    setEditingId(null);
    setName("");
    setSkills(["Network"]);
    setCapacity(5);
    setAvailable(true);
    setSeedOrder(10);
  };

  const startEdit = (agent: AgentResponse) => {
    setEditingId(agent.id);
    setName(agent.name);
    setSkills(agent.skills.length > 0 ? [...agent.skills] : ["General"]);
    setCapacity(agent.capacity);
    setAvailable(agent.available);
    setSeedOrder(agent.seed_order);
    setError(null);
    setNotice(null);
  };

  const handleAgentSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setError(null);
    setNotice(null);
    if (name.trim().length < 2) {
      setError(
        locale === "ar"
          ? "اسم الموظف يجب ألا يقل عن حرفين."
          : "Agent name must be at least 2 characters."
      );
      return;
    }
    if (skills.length === 0) {
      setError(
        locale === "ar"
          ? "اختر مهارة واحدة على الأقل للموظف."
          : "Select at least one telecom care skill."
      );
      return;
    }
    setBusy(true);
    try {
      if (editingId) {
        await api.updateAgent(editingId, {
          name: name.trim(),
          skills,
          capacity,
          available,
          seed_order: seedOrder,
        });
        setNotice(locale === "ar" ? "تم تحديث بيانات الموظف." : "Agent updated successfully.");
      } else {
        await api.createAgent({
          name: name.trim(),
          skills,
          capacity,
          available,
          seed_order: seedOrder,
        });
        setNotice(locale === "ar" ? "تمت إضافة الموظف الجديد." : "New agent added to routing roster.");
      }
      resetForm();
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to save agent.");
    } finally {
      setBusy(false);
    }
  };

  const handleToggleAvailable = async (agent: AgentResponse) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.updateAgent(agent.id, { available: !agent.available });
      setNotice(
        locale === "ar"
          ? `تم تحديث حالة التوفر للموظف ${agent.name}.`
          : `Availability updated for ${agent.name}.`
      );
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to update availability.");
    } finally {
      setBusy(false);
    }
  };

  const handleConfirmDeactivateOrReactivate = async () => {
    if (!confirmAgent) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.updateAgent(confirmAgent.id, { active: !confirmAgent.active });
      setNotice(
        confirmAgent.active
          ? locale === "ar"
            ? `تم تعطيل الموظف ${confirmAgent.name}.`
            : `${confirmAgent.name} deactivated.`
          : locale === "ar"
            ? `تم إعادة تفعيل الموظف ${confirmAgent.name}.`
            : `${confirmAgent.name} reactivated.`
      );
      setConfirmAgent(null);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to change agent status.");
    } finally {
      setBusy(false);
    }
  };

  const handleSaveSkillMappings = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const fullMap: Record<string, string> = {};
      for (const cat of COMPLAINT_CATEGORIES) {
        fullMap[cat] = skillMap[cat] || "General";
      }
      await api.updateSkillMappings(fullMap);
      setNotice(
        locale === "ar"
          ? "تم حفظ ربط الـ 11 فئة بالمهارات بنجاح."
          : "All 11 telecom categories skill mapping saved."
      );
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to save skill mapping.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell allowedRoles={["admin"]}>
      <div className="page-head">
        <div>
          <h1>
            {locale === "ar"
              ? "إدارة الموظفين وربط المهارات"
              : "Agents & Telecom Skill Mapping"}
          </h1>
          <p className="sub" style={{ margin: 0 }}>
            {locale === "ar"
              ? "إدارة فرق رعاية الشبكة والفواتير والمشتركين وسعة كل موظف وربط الـ 11 فئة."
              : "Manage Network Care, Billing & Bundles Care, and Subscriber & Retention Care specialists, capacity, and the 11-category skill mapping."}
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

      {loading ? (
        <p className="loading-state">{t.loading}</p>
      ) : (
        <>
          {/* Add / Edit Agent Form */}
          <section className="card">
            <h2>
              {editingId
                ? locale === "ar"
                  ? "تعديل بيانات موظف"
                  : "Edit Care Specialist"
                : locale === "ar"
                  ? "إضافة موظف جديد"
                  : "Add Care Specialist"}
            </h2>
            <form onSubmit={handleAgentSubmit} style={{ display: "grid", gap: 14 }}>
              <div className="detail-grid" style={{ marginBottom: 0 }}>
                <label className="field">
                  <span>{locale === "ar" ? "اسم الموظف" : "Specialist Name"}</span>
                  <input
                    type="text"
                    required
                    minLength={2}
                    maxLength={160}
                    value={name}
                    onChange={(ev) => setName(ev.target.value)}
                    placeholder={
                      locale === "ar" ? "أخصائي رعاية الشبكة 2" : "Network Care Specialist 2"
                    }
                  />
                </label>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <label className="field">
                    <span>{locale === "ar" ? "السعة القصوى" : "Max Capacity"}</span>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={capacity}
                      onChange={(ev) => setCapacity(Number(ev.target.value) || 1)}
                    />
                  </label>
                  <label className="field">
                    <span>{locale === "ar" ? "ترتيب الأولوية (Seed Order)" : "Seed Order"}</span>
                    <input
                      type="number"
                      min={1}
                      max={10000}
                      value={seedOrder}
                      onChange={(ev) => setSeedOrder(Number(ev.target.value) || 1)}
                    />
                  </label>
                </div>
              </div>

              <div style={{ display: "flex", gap: 18, flexWrap: "wrap", alignItems: "center" }}>
                <span className="field-label">{locale === "ar" ? "المهارات:" : "Skills:"}</span>
                {TELECOM_SKILLS.map((sk) => (
                  <label className="checkbox-label" key={sk}>
                    <input
                      type="checkbox"
                      checked={skills.includes(sk)}
                      onChange={() => toggleSkillCheckbox(sk)}
                    />
                    <span>
                      {labelForSkill(sk, locale)} ({sk})
                    </span>
                  </label>
                ))}
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={available}
                    onChange={(ev) => setAvailable(ev.target.checked)}
                  />
                  <span>{locale === "ar" ? "متاح لاستلام تذاكر" : "Available for routing"}</span>
                </label>
              </div>

              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button type="submit" className="btn primary" disabled={busy}>
                  <IconPlus size={16} stroke={1.8} aria-hidden="true" />
                  <span>
                    {editingId
                      ? t.saveChanges
                      : locale === "ar"
                        ? "إضافة الموظف"
                        : "Add Specialist"}
                  </span>
                </button>
                {editingId && (
                  <button type="button" className="btn" onClick={resetForm} disabled={busy}>
                    {t.cancel}
                  </button>
                )}
              </div>
            </form>
          </section>

          {/* Roster Table */}
          <section className="card">
            <h2>{locale === "ar" ? "قائمة الموظفين الحاليين" : "Active & Inactive Roster"}</h2>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th className="num">{locale === "ar" ? "الترتيب" : "Order"}</th>
                    <th>{locale === "ar" ? "الاسم" : "Name"}</th>
                    <th>{locale === "ar" ? "المهارات" : "Skills"}</th>
                    <th className="num">{locale === "ar" ? "الحمل / السعة" : "Load / Capacity"}</th>
                    <th>{locale === "ar" ? "التوفر" : "Availability"}</th>
                    <th>{locale === "ar" ? "الحالة" : "Status"}</th>
                    <th>{locale === "ar" ? "إجراءات" : "Actions"}</th>
                  </tr>
                </thead>
                <tbody>
                  {agents.map((agent) => (
                    <tr key={agent.id}>
                      <td className="num mono">{agent.seed_order}</td>
                      <td>
                        <strong>{agent.name}</strong>
                      </td>
                      <td>
                        {agent.skills.map((s) => labelForSkill(s, locale)).join(", ")}
                      </td>
                      <td className="num">
                        {agent.current_load} / {agent.capacity}
                      </td>
                      <td>
                        <span className={agent.available ? "ok-text" : "high-text"}>
                          {agent.available
                            ? locale === "ar"
                              ? "متاح"
                              : "Available"
                            : locale === "ar"
                              ? "غير متاح"
                              : "Unavailable"}
                        </span>
                      </td>
                      <td>
                        <span className={agent.active ? "ok-text" : "muted"}>
                          {agent.active
                            ? locale === "ar"
                              ? "نشط"
                              : "Active"
                            : locale === "ar"
                              ? "معطل"
                              : "Deactivated"}
                        </span>
                      </td>
                      <td>
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                          <button
                            type="button"
                            className="btn"
                            onClick={() => startEdit(agent)}
                            disabled={busy}
                          >
                            <IconEdit size={15} stroke={1.8} aria-hidden="true" />
                            <span>{locale === "ar" ? "تعديل" : "Edit"}</span>
                          </button>
                          <button
                            type="button"
                            className="btn"
                            onClick={() => void handleToggleAvailable(agent)}
                            disabled={busy || !agent.active}
                          >
                            <span>
                              {agent.available
                                ? locale === "ar"
                                  ? "إيقاف التوفر"
                                  : "Set Away"
                                : locale === "ar"
                                  ? "تفعيل التوفر"
                                  : "Set Available"}
                            </span>
                          </button>
                          <button
                            type="button"
                            className={agent.active ? "btn danger" : "btn"}
                            onClick={() => setConfirmAgent(agent)}
                            disabled={busy}
                          >
                            {agent.active ? (
                              <IconUserOff size={15} stroke={1.8} aria-hidden="true" />
                            ) : (
                              <IconUserCheck size={15} stroke={1.8} aria-hidden="true" />
                            )}
                            <span>
                              {agent.active
                                ? locale === "ar"
                                  ? "تعطيل"
                                  : "Deactivate"
                                : locale === "ar"
                                  ? "تفعيل"
                                  : "Reactivate"}
                            </span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* 11-Category Telecom Skill Mapping */}
          <section className="card">
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
                flexWrap: "wrap",
                marginBottom: 12,
              }}
            >
              <div>
                <h2 style={{ margin: 0 }}>
                  {locale === "ar"
                    ? "ربط فئات الشكاوى الـ 11 بمهارات الفرق"
                    : "11-Category Telecom Skill Mapping (FR20)"}
                </h2>
                <p className="sub" style={{ margin: "4px 0 0" }}>
                  {locale === "ar"
                    ? "يجب ربط جميع الفئات الـ 11 بفريق مهارات صالح."
                    : "Every one of the 11 complaint categories must map to a valid care team skill."}
                </p>
              </div>
              <button
                type="button"
                className="btn"
                onClick={() => void handleSaveSkillMappings()}
                disabled={busy}
              >
                <IconCheck size={16} stroke={1.8} aria-hidden="true" />
                <span>{locale === "ar" ? "حفظ ربط المهارات" : "Save Skill Mapping"}</span>
              </button>
            </div>

            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>{locale === "ar" ? "فئة الشكوى" : "Complaint Category"}</th>
                    <th>{locale === "ar" ? "المعرّف البرمجي" : "Taxonomy Key"}</th>
                    <th>{locale === "ar" ? "فريق المهارة المطلوب" : "Required Skill"}</th>
                  </tr>
                </thead>
                <tbody>
                  {COMPLAINT_CATEGORIES.map((cat) => (
                    <tr key={cat}>
                      <td>
                        <strong>{labelForCategory(cat, locale)}</strong>
                      </td>
                      <td className="mono muted">{cat}</td>
                      <td>
                        <select
                          aria-label={`Skill mapping for ${cat}`}
                          value={skillMap[cat] || "General"}
                          onChange={(ev) =>
                            setSkillMap((prev) => ({ ...prev, [cat]: ev.target.value }))
                          }
                          disabled={busy}
                        >
                          {TELECOM_SKILLS.map((sk) => (
                            <option key={sk} value={sk}>
                              {labelForSkill(sk, locale)} ({sk})
                            </option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      <ConfirmModal
        open={Boolean(confirmAgent)}
        title={
          confirmAgent?.active
            ? locale === "ar"
              ? "تأكيد تعطيل الموظف"
              : "Confirm Agent Deactivation"
            : locale === "ar"
              ? "تأكيد إعادة تفعيل الموظف"
              : "Confirm Agent Reactivation"
        }
        description={
          confirmAgent?.active
            ? locale === "ar"
              ? `هل تريد تعطيل ${confirmAgent.name}؟ لن يتم توجيه أي تذاكر جديدة لهذا الموظف.`
              : `Deactivate ${confirmAgent.name}? No new subscriber tickets will route to this specialist until reactivated.`
            : locale === "ar"
              ? `هل تريد إعادة تفعيل ${confirmAgent?.name || ""} في قائمة التوجيه؟`
              : `Reactivate ${confirmAgent?.name || ""} so eligible tickets can route to this specialist again?`
        }
        confirmLabel={
          confirmAgent?.active
            ? locale === "ar"
              ? "نعم، تعطيل"
              : "Confirm Deactivate"
            : locale === "ar"
              ? "نعم، تفعيل"
              : "Confirm Reactivate"
        }
        cancelLabel={t.cancel}
        danger={Boolean(confirmAgent?.active)}
        busy={busy}
        onCancel={() => setConfirmAgent(null)}
        onConfirm={() => void handleConfirmDeactivateOrReactivate()}
      />
    </AppShell>
  );
}
