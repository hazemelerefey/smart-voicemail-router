"""Production evaluation CLI for SVR (AI9, AI10, WF5, D5).

Runs real Whisper large-v3 STT on sampled validation WAVs, runs the 4 real
single-task MARBERTv2 checkpoints across all 1,003 validation rows, scores via
``infra/harness.py``, computes FR20 telecom Routing Agreement, measures
per-stage and end-to-end p50/p95 latency, persists an ``EvalRun`` DB row, and
writes ``eval_report.json`` plus ``eval_summary.md``.

Usage:
    python -m svr_platform.eval.cli --split validation --stt-sample-size 10
"""

from __future__ import annotations

import argparse
import csv
import gc
import importlib.metadata
import io
import json
import math
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
from sqlalchemy import select

from ..auth import record_audit_event
from ..config import Settings, get_settings
from ..database import DatabaseManager
from ..models import EvalRun, Organization
from ..seed import DEFAULT_TEMPLATES, seed_initial_data
from ..services.classification import (
    CLASSIFICATION_FIELDS,
    MAX_SEQ_LEN,
    ClassificationResult,
    MARBERTv2ClassifierService,
    discover_single_task_checkpoints,
    validate_and_score_raw_outputs,
)
from ..services.factories import build_stt_service, build_transcript_gate
from ..services.intake import validate_and_probe_audio
from ..services.priority import compute_priority
from ..services.routing import recommend_route
from ..services.stt import STT_V1_COLUMNS, BaseSTTService
from ..taxonomy import DEFAULT_SKILL_MAPPING, TRAINED_CLASSES_BY_FIELD
from .once_guard import (
    compute_checkpoint_set_sha256,
    compute_file_sha256,
    finalize_test_claim,
    guarded_read_test_file,
)

# PRD AI9 release gates on validation
AI9_THRESHOLDS: dict[str, float] = {
    "complaint_category": 0.75,
    "complaint_urgency": 0.70,
    "customer_state": 0.70,
    "churn_risk": 0.80,
    "combined": 0.75,
    "routing_agreement": 0.80,
}

# Validated Sira 5-seed reference numbers from PRD AI9
SIRA_REFERENCE_VAL_F1: dict[str, float] = {
    "complaint_category": 0.7872,
    "complaint_urgency": 0.7211,
    "customer_state": 0.7471,
    "churn_risk": 0.8277,
    "combined": 0.7708,
}

SKILL_GROUPS: tuple[str, ...] = ("Network", "Billing", "General")

IDEAL_AGENT_BY_SKILL: dict[str, str] = {
    "Network": "Network Care Specialist",
    "Billing": "Billing & Bundles Specialist",
    "General": "Subscriber Care Specialist",
}

UNCLEAR_EXCLUSION_RULE: dict[str, dict[str, Any]] = {
    "customer_state": {
        "labels": ["unclear"],
        "reason": (
            "unclear has 0 rows in train (1 in val, 0 in test), so the model never "
            "trains on it; excluded from customer_state macro-F1 only (Hazem's decision)."
        ),
    }
}

PRD_P95_LATENCY_TARGET_MS = 10000.0


def _ensure_repo_on_syspath(repo_root: Path) -> None:
    root_str = str(repo_root.resolve())
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


def _normalize_split_arg(split_arg: str) -> tuple[str, str]:
    """Return (canonical_prd_split, infra_split). Rejects 'dev' per SVR rules."""
    cleaned = str(split_arg or "").strip().lower()
    if cleaned in ("validation", "val"):
        return "validation", "val"
    if cleaned == "test":
        return "test", "test"
    raise ValueError(f"Unsupported split {split_arg!r}. Allowed splits: 'validation' or 'test'.")


def _latency_summary(samples_ms: list[float]) -> dict[str, float | int | None]:
    if not samples_ms:
        return {"n": 0, "min": None, "p50": None, "p95": None, "max": None, "mean": None}
    arr = np.asarray(samples_ms, dtype=np.float64)
    return {
        "n": int(arr.size),
        "min": round(float(np.min(arr)), 2),
        "p50": round(float(np.percentile(arr, 50)), 2),
        "p95": round(float(np.percentile(arr, 95)), 2),
        "max": round(float(np.max(arr)), 2),
        "mean": round(float(np.mean(arr)), 2),
    }


def _safe_pkg_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def collect_hardware_metadata(
    *,
    classifier_device: str,
    stt_device: str,
    stt_compute_type: str,
    e2e_p95_ms: float | None,
) -> dict[str, Any]:
    cuda_available = False
    cuda_device_name: str | None = None
    try:
        import torch

        cuda_available = bool(torch.cuda.is_available())
        if cuda_available:
            cuda_device_name = str(torch.cuda.get_device_name(0))
    except ImportError:
        cuda_available = False

    meets_target = e2e_p95_ms is not None and e2e_p95_ms <= PRD_P95_LATENCY_TARGET_MS
    note = (
        "Measured on local CPU hardware; PRD <= 10s p95 latency target assumes a production GPU server (PRD L8/R3)."
        if classifier_device == "cpu" or stt_device == "cpu"
        else "Measured on GPU hardware against the PRD <= 10s p95 latency target."
    )
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "cpu_count": os.cpu_count() or 1,
        "python_version": platform.python_version(),
        "classifier_device": classifier_device,
        "stt_device": stt_device,
        "stt_compute_type": stt_compute_type,
        "cuda_available": cuda_available,
        "cuda_device_name": cuda_device_name,
        "packages": {
            "torch": _safe_pkg_version("torch"),
            "transformers": _safe_pkg_version("transformers"),
            "faster-whisper": _safe_pkg_version("faster-whisper"),
            "scikit-learn": _safe_pkg_version("scikit-learn"),
            "numpy": _safe_pkg_version("numpy"),
            "pandas": _safe_pkg_version("pandas"),
        },
        "prd_p95_target_ms": PRD_P95_LATENCY_TARGET_MS,
        "meets_prd_p95_target": meets_target,
        "hardware_note": note,
    }


def compute_routing_agreement(
    truth_rows: list[dict[str, Any]],
    pred_rows: list[dict[str, Any]],
    skill_mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Compute FR20 telecom Routing Agreement across all evaluated rows.

    Compares the model-predicted telecom skill queue and ideal seeded agent
    (Network / Billing / General under FR20) against the ground-truth ideal
    assignment derived from the true ``complaint_category``.
    """
    mapping = dict(skill_mapping or DEFAULT_SKILL_MAPPING)
    truth_by_audio = {row["audio_file"]: row for row in truth_rows}
    pred_by_audio = {row["audio_file"]: row for row in pred_rows}

    if set(truth_by_audio.keys()) != set(pred_by_audio.keys()):
        raise ValueError("truth_rows and pred_rows must contain the exact same audio_file keys.")

    total = len(truth_rows)
    if total == 0:
        raise ValueError("Cannot compute routing agreement on zero rows.")

    skill_index = {s: idx for idx, s in enumerate(SKILL_GROUPS)}
    matrix = np.zeros((len(SKILL_GROUPS), len(SKILL_GROUPS)), dtype=np.int64)

    agreed = 0
    exact_category_matches = 0
    unmapped_predictions = 0
    per_skill_true = {s: 0 for s in SKILL_GROUPS}
    per_skill_pred = {s: 0 for s in SKILL_GROUPS}
    per_skill_correct = {s: 0 for s in SKILL_GROUPS}

    for row in truth_rows:
        af = row["audio_file"]
        true_cat = row["complaint_category"]
        pred_cat = pred_by_audio[af].get("complaint_category")

        true_skill = mapping.get(true_cat)
        pred_skill = mapping.get(pred_cat) if pred_cat else None

        if true_skill not in skill_index:
            raise ValueError(f"Unmapped ground-truth category {true_cat!r} for {af}")

        per_skill_true[true_skill] += 1
        if pred_cat == true_cat:
            exact_category_matches += 1

        if pred_skill not in skill_index:
            unmapped_predictions += 1
            continue

        per_skill_pred[pred_skill] += 1
        matrix[skill_index[true_skill], skill_index[pred_skill]] += 1

        true_agent = IDEAL_AGENT_BY_SKILL[true_skill]
        pred_agent = IDEAL_AGENT_BY_SKILL[pred_skill]
        if pred_skill == true_skill and pred_agent == true_agent:
            agreed += 1
            per_skill_correct[true_skill] += 1

    per_skill_metrics: dict[str, dict[str, float | int | str]] = {}
    for skill in SKILL_GROUPS:
        tp = per_skill_correct[skill]
        sup = per_skill_true[skill]
        pred_cnt = per_skill_pred[skill]
        precision = (tp / pred_cnt) if pred_cnt > 0 else 0.0
        recall = (tp / sup) if sup > 0 else 0.0
        f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        per_skill_metrics[skill] = {
            "ideal_agent": IDEAL_AGENT_BY_SKILL[skill],
            "support": sup,
            "predicted": pred_cnt,
            "agreed": tp,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
        }

    agreement_ratio = agreed / total
    exact_cat_ratio = exact_category_matches / total
    return {
        "total_rows": total,
        "agreed_rows": agreed,
        "disagreed_rows": total - agreed,
        "unmapped_predictions": unmapped_predictions,
        "routing_agreement": round(agreement_ratio, 6),
        "routing_agreement_pct": round(agreement_ratio * 100.0, 2),
        "exact_category_match_rate": round(exact_cat_ratio, 6),
        "exact_category_match_pct": round(exact_cat_ratio * 100.0, 2),
        "threshold": AI9_THRESHOLDS["routing_agreement"],
        "meets_ai9_threshold": agreement_ratio >= AI9_THRESHOLDS["routing_agreement"],
        "skill_mapping": mapping,
        "per_skill": per_skill_metrics,
        "confusion_matrix": {
            "rows_are": "true_skill",
            "columns_are": "predicted_skill",
            "labels": list(SKILL_GROUPS),
            "counts": matrix.tolist(),
        },
    }


def compute_priority_agreement(
    truth_rows: list[dict[str, Any]],
    pred_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare deterministic priority buckets between predicted labels and truth labels."""
    pred_by_audio = {row["audio_file"]: row for row in pred_rows}
    scored = 0
    excluded_unclear = 0
    bucket_matches = 0
    exact_score_matches = 0

    for trow in truth_rows:
        if trow.get("customer_state") == "unclear":
            excluded_unclear += 1
            continue
        prow = pred_by_audio[trow["audio_file"]]
        t_prio = compute_priority(
            trow.get("complaint_urgency"),
            trow.get("churn_risk"),
            trow.get("customer_state"),
        )
        p_prio = compute_priority(
            prow.get("complaint_urgency"),
            prow.get("churn_risk"),
            prow.get("customer_state"),
        )
        scored += 1
        if t_prio.queue_priority == p_prio.queue_priority:
            bucket_matches += 1
        if t_prio.priority_score == p_prio.priority_score:
            exact_score_matches += 1

    bucket_rate = (bucket_matches / scored) if scored > 0 else 0.0
    score_rate = (exact_score_matches / scored) if scored > 0 else 0.0
    return {
        "scored_rows": scored,
        "excluded_unclear_rows": excluded_unclear,
        "bucket_agreement": round(bucket_rate, 6),
        "bucket_agreement_pct": round(bucket_rate * 100.0, 2),
        "exact_score_agreement": round(score_rate, 6),
        "exact_score_agreement_pct": round(score_rate * 100.0, 2),
    }


def _load_fair_rerun_5seed(repo_root: Path) -> dict[str, Any] | None:
    record_path = repo_root / "runs" / "exp_fair-marbertv2-lr2e5" / "run_record.json"
    if not record_path.is_file():
        return None
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    per_seed_clean = []
    for item in payload.get("per_seed", []):
        m = item.get("metrics", {})
        vals = [
            float(m.get("complaint_category_macro_f1", 0.0)),
            float(m.get("complaint_urgency_macro_f1", 0.0)),
            float(m.get("customer_state_macro_f1", 0.0)),
            float(m.get("churn_risk_macro_f1", 0.0)),
        ]
        per_seed_clean.append(
            {
                "seed": item.get("seed"),
                "complaint_category_macro_f1": round(vals[0], 6),
                "complaint_urgency_macro_f1": round(vals[1], 6),
                "customer_state_macro_f1": round(vals[2], 6),
                "churn_risk_macro_f1": round(vals[3], 6),
                "combined_macro_f1": round(float(np.mean(vals)), 6),
            }
        )
    aggregate = payload.get("aggregate", {})
    combined_means = [s["combined_macro_f1"] for s in per_seed_clean]
    return {
        "source_path": "runs/exp_fair-marbertv2-lr2e5/run_record.json",
        "run_id": payload.get("run_id"),
        "evaluated_split": payload.get("evaluated_split"),
        "per_seed": per_seed_clean,
        "aggregate": aggregate,
        "combined_mean": round(float(np.mean(combined_means)), 6) if combined_means else None,
        "combined_std": round(float(np.std(combined_means, ddof=1)), 6) if len(combined_means) > 1 else None,
    }


def _load_split_csv_rows(csv_bytes: bytes, expected_infra_split: str) -> list[dict[str, str]]:
    text = csv_bytes.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, str]] = []
    required = {"audio_file", "text_norm", "split", *CLASSIFICATION_FIELDS}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        missing = sorted(required - set(reader.fieldnames or []))
        raise ValueError(f"Split CSV is missing required columns: {missing}")
    for row in reader:
        row_split = (row.get("split") or "").strip()
        if row_split != expected_infra_split:
            raise ValueError(
                f"Split CSV contains unexpected split={row_split!r}; expected {expected_infra_split!r}"
            )
        rows.append(dict(row))
    if not rows:
        raise ValueError("Split CSV contains zero rows.")
    return rows


def _select_sample_rows(rows: list[dict[str, str]], sample_size: int, audio_dir: Path) -> list[dict[str, str]]:
    if sample_size <= 0:
        return []
    available = [r for r in rows if (audio_dir / r["audio_file"]).is_file()]
    if len(available) < sample_size:
        raise FileNotFoundError(
            f"Requested stt_sample_size={sample_size} WAVs under {audio_dir}, "
            f"but only {len(available)} matching WAV files were found."
        )
    if sample_size == len(available):
        return available
    # Evenly spaced deterministic sample across the sorted validation set
    indices = sorted(
        {
            int(round(i * (len(available) - 1) / max(1, sample_size - 1)))
            for i in range(sample_size)
        }
    )
    selected = [available[i] for i in indices]
    idx = 0
    while len(selected) < sample_size and idx < len(available):
        if available[idx] not in selected:
            selected.append(available[idx])
        idx += 1
    return selected[:sample_size]


def _predict_batch_with_checkpoints(
    classifier_service: MARBERTv2ClassifierService,
    rows: list[dict[str, str]],
    *,
    batch_size: int,
    confidence_threshold: float,
) -> list[ClassificationResult]:
    """Run batched PyTorch inference over all rows using the 4 real MARBERTv2 checkpoints."""
    classifier_service._load_checkpoints()
    import torch

    assert classifier_service._tokenizer is not None and classifier_service._models is not None
    model_version = classifier_service._loaded_model_version or f"{classifier_service.base_model_id}:single-task-lr2e5"
    results: list[ClassificationResult] = []

    for start in range(0, len(rows), batch_size):
        chunk = rows[start : start + batch_size]
        if start == 0 or (start // batch_size) % 5 == 0 or start + batch_size >= len(rows):
            print(
                f"[eval-cli] MARBERTv2 batch {start + len(chunk)}/{len(rows)}",
                file=sys.stderr,
                flush=True,
            )
        texts = [str(r.get("text_norm") or "").strip() for r in chunk]
        enc = classifier_service._tokenizer(
            texts,
            truncation=True,
            max_length=MAX_SEQ_LEN,
            padding=True,
            return_tensors="pt",
        )
        enc = {k: v.to(classifier_service._device) for k, v in enc.items()}

        batch_probs_by_field: dict[str, list[dict[str, float]]] = {}
        batch_labels_by_field: dict[str, list[str]] = {}

        with torch.no_grad():
            for field_name in CLASSIFICATION_FIELDS:
                model = classifier_service._models[field_name]
                logits = model(**enc).logits
                probs_matrix = torch.softmax(logits.float(), dim=-1).cpu().tolist()
                id2label = getattr(model.config, "id2label", None) or {}
                classes = TRAINED_CLASSES_BY_FIELD[field_name]
                use_id2label = bool(id2label) and set(str(v) for v in id2label.values()) == set(classes)

                field_probs_list: list[dict[str, float]] = []
                field_labels_list: list[str] = []
                for prob_vec in probs_matrix:
                    if use_id2label:
                        prob_map = {str(id2label[i]): float(prob_vec[i]) for i in range(len(prob_vec))}
                    else:
                        prob_map = {classes[i]: float(prob_vec[i]) for i in range(len(classes))}
                    total = sum(prob_map.values())
                    if total > 0:
                        prob_map = {k: v / total for k, v in prob_map.items()}
                    best_label = max(classes, key=lambda c: prob_map[c])
                    field_probs_list.append(prob_map)
                    field_labels_list.append(best_label)
                batch_probs_by_field[field_name] = field_probs_list
                batch_labels_by_field[field_name] = field_labels_list

        for i in range(len(chunk)):
            if not texts[i]:
                results.append(
                    ClassificationResult(
                        labels={f: None for f in CLASSIFICATION_FIELDS},
                        probabilities={f: {} for f in CLASSIFICATION_FIELDS},
                        confidence=0.0,
                        needs_human_review=True,
                        review_reason="missing_label",
                        model_version=model_version,
                        label_sources={f: "model" for f in CLASSIFICATION_FIELDS},
                        error="Empty normalized transcript cannot be classified.",
                    )
                )
                continue
            raw_out = {
                field_name: {
                    "label": batch_labels_by_field[field_name][i],
                    "probabilities": batch_probs_by_field[field_name][i],
                }
                for field_name in CLASSIFICATION_FIELDS
            }
            results.append(
                validate_and_score_raw_outputs(
                    raw_out,
                    confidence_threshold=confidence_threshold,
                    model_version=model_version,
                )
            )
    return results


def _build_eval_summary_markdown(report: dict[str, Any]) -> str:
    """Render a concise Markdown evaluation report with zero em/en dashes."""
    split = report["split"]
    model_version = report["model_version"]
    metrics = report["classification"]
    combined = metrics["combined_macro_f1"]["mean"]
    routing = report["routing_agreement"]
    latency = report["latency_ms"]
    hw = report["hardware"]
    churn_info = report["churn_at_risk_analysis"]
    gates = report["ai9_gates"]

    lines: list[str] = [
        f"# SVR Production Evaluation Summary ({split})",
        "",
        f"- **Generated UTC:** `{report['created_utc']}`",
        f"- **Split:** `{split}` (`{report['n_rows']}` rows, dataset version `{report['dataset_version']}`)",
        f"- **Model version:** `{model_version}`",
        f"- **Checkpoint SHA-256 (combined):** `{report['checkpoint_provenance']['combined_sha256']}`",
        f"- **Database EvalRun ID:** `{report.get('eval_run_id')}`",
    ]
    if report.get("guard_claim_id"):
        lines.append(f"- **Test-Once Guard Claim ID:** `{report['guard_claim_id']}`")

    lines.extend(
        [
            "",
            "## 1. Classification Macro-F1 & AI9 Release Gates",
            "",
            "| Field | Live Macro-F1 | AI9 Gate | Status | Sira Val Ref | Fair 5-Seed Mean +/- Std | Scored Rows |",
            "|---|---:|---:|---|---:|---|---:|",
        ]
    )

    fair_agg = (report.get("fair_rerun_5seed") or {}).get("aggregate", {})
    for field_name in CLASSIFICATION_FIELDS:
        field_rep = metrics["fields"][field_name]
        f1_val = field_rep["macro"]["f1"]
        gate = gates["checks"][field_name]
        sira_ref = SIRA_REFERENCE_VAL_F1[field_name]
        agg_entry = fair_agg.get(f"{field_name}_macro_f1")
        if agg_entry:
            fair_str = f"{agg_entry['mean']:.4f} +/- {agg_entry['std']:.4f}"
        else:
            fair_str = "N/A"
        status_str = "PASS" if gate["passed"] else "FAIL"
        lines.append(
            f"| `{field_name}` | **{f1_val:.4f}** | >= {gate['threshold']:.2f} | {status_str} | "
            f"{sira_ref:.4f} | {fair_str} | {field_rep['n']} (excl {field_rep['n_excluded']}) |"
        )

    comb_gate = gates["checks"]["combined"]
    fair_comb_mean = (report.get("fair_rerun_5seed") or {}).get("combined_mean")
    fair_comb_std = (report.get("fair_rerun_5seed") or {}).get("combined_std")
    fair_comb_str = (
        f"{fair_comb_mean:.4f} +/- {fair_comb_std:.4f}"
        if fair_comb_mean is not None and fair_comb_std is not None
        else "N/A"
    )
    lines.append(
        f"| **Combined (unweighted mean)** | **{combined:.4f}** | >= {comb_gate['threshold']:.2f} | "
        f"{'PASS' if comb_gate['passed'] else 'FAIL'} | {SIRA_REFERENCE_VAL_F1['combined']:.4f} | "
        f"{fair_comb_str} | {report['n_rows']} |"
    )

    lines.extend(
        [
            "",
            "### Churn Risk Fragility Note (AI9)",
            "",
            f"- True `at_risk` rows in `{split}`: **{churn_info['true_at_risk_count']}** of {report['n_rows']}",
            f"- Predicted `at_risk` rows: **{churn_info['predicted_at_risk_count']}** (TP: {churn_info['true_positives']}, FP: {churn_info['false_positives']}, FN: {churn_info['false_negatives']})",
            f"- `at_risk` precision: {churn_info['at_risk_precision']:.4f}, recall: {churn_info['at_risk_recall']:.4f}, F1: {churn_info['at_risk_f1']:.4f}",
            "- Because validation contains only 7 `at_risk` rows, a single flipped prediction changes churn macro-F1 substantially. Always inspect per-seed churn values below alongside the mean.",
        ]
    )

    fair_5seed = report.get("fair_rerun_5seed")
    if fair_5seed and fair_5seed.get("per_seed"):
        lines.extend(
            [
                "",
                "### 5-Seed Breakdown (`runs/exp_fair-marbertv2-lr2e5/run_record.json`)",
                "",
                "| Seed | Category F1 | Urgency F1 | State F1 | Churn F1 | Combined F1 |",
                "|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for s in fair_5seed["per_seed"]:
            lines.append(
                f"| {s['seed']} | {s['complaint_category_macro_f1']:.4f} | "
                f"{s['complaint_urgency_macro_f1']:.4f} | {s['customer_state_macro_f1']:.4f} | "
                f"{s['churn_risk_macro_f1']:.4f} | {s['combined_macro_f1']:.4f} |"
            )

    lines.extend(
        [
            "",
            "## 2. Routing Agreement (FR20 Telecom Skill Mapping)",
            "",
            f"- **Routing Agreement:** **{routing['routing_agreement_pct']:.2f}%** ({routing['agreed_rows']}/{routing['total_rows']} rows) "
            f"- AI9 Gate >= 80.00%: **{'PASS' if routing['meets_ai9_threshold'] else 'FAIL'}**",
            f"- **Exact 11-Category Match Rate:** {routing['exact_category_match_pct']:.2f}%",
            f"- **Priority Bucket Agreement:** {report['priority_agreement']['bucket_agreement_pct']:.2f}% "
            f"({report['priority_agreement']['scored_rows']} scored, {report['priority_agreement']['excluded_unclear_rows']} unclear excluded)",
            f"- **Human Review Rate (threshold {report['confidence_threshold']:.2f}):** "
            f"{report['operational_metrics']['human_review_rate_pct']:.2f}% "
            f"({report['operational_metrics']['human_review_count']}/{report['n_rows']}, AI10 target <= 20.00%)",
            "",
            "| Telecom Skill | Ideal Agent | Support | Predicted | Agreed | Precision | Recall | F1 |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for skill in SKILL_GROUPS:
        sm = routing["per_skill"][skill]
        lines.append(
            f"| {skill} | {sm['ideal_agent']} | {sm['support']} | {sm['predicted']} | "
            f"{sm['agreed']} | {sm['precision']:.4f} | {sm['recall']:.4f} | {sm['f1']:.4f} |"
        )

    stt_info = report["stt_sample"]
    lines.extend(
        [
            "",
            f"## 3. STT Sample ({stt_info['model']}) & Per-Stage Latency",
            "",
            f"- **Real WAVs Transcribed:** {stt_info['sample_size']} from `dataset/{report['infra_split']}/`",
            f"- **10-Column STT v1 Schema Valid:** {stt_info['v1_schema_valid_count']}/{stt_info['sample_size']} (errors: {stt_info['error_count']})",
            f"- **Hardware:** `{hw['platform']}`, CPUs: `{hw['cpu_count']}`, Classifier device: `{hw['classifier_device']}`, STT: `{hw['stt_device']}` (`{hw['stt_compute_type']}`)",
            f"- **Hardware Note:** {hw['hardware_note']}",
            "",
            "| Stage | Samples (n) | p50 (ms) | p95 (ms) | Mean (ms) | Max (ms) |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )

    stage_list = ["transcribe"]
    if "verify_transcript" in latency:
        stage_list.append("verify_transcript")
    stage_list.extend(["classify", "priority", "route", "brief", "end_to_end"])
    for stage in stage_list:
        st = latency[stage]
        p50 = f"{st['p50']:.2f}" if st["p50"] is not None else "N/A"
        p95 = f"{st['p95']:.2f}" if st["p95"] is not None else "N/A"
        mean_v = f"{st['mean']:.2f}" if st["mean"] is not None else "N/A"
        max_v = f"{st['max']:.2f}" if st["max"] is not None else "N/A"
        lines.append(f"| `{stage}` | {st['n']} | {p50} | {p95} | {mean_v} | {max_v} |")

    lines.extend(
        [
            "",
            "## 4. Exceptions & Provenance",
            "",
            f"- Label status: {metrics['label_status']}",
        ]
    )
    for exc in metrics.get("exceptions", []):
        lines.append(
            f"- Exception on `{exc['field']}`: excluded `{exc['excluded_labels']}` "
            f"({exc['rows_excluded']} row(s), scored {exc['n_scored']}/{exc['n_total_rows']}). Reason: {exc['reason']}"
        )
    lines.append("")
    return "\n".join(lines)


def run_evaluation(
    *,
    split: str = "validation",
    stt_sample_size: int = 10,
    seed: int = 42,
    batch_size: int = 32,
    confidence_threshold: float = 0.5,
    dataset_version: str = "v2",
    actor: str = "eval-cli",
    repo_root: Path | None = None,
    models_dir: Path | None = None,
    output_dir: Path | None = None,
    database_url: str | None = None,
    ledger_path: Path | None = None,
    allow_fallback: bool = False,
    with_voicegate: bool = False,
    stt_service: BaseSTTService | None = None,
    transcript_gate: Any | None = None,
    classifier_service: MARBERTv2ClassifierService | None = None,
    settings_override: Settings | None = None,
) -> dict[str, Any]:
    """Execute the full production evaluation pipeline and persist EvalRun + artifacts."""
    canonical_split, infra_split = _normalize_split_arg(split)
    settings = settings_override or get_settings()
    root = Path(repo_root) if repo_root else settings.repo_root
    _ensure_repo_on_syspath(root)

    from infra.harness import evaluate_predictions

    resolved_models_dir = Path(models_dir) if models_dir else settings.svr_models_dir
    resolved_output_dir = (
        Path(output_dir)
        if output_dir
        else root / "runs" / f"eval_{canonical_split}_production"
    )
    resolved_db_url = database_url or settings.database_url
    resolved_ledger = Path(ledger_path) if ledger_path else root / "runs" / "test_evaluations.json"

    csv_path = root / "final" / f"clean_training_{infra_split}.csv"
    audio_dir = root / "dataset" / infra_split

    clf = classifier_service or MARBERTv2ClassifierService(
        models_dir=resolved_models_dir,
        repo_root=root,
        base_model_id=settings.marbert_base_model,
        seed=seed,
        allow_validated_artifact_fallback=allow_fallback,
    )

    ckpt_dirs = discover_single_task_checkpoints(resolved_models_dir, seed=seed)
    has_local_ckpts = clf.has_local_checkpoints()

    checkpoint_files: dict[str, Path] = {}
    checkpoint_hashes: dict[str, str] = {}
    if ckpt_dirs is not None:
        for field_name in CLASSIFICATION_FIELDS:
            cdir = ckpt_dirs[field_name]
            wfile = next(
                (
                    cdir / fname
                    for fname in ("model.safetensors", "pytorch_model.bin", "model_int8.onnx", "model.onnx")
                    if (cdir / fname).is_file()
                ),
                cdir / "model.safetensors",
            )
            checkpoint_files[field_name] = wfile
            checkpoint_hashes[field_name] = compute_file_sha256(wfile)
        combined_ckpt_sha256 = compute_checkpoint_set_sha256(checkpoint_files)
        model_version = f"{settings.marbert_base_model}:single-task-lr2e5-seed{seed}-sha{combined_ckpt_sha256[:12]}"
    elif clf._predictor_override is not None:
        combined_ckpt_sha256 = "0" * 64
        model_version = f"{settings.marbert_base_model}:single-task-lr2e5-test-override"
    elif allow_fallback:
        combined_ckpt_sha256 = "f" * 64
        model_version = f"{settings.marbert_base_model}:validated-artifact-fallback-seed{seed}"
    else:
        raise RuntimeError(
            f"Local MARBERTv2 single-task checkpoints are required under {resolved_models_dir} "
            f"(seed_{seed}/<field>/). Pass --allow-fallback only for dry tests."
        )

    # Guarded test-once enforcement: log claim to runs/test_evaluations.json BEFORE opening test CSV
    guard_claim_id: str | None = None
    dataset_sha256: str | None = None
    if canonical_split == "test":
        claim, csv_bytes, dataset_sha256 = guarded_read_test_file(
            resolved_ledger,
            csv_path,
            model_version=model_version,
            dataset_version=dataset_version,
            checkpoint_sha256=combined_ckpt_sha256,
            actor=actor,
        )
        guard_claim_id = claim.claim_id
    else:
        if not csv_path.is_file():
            raise FileNotFoundError(f"Evaluation CSV not found: {csv_path}")
        csv_bytes = csv_path.read_bytes()
        dataset_sha256 = compute_file_sha256(csv_path)

    try:
        rows = _load_split_csv_rows(csv_bytes, expected_infra_split=infra_split)
        n_rows = len(rows)

        # Ensure DB and default seeded telecom org/agents exist for real routing & EvalRun persistence
        db_mgr = DatabaseManager(resolved_db_url)
        db_mgr.create_all()
        with db_mgr.session_factory() as db:
            org = seed_initial_data(db, settings)
            org_id = org.id

        # 1. Live STT sample evaluation (+ optional VoiceGate ablation)
        stt = stt_service or build_stt_service(settings)
        gate = transcript_gate or (build_transcript_gate(settings) if with_voicegate else None)
        sample_rows = _select_sample_rows(rows, stt_sample_size, audio_dir)
        stt_latencies_ms: list[float] = []
        vg_latencies_ms: list[float] = []
        vg_repaired_count = 0
        vg_uncertain_count = 0
        stt_v1_valid = 0
        stt_errors = 0
        stt_needs_review = 0
        stt_file_records: list[dict[str, Any]] = []
        stt_e2e_candidates: list[tuple[dict[str, str], float, str]] = []

        if sample_rows and stt._transcriber_override is None:
            # Warm model download/load outside per-voicemail inference timing
            print(
                f"[eval-cli] Loading STT {stt.canonical_model_name} ({stt.device}/{stt.compute_type})...",
                file=sys.stderr,
                flush=True,
            )
            stt._get_model()

        for idx, srow in enumerate(sample_rows, start=1):
            wav_path = audio_dir / srow["audio_file"]
            wav_bytes = wav_path.read_bytes()
            meta = validate_and_probe_audio(wav_bytes, srow["audio_file"], ffprobe_bin=settings.ffprobe_bin)
            t0 = time.perf_counter()
            stt_res = stt.transcribe(wav_bytes, "wav", file_label=srow["audio_file"])
            stt_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            stt_latencies_ms.append(stt_ms)
            if stt._transcriber_override is None:
                print(
                    f"[eval-cli] STT {idx}/{len(sample_rows)}: {srow['audio_file']} "
                    f"({meta.duration_seconds:.1f}s) -> {stt_ms:.0f} ms",
                    file=sys.stderr,
                    flush=True,
                )

            v1_dict = stt_res.to_v1_dict()
            is_v1_valid = (
                tuple(v1_dict.keys()) == STT_V1_COLUMNS
                and isinstance(v1_dict["file"], str)
                and isinstance(v1_dict["model"], str)
                and isinstance(v1_dict["needs_review"], bool)
                and isinstance(v1_dict["dup_text_size"], int)
            )
            if is_v1_valid:
                stt_v1_valid += 1
            if stt_res.error:
                stt_errors += 1
            if stt_res.needs_review:
                stt_needs_review += 1

            final_text_norm = stt_res.text_norm or srow["text_norm"]
            vg_ms = 0.0
            vg_status = "disabled"
            if gate is not None:
                gate_res = gate.verify(
                    stt_res.text,
                    min_avg_logprob=stt_res.min_avg_logprob,
                    max_no_speech_prob=stt_res.max_no_speech_prob,
                    stt_review_reasons=stt_res.review_reasons,
                )
                vg_ms = round(float(gate_res.latency_ms), 2)
                vg_latencies_ms.append(vg_ms)
                vg_status = gate_res.status
                if gate_res.correction_applied:
                    vg_repaired_count += 1
                if gate_res.needs_human_review:
                    vg_uncertain_count += 1
                if gate_res.final_text_norm:
                    final_text_norm = gate_res.final_text_norm

            stt_file_records.append(
                {
                    "audio_file": srow["audio_file"],
                    "duration_seconds": round(float(meta.duration_seconds), 3),
                    "latency_ms": stt_ms,
                    "voicegate_latency_ms": vg_ms if gate is not None else None,
                    "voicegate_status": vg_status if gate is not None else None,
                    "min_avg_logprob": stt_res.min_avg_logprob,
                    "max_no_speech_prob": stt_res.max_no_speech_prob,
                    "needs_review": stt_res.needs_review,
                    "review_reasons": stt_res.review_reasons,
                    "v1_columns_valid": is_v1_valid,
                    "error": stt_res.error,
                }
            )
            stt_e2e_candidates.append((srow, stt_ms + vg_ms, final_text_norm))

        # Release STT model from RAM/VRAM before loading the 4 MARBERTv2 checkpoints
        if stt_service is None and hasattr(stt, "unload"):
            stt.unload()

        # 2. MARBERTv2 4-field single-task classification on ALL rows (using text_norm)
        t_cls_total_0 = time.perf_counter()
        if has_local_ckpts and clf._predictor_override is None and batch_size > 1:
            cls_results = _predict_batch_with_checkpoints(
                clf,
                rows,
                batch_size=batch_size,
                confidence_threshold=confidence_threshold,
            )
            actual_model_version = cls_results[0].model_version if cls_results else model_version
        else:
            cls_results = []
            for row in rows:
                res = clf.classify(
                    row["text_norm"],
                    confidence_threshold=confidence_threshold,
                    file_name=row["audio_file"],
                )
                cls_results.append(res)
            actual_model_version = cls_results[0].model_version if cls_results else model_version
        total_classify_seconds = round(time.perf_counter() - t_cls_total_0, 2)

        # Measure real single-voicemail stage latencies (classify, priority, route, brief, end_to_end)
        classify_latencies_ms: list[float] = []
        priority_latencies_ms: list[float] = []
        route_latencies_ms: list[float] = []
        brief_latencies_ms: list[float] = []
        end_to_end_latencies_ms: list[float] = []

        latency_probe_count = min(n_rows, max(stt_sample_size, 30))
        seen_probe_files: set[str] = set()
        probe_rows: list[dict[str, str]] = []
        for srow in sample_rows:
            if srow["audio_file"] not in seen_probe_files:
                seen_probe_files.add(srow["audio_file"])
                probe_rows.append(srow)
        for row in rows:
            if len(probe_rows) >= latency_probe_count:
                break
            if row["audio_file"] not in seen_probe_files:
                seen_probe_files.add(row["audio_file"])
                probe_rows.append(row)

        with db_mgr.session_factory() as db:
            # Measure single-ticket pipeline stage timings
            sample_stt_ms_by_file = {r["audio_file"]: stt_ms for r, stt_ms, _ in stt_e2e_candidates}
            for prow in probe_rows:
                t_c0 = time.perf_counter()
                single_cls = clf.classify(
                    prow["text_norm"],
                    confidence_threshold=confidence_threshold,
                    file_name=prow["audio_file"],
                )
                c_ms = round((time.perf_counter() - t_c0) * 1000.0, 2)
                classify_latencies_ms.append(c_ms)

                t_p0 = time.perf_counter()
                compute_priority(
                    single_cls.labels["complaint_urgency"],
                    single_cls.labels["churn_risk"],
                    single_cls.labels["customer_state"],
                )
                p_ms = round((time.perf_counter() - t_p0) * 1000.0, 2)
                priority_latencies_ms.append(p_ms)

                t_r0 = time.perf_counter()
                recommend_route(
                    db,
                    organization_id=org_id,
                    complaint_category=single_cls.labels["complaint_category"],
                    auto_routing_enabled=True,
                    human_review_blocker=None,
                )
                r_ms = round((time.perf_counter() - t_r0) * 1000.0, 2)
                route_latencies_ms.append(r_ms)

                t_b0 = time.perf_counter()
                cat = single_cls.labels["complaint_category"] or "other"
                tpl = DEFAULT_TEMPLATES.get(cat, DEFAULT_TEMPLATES["other"])
                _summary = (prow.get("text") or prow["text_norm"])[:200]
                _script = tpl["template_ar"]
                b_ms = round((time.perf_counter() - t_b0) * 1000.0, 2)
                brief_latencies_ms.append(b_ms)

                if prow["audio_file"] in sample_stt_ms_by_file:
                    e2e_ms = round(sample_stt_ms_by_file[prow["audio_file"]] + c_ms + p_ms + r_ms + b_ms, 2)
                    end_to_end_latencies_ms.append(e2e_ms)

        # Build truth and prediction rows for infra/harness.py
        truth_rows = [
            {"audio_file": r["audio_file"], **{f: r[f] for f in CLASSIFICATION_FIELDS}}
            for r in rows
        ]
        pred_rows: list[dict[str, Any]] = []
        human_review_count = 0
        confidences: list[float] = []
        prob_sum_violations = 0

        for row, cls_res in zip(rows, cls_results):
            if cls_res.error or any(cls_res.labels[f] is None for f in CLASSIFICATION_FIELDS):
                raise RuntimeError(
                    f"Classification failed on {row['audio_file']}: {cls_res.error or cls_res.review_reason}"
                )
            if cls_res.needs_human_review:
                human_review_count += 1
            confidences.append(float(cls_res.confidence))
            for f in CLASSIFICATION_FIELDS:
                if abs(sum(cls_res.probabilities[f].values()) - 1.0) > 0.001:
                    prob_sum_violations += 1
            pred_rows.append(
                {
                    "audio_file": row["audio_file"],
                    **{f: cls_res.labels[f] for f in CLASSIFICATION_FIELDS},
                }
            )

        # Score via infra/harness.py (excluding customer_state == 'unclear')
        harness_report = evaluate_predictions(
            split=infra_split,
            truth_rows=truth_rows,
            pred_rows=pred_rows,
            classes_by_field=TRAINED_CLASSES_BY_FIELD,
            exclusions_by_field=UNCLEAR_EXCLUSION_RULE,
        )

        # Churn at_risk fragility breakdown
        true_at_risk = [r["churn_risk"] == "at_risk" for r in truth_rows]
        pred_at_risk = [r["churn_risk"] == "at_risk" for r in pred_rows]
        tp_churn = sum(1 for t, p in zip(true_at_risk, pred_at_risk) if t and p)
        fp_churn = sum(1 for t, p in zip(true_at_risk, pred_at_risk) if (not t) and p)
        fn_churn = sum(1 for t, p in zip(true_at_risk, pred_at_risk) if t and (not p))
        churn_at_risk_class = harness_report["fields"]["churn_risk"]["per_class"]["at_risk"]
        churn_analysis = {
            "true_at_risk_count": sum(1 for x in true_at_risk if x),
            "predicted_at_risk_count": sum(1 for x in pred_at_risk if x),
            "true_positives": tp_churn,
            "false_positives": fp_churn,
            "false_negatives": fn_churn,
            "at_risk_precision": round(float(churn_at_risk_class["precision"]), 6),
            "at_risk_recall": round(float(churn_at_risk_class["recall"]), 6),
            "at_risk_f1": round(float(churn_at_risk_class["f1"]), 6),
            "fragility_warning": (
                "Churn macro-F1 depends on only 7 at_risk rows in validation; one row shifts "
                "the score materially. Inspect per-seed churn values alongside the mean."
            ),
        }

        # Routing agreement + priority agreement
        routing_report = compute_routing_agreement(truth_rows, pred_rows, DEFAULT_SKILL_MAPPING)
        priority_report = compute_priority_agreement(truth_rows, pred_rows)

        # AI9 release gate checks
        per_field_f1 = {
            f: round(float(harness_report["fields"][f]["macro"]["f1"]), 6)
            for f in CLASSIFICATION_FIELDS
        }
        combined_f1 = round(float(harness_report["combined_macro_f1"]["mean"]), 6)

        gate_checks = {
            field_name: {
                "actual": per_field_f1[field_name],
                "threshold": AI9_THRESHOLDS[field_name],
                "passed": per_field_f1[field_name] >= AI9_THRESHOLDS[field_name],
            }
            for field_name in CLASSIFICATION_FIELDS
        }
        gate_checks["combined"] = {
            "actual": combined_f1,
            "threshold": AI9_THRESHOLDS["combined"],
            "passed": combined_f1 >= AI9_THRESHOLDS["combined"],
        }
        gate_checks["routing_agreement"] = {
            "actual": routing_report["routing_agreement"],
            "threshold": AI9_THRESHOLDS["routing_agreement"],
            "passed": routing_report["meets_ai9_threshold"],
        }
        ai9_gates = {
            "all_passed": all(g["passed"] for g in gate_checks.values()),
            "checks": gate_checks,
        }

        latency_report: dict[str, Any] = {
            "transcribe": _latency_summary(stt_latencies_ms),
            "classify": _latency_summary(classify_latencies_ms),
            "priority": _latency_summary(priority_latencies_ms),
            "route": _latency_summary(route_latencies_ms),
            "brief": _latency_summary(brief_latencies_ms),
            "end_to_end": _latency_summary(end_to_end_latencies_ms),
            "full_split_classification_seconds": total_classify_seconds,
            "full_split_batch_size": batch_size if (has_local_ckpts and clf._predictor_override is None) else 1,
        }
        if gate is not None:
            latency_report["verify_transcript"] = _latency_summary(vg_latencies_ms)

        hardware = collect_hardware_metadata(
            classifier_device=clf._device,
            stt_device=stt.device,
            stt_compute_type=stt.compute_type,
            e2e_p95_ms=latency_report["end_to_end"]["p95"],
        )

        fair_rerun = _load_fair_rerun_5seed(root)
        created_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

        human_review_rate = human_review_count / n_rows
        conf_arr = np.asarray(confidences, dtype=np.float64)
        operational_metrics = {
            "confidence_threshold": confidence_threshold,
            "human_review_count": human_review_count,
            "human_review_rate": round(human_review_rate, 6),
            "human_review_rate_pct": round(human_review_rate * 100.0, 2),
            "meets_ai10_review_rate_target": human_review_rate <= 0.20,
            "prob_sum_violations": prob_sum_violations,
            "confidence_distribution": {
                "min": round(float(np.min(conf_arr)), 4),
                "p10": round(float(np.percentile(conf_arr, 10)), 4),
                "p50": round(float(np.percentile(conf_arr, 50)), 4),
                "p90": round(float(np.percentile(conf_arr, 90)), 4),
                "mean": round(float(np.mean(conf_arr)), 4),
            },
        }

        stt_sample_report = {
            "model": stt.canonical_model_name,
            "sample_size": len(sample_rows),
            "v1_schema_valid_count": stt_v1_valid,
            "v1_columns": list(STT_V1_COLUMNS),
            "error_count": stt_errors,
            "needs_review_count": stt_needs_review,
            "voicegate_enabled": gate is not None,
            "voicegate_repaired_count": vg_repaired_count if gate is not None else 0,
            "voicegate_uncertain_count": vg_uncertain_count if gate is not None else 0,
            "latency_ms": latency_report["transcribe"],
            "files": stt_file_records,
        }

        checkpoint_provenance = {
            "models_dir": str(resolved_models_dir),
            "seed": seed,
            "has_local_checkpoints": has_local_ckpts,
            "combined_sha256": combined_ckpt_sha256,
            "files": {
                field_name: {
                    "path": str(checkpoint_files[field_name]),
                    "sha256": checkpoint_hashes[field_name],
                }
                for field_name in checkpoint_files
            },
        }

        eval_config = {
            "seed": seed,
            "batch_size": batch_size,
            "stt_sample_size": stt_sample_size,
            "confidence_threshold": confidence_threshold,
            "dataset_sha256": dataset_sha256,
            "checkpoint_sha256": combined_ckpt_sha256,
            "whisper_model": stt.canonical_model_name,
            "whisper_device": stt.device,
            "whisper_compute_type": stt.compute_type,
        }

        # Persist EvalRun row to database
        db_metrics = {
            "n_rows": n_rows,
            "per_field_macro_f1": per_field_f1,
            "combined_macro_f1": combined_f1,
            "routing_agreement": routing_report["routing_agreement"],
            "routing_agreement_pct": routing_report["routing_agreement_pct"],
            "priority_bucket_agreement": priority_report["bucket_agreement"],
            "human_review_rate": operational_metrics["human_review_rate"],
            "churn_at_risk_true_count": churn_analysis["true_at_risk_count"],
            "churn_at_risk_pred_count": churn_analysis["predicted_at_risk_count"],
            "churn_at_risk_analysis": churn_analysis,
            "ai9_gates": ai9_gates,
            "latency_ms": latency_report,
            "stt_sample": {k: v for k, v in stt_sample_report.items() if k != "files"},
            "routing_per_skill": routing_report["per_skill"],
            "routing_confusion_matrix": routing_report["confusion_matrix"],
            "fields": harness_report["fields"],
            "exceptions": harness_report["exceptions"],
            "fair_rerun_5seed": fair_rerun,
            "sira_reference_val_f1": SIRA_REFERENCE_VAL_F1,
            "hardware": hardware,
            "operational_metrics": operational_metrics,
        }

        with db_mgr.session_factory() as db:
            org = db.scalar(select(Organization).where(Organization.id == org_id))
            assert org is not None
            eval_row = EvalRun(
                organization_id=org.id,
                dataset_version=dataset_version,
                split=canonical_split,
                model_version=actual_model_version,
                config=eval_config,
                metrics=db_metrics,
                guard_claim_id=guard_claim_id,
                created_by=actor,
            )
            db.add(eval_row)
            db.flush()
            eval_run_id = eval_row.id
            record_audit_event(
                db,
                organization_id=org.id,
                entity_type="eval",
                entity_id=eval_run_id,
                action="eval_run_recorded",
                actor=actor,
                old_value=None,
                new_value={
                    "split": canonical_split,
                    "dataset_version": dataset_version,
                    "model_version": actual_model_version,
                    "combined_macro_f1": combined_f1,
                    "routing_agreement_pct": routing_report["routing_agreement_pct"],
                    "ai9_all_passed": ai9_gates["all_passed"],
                    "guard_claim_id": guard_claim_id,
                },
            )
            db.commit()

        report = {
            "schema_version": 1,
            "created_utc": created_utc,
            "eval_run_id": eval_run_id,
            "guard_claim_id": guard_claim_id,
            "split": canonical_split,
            "infra_split": infra_split,
            "dataset_version": dataset_version,
            "dataset_sha256": dataset_sha256,
            "n_rows": n_rows,
            "model_version": actual_model_version,
            "confidence_threshold": confidence_threshold,
            "checkpoint_provenance": checkpoint_provenance,
            "ai9_gates": ai9_gates,
            "classification": harness_report,
            "per_field_macro_f1": per_field_f1,
            "combined_macro_f1": combined_f1,
            "churn_at_risk_analysis": churn_analysis,
            "sira_reference_val_f1": SIRA_REFERENCE_VAL_F1,
            "fair_rerun_5seed": fair_rerun,
            "routing_agreement": routing_report,
            "priority_agreement": priority_report,
            "operational_metrics": operational_metrics,
            "stt_sample": stt_sample_report,
            "latency_ms": latency_report,
            "hardware": hardware,
        }

        resolved_output_dir.mkdir(parents=True, exist_ok=True)
        report_json_path = resolved_output_dir / "eval_report.json"
        summary_md_path = resolved_output_dir / "eval_summary.md"
        report_json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        summary_md_path.write_text(_build_eval_summary_markdown(report), encoding="utf-8")

        report["artifacts"] = {
            "eval_report_json": str(report_json_path),
            "eval_summary_md": str(summary_md_path),
        }
        # Rewrite report JSON with artifact paths included
        report_json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        if guard_claim_id is not None:
            finalize_test_claim(
                resolved_ledger,
                guard_claim_id,
                status="completed",
                result_summary={
                    "eval_run_id": eval_run_id,
                    "combined_macro_f1": combined_f1,
                    "per_field_macro_f1": per_field_f1,
                    "routing_agreement": routing_report["routing_agreement"],
                },
            )

        return report
    except Exception as exc:
        if guard_claim_id is not None:
            finalize_test_claim(
                resolved_ledger,
                guard_claim_id,
                status="failed",
                result_summary={"error": str(exc)},
            )
        raise


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m svr_platform.eval.cli",
        description="Run SVR production evaluation (Whisper large-v3 STT + 4x MARBERTv2 + FR20 routing).",
    )
    parser.add_argument(
        "--split",
        default="validation",
        choices=["validation", "test"],
        help="Dataset split to evaluate (default: validation; test is guarded once-only).",
    )
    parser.add_argument(
        "--stt-sample-size",
        type=int,
        default=10,
        help="Number of real WAV files to transcribe with Whisper large-v3 (default: 10).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=99,
        help="Single-task MARBERTv2 checkpoint seed directory (default: 99).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for MARBERTv2 full-split inference (default: 32).",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.5,
        help="Human Review confidence threshold (default: 0.5).",
    )
    parser.add_argument(
        "--dataset-version",
        default="v2",
        help="Dataset version tag recorded on EvalRun and test guard ledger (default: v2).",
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=None,
        help="Override path to models/marbertv2-single-task directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override output directory for eval_report.json and eval_summary.md.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Override SQLAlchemy database URL for persisting EvalRun.",
    )
    parser.add_argument(
        "--ledger-path",
        type=Path,
        default=None,
        help="Override path to runs/test_evaluations.json guard ledger.",
    )
    parser.add_argument(
        "--actor",
        default="eval-cli",
        help="Actor recorded in EvalRun and AuditEvent.",
    )
    parser.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Allow validated artifact fallback when local checkpoints are not mounted (for dry tests only).",
    )
    parser.add_argument(
        "--with-voicegate",
        action="store_true",
        help="Run VoiceGate transcript verification ablation on sampled STT outputs.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    report = run_evaluation(
        split=args.split,
        stt_sample_size=args.stt_sample_size,
        seed=args.seed,
        batch_size=args.batch_size,
        confidence_threshold=args.confidence_threshold,
        dataset_version=args.dataset_version,
        actor=args.actor,
        models_dir=args.models_dir,
        output_dir=args.output_dir,
        database_url=args.database_url,
        ledger_path=args.ledger_path,
        allow_fallback=args.allow_fallback,
        with_voicegate=args.with_voicegate,
    )
    print(
        json.dumps(
            {
                "eval_run_id": report["eval_run_id"],
                "split": report["split"],
                "n_rows": report["n_rows"],
                "model_version": report["model_version"],
                "per_field_macro_f1": report["per_field_macro_f1"],
                "combined_macro_f1": report["combined_macro_f1"],
                "routing_agreement_pct": report["routing_agreement"]["routing_agreement_pct"],
                "ai9_all_passed": report["ai9_gates"]["all_passed"],
                "latency_p50_p95_ms": {
                    stage: {
                        "p50": report["latency_ms"][stage]["p50"],
                        "p95": report["latency_ms"][stage]["p95"],
                    }
                    for stage in ("transcribe", "classify", "end_to_end")
                },
                "artifacts": report["artifacts"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
