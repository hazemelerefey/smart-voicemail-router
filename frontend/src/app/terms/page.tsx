"use client";

import Link from "next/link";
import { IconArrowLeft, IconFileText } from "@tabler/icons-react";
import { useApp } from "@/components/AppProvider";
import { SvrBrandMark } from "@/components/SvrBrandMark";
import { UI_COPY } from "@/lib/i18n";

export default function TermsPage() {
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
                ? "شروط الاستخدام التشغيلي والإشراف البشري"
                : "Operator Terms of Use & Human Oversight"}
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
          <IconFileText
            size={16}
            stroke={1.8}
            aria-hidden="true"
            style={{ verticalAlign: "text-bottom", marginInlineEnd: 6 }}
          />
          {locale === "ar" ? "نطاق التشغيل البشري المساعد" : "Human-Assisted Routing Scope"}
        </h2>
        <p>
          {locale === "ar"
            ? "نظام توجيه الرسائل الصوتية الذكي هو نظام ذكاء اصطناعي محدود المخاطر يساعد فرق خدمة العملاء على تصنيف الشكاوى وتحديد الأولويات واقتراح نص معاودة الاتصال. يقوم الموظف المختص بإجراء المكالمة والقرار النهائي."
            : "SVR is a limited-risk decision-support system for telecom customer-care operations. It transcribes, classifies, prioritizes, and routes subscriber voicemails, and prepares a grounded callback script template. It never places automatic calls or sends automated messages to subscribers."}
        </p>
      </section>

      <section className="card">
        <h2>{locale === "ar" ? "مسؤوليات المشغل والصلاحيات" : "Role Responsibilities & Controls"}</h2>
        <ul style={{ margin: 0, paddingInlineStart: 20, display: "grid", gap: 8 }}>
          <li>
            {locale === "ar"
              ? "مخرجات النماذج احتمالية ويتم تمييزها بوضوح كمخرجات نموذج منفصلة عن التصحيحات البشرية."
              : "Model outputs are probabilistic and labeled explicitly as model outputs, distinct from human supervisor corrections."}
          </li>
          <li>
            {locale === "ar"
              ? "التذاكر ذات الثقة المنخفضة أو التصنيفات الناقصة أو عند عدم توفر موظف تحول تلقائيا إلى قائمة المراجعة البشرية."
              : "Low-confidence, missing/invalid label, or capacity-constrained tickets are routed automatically to the Human Routing Queue."}
          </li>
          <li>
            {locale === "ar"
              ? "يمتلك المشرف ومدير النظام حق إيقاف التوجيه التلقائي فورا عبر مفتاح الإيقاف الطارئ."
              : "Admins and Supervisors can pause automatic routing immediately via the Kill Switch."}
          </li>
          <li>
            {locale === "ar"
              ? "الوصول مقصور على حسابات المشغل المصرح بها، ويحظر مشاركة بيانات الدخول."
              : "Access is restricted to authorized operator accounts under Role-Based Access Control (Admin, Supervisor, Agent). Credential sharing is prohibited."}
          </li>
        </ul>
      </section>
    </main>
  );
}
