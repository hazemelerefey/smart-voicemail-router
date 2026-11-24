import json

import pytest

from infra.compare_runs import (
     FIELDS,
    CompareError,
    check_comparable,
    compare,
    format_table,
    load_runs,
    pick_by_rule,
    summarize_run,
)
from infra.experiment_config import ExperimentConfig
from infra.run_record import build_run_record, make_seed_result, save_run_record

SHARED = {
    "split_seed": 42,
    "experiment_seeds": [42, 1337, 2023, 7, 99],
    "max_seq_len": 128,
    "split_ratio": "70/20/10",
    "dataset_version": "v2",
    "dataset": "svr-voicemail-corpus",
    "train_rows": 3575,
    "val_rows": 1003,
    "test_rows": 518,
}

NEUTRAL_REASON = (
    "customer_state is scored on 4 classes: the unclear rows "
    "(no rows in train) are left out of customer_state only and still count in "
    "the other fields."
)

SYNTHETIC_VAL_HASH = "a" * 64


def _make_config(
    model="MARBERTv2",
    dataset_version="v2",
    learning_rate=2e-5,
    batch_size=16,
    epochs=3,
    other_hyperparameters=None,
):
    if other_hyperparameters is None:
        other_hyperparameters = {"eval_data_sha256_val": SYNTHETIC_VAL_HASH}
    return ExperimentConfig(
        model=model,
        dataset_version=dataset_version,
        split="train",
        learning_rate=learning_rate,
        batch_size=batch_size,
        epochs=epochs,
        other_hyperparameters=other_hyperparameters,
    )


def _make_exception(
    field="customer_state",
    excluded_labels=None,
    rows_excluded=1,
    n_scored=1002,
    n_total_rows=1003,
    reason=NEUTRAL_REASON,
):
    return {
        "field": field,
        "excluded_labels": excluded_labels or ["unclear"],
        "rows_excluded": rows_excluded,
        "n_scored": n_scored,
        "n_total_rows": n_total_rows,
        "reason": reason,
    }


def _make_seed_metrics(cat, urg, state, churn, acc_offset=0.02):
    return {
        "complaint_category_macro_f1": cat,
        "complaint_urgency_macro_f1": urg,
        "customer_state_macro_f1": state,
        "churn_risk_macro_f1": churn,
        "complaint_category_accuracy": min(1.0, cat + acc_offset),
        "complaint_urgency_accuracy": min(1.0, urg + acc_offset),
        "customer_state_accuracy": min(1.0, state + acc_offset),
        "churn_risk_accuracy": min(1.0, churn + acc_offset),
    }


def _build_and_save_synthetic_record(
    runs_dir,
    run_id="run-001",
    model="MARBERTv2",
    per_seed_tuples=None,
    shared_config=None,
    evaluated_split="val",
    exceptions=None,
    other_hyperparameters=None,
    reference_config=None,
    changed_factor=None,
    reference_run_id=None,
):
    shared = dict(shared_config or SHARED)
    config = _make_config(
        model=model,
        dataset_version=shared["dataset_version"],
        other_hyperparameters=other_hyperparameters,
    )
    if per_seed_tuples is None:
        # 5 seeds with simple hand-checkable numbers:
        # For each seed s_i, the 4 fields are (b + 0.00, b + 0.10, b + 0.20, b + 0.30)
        # so the per-seed combined mean is b + 0.15.
        bases = [0.45, 0.50, 0.55, 0.60, 0.65]
        per_seed_tuples = [
            (b, b + 0.10, b + 0.20, b + 0.30) for b in bases
        ]

    per_seed = [
        make_seed_result(
            run_id,
            config,
            evaluated_split,
            seed,
            _make_seed_metrics(*vals),
        )
        for seed, vals in zip(shared["experiment_seeds"], per_seed_tuples)
    ]

    if exceptions is None:
        total = shared[f"{evaluated_split}_rows"]
        exceptions = [
            _make_exception(
                rows_excluded=1, n_scored=total - 1, n_total_rows=total
            )
        ]

    record = build_run_record(
        run_id=run_id,
        hypothesis=f"Synthetic experiment record for {run_id}.",
        config=config,
        shared_config=shared,
        per_seed=per_seed,
        evaluated_split=evaluated_split,
        artifacts={
            "predictions": [
                f"runs/exp_{run_id}/predictions_{evaluated_split}_seed{s}.json"
                for s in shared["experiment_seeds"]
            ]
        },
        device="cpu",
        exceptions=exceptions,
        reference_config=reference_config,
        changed_factor=changed_factor,
        reference_run_id=reference_run_id,
        created_utc="2026-11-19T00:00:00+00:00",
    )
    save_run_record(record, runs_dir)
    return record


def test_table_values_match_hand_calculation_with_ddof1(tmp_path):
    runs_dir = tmp_path / "runs"
    # Run A: bases [0.45, 0.50, 0.55, 0.60, 0.65]
    # Per-field means across 5 seeds:
    #   complaint_category: 0.55, complaint_urgency: 0.65,
    #   customer_state: 0.75, churn_risk: 0.85
    # Per-seed combined means: [0.60, 0.65, 0.70, 0.75, 0.80]
    # Combined mean = 0.70
    # Sample variance (ddof=1) of [0.60, 0.65, 0.70, 0.75, 0.80]:
    #   ((0.10^2 + 0.05^2 + 0 + 0.05^2 + 0.10^2) / 4) = 0.025 / 4 = 0.00625
    #   Sample std (ddof=1) = sqrt(0.00625) = 0.07905694150420949
    rec_a = _build_and_save_synthetic_record(
        runs_dir, run_id="run-a", model="MARBERTv2"
    )
    # Run B: constant across all 5 seeds: (0.50, 0.60, 0.70, 0.80) -> combined mean 0.65, std 0.0
    rec_b = _build_and_save_synthetic_record(
        runs_dir,
        run_id="run-b",
        model="EgyBERT",
        per_seed_tuples=[(0.50, 0.60, 0.70, 0.80)] * 5,
    )

    summary_a = summarize_run(rec_a)
    assert summary_a["macro_f1"]["complaint_category"]["mean"] == pytest.approx(0.55)
    assert summary_a["macro_f1"]["complaint_urgency"]["mean"] == pytest.approx(0.65)
    assert summary_a["macro_f1"]["customer_state"]["mean"] == pytest.approx(0.75)
    assert summary_a["macro_f1"]["churn_risk"]["mean"] == pytest.approx(0.85)
    assert summary_a["combined_macro_f1"]["per_seed"] == pytest.approx(
        [0.60, 0.65, 0.70, 0.75, 0.80]
    )
    assert summary_a["combined_macro_f1"]["mean"] == pytest.approx(0.70)
    assert summary_a["combined_macro_f1"]["std"] == pytest.approx(0.00625 ** 0.5)
    assert summary_a["combined_macro_f1"]["ddof"] == 1
    assert summary_a["combined_macro_f1"]["n"] == 5

    res = compare(runs_dir, ["run-b", "run-a"])
    table = format_table(res)
    assert "0.550000+-0.079057" in table
    assert "0.650000+-0.079057" in table
    assert "0.750000+-0.079057" in table
    assert "0.850000+-0.079057" in table
    assert "0.700000+-0.079057" in table
    assert "0.650000+-0.000000" in table
    assert summary_b_check(rec_b)


def summary_b_check(rec_b):
    sb = summarize_run(rec_b)
    return (
        sb["combined_macro_f1"]["mean"] == pytest.approx(0.65)
        and sb["combined_macro_f1"]["std"] == pytest.approx(0.0)
    )


def test_rows_are_sorted_by_combined_mean_and_keep_four_field_values(tmp_path):
    runs_dir = tmp_path / "runs"
    _build_and_save_synthetic_record(
        runs_dir,
        run_id="low-run",
        model="tfidf-logreg",
        per_seed_tuples=[(0.50, 0.50, 0.50, 0.50)] * 5,
    )
    _build_and_save_synthetic_record(
        runs_dir,
        run_id="high-run",
        model="MARBERTv2",
        per_seed_tuples=[(0.80, 0.82, 0.84, 0.86)] * 5,
    )
    _build_and_save_synthetic_record(
        runs_dir,
        run_id="mid-run",
        model="EgyBERT",
        per_seed_tuples=[(0.70, 0.70, 0.70, 0.70)] * 5,
    )

    result = compare(runs_dir, ["low-run", "high-run", "mid-run"])
    assert [r["run_id"] for r in result["rows"]] == [
        "high-run",
        "mid-run",
        "low-run",
    ]
    for row in result["rows"]:
        assert set(row["combined_macro_f1"]["values"].keys()) == set(FIELDS)
        for field in FIELDS:
            assert (
                row["combined_macro_f1"]["values"][field]
                == row["macro_f1"][field]["mean"]
            )


def test_refuses_different_evaluated_split(tmp_path):
    runs_dir = tmp_path / "runs"
    rec_val = _build_and_save_synthetic_record(
        runs_dir, run_id="run-val", evaluated_split="val"
    )
    rec_test = _build_and_save_synthetic_record(
        runs_dir, run_id="run-test", evaluated_split="test"
    )
    with pytest.raises(CompareError, match="evaluated_split"):
        check_comparable([rec_val, rec_test])


def test_refuses_different_dataset_version(tmp_path):
    runs_dir = tmp_path / "runs"
    rec_v2 = _build_and_save_synthetic_record(runs_dir, run_id="run-v2")
    shared_v3 = {**SHARED, "dataset_version": "v3"}
    rec_v3 = _build_and_save_synthetic_record(
        runs_dir, run_id="run-v3", shared_config=shared_v3
    )
    with pytest.raises(CompareError, match="dataset.version"):
        check_comparable([rec_v2, rec_v3])


def test_refuses_different_dataset_rows(tmp_path):
    runs_dir = tmp_path / "runs"
    rec_a = _build_and_save_synthetic_record(runs_dir, run_id="run-a")
    shared_other_rows = {**SHARED, "train_rows": 4000}
    rec_b = _build_and_save_synthetic_record(
        runs_dir, run_id="run-b", shared_config=shared_other_rows
    )
    with pytest.raises(CompareError, match="dataset.rows"):
        check_comparable([rec_a, rec_b])


def test_refuses_different_seeds(tmp_path):
    runs_dir = tmp_path / "runs"
    rec_a = _build_and_save_synthetic_record(runs_dir, run_id="run-a")
    shared_other_seeds = {**SHARED, "experiment_seeds": [42, 1337, 2023, 7, 100]}
    rec_b = _build_and_save_synthetic_record(
        runs_dir, run_id="run-b", shared_config=shared_other_seeds
    )
    with pytest.raises(CompareError, match="seed list"):
        check_comparable([rec_a, rec_b])


def test_refuses_different_exceptions(tmp_path):
    runs_dir = tmp_path / "runs"
    rec_a = _build_and_save_synthetic_record(runs_dir, run_id="run-a")
    rec_b = _build_and_save_synthetic_record(
        runs_dir,
        run_id="run-b",
        exceptions=[
            _make_exception(rows_excluded=2, n_scored=1001, n_total_rows=1003)
        ],
    )
    with pytest.raises(CompareError, match="exceptions differ"):
        check_comparable([rec_a, rec_b])


def test_refuses_different_validation_hash(tmp_path):
    runs_dir = tmp_path / "runs"
    rec_a = _build_and_save_synthetic_record(
        runs_dir,
        run_id="run-a",
        other_hyperparameters={"eval_data_sha256_val": "1" * 64},
    )
    rec_b = _build_and_save_synthetic_record(
        runs_dir,
        run_id="run-b",
        other_hyperparameters={"eval_data_sha256_val": "2" * 64},
    )
    with pytest.raises(CompareError, match="hash mismatch"):
        check_comparable([rec_a, rec_b])


def test_refuses_test_split_run_records(tmp_path):
    runs_dir = tmp_path / "runs"
    rec_1 = _build_and_save_synthetic_record(
        runs_dir, run_id="test-1", evaluated_split="test"
    )
    rec_2 = _build_and_save_synthetic_record(
        runs_dir, run_id="test-2", evaluated_split="test"
    )
    with pytest.raises(CompareError, match="validation results only"):
        check_comparable([rec_1, rec_2])


def test_refuses_one_run_only(tmp_path):
    runs_dir = tmp_path / "runs"
    rec_1 = _build_and_save_synthetic_record(runs_dir, run_id="only-1")
    with pytest.raises(CompareError, match="at least two runs"):
        check_comparable([rec_1])
    with pytest.raises(CompareError, match="at least two runs"):
        compare(runs_dir, ["only-1"])


def test_refuses_duplicate_run_id(tmp_path):
    runs_dir = tmp_path / "runs"
    rec_1 = _build_and_save_synthetic_record(runs_dir, run_id="dup-1")
    with pytest.raises(CompareError, match="duplicate run_id"):
        check_comparable([rec_1, rec_1])
    with pytest.raises(CompareError, match="duplicate run_id"):
        compare(runs_dir, ["dup-1", "dup-1"])


def test_refuses_missing_run(tmp_path):
    runs_dir = tmp_path / "runs"
    _build_and_save_synthetic_record(runs_dir, run_id="existing-1")
    with pytest.raises(CompareError, match="missing-999"):
        load_runs(runs_dir, ["existing-1", "missing-999"])


def test_missing_hash_warns_and_both_hash_keys_are_understood(tmp_path):
    runs_dir = tmp_path / "runs"
    _build_and_save_synthetic_record(
        runs_dir,
        run_id="run-no-hash",
        other_hyperparameters={},
    )
    _build_and_save_synthetic_record(
        runs_dir,
        run_id="run-baseline-key",
        other_hyperparameters={"data_sha256_val": SYNTHETIC_VAL_HASH},
    )
    _build_and_save_synthetic_record(
        runs_dir,
        run_id="run-eval-key",
        other_hyperparameters={"eval_data_sha256_val": SYNTHETIC_VAL_HASH},
    )

    res = compare(
        runs_dir, ["run-no-hash", "run-baseline-key", "run-eval-key"]
    )
    assert len(res["warnings"]) == 1
    assert "run-no-hash" in res["warnings"][0]
    assert (
        "no validation-file hash recorded: the data version cannot be checked"
        in res["warnings"][0]
    )


def test_pick_by_rule_clear_difference_picks_higher_mean(tmp_path):
    runs_dir = tmp_path / "runs"
    rec_a = _build_and_save_synthetic_record(
        runs_dir,
        run_id="egy-001",
        model="EgyBERT",
        per_seed_tuples=[
            (0.80, 0.80, 0.80, 0.80),
            (0.81, 0.81, 0.81, 0.81),
            (0.82, 0.82, 0.82, 0.82),
            (0.83, 0.83, 0.83, 0.83),
            (0.84, 0.84, 0.84, 0.84),
        ],
    )
    rec_b = _build_and_save_synthetic_record(
        runs_dir,
        run_id="mar-001",
        model="MARBERTv2",
        per_seed_tuples=[(0.75, 0.75, 0.75, 0.75)] * 5,
    )
    decision = pick_by_rule(
        summarize_run(rec_a),
        summarize_run(rec_b),
        tie_rule="larger_std",
        tie_preference="MARBERTv2",
    )
    assert decision["winner"] == "EgyBERT"
    assert decision["reason"] == "higher_mean"
    assert decision["rule"] == "larger_std"
    assert decision["difference"] > decision["tie_threshold"]


def test_pick_by_rule_difference_equal_to_larger_std_is_tie_and_picks_preferred():
    # Construct two summarized rows directly with exact combined mean and std:
    # std_a = 0.02, std_b = 0.01 -> larger_std = 0.02
    # mean_a = 0.82, mean_b = 0.80 -> difference = 0.02 == larger_std -> tie -> MARBERTv2
    row_a = {
        "run_id": "egy-001",
        "model": "EgyBERT",
        "combined_macro_f1": {"mean": 0.82, "std": 0.02},
    }
    row_b = {
        "run_id": "mar-001",
        "model": "MARBERTv2",
        "combined_macro_f1": {"mean": 0.80, "std": 0.01},
    }
    decision = pick_by_rule(
        row_a,
        row_b,
        tie_rule="larger_std",
        tie_preference="MARBERTv2",
    )
    assert decision["winner"] == "MARBERTv2"
    assert decision["reason"] == "tie_preference"
    assert decision["difference"] == pytest.approx(0.02)
    assert decision["tie_threshold"] == pytest.approx(0.02)


def test_pick_by_rule_difference_just_above_larger_std_is_not_tie():
    row_a = {
        "run_id": "egy-001",
        "model": "EgyBERT",
        "combined_macro_f1": {"mean": 0.820001, "std": 0.02},
    }
    row_b = {
        "run_id": "mar-001",
        "model": "MARBERTv2",
        "combined_macro_f1": {"mean": 0.80, "std": 0.01},
    }
    decision = pick_by_rule(
        row_a,
        row_b,
        tie_rule="larger_std",
        tie_preference="MARBERTv2",
    )
    assert decision["winner"] == "EgyBERT"
    assert decision["reason"] == "higher_mean"


def test_pick_by_rule_errors_on_bad_preference_same_model_or_bad_tie_rule():
    row_a = {
        "run_id": "egy-001",
        "model": "EgyBERT",
        "combined_macro_f1": {"mean": 0.81, "std": 0.02},
    }
    row_b = {
        "run_id": "mar-001",
        "model": "MARBERTv2",
        "combined_macro_f1": {"mean": 0.80, "std": 0.01},
    }

    with pytest.raises(CompareError, match="tie_preference"):
        pick_by_rule(
            row_a, row_b, tie_rule="larger_std", tie_preference="NotAModel"
        )

    with pytest.raises(CompareError, match="different models"):
        pick_by_rule(
            row_a,
            {**row_b, "model": "EgyBERT"},
            tie_rule="larger_std",
            tie_preference="EgyBERT",
        )

    with pytest.raises(TypeError):
        pick_by_rule(row_a, row_b, tie_preference="MARBERTv2")

    with pytest.raises(CompareError, match="unsupported tie_rule"):
        pick_by_rule(
            row_a, row_b, tie_rule="unknown_rule", tie_preference="MARBERTv2"
        )
