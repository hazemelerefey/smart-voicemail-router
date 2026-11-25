"""Tests for production evaluation CLI, FR20 routing agreement, and SHA-256 test-once guard."""

from __future__ import annotations

import csv
import io
import json
import wave
from pathlib import Path

import pytest
from sqlalchemy import select

from svr_platform.config import Settings
from svr_platform.database import DatabaseManager
from svr_platform.eval.cli import (
    AI9_THRESHOLDS,
    compute_routing_agreement,
    run_evaluation,
)
from svr_platform.eval.once_guard import (
    TestOnceGuardError,
    compute_checkpoint_set_sha256,
    compute_file_sha256,
    finalize_test_claim,
    guarded_read_test_file,
    load_test_ledger,
)
from svr_platform.models import AuditEvent, EvalRun
from svr_platform.services.classification import CLASSIFICATION_FIELDS, MARBERTv2ClassifierService
from svr_platform.services.stt import WhisperSTTService
from svr_platform.taxonomy import DEFAULT_SKILL_MAPPING, TRAINED_CLASSES_BY_FIELD

def make_wav_bytes(duration_s: float = 1.0, rate: int = 16000, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    n_frames = int(duration_s * rate)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * n_frames * channels)
    return buf.getvalue()


def _dist(classes: list[str], winner: str, p_win: float = 0.85) -> dict[str, float]:
    rest = (1.0 - p_win) / (len(classes) - 1)
    return {c: (p_win if c == winner else rest) for c in classes}


def _make_synthetic_dataset(root: Path, infra_split: str) -> list[dict[str, str]]:
    """Build a synthetic clean_training_<split>.csv + WAVs inside tmp_path only."""
    final_dir = root / "final"
    audio_dir = root / "dataset" / infra_split
    final_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)

    categories = TRAINED_CLASSES_BY_FIELD["complaint_category"]
    urgencies = TRAINED_CLASSES_BY_FIELD["complaint_urgency"]
    states = TRAINED_CLASSES_BY_FIELD["customer_state"]

    rows: list[dict[str, str]] = []
    for idx, cat in enumerate(categories):
        af = f"sample_{idx:03d}.wav"
        urg = urgencies[idx % len(urgencies)]
        state = states[idx % len(states)]
        churn = "at_risk" if idx < 2 else "not_at_risk"
        text = f"مكالمة تجريبية رقم {idx} بخصوص {cat}"
        rows.append(
            {
                "audio_file": af,
                "file": f"dataset/{infra_split}/{af}",
                "text": text,
                "text_norm": text,
                "complaint_category": cat,
                "complaint_urgency": urg,
                "customer_state": state,
                "churn_risk": churn,
                "note": "",
                "confidence": "high",
                "split": infra_split,
                "source": "synthetic",
            }
        )
        (audio_dir / af).write_bytes(make_wav_bytes(duration_s=1.0))

    # Add 1 unclear customer_state row to verify harness exclusion
    unclear_af = "sample_unclear.wav"
    rows.append(
        {
            "audio_file": unclear_af,
            "file": f"dataset/{infra_split}/{unclear_af}",
            "text": "رسالة غير واضحة للاختبار",
            "text_norm": "رسالة غير واضحة للاختبار",
            "complaint_category": "other",
            "complaint_urgency": "low",
            "customer_state": "unclear",
            "churn_risk": "not_at_risk",
            "note": "",
            "confidence": "low",
            "split": infra_split,
            "source": "synthetic",
        }
    )
    (audio_dir / unclear_af).write_bytes(make_wav_bytes(duration_s=1.0))

    csv_path = final_dir / f"clean_training_{infra_split}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def test_once_guard_logs_claim_before_opening_file_and_blocks_repeat(tmp_path: Path):
    ledger_path = tmp_path / "runs" / "test_evaluations.json"

    # 1. Missing synthetic file still logs claim BEFORE attempting file open
    missing_file = tmp_path / "does_not_exist_test.csv"
    with pytest.raises(FileNotFoundError):
        guarded_read_test_file(
            ledger_path,
            missing_file,
            model_version="MARBERTv2:missing-file-check",
            dataset_version="v2-synth",
            checkpoint_sha256="a" * 64,
            actor="pytest",
        )
    ledger = load_test_ledger(ledger_path)
    assert len(ledger["claims"]) == 1
    assert ledger["claims"][0]["status"] == "failed"
    assert ledger["claims"][0]["dataset_sha256"] is None

    # Repeat for same model+dataset is blocked even after failed first attempt
    with pytest.raises(TestOnceGuardError):
        guarded_read_test_file(
            ledger_path,
            missing_file,
            model_version="MARBERTv2:missing-file-check",
            dataset_version="v2-synth",
            checkpoint_sha256="a" * 64,
            actor="pytest",
        )

    # 2. Valid synthetic test file: first run succeeds, second run is refused before file access
    synth_test_file = tmp_path / "synthetic_test.csv"
    synth_test_file.write_text("audio_file,split\nsynth_1.wav,test\n", encoding="utf-8")

    claim, raw_bytes, ds_sha = guarded_read_test_file(
        ledger_path,
        synth_test_file,
        model_version="MARBERTv2:model-v1",
        dataset_version="v2-synth",
        checkpoint_sha256="b" * 64,
        actor="pytest",
    )
    assert raw_bytes == synth_test_file.read_bytes()
    assert ds_sha == compute_file_sha256(synth_test_file)
    assert claim.dataset_sha256 == ds_sha

    finalize_test_claim(
        ledger_path,
        claim.claim_id,
        status="completed",
        result_summary={"combined_macro_f1": 0.81},
    )

    # Remove the file to prove the guard blocks BEFORE touching the filesystem target
    synth_test_file.unlink()
    with pytest.raises(TestOnceGuardError):
        guarded_read_test_file(
            ledger_path,
            synth_test_file,
            model_version="MARBERTv2:model-v1",
            dataset_version="v2-synth",
            checkpoint_sha256="b" * 64,
            actor="pytest",
        )

    # Renamed model with identical checkpoint SHA-256 on same dataset_version is also refused
    with pytest.raises(TestOnceGuardError):
        guarded_read_test_file(
            ledger_path,
            synth_test_file,
            model_version="MARBERTv2:renamed-model",
            dataset_version="v2-synth",
            checkpoint_sha256="b" * 64,
            actor="pytest",
        )

    # Different model + different checkpoint SHA-256 is permitted once
    synth_test_file.write_text("audio_file,split\nsynth_1.wav,test\n", encoding="utf-8")
    claim2, _raw2, _sha2 = guarded_read_test_file(
        ledger_path,
        synth_test_file,
        model_version="MARBERTv2:model-v2",
        dataset_version="v2-synth",
        checkpoint_sha256="c" * 64,
        actor="pytest",
    )
    assert claim2.claim_id != claim.claim_id
    assert len(load_test_ledger(ledger_path)["claims"]) == 3


def test_checkpoint_set_sha256_is_deterministic(tmp_path: Path):
    f1 = tmp_path / "cat.safetensors"
    f2 = tmp_path / "urg.safetensors"
    f1.write_bytes(b"weights-category-v1")
    f2.write_bytes(b"weights-urgency-v1")

    h1 = compute_checkpoint_set_sha256({"complaint_category": f1, "complaint_urgency": f2})
    h2 = compute_checkpoint_set_sha256({"complaint_urgency": f2, "complaint_category": f1})
    assert h1 == h2
    assert len(h1) == 64

    f2.write_bytes(b"weights-urgency-v2")
    h3 = compute_checkpoint_set_sha256({"complaint_category": f1, "complaint_urgency": f2})
    assert h3 != h1


def test_routing_agreement_fr20_telecom_skill_mapping():
    truth_rows = [
        {"audio_file": "a1.wav", "complaint_category": "network_and_connectivity"},  # Network
        {"audio_file": "a2.wav", "complaint_category": "no_reply_or_long_wait"},  # Network
        {"audio_file": "a3.wav", "complaint_category": "billing_and_charges"},  # Billing
        {"audio_file": "a4.wav", "complaint_category": "balance_and_data"},  # Billing
        {"audio_file": "a5.wav", "complaint_category": "app_and_account"},  # General
    ]
    pred_rows = [
        # Same skill (Network) despite different fine-grained category -> agrees on routing
        {"audio_file": "a1.wav", "complaint_category": "sim_services"},
        {"audio_file": "a2.wav", "complaint_category": "no_reply_or_long_wait"},
        # Exact Billing match -> agrees
        {"audio_file": "a3.wav", "complaint_category": "offers_and_packages"},
        # Wrong skill (Network instead of Billing) -> disagrees
        {"audio_file": "a4.wav", "complaint_category": "network_and_connectivity"},
        # Exact General match -> agrees
        {"audio_file": "a5.wav", "complaint_category": "cancellation_request"},
    ]

    result = compute_routing_agreement(truth_rows, pred_rows, DEFAULT_SKILL_MAPPING)
    assert result["total_rows"] == 5
    assert result["agreed_rows"] == 4
    assert result["disagreed_rows"] == 1
    assert result["routing_agreement"] == pytest.approx(0.8)
    assert result["routing_agreement_pct"] == 80.0
    assert result["exact_category_match_rate"] == pytest.approx(0.2)
    assert result["meets_ai9_threshold"] is True
    assert result["per_skill"]["Network"]["agreed"] == 2
    assert result["per_skill"]["Billing"]["agreed"] == 1
    assert result["per_skill"]["General"]["agreed"] == 1
    assert result["confusion_matrix"]["labels"] == ["Network", "Billing", "General"]
    assert result["confusion_matrix"]["counts"] == [
        [2, 0, 0],
        [1, 1, 0],
        [0, 0, 1],
    ]


def test_eval_cli_validation_synthetic_schema_db_and_artifacts(tmp_path: Path):
    rows = _make_synthetic_dataset(tmp_path, "val")
    rows_by_text = {r["text_norm"]: r for r in rows}

    db_path = tmp_path / "storage" / "eval_test.db"
    settings = Settings(
        SVR_ENV="test",
        DATABASE_URL=f"sqlite:///{db_path.as_posix()}",
        SVR_STORAGE_DIR=tmp_path / "storage",
        SVR_MODELS_DIR=tmp_path / "models",
        SVR_BOOTSTRAP_PASSWORD="TestPassword123!",
        SVR_SECRET_KEY="test-secret-key-eval-cli",
    )

    def _fake_stt(_audio_bytes: bytes, _fmt: str) -> dict:
        return {
            "text": "الشبكة ضعيفة جدا في الخط",
            "min_avg_logprob": -0.15,
            "max_no_speech_prob": 0.05,
        }

    def _fake_predict(text_norm: str) -> dict[str, dict]:
        row = rows_by_text[text_norm]
        state_lbl = row["customer_state"] if row["customer_state"] != "unclear" else "calm"
        return {
            "complaint_category": {
                "label": row["complaint_category"],
                "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["complaint_category"], row["complaint_category"]),
            },
            "complaint_urgency": {
                "label": row["complaint_urgency"],
                "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["complaint_urgency"], row["complaint_urgency"]),
            },
            "customer_state": {
                "label": state_lbl,
                "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["customer_state"], state_lbl),
            },
            "churn_risk": {
                "label": row["churn_risk"],
                "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["churn_risk"], row["churn_risk"]),
            },
        }

    stt_svc = WhisperSTTService(transcriber_override=_fake_stt)
    clf_svc = MARBERTv2ClassifierService(
        models_dir=tmp_path / "models",
        repo_root=tmp_path,
        allow_validated_artifact_fallback=False,
        predictor_override=_fake_predict,
    )

    out_dir = tmp_path / "runs" / "eval_validation_production"
    report = run_evaluation(
        split="validation",
        stt_sample_size=2,
        seed=42,
        batch_size=4,
        repo_root=tmp_path,
        models_dir=tmp_path / "models",
        output_dir=out_dir,
        database_url=settings.database_url,
        ledger_path=tmp_path / "runs" / "test_evaluations.json",
        stt_service=stt_svc,
        classifier_service=clf_svc,
        settings_override=settings,
    )

    assert report["split"] == "validation"
    assert report["n_rows"] == len(rows)
    assert report["guard_claim_id"] is None
    assert report["combined_macro_f1"] == pytest.approx(1.0)
    assert report["routing_agreement"]["routing_agreement"] == pytest.approx(1.0)
    assert report["ai9_gates"]["all_passed"] is True
    assert report["churn_at_risk_analysis"]["true_at_risk_count"] == 2
    assert report["stt_sample"]["sample_size"] == 2
    assert report["stt_sample"]["v1_schema_valid_count"] == 2
    assert report["latency_ms"]["transcribe"]["p50"] is not None
    assert report["latency_ms"]["transcribe"]["n"] == 2
    assert report["latency_ms"]["classify"]["p50"] is not None
    assert report["latency_ms"]["end_to_end"]["p95"] is not None
    assert report["latency_ms"]["end_to_end"]["n"] == 2
    assert report["classification"]["exceptions"][0]["field"] == "customer_state"
    assert report["classification"]["exceptions"][0]["rows_excluded"] == 1

    # Verify artifacts on disk and zero em/en dashes
    report_json = out_dir / "eval_report.json"
    summary_md = out_dir / "eval_summary.md"
    assert report_json.is_file()
    assert summary_md.is_file()
    md_text = summary_md.read_text(encoding="utf-8")
    assert "\u2014" not in md_text
    assert "\u2013" not in md_text
    parsed_json = json.loads(report_json.read_text(encoding="utf-8"))
    assert parsed_json["eval_run_id"] == report["eval_run_id"]

    # Verify DB persistence (EvalRun + AuditEvent)
    db_mgr = DatabaseManager(settings.database_url)
    with db_mgr.session_factory() as db:
        eval_rows = db.scalars(select(EvalRun)).all()
        assert len(eval_rows) == 1
        assert eval_rows[0].split == "validation"
        assert eval_rows[0].metrics["combined_macro_f1"] == pytest.approx(1.0)
        assert eval_rows[0].metrics["routing_agreement_pct"] == 100.0
        audit_rows = db.scalars(select(AuditEvent).where(AuditEvent.entity_type == "eval")).all()
        assert len(audit_rows) == 1
        assert audit_rows[0].entity_id == eval_rows[0].id


def test_eval_cli_test_split_guarded_once_on_synthetic_fixture(tmp_path: Path):
    rows = _make_synthetic_dataset(tmp_path, "test")
    rows_by_text = {r["text_norm"]: r for r in rows}

    db_path = tmp_path / "storage" / "eval_test_split.db"
    settings = Settings(
        SVR_ENV="test",
        DATABASE_URL=f"sqlite:///{db_path.as_posix()}",
        SVR_STORAGE_DIR=tmp_path / "storage",
        SVR_MODELS_DIR=tmp_path / "models",
        SVR_BOOTSTRAP_PASSWORD="TestPassword123!",
        SVR_SECRET_KEY="test-secret-key-eval-test",
    )

    def _fake_predict(text_norm: str) -> dict[str, dict]:
        row = rows_by_text[text_norm]
        state_lbl = row["customer_state"] if row["customer_state"] != "unclear" else "calm"
        return {
            "complaint_category": {
                "label": row["complaint_category"],
                "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["complaint_category"], row["complaint_category"]),
            },
            "complaint_urgency": {
                "label": row["complaint_urgency"],
                "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["complaint_urgency"], row["complaint_urgency"]),
            },
            "customer_state": {
                "label": state_lbl,
                "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["customer_state"], state_lbl),
            },
            "churn_risk": {
                "label": row["churn_risk"],
                "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["churn_risk"], row["churn_risk"]),
            },
        }

    clf_svc = MARBERTv2ClassifierService(
        models_dir=tmp_path / "models",
        repo_root=tmp_path,
        allow_validated_artifact_fallback=False,
        predictor_override=_fake_predict,
    )
    ledger = tmp_path / "runs" / "test_evaluations.json"

    first = run_evaluation(
        split="test",
        stt_sample_size=0,
        repo_root=tmp_path,
        models_dir=tmp_path / "models",
        output_dir=tmp_path / "runs" / "eval_test_synth",
        database_url=settings.database_url,
        ledger_path=ledger,
        classifier_service=clf_svc,
        settings_override=settings,
    )
    assert first["guard_claim_id"] is not None
    assert load_test_ledger(ledger)["claims"][0]["status"] == "completed"

    # Second run on synthetic test split MUST be refused by once_guard
    with pytest.raises(TestOnceGuardError):
        run_evaluation(
            split="test",
            stt_sample_size=0,
            repo_root=tmp_path,
            models_dir=tmp_path / "models",
            output_dir=tmp_path / "runs" / "eval_test_synth_2",
            database_url=settings.database_url,
            ledger_path=ledger,
            classifier_service=clf_svc,
            settings_override=settings,
        )

    # 'dev' split is forbidden per SVR rules
    with pytest.raises(ValueError):
        run_evaluation(
            split="dev",
            stt_sample_size=0,
            repo_root=tmp_path,
            models_dir=tmp_path / "models",
            database_url=settings.database_url,
            classifier_service=clf_svc,
            settings_override=settings,
        )
