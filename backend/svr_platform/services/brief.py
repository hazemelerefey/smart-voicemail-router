"""Rule-based callback brief and template script builder (FR12, FR14, FR15, AI6, S1, S3)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ScriptTemplate
from ..seed import DEFAULT_TEMPLATES

_UNEXPANDED_PLACEHOLDER_RE = re.compile(r"\{[^{}]+\}")


@dataclass(frozen=True)
class CallbackBrief:
    summary: str
    customer_request: str
    suggested_script: str
    flagged: bool
    flag_reason: str | None = None


def build_callback_brief(
    db: Session,
    *,
    organization_id: str,
    transcript: str,
    complaint_category: str | None,
) -> CallbackBrief:
    """Build deterministic summary, customer_request, and category template script.

    FR15: summary is transcript truncated to 200 characters; customer_request is a sentence
    from the predicted category.
    FR14 & S3: suggested_script comes strictly from the versioned category template using
    only verified ticket facts, never invents facts, and is never sent automatically.
    """
    clean_transcript = (transcript or "").strip()
    summary = clean_transcript[:200]

    if not complaint_category:
        return CallbackBrief(
            summary=summary,
            customer_request="Category pending supervisor review; review the transcript directly before callback.",
            suggested_script="",
            flagged=True,
            flag_reason="missing_category_for_brief",
        )

    tpl = db.scalar(
        select(ScriptTemplate).where(
            ScriptTemplate.organization_id == organization_id,
            ScriptTemplate.category == complaint_category,
        )
    )
    if tpl is not None:
        customer_request = tpl.customer_request_ar.strip()
        suggested_script = tpl.template_ar.strip()
    elif complaint_category in DEFAULT_TEMPLATES:
        customer_request = DEFAULT_TEMPLATES[complaint_category]["customer_request_ar"].strip()
        suggested_script = DEFAULT_TEMPLATES[complaint_category]["template_ar"].strip()
    else:
        return CallbackBrief(
            summary=summary,
            customer_request="",
            suggested_script="",
            flagged=True,
            flag_reason="missing_template",
        )

    # S3 output guardrail: block any unexpanded template variable or empty script
    if not suggested_script or _UNEXPANDED_PLACEHOLDER_RE.search(suggested_script):
        return CallbackBrief(
            summary=summary,
            customer_request=customer_request,
            suggested_script="",
            flagged=True,
            flag_reason="ungrounded_script_blocked",
        )

    return CallbackBrief(
        summary=summary,
        customer_request=customer_request,
        suggested_script=suggested_script,
        flagged=False,
        flag_reason=None,
    )
