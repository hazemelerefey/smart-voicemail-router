"""Stage 5: Ibthal's Phase 1 triage and demo routing integration.

The stage revalidates its official contract inputs, computes priority from the
approved text signals, reserves one unit of capacity through the shared seeded-
agent registry, and returns an explainable ``TriageDecision``. It uses only
listed demo skills, shift, capacity, and the existing seed order. It does not
apply a production mapping or tier policy.

When any priority input is missing, both priority fields stay null and the
existing text-review flag is preserved. Voice evidence is validated but never
changes priority or routing because fusion remains disabled.
"""

from __future__ import annotations

from .. import agents as agents_module
from ..schemas import (
    LABEL_VERSION,
    SCHEMA_VERSION,
    AssignmentStatus,
    ChurnRisk,
    CustomerState,
    QueuePriority,
    TextAnalysis,
    TriageDecision,
    VoiceEvidence,
    ComplaintUrgency,
)

TRIAGE_CONFIG_VERSION = "ibthal-phase1-demo-0.2"
_LABEL_FIELDS = (
    "complaint_category",
    "complaint_urgency",
    "customer_state_text",
    "churn_risk",
)
URGENCY_POINTS = {
    ComplaintUrgency.HIGH: 3,
    ComplaintUrgency.MEDIUM: 2,
    ComplaintUrgency.LOW: 1,
}
CHURN_POINTS = {
    ChurnRisk.AT_RISK: 2,
    ChurnRisk.NOT_AT_RISK: 0,
}
STATE_POINTS = {
    state: int(state in (CustomerState.MAD, CustomerState.FRUSTRATED))
    for state in CustomerState
}
_QUEUE_BUCKETS = {
    1: QueuePriority.LOW,
    2: QueuePriority.LOW,
    3: QueuePriority.NORMAL,
    4: QueuePriority.NORMAL,
    5: QueuePriority.HIGH,
    6: QueuePriority.URGENT,
}
_PRIORITY_INPUTS = ("complaint_urgency", "churn_risk", "customer_state_text")


def calculate_priority(
    text: TextAnalysis,
) -> tuple[int | None, QueuePriority | None, list[str], str]:
    """Apply Ibthal's approved score and queue buckets to validated text.

    A missing scoring input never receives a default or an inferred value.
    The caller preserves the input's human-review flag for ticket assembly.
    """
    text = TextAnalysis.model_validate(text.model_dump())
    missing = [field for field in _PRIORITY_INPUTS if getattr(text, field) is None]
    if missing:
        explanation = (
            "Priority inputs missing: "
            + ", ".join(missing)
            + ". Priority remains null for human review under the approved "
            "missing-input policy."
        )
        return None, None, ["priority_missing=" + ",".join(missing)], explanation

    urgency = URGENCY_POINTS[text.complaint_urgency]
    churn = CHURN_POINTS[text.churn_risk]
    state = STATE_POINTS[text.customer_state_text]
    score = urgency + churn + state
    bucket = _QUEUE_BUCKETS[score]
    signals = [
        f"urgency_points={urgency}",
        f"churn_points={churn}",
        f"customer_state_points={state}",
        f"priority_score={score}",
        f"queue_priority={bucket.value}",
    ]
    explanation = (
        f"Priority calculation: {urgency} + {churn} + {state} = {score}; "
        f"queue_priority={bucket.value}."
    )
    return score, bucket, signals, explanation


def triage_phase1(
    text: TextAnalysis, voice_evidence: VoiceEvidence | None = None
) -> TriageDecision:
    """Produce Ibthal's approved Phase 1 decision from official evidence.

    Revalidating model dumps is intentional: ``model_copy`` can construct
    objects that bypass Pydantic validation. Agent capacity is reserved once,
    atomically by ``assign_agent``. If decision construction then fails, this
    function releases its reservation before propagating the error.
    """
    if not isinstance(text, TextAnalysis):
        raise TypeError("text must be an official TextAnalysis object.")
    text = TextAnalysis.model_validate(text.model_dump())

    if voice_evidence is not None:
        if not isinstance(voice_evidence, VoiceEvidence):
            raise TypeError("voice_evidence must be an official VoiceEvidence object.")
        voice_evidence = VoiceEvidence.model_validate(voice_evidence.model_dump())
        if voice_evidence.voicemail_id != text.voicemail_id:
            raise ValueError("Text and voice evidence must belong to the same voicemail.")

    signals = [
        f"{field}={getattr(text, field).value if getattr(text, field) is not None else 'null'}"
        for field in _LABEL_FIELDS
    ]
    signals.append(f"needs_human_review={str(text.needs_human_review).lower()}")
    if voice_evidence is not None:
        signals.append("voice_evidence=ignored_fusion_disabled")

    score, bucket, priority_signals, priority_reason = calculate_priority(text)
    signals.extend(priority_signals)
    agent = None
    try:
        if text.complaint_category is None:
            reason = (
                "Complaint category is missing; no skill is guessed. "
                "The decision stays unassigned for human routing."
            )
        else:
            # Selection and capacity reservation happen atomically here.
            agent = agents_module.assign_agent(text.complaint_category)
            if agent is None:
                reason = (
                    "No fictional seeded demo agent has a matching listed skill, "
                    "is on shift, and has spare capacity. The decision stays "
                    "unassigned for human routing."
                )
            else:
                reason = (
                    f"Fictional seeded demo routing assigns {agent.id}: its listed "
                    f"skill matches {text.complaint_category.value}, it is on shift, "
                    "and one capacity unit is reserved. Selection uses the existing "
                    "demo seed order, not a production tie-breaking policy."
                )

        if text.needs_human_review:
            reason += " Text analysis still requires human review; routing does not clear it."
        reason += f" {priority_reason} Voice fusion is disabled."

        return TriageDecision(
            voicemail_id=text.voicemail_id,
            priority_score=score,
            queue_priority=bucket,
            assigned_agent_id=agent.id if agent else None,
            assignment_status=(
                AssignmentStatus.ASSIGNED if agent else AssignmentStatus.UNASSIGNED
            ),
            route_reason=reason,
            contributing_signals=signals,
            config_version=TRIAGE_CONFIG_VERSION,
            evaluation=None,
            schema_version=SCHEMA_VERSION,
            label_version=LABEL_VERSION,
        )
    except Exception:
        if agent is not None:
            agents_module.release(agent.id)
        raise
