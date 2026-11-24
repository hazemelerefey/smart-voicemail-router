"""Fixed SVR taxonomy, lifecycle states, and telecom care constants (SVR-PRD-02)."""

from __future__ import annotations

from enum import Enum


class ComplaintCategory(str, Enum):
    """Fixed 11 telecom complaint categories (PRD Appendix B, FR6)."""

    NETWORK_AND_CONNECTIVITY = "network_and_connectivity"
    BILLING_AND_CHARGES = "billing_and_charges"
    BALANCE_AND_DATA = "balance_and_data"
    APP_AND_ACCOUNT = "app_and_account"
    BRANCH_AND_STAFF = "branch_and_staff"
    NO_REPLY_OR_LONG_WAIT = "no_reply_or_long_wait"
    CANCELLATION_REQUEST = "cancellation_request"
    THANKS_OR_PRAISE = "thanks_or_praise"
    OTHER = "other"
    OFFERS_AND_PACKAGES = "offers_and_packages"
    SIM_SERVICES = "sim_services"


class ComplaintUrgency(str, Enum):
    """Fixed 3 complaint urgency values (PRD Appendix B)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CustomerState(str, Enum):
    """Customer interaction state values (PRD Appendix B).

    The classifier is trained on the 4 scored classes (calm, frustrated, mad,
    satisfied). 'unclear' has 0 train rows and 1 validation row, and may appear
    on human review or truth tables.
    """

    CALM = "calm"
    FRUSTRATED = "frustrated"
    MAD = "mad"
    SATISFIED = "satisfied"
    UNCLEAR = "unclear"


class ChurnRisk(str, Enum):
    """Fixed 2 churn risk values (PRD Appendix B)."""

    AT_RISK = "at_risk"
    NOT_AT_RISK = "not_at_risk"


class QueuePriority(str, Enum):
    """Queue priority buckets (PRD FR9, Appendix C)."""

    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class TicketStatus(str, Enum):
    """8-state ticket lifecycle (PRD WF1, Section 11.4)."""

    RECEIVED = "received"
    PROCESSING = "processing"
    READY = "ready"
    UNASSIGNED = "unassigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    FAILED = "failed"


class UserRole(str, Enum):
    """RBAC roles (PRD Section 3.1, FR23)."""

    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    AGENT = "agent"


ALLOWED_TICKET_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    TicketStatus.RECEIVED: frozenset({TicketStatus.PROCESSING, TicketStatus.FAILED}),
    TicketStatus.PROCESSING: frozenset(
        {TicketStatus.READY, TicketStatus.UNASSIGNED, TicketStatus.FAILED}
    ),
    TicketStatus.READY: frozenset(
        {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.UNASSIGNED}
    ),
    TicketStatus.UNASSIGNED: frozenset(
        {TicketStatus.READY, TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED}
    ),
    TicketStatus.IN_PROGRESS: frozenset({TicketStatus.RESOLVED}),
    TicketStatus.RESOLVED: frozenset({TicketStatus.CLOSED}),
    TicketStatus.CLOSED: frozenset(),
    TicketStatus.FAILED: frozenset({TicketStatus.UNASSIGNED}),
}

TRAINED_CLASSES_BY_FIELD: dict[str, list[str]] = {
    "complaint_category": [c.value for c in ComplaintCategory],
    "complaint_urgency": [u.value for u in ComplaintUrgency],
    "customer_state": ["calm", "frustrated", "mad", "satisfied"],
    "churn_risk": [r.value for r in ChurnRisk],
}

ALLOWED_CLASSES_BY_FIELD: dict[str, frozenset[str]] = {
    "complaint_category": frozenset(c.value for c in ComplaintCategory),
    "complaint_urgency": frozenset(u.value for u in ComplaintUrgency),
    "customer_state": frozenset(s.value for s in CustomerState),
    "churn_risk": frozenset(r.value for r in ChurnRisk),
}

# PRD FR20 default telecom skill mapping (all 11 categories covered)
DEFAULT_SKILL_MAPPING: dict[str, str] = {
    "network_and_connectivity": "Network",
    "no_reply_or_long_wait": "Network",
    "sim_services": "Network",
    "billing_and_charges": "Billing",
    "balance_and_data": "Billing",
    "offers_and_packages": "Billing",
    "app_and_account": "General",
    "branch_and_staff": "General",
    "cancellation_request": "General",
    "thanks_or_praise": "General",
    "other": "General",
}

CATEGORY_DISPLAY_EN: dict[str, str] = {
    "network_and_connectivity": "Network & Connectivity",
    "billing_and_charges": "Billing & Charges",
    "balance_and_data": "Balance & Data Bundles",
    "app_and_account": "Subscriber App & Account",
    "branch_and_staff": "Branch & Care Staff",
    "no_reply_or_long_wait": "Delayed Follow-up & Wait Time",
    "cancellation_request": "Line Cancellation & Retention",
    "thanks_or_praise": "Appreciation & Positive Feedback",
    "other": "General Subscriber Inquiry",
    "offers_and_packages": "Rate Plans & Offers",
    "sim_services": "SIM & eSIM Services",
}

CATEGORY_DISPLAY_AR: dict[str, str] = {
    "network_and_connectivity": "الشبكة والتغطية",
    "billing_and_charges": "الفواتير والرسوم",
    "balance_and_data": "الرصيد وباقات الإنترنت",
    "app_and_account": "التطبيق وحساب المشترك",
    "branch_and_staff": "الفروع وخدمة العملاء",
    "no_reply_or_long_wait": "تأخر الرد والمتابعة",
    "cancellation_request": "طلب إلغاء الخط",
    "thanks_or_praise": "شكر وإشادة بالخدمة",
    "other": "استفسار عام",
    "offers_and_packages": "العروض والباقات",
    "sim_services": "خدمات الشريحة و eSIM",
}

SKILL_DISPLAY_EN: dict[str, str] = {
    "Network": "Network Care",
    "Billing": "Billing & Bundles Care",
    "General": "Subscriber & Retention Care",
}

REVIEW_REASONS = (
    "low_confidence",
    "missing_label",
    "invalid_label",
    "no_eligible_agent",
    "processing_error",
    "kill_switch_active",
    "supervisor_requested",
    "weekly_quality_sample",
)
