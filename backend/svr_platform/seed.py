"""Idempotent bootstrap seed for default telecom organization, agents, mappings, templates, and users."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import hash_password
from .config import Settings
from .models import (
    Agent,
    Organization,
    ScriptTemplate,
    SkillMapping,
    SystemSetting,
    User,
)
from .taxonomy import DEFAULT_SKILL_MAPPING

# Grounded telecom customer-care templates (FR14, FR15, AI6, AI7, zero invented facts)
DEFAULT_TEMPLATES: dict[str, dict[str, str]] = {
    "network_and_connectivity": {
        "customer_request_ar": "المشترك يبلغ عن مشكلة في تغطية الشبكة أو جودة الاتصال ويطلب المتابعة.",
        "customer_request_en": "Subscriber reports a mobile network coverage or connectivity issue and requests technical follow-up.",
        "template_ar": "أهلا بحضرتك من فريق رعاية الشبكة. تم استلام رسالتك الصوتية بخصوص الشبكة والتغطية، وبنتواصل معاك لمراجعة حالة الخط.",
        "template_en": "Hello from Network Care. We received your voicemail regarding network and connectivity and are calling back to review your line status.",
    },
    "billing_and_charges": {
        "customer_request_ar": "المشترك يراجع رسوم أو خصومات على الفاتورة ويطلب توضيحها.",
        "customer_request_en": "Subscriber reports a billing or charge inquiry and requests invoice clarification.",
        "template_ar": "أهلا بحضرتك من فريق الفواتير والباقات. تم استلام رسالتك بخصوص الفواتير والرسوم، وبنتواصل معاك لمراجعة التفاصيل.",
        "template_en": "Hello from Billing & Bundles Care. We received your voicemail regarding billing and charges and are calling to review the statement details.",
    },
    "balance_and_data": {
        "customer_request_ar": "المشترك يستفسر أو يشتكي من الرصيد أو استهلاك باقة الإنترنت.",
        "customer_request_en": "Subscriber reports an issue with mobile balance or data bundle consumption.",
        "template_ar": "أهلا بحضرتك من فريق الفواتير والباقات. تم استلام رسالتك بخصوص الرصيد وباقات الإنترنت، وبنتواصل معاك للمراجعة.",
        "template_en": "Hello from Billing & Bundles Care. We received your voicemail regarding balance and data usage and are calling to check your account.",
    },
    "app_and_account": {
        "customer_request_ar": "المشترك يواجه مشكلة في التطبيق أو الوصول إلى حساب المشترك.",
        "customer_request_en": "Subscriber reports an issue with the operator app or subscriber account access.",
        "template_ar": "أهلا بحضرتك من فريق خدمة المشتركين. تم استلام رسالتك بخصوص التطبيق وحساب المشترك، وبنتواصل معاك للمساعدة.",
        "template_en": "Hello from Subscriber Care. We received your voicemail regarding the app and subscriber account and are calling to assist.",
    },
    "branch_and_staff": {
        "customer_request_ar": "المشترك يشارك ملاحظة أو شكوى حول تجربة الفرع أو موظفي الخدمة.",
        "customer_request_en": "Subscriber shares feedback or a complaint regarding a retail branch or care staff interaction.",
        "template_ar": "أهلا بحضرتك من فريق خدمة المشتركين. تم استلام رسالتك بخصوص تجربة الفرع وخدمة العملاء، وبنتواصل معاك للمتابعة.",
        "template_en": "Hello from Subscriber Care. We received your voicemail regarding branch and staff service and are calling to follow up.",
    },
    "no_reply_or_long_wait": {
        "customer_request_ar": "المشترك يبلغ عن تأخر الرد أو عدم المتابعة على بلاغ سابق.",
        "customer_request_en": "Subscriber reports delayed response or lack of follow-up on a prior care ticket.",
        "template_ar": "أهلا بحضرتك من فريق متابعة الشبكة والخدمة. نعتذر عن تأخر الرد، وبنتواصل معاك الآن لمتابعة رسالتك.",
        "template_en": "Hello from Network Care Follow-up. We received your voicemail regarding delayed response and are calling now to follow up.",
    },
    "cancellation_request": {
        "customer_request_ar": "المشترك يطلب إلغاء الخدمة أو إيقاف الخط.",
        "customer_request_en": "Subscriber requests service cancellation or line termination review.",
        "template_ar": "أهلا بحضرتك من فريق الحفاظ على المشتركين. تم استلام رسالتك بخصوص طلب إلغاء الخط، وبنتواصل معاك لمراجعة الطلب.",
        "template_en": "Hello from Subscriber Retention Care. We received your voicemail regarding line cancellation and are calling to review your request.",
    },
    "thanks_or_praise": {
        "customer_request_ar": "المشترك يوجه شكر أو إشادة بجودة الخدمة.",
        "customer_request_en": "Subscriber shares appreciation or positive feedback for service quality.",
        "template_ar": "أهلا بحضرتك من فريق خدمة المشتركين. نشكرك على رسالتك وتقديرك، وبنتواصل معاك للتأكيد والمتابعة.",
        "template_en": "Hello from Subscriber Care. Thank you for your positive voicemail feedback, we are calling briefly to confirm your satisfaction.",
    },
    "other": {
        "customer_request_ar": "المشترك يطرح استفسار عام يحتاج إلى متابعة من خدمة المشتركين.",
        "customer_request_en": "Subscriber leaves a general telecom care inquiry requiring callback clarification.",
        "template_ar": "أهلا بحضرتك من فريق خدمة المشتركين. تم استلام رسالتك الصوتية، وبنتواصل معاك لمراجعة طلبك.",
        "template_en": "Hello from Subscriber Care. We received your voicemail and are calling back to review your request.",
    },
    "offers_and_packages": {
        "customer_request_ar": "المشترك يستفسر أو يشتكي بخصوص العروض والباقات المتاحة.",
        "customer_request_en": "Subscriber asks about or reports an issue with telecom rate plans, offers, or packages.",
        "template_ar": "أهلا بحضرتك من فريق الفواتير والباقات. تم استلام رسالتك بخصوص العروض والباقات، وبنتواصل معاك للتوضيح.",
        "template_en": "Hello from Billing & Bundles Care. We received your voicemail regarding offers and packages and are calling to assist.",
    },
    "sim_services": {
        "customer_request_ar": "المشترك يطلب مساعدة في خدمات الشريحة أو استبدال الشريحة أو eSIM.",
        "customer_request_en": "Subscriber requests assistance with SIM card, SIM swap, or eSIM provisioning services.",
        "template_ar": "أهلا بحضرتك من فريق رعاية الشبكة والشرائح. تم استلام رسالتك بخصوص خدمات الشريحة، وبنتواصل معاك للمتابعة.",
        "template_en": "Hello from Network & SIM Care. We received your voicemail regarding SIM services and are calling to assist.",
    },
}


def seed_initial_data(db: Session, settings: Settings) -> Organization:
    """Ensure the default single-tenant organization, agents, skills, templates, and users exist."""
    org = db.scalar(select(Organization).where(Organization.slug == settings.svr_org_slug))
    if org is None:
        org = Organization(name=settings.svr_org_name, slug=settings.svr_org_slug)
        db.add(org)
        db.flush()

    sys_setting = db.get(SystemSetting, org.id)
    if sys_setting is None:
        sys_setting = SystemSetting(
            organization_id=org.id,
            confidence_threshold=0.5,
            auto_routing_enabled=True,
            retention_days=90,
            weekly_sample_rate=0.05,
        )
        db.add(sys_setting)

    for category, skill_name in DEFAULT_SKILL_MAPPING.items():
        existing_map = db.scalar(
            select(SkillMapping).where(
                SkillMapping.organization_id == org.id,
                SkillMapping.category == category,
            )
        )
        if existing_map is None:
            db.add(
                SkillMapping(
                    organization_id=org.id,
                    category=category,
                    skill_name=skill_name,
                )
            )

    for category, tpl in DEFAULT_TEMPLATES.items():
        existing_tpl = db.scalar(
            select(ScriptTemplate).where(
                ScriptTemplate.organization_id == org.id,
                ScriptTemplate.category == category,
            )
        )
        if existing_tpl is None:
            db.add(
                ScriptTemplate(
                    organization_id=org.id,
                    category=category,
                    template_ar=tpl["template_ar"],
                    template_en=tpl["template_en"],
                    customer_request_ar=tpl["customer_request_ar"],
                    customer_request_en=tpl["customer_request_en"],
                    version=1,
                )
            )

    existing_agents = db.scalars(
        select(Agent).where(Agent.organization_id == org.id).order_by(Agent.seed_order.asc())
    ).all()
    agents_by_name = {a.name: a for a in existing_agents}

    seed_agent_specs = [
        ("Network Care Specialist", ["Network"], 5, 1),
        ("Billing & Bundles Specialist", ["Billing"], 5, 2),
        ("Subscriber Care Specialist", ["General"], 5, 3),
    ]
    for name, skills, capacity, order in seed_agent_specs:
        if name not in agents_by_name:
            agent = Agent(
                organization_id=org.id,
                name=name,
                skills=skills,
                capacity=capacity,
                current_load=0,
                available=True,
                active=True,
                seed_order=order,
            )
            db.add(agent)
            db.flush()
            agents_by_name[name] = agent

    default_pw_hash = hash_password(settings.svr_bootstrap_password)
    seed_users = [
        ("admin@telecom.local", "Telecom Operations Admin", "admin", None),
        ("supervisor@telecom.local", "Queue Care Supervisor", "supervisor", None),
        (
            "network.agent@telecom.local",
            "Network Care Specialist",
            "agent",
            agents_by_name["Network Care Specialist"].id,
        ),
        (
            "billing.agent@telecom.local",
            "Billing & Bundles Specialist",
            "agent",
            agents_by_name["Billing & Bundles Specialist"].id,
        ),
        (
            "general.agent@telecom.local",
            "Subscriber Care Specialist",
            "agent",
            agents_by_name["Subscriber Care Specialist"].id,
        ),
    ]
    for email, full_name, role, agent_id in seed_users:
        existing_user = db.scalar(
            select(User).where(User.organization_id == org.id, User.email == email)
        )
        if existing_user is None:
            db.add(
                User(
                    organization_id=org.id,
                    email=email,
                    full_name=full_name,
                    password_hash=default_pw_hash,
                    role=role,
                    active=True,
                    token_version=1,
                    linked_agent_id=agent_id,
                )
            )

    db.commit()
    return org
