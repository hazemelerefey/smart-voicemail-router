import csv
import json

import pytest

from infra.churn_metrics import churn_report, summarize_seeds
from infra.churn_run_report import (
    OPTIMISTIC_THRESHOLD_NOTE,
    ChurnRunReportError,
    churn_run_report,
    format_churn_report,
)
from infra.harness import load_truth_table
from infra.predictions_file import write_predictions_file
from infra.shared_config import load_shared_config
from infra.tests.test_evaluate_run import _probs_for_chosen
from infra.tests.test_tfidf_baseline import SECRET_MARKER, _make_synthetic_dataset
from infra.tfidf_baseline import load_classes_by_field


def _make_churn_fixture(tmp_path, *, drop_at_risk=False):
    data_dir = _make_synthetic_dataset(tmp_path / "data", include_unclear=True)
    shared = load_shared_config(
        data_dir / "notebooks" / "training" / "shared_config.json"
    )
    classes = load_classes_by_field(data_dir / "final" / "class_weights.json")

    val_csv = data_dir / "final" / "clean_training_val.csv"
    if drop_at_risk:
        with val_csv.open("r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            r["churn_risk"] = "not_at_risk"
        with val_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    truth = load_truth_table(val_csv, "val", list(classes.keys()))

    # Distinct per-seed at_risk probabilities so wrong class column or cross-seed
    # array mixing produces completely different thresholds and AP values.
    per_seed_at_risk_probs = {
        42: [0.85, 0.20, 0.15, 0.10, 0.05],
        1337: [0.62, 0.40, 0.25, 0.15, 0.10],
        2023: [0.44, 0.55, 0.20, 0.15, 0.05],
        7: [0.91, 0.30, 0.25, 0.10, 0.05],
        99: [0.73, 0.65, 0.30, 0.20, 0.10],
    }

    preds_dir = tmp_path / "preds"
    preds_dir.mkdir(parents=True, exist_ok=True)

    for seed in shared["experiment_seeds"]:
        p_list = per_seed_at_risk_probs[seed]
        rows = []
        for row_i, tr_row in enumerate(truth):
            chosen = {
                f: (tr_row[f] if tr_row[f] in cls_list else cls_list[0])
                for f, cls_list in classes.items()
            }
            probs = _probs_for_chosen(classes, chosen)
            p_pos = p_list[row_i]
            probs["churn_risk"] = {
                "at_risk": p_pos,
                "not_at_risk": round(1.0 - p_pos, 6),
            }
            rows.append({
                "audio_file": tr_row["audio_file"],
                "probabilities": probs,
            })

        write_predictions_file(
            path=preds_dir / f"predictions_val_seed{seed}.json",
            run_id="marbert-001",
            model="MARBERTv2",
            split="val",
            seed=seed,
            dataset_version=shared["dataset_version"],
            rows=rows,
            classes_by_field=classes,
        )

    return data_dir, preds_dir, shared, classes, truth, per_seed_at_risk_probs


def test_churn_run_report_equals_direct_churn_metrics_calls(tmp_path, capsys):
    data_dir, preds_dir, shared, classes, truth, per_seed_probs = _make_churn_fixture(
        tmp_path
    )
    result = churn_run_report(
        data_dir, preds_dir, positive_class="at_risk", field="churn_risk"
    )
    text = format_churn_report(result)

    y_true = [r["churn_risk"] for r in truth]
    direct_reports = []
    for seed, seed_entry in zip(shared["experiment_seeds"], result["per_seed"]):
        direct = churn_report(
            y_true,
            per_seed_probs[seed],
            classes["churn_risk"],
            "at_risk",
        )
        direct_reports.append(direct)
        assert seed_entry["seed"] == seed
        assert seed_entry["average_precision"] == pytest.approx(
            direct["average_precision"]
        )
        assert seed_entry["at_threshold"] == direct["at_threshold"]
        assert seed_entry["at_default_threshold"] == direct["at_default_threshold"]
        assert result["validation_threshold_per_seed"][seed] == pytest.approx(
            direct["at_threshold"]["threshold"]
        )

    direct_summary = summarize_seeds(direct_reports)
    assert result["summary"]["average_precision"] == direct_summary["average_precision"]
    assert (
        result["summary"]["macro_f1_at_threshold"]
        == direct_summary["macro_f1_at_threshold"]
    )
    assert (
        result["summary"]["balanced_accuracy_at_threshold"]
        == direct_summary["balanced_accuracy_at_threshold"]
    )

    assert OPTIMISTIC_THRESHOLD_NOTE in text
    captured = capsys.readouterr()
    assert SECRET_MARKER not in text
    assert SECRET_MARKER not in captured.out
    assert SECRET_MARKER not in captured.err


def test_refuses_field_with_three_classes(tmp_path):
    data_dir, preds_dir, _, _, _, _ = _make_churn_fixture(tmp_path)
    with pytest.raises(ChurnRunReportError, match="exactly 2 classes"):
        churn_run_report(
            data_dir, preds_dir, positive_class="high", field="complaint_urgency"
        )


def test_refuses_missing_seed_file(tmp_path):
    data_dir, preds_dir, _, _, _, _ = _make_churn_fixture(tmp_path)
    (preds_dir / "predictions_val_seed2023.json").unlink()
    with pytest.raises(ChurnRunReportError, match="seed 2023: missing prediction file"):
        churn_run_report(data_dir, preds_dir, positive_class="at_risk")


def test_refuses_extra_seed_file(tmp_path):
    data_dir, preds_dir, _, _, _, _ = _make_churn_fixture(tmp_path)
    extra = preds_dir / "predictions_val_seed999.json"
    extra.write_text(
        (preds_dir / "predictions_val_seed42.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    with pytest.raises(ChurnRunReportError, match="extra unknown seed file"):
        churn_run_report(data_dir, preds_dir, positive_class="at_risk")


def test_refuses_header_with_another_seed(tmp_path):
    data_dir, preds_dir, _, _, _, _ = _make_churn_fixture(tmp_path)
    f42 = preds_dir / "predictions_val_seed42.json"
    payload = json.loads(f42.read_text(encoding="utf-8"))
    payload["seed"] = 1337
    f42.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ChurnRunReportError, match="seed 42: header seed is 1337"):
        churn_run_report(data_dir, preds_dir, positive_class="at_risk")


def test_refuses_no_at_risk_row_in_validation_labels(tmp_path):
    data_dir, preds_dir, _, _, _, _ = _make_churn_fixture(tmp_path, drop_at_risk=True)
    with pytest.raises(ChurnRunReportError, match="no 'at_risk' row"):
        churn_run_report(data_dir, preds_dir, positive_class="at_risk")


def test_refuses_test_split_file(tmp_path):
    data_dir, preds_dir, _, _, _, _ = _make_churn_fixture(tmp_path)
    f42 = preds_dir / "predictions_val_seed42.json"
    payload = json.loads(f42.read_text(encoding="utf-8"))
    payload["split"] = "test"
    f42.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ChurnRunReportError, match="seed 42:.*split 'test'"):
        churn_run_report(data_dir, preds_dir, positive_class="at_risk")
