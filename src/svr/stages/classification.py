"""Stage 3: text analysis (owner: Lama, mock in Phase 1).

Phase 1 mock: returns the fixed fixture fields from contracts section 9
(category network_and_connectivity, urgency medium, state frustrated,
churn not_at_risk). Phase 2 plugs in the fine-tuned EgyBERT / MARBERTv2
model here, behind the same signature.

Schema validation is the guardrail: an out-of-enum label raises
``ValueError`` and the pipeline turns the ticket into ``needs_review``
(contracts section 4, rule 2). A null label is a correct output and the
ticket is marked for human review instead of guessing (rule 1).
"""

from __future__ import annotations

from .. import fixtures
from ..schemas import AudioEvidence, TextAnalysis
from pydantic import ValidationError


def classify_mock(
    audio: AudioEvidence, override: dict | None = None
) -> TextAnalysis:
    """Mock classifier. ``override`` is for tests only: it replaces fields
    of the fixture payload, e.g. ``{"complaint_category": None}`` to prove
    the null/review rules, or an invalid value to prove rejection."""
    payload = dict(fixtures.FIXTURE_TEXT_ANALYSIS)
    payload["voicemail_id"] = audio.voicemail_id
    if override:
        payload.update(override)
    try:
        return TextAnalysis.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"invalid TextAnalysis output: {exc}") from exc
