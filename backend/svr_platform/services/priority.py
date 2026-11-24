"""Fixed deterministic queue priority formula (PRD FR9, Appendix C)."""

from __future__ import annotations

from dataclasses import dataclass

from ..taxonomy import QueuePriority

URGENCY_POINTS: dict[str, int] = {"high": 3, "medium": 2, "low": 1}
CHURN_POINTS: dict[str, int] = {"at_risk": 2, "not_at_risk": 0}
STATE_POINTS: dict[str, int] = {
    "mad": 1,
    "frustrated": 1,
    "calm": 0,
    "satisfied": 0,
    "unclear": 0,
}


@dataclass(frozen=True)
class PriorityResult:
    priority_score: int | None
    queue_priority: str | None
    contributing_signals: dict[str, object]
    priority_reason: str
    needs_human_review: bool
    review_reason: str | None = None


def score_to_bucket(score: int) -> QueuePriority:
    if score >= 6:
        return QueuePriority.URGENT
    if score == 5:
        return QueuePriority.HIGH
    if score >= 3:
        return QueuePriority.NORMAL
    return QueuePriority.LOW


def compute_priority(
    complaint_urgency: str | None,
    churn_risk: str | None,
    customer_state: str | None,
) -> PriorityResult:
    """Compute priority_score (1 to 6) and bucket per fixed PRD formula.

    If any input is null or invalid, priority_score and queue_priority stay null
    and the ticket goes to Human Review. Never substitute default values.
    """
    missing: list[str] = []
    if complaint_urgency not in URGENCY_POINTS:
        missing.append("complaint_urgency")
    if churn_risk not in CHURN_POINTS:
        missing.append("churn_risk")
    if customer_state not in STATE_POINTS:
        missing.append("customer_state")

    if missing:
        return PriorityResult(
            priority_score=None,
            queue_priority=None,
            contributing_signals={
                "complaint_urgency": complaint_urgency,
                "churn_risk": churn_risk,
                "customer_state": customer_state,
                "missing_inputs": missing,
            },
            priority_reason=(
                "Priority could not be computed because required signal(s) are missing: "
                + ", ".join(missing)
                + ". Routed to Human Review."
            ),
            needs_human_review=True,
            review_reason="missing_label",
        )

    assert complaint_urgency is not None and churn_risk is not None and customer_state is not None
    u_pts = URGENCY_POINTS[complaint_urgency]
    c_pts = CHURN_POINTS[churn_risk]
    s_pts = STATE_POINTS[customer_state]
    total = u_pts + c_pts + s_pts
    bucket = score_to_bucket(total).value

    signals = {
        "complaint_urgency": {"value": complaint_urgency, "points": u_pts},
        "churn_risk": {"value": churn_risk, "points": c_pts},
        "customer_state": {"value": customer_state, "points": s_pts},
        "total_score": total,
        "bucket": bucket,
    }
    reason = (
        f"Score {total}/6 ({bucket}): urgency {complaint_urgency} (+{u_pts}), "
        f"churn {churn_risk} (+{c_pts}), customer state {customer_state} (+{s_pts})."
    )
    return PriorityResult(
        priority_score=total,
        queue_priority=bucket,
        contributing_signals=signals,
        priority_reason=reason,
        needs_human_review=False,
        review_reason=None,
    )
