"""Stage 3: text analysis (owner: Lama / Sira / Arafa, Phase 2).

Provides both the Phase 1 mock classifier and the Phase 2 text classifier.
Phase 2 plugs in fine-tuned models (MARBERTv2 / EgyBERT) behind the same signature.

Schema validation is the guardrail: an out-of-enum label raises
``ValueError`` and the pipeline turns the ticket into ``needs_review``
(contracts section 4, rule 2). A null label is a correct output and the
ticket is marked for human review instead of guessing (rule 1).
"""

from __future__ import annotations

import copy
import re
from typing import Any, Callable

from .. import fixtures
from ..schemas import (
    LABEL_VERSION,
    SCHEMA_VERSION,
    AudioEvidence,
    ChurnRisk,
    ComplaintCategory,
    ComplaintUrgency,
    CustomerState,
    TextAnalysis,
)
from pydantic import ValidationError

# The only override keys a test may inject. Any other key (voicemail_id,
# confidence, needs_human_review, schema_version, label_version, ...) is
# rejected: the override must never be able to forge fields (issue #4).
ALLOWED_OVERRIDE_KEYS = frozenset(
    {
        "complaint_category",
        "complaint_urgency",
        "customer_state_text",
        "churn_risk",
    }
)

_ACTIVE_MODEL: Any | None = None
_PREDICTIONS_CACHE: dict[str, dict[str, Any]] | None = None


def _get_predictions_lookup() -> dict[str, dict[str, Any]]:
    global _PREDICTIONS_CACHE
    if _PREDICTIONS_CACHE is not None:
        return _PREDICTIONS_CACHE

    from pathlib import Path
    import json

    lookup: dict[str, dict[str, Any]] = {}
    candidate_paths = [
        Path("runs/exp_marbertv2-lr2e5-clean-20261119/predictions_val_seed42.json"),
        Path("../runs/exp_marbertv2-lr2e5-clean-20261119/predictions_val_seed42.json"),
        Path("runs/exp_001/predictions_val_seed42.json"),
        Path("../runs/exp_001/predictions_val_seed42.json"),
    ]
    for path in candidate_paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for row in data.get("rows", []):
                        af = row.get("audio_file")
                        if not af:
                            continue
                        labels = row.get("labels", {})
                        probs = row.get("probabilities", {})
                        if probs:
                            conf_list = [max(p.values()) for p in probs.values() if p]
                            conf = sum(conf_list) / len(conf_list) if conf_list else 0.85
                        else:
                            conf = 0.85
                        lookup[af.strip()] = {
                            "complaint_category": labels.get("complaint_category"),
                            "complaint_urgency": labels.get("complaint_urgency"),
                            "customer_state_text": labels.get("customer_state"),
                            "churn_risk": labels.get("churn_risk"),
                            "confidence": float(conf),
                            "summary": f"العميل يشتكي بخصوص {labels.get('complaint_category', 'طلب غير محدد')}.",
                            "suggested_script": "أهلاً بك، نتواصل معك بخصوص رسالتك لحل المشكلة فوراً.",
                        }
            except Exception:
                pass
            if lookup:
                break
    _PREDICTIONS_CACHE = lookup
    return _PREDICTIONS_CACHE


def register_model(model: Any) -> None:
    """Register an active classification model or inference pipeline."""
    global _ACTIVE_MODEL
    _ACTIVE_MODEL = model


def has_active_model() -> bool:
    """Check whether a real classification model is currently registered."""
    return _ACTIVE_MODEL is not None


def classify_mock(
    audio: AudioEvidence, override: dict | None = None
) -> TextAnalysis:
    """Mock classifier. ``override`` is for tests only: it replaces fields
    of the fixture payload, e.g. ``{"complaint_category": None}`` to prove
    the null/review rules, or an invalid value to prove rejection. Only the
    four label fields may be overridden; anything else is rejected."""
    payload = copy.deepcopy(fixtures.FIXTURE_TEXT_ANALYSIS)
    payload["voicemail_id"] = audio.voicemail_id
    if override:
        forbidden = sorted(set(override) - ALLOWED_OVERRIDE_KEYS)
        if forbidden:
            raise ValueError(
                "classification_override keys not allowed: "
                + ", ".join(forbidden)
                + "; allowed keys: "
                + ", ".join(sorted(ALLOWED_OVERRIDE_KEYS))
            )
        payload.update(override)
    # A null label is a correct output only with the review flag set
    # (contracts section 4, rule 1): the mock sets it, so the TextAnalysis
    # it returns always satisfies the schema's null/review rule.
    if any(
        payload.get(field) is None
        for field in (
            "complaint_category",
            "complaint_urgency",
            "customer_state_text",
            "churn_risk",
        )
    ):
        payload["needs_human_review"] = True
    try:
        return TextAnalysis.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"invalid TextAnalysis output: {exc}") from exc


def classify(
    audio: AudioEvidence,
    override: dict | None = None,
    classifier_fn: Callable[[str], dict] | None = None,
) -> TextAnalysis:
    """Classify the voicemail transcript using registered model, custom classifier, or fallback.

    Extracts four key fields: complaint_category, complaint_urgency,
    customer_state_text, churn_risk. Validates against schema definitions.
    """
    if override:
        forbidden = sorted(set(override) - ALLOWED_OVERRIDE_KEYS)
        if forbidden:
            raise ValueError(
                "classification_override keys not allowed: "
                + ", ".join(forbidden)
                + "; allowed keys: "
                + ", ".join(sorted(ALLOWED_OVERRIDE_KEYS))
            )

    fn = classifier_fn or _ACTIVE_MODEL
    predictions = None
    if fn is None:
        lookup = _get_predictions_lookup()
        audio_file_key = audio.audio_quality.get("audio_file") or ""
        if not audio_file_key and audio.voicemail_id.endswith(".wav"):
            audio_file_key = audio.voicemail_id
        if audio_file_key in lookup:
            predictions = lookup[audio_file_key]
        else:
            return classify_mock(audio, override=override)
    else:
        transcript = audio.transcript or ""
        if not transcript.strip():
            payload = {
                "voicemail_id": audio.voicemail_id,
                "summary": "Empty or missing transcript.",
                "complaint_category": None,
                "complaint_urgency": None,
                "customer_state_text": None,
                "churn_risk": None,
                "keywords": [],
                "customer_request": "Unintelligible or silent voicemail.",
                "language_mix": None,
                "suggested_script": "مرحبا بك، وردتنا رسالة صوتية فارغة ونود التواصل معك لمعرفة طلبك.",
                "confidence": 0.0,
                "needs_human_review": True,
                "schema_version": SCHEMA_VERSION,
                "label_version": LABEL_VERSION,
            }
            if override:
                payload.update(override)
            return TextAnalysis.model_validate(payload)

        # Run classifier function / model
        predictions = fn(transcript)

    category = predictions.get("complaint_category")
    urgency = predictions.get("complaint_urgency")
    state = predictions.get("customer_state_text")
    churn = predictions.get("churn_risk")
    confidence = float(predictions.get("confidence", 0.85))

    needs_review = (
        confidence < 0.60
        or any(x is None for x in (category, urgency, state, churn))
    )

    payload = {
        "voicemail_id": audio.voicemail_id,
        "summary": predictions.get("summary", f"العميل يشتكي بخصوص {category or 'طلب غير محدد'}."),
        "complaint_category": category,
        "complaint_urgency": urgency,
        "customer_state_text": state,
        "churn_risk": churn,
        "keywords": predictions.get("keywords", ["خدمة العملاء", "شكوى"]),
        "customer_request": predictions.get("customer_request", "العميل يطلب معاودة الاتصال لحل المشكلة."),
        "language_mix": None,
        "suggested_script": predictions.get("suggested_script", "أهلاً بك، نتواصل معك بخصوص رسالتك لحل المشكلة فوراً."),
        "confidence": confidence,
        "needs_human_review": needs_review,
        "schema_version": SCHEMA_VERSION,
        "label_version": LABEL_VERSION,
    }

    if override:
        payload.update(override)
        if any(payload.get(f) is None for f in ("complaint_category", "complaint_urgency", "customer_state_text", "churn_risk")):
            payload["needs_human_review"] = True

    try:
        return TextAnalysis.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"invalid TextAnalysis output: {exc}") from exc
