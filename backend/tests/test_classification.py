"""Tests for Module 3: 4-field independent classification, taxonomy guardrails, and confidence gating."""

from __future__ import annotations

from pathlib import Path

from svr_platform.services.classification import (
    CLASSIFICATION_FIELDS,
    MARBERTv2ClassifierService,
    validate_and_score_raw_outputs,
)
from svr_platform.taxonomy import TRAINED_CLASSES_BY_FIELD


def _valid_raw_output(conf_cat=0.90, conf_urg=0.80, conf_state=0.75, conf_churn=0.95):
    def _dist(classes, winner, p_win):
        rest = (1.0 - p_win) / (len(classes) - 1)
        return {c: (p_win if c == winner else rest) for c in classes}

    return {
        "complaint_category": {
            "label": "sim_services",
            "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["complaint_category"], "sim_services", conf_cat),
        },
        "complaint_urgency": {
            "label": "high",
            "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["complaint_urgency"], "high", conf_urg),
        },
        "customer_state": {
            "label": "frustrated",
            "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["customer_state"], "frustrated", conf_state),
        },
        "churn_risk": {
            "label": "not_at_risk",
            "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["churn_risk"], "not_at_risk", conf_churn),
        },
    }


def test_valid_classification_computes_min_confidence_and_sums_to_1():
    raw = _valid_raw_output(conf_cat=0.90, conf_urg=0.80, conf_state=0.72, conf_churn=0.98)
    res = validate_and_score_raw_outputs(raw, confidence_threshold=0.5, model_version="UBC-NLP/MARBERTv2:test")
    assert res.needs_human_review is False
    assert res.review_reason is None
    assert res.confidence == 0.72
    assert res.labels == {
        "complaint_category": "sim_services",
        "complaint_urgency": "high",
        "customer_state": "frustrated",
        "churn_risk": "not_at_risk",
    }
    for field_name in CLASSIFICATION_FIELDS:
        assert abs(sum(res.probabilities[field_name].values()) - 1.0) <= 0.001
        assert res.label_sources[field_name] == "model"


def test_low_confidence_sends_to_human_review_ai3():
    raw = _valid_raw_output(conf_cat=0.90, conf_urg=0.40, conf_state=0.85, conf_churn=0.95)
    res = validate_and_score_raw_outputs(raw, confidence_threshold=0.5, model_version="UBC-NLP/MARBERTv2:test")
    assert res.confidence == 0.40
    assert res.needs_human_review is True
    assert res.review_reason == "low_confidence"


def test_out_of_taxonomy_label_is_rejected_and_recorded_fr8():
    raw = _valid_raw_output()
    raw["complaint_category"]["label"] = "greeting_only"  # excluded from fixed 11-category taxonomy
    res = validate_and_score_raw_outputs(raw, confidence_threshold=0.5, model_version="UBC-NLP/MARBERTv2:test")
    assert res.labels["complaint_category"] is None
    assert res.rejected_labels == {"complaint_category": "greeting_only"}
    assert res.needs_human_review is True
    assert res.review_reason == "invalid_label"


def test_probabilities_not_summing_to_1_rejected_fr6():
    raw = _valid_raw_output()
    raw["churn_risk"]["probabilities"] = {"at_risk": 0.9, "not_at_risk": 0.9}
    res = validate_and_score_raw_outputs(raw, confidence_threshold=0.5, model_version="UBC-NLP/MARBERTv2:test")
    assert res.labels["churn_risk"] is None
    assert res.needs_human_review is True
    assert res.review_reason == "invalid_label"


def test_classifier_degrades_safely_to_human_review_when_checkpoints_unavailable(tmp_path: Path):
    svc = MARBERTv2ClassifierService(
        models_dir=tmp_path / "missing_checkpoints",
        repo_root=tmp_path,
        max_retries=2,
        retry_backoff_s=0.01,
        allow_validated_artifact_fallback=False,
    )
    res = svc.classify("الشبكة فصلت تماما في الخط", confidence_threshold=0.5)
    assert res.needs_human_review is True
    assert res.review_reason == "processing_error"
    assert all(v is None for v in res.labels.values())
    assert "checkpoints not mounted" in res.error


def test_classifier_serves_validated_marbertv2_artifact_on_validation_corpus(tmp_path: Path):
    import csv
    import json

    repo_root = Path(__file__).resolve().parents[2]
    if not (repo_root / "final" / "clean_training_val.csv").is_file():
        repo_root = tmp_path
        final_dir = repo_root / "final"
        runs_dir = repo_root / "runs" / "exp_fair-marbertv2-lr2e5"
        final_dir.mkdir(parents=True, exist_ok=True)
        runs_dir.mkdir(parents=True, exist_ok=True)
        sample_text = "الصوت في المكالمات دائما عالي وش جامد ومش سامع علي الطرف التاني"
        with (final_dir / "clean_training_val.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["audio_file", "text", "text_norm"])
            writer.writeheader()
            writer.writerow({"audio_file": "calm_0001.wav", "text": sample_text, "text_norm": sample_text})
        from svr_platform.taxonomy import TRAINED_CLASSES_BY_FIELD

        chosen = {
            "complaint_category": "network_and_connectivity",
            "complaint_urgency": "high",
            "customer_state": "frustrated",
            "churn_risk": "not_at_risk",
        }
        probs = {}
        for fld, top_cls in chosen.items():
            classes = list(TRAINED_CLASSES_BY_FIELD[fld])
            rem = round(0.10 / max(len(classes) - 1, 1), 6)
            d = {c: rem for c in classes if c != top_cls}
            d[top_cls] = round(1.0 - sum(d.values()), 6)
            probs[fld] = d
        pred_payload = {
            "rows": [
                {
                    "audio_file": "calm_0001.wav",
                    "labels": chosen,
                    "probabilities": probs,
                }
            ]
        }
        for s in (42, 99):
            (runs_dir / f"predictions_val_seed{s}.json").write_text(
                json.dumps(pred_payload, ensure_ascii=False), encoding="utf-8"
            )

    svc = MARBERTv2ClassifierService(
        models_dir=tmp_path / "no_local_ckpts",
        repo_root=repo_root,
        allow_validated_artifact_fallback=True,
    )
    res = svc.classify(
        "الصوت في المكالمات دائما عالي وش جامد ومش سامع علي الطرف التاني",
        confidence_threshold=0.5,
        file_name="calm_0001.wav",
    )
    assert res.error == ""
    assert res.labels["complaint_category"] == "network_and_connectivity"
    assert abs(sum(res.probabilities["complaint_category"].values()) - 1.0) <= 0.001
    assert "MARBERTv2" in res.model_version


def test_onnx_path_discovery_and_logits_scoring(tmp_path: Path):
    ckpt = tmp_path / "complaint_category"
    ckpt.mkdir(parents=True)
    assert MARBERTv2ClassifierService._onnx_path_for(ckpt) is None

    fp32 = ckpt / "model.onnx"
    fp32.write_bytes(b"fp32")
    assert MARBERTv2ClassifierService._onnx_path_for(ckpt) == fp32

    int8 = ckpt / "model_int8.onnx"
    int8.write_bytes(b"int8")
    assert MARBERTv2ClassifierService._onnx_path_for(ckpt) == int8

    classes = list(TRAINED_CLASSES_BY_FIELD["churn_risk"])
    id2label = {i: c for i, c in enumerate(classes)}
    pred = MARBERTv2ClassifierService._logits_to_prediction([0.1, 2.5], id2label, "churn_risk")
    assert pred["label"] == classes[1]
    assert abs(sum(pred["probabilities"].values()) - 1.0) <= 0.001


def test_onnx_backend_forced_on_cuda_when_env_is_onnx(tmp_path: Path, monkeypatch):
    ckpt_dirs = {}
    for field_name in CLASSIFICATION_FIELDS:
        d = tmp_path / field_name
        d.mkdir(parents=True)
        (d / "model_int8.onnx").write_bytes(b"onnx")
        ckpt_dirs[field_name] = d

    svc = MARBERTv2ClassifierService(
        models_dir=tmp_path, repo_root=tmp_path, allow_validated_artifact_fallback=False
    )
    svc._device = "cuda"

    monkeypatch.setenv("SVR_MARBERT_BACKEND", "auto")
    assert svc._use_onnx_backend(ckpt_dirs) is False

    monkeypatch.setenv("SVR_MARBERT_BACKEND", "onnx")
    assert svc._use_onnx_backend(ckpt_dirs) is True
