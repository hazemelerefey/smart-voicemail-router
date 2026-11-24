import csv
import hashlib
import json

import pytest

from infra.evaluate_run import (
    EVAL_TEST_HASH_KEY,
    EvaluateRunError,
    evaluate_run,
    evaluate_test_run,
)
from infra.experiment_config import ExperimentConfig, save_experiment_config
from infra.once_guard import AlreadyEvaluatedError, read_log
from infra.predictions_file import write_predictions_file
from infra.run_record import load_run_record
from infra.shared_config import load_shared_config
from infra.tests.test_evaluate_run import _probs_for_chosen
from infra.tests.test_tfidf_baseline import _make_synthetic_dataset
from infra.tfidf_baseline import load_classes_by_field

TEST_SECRET_MARKER = "DUMMY_SECRET_TEST_TRANSCRIPT_776655"


def _make_synthetic_test_setup(
    tmp_path,
    *,
    run_id="marbert-test-001",
    model="MARBERTv2",
    include_unclear=False,
    other_hyperparameters=None,
):
    data_dir = _make_synthetic_dataset(tmp_path / "data")
    shared_path = data_dir / "notebooks" / "training" / "shared_config.json"
    shared = load_shared_config(shared_path)
    classes = load_classes_by_field(data_dir / "final" / "class_weights.json")

    test_rows = [
        {
            "audio_file": "te_00.wav",
            "split": "test",
            "text_norm": f"{TEST_SECRET_MARKER} cat_app urg_high state_calm churn_yes",
            "complaint_category": "app_and_account",
            "complaint_urgency": "high",
            "customer_state": "calm",
            "churn_risk": "at_risk",
        },
        {
            "audio_file": "te_01.wav",
            "split": "test",
            "text_norm": f"{TEST_SECRET_MARKER} cat_bill urg_low state_frustrated churn_no",
            "complaint_category": "billing_and_charges",
            "complaint_urgency": "low",
            "customer_state": "frustrated",
            "churn_risk": "not_at_risk",
        },
        {
            "audio_file": "te_02.wav",
            "split": "test",
            "text_norm": f"{TEST_SECRET_MARKER} cat_net urg_med state_mad churn_no",
            "complaint_category": "network_and_connectivity",
            "complaint_urgency": "medium",
            "customer_state": "unclear" if include_unclear else "mad",
            "churn_risk": "not_at_risk",
        },
    ]
    assert len(test_rows) == shared["test_rows"]

    test_csv = data_dir / "final" / "clean_training_test.csv"
    with test_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(test_rows[0].keys()))
        writer.writeheader()
        writer.writerows(test_rows)

    cfg = ExperimentConfig(
        model=model,
        dataset_version=shared["dataset_version"],
        split="train",
        learning_rate=2e-5,
        batch_size=16,
        epochs=3,
        other_hyperparameters=other_hyperparameters or {},
    )
    cfg_path = tmp_path / "config.json"
    save_experiment_config(cfg, cfg_path)

    preds_dir = tmp_path / "preds"
    preds_dir.mkdir(parents=True, exist_ok=True)
    for idx, seed in enumerate(shared["experiment_seeds"]):
        rows = []
        for row_i, tr_row in enumerate(test_rows):
            chosen = {}
            for field, cls_list in classes.items():
                true_label = tr_row[field]
                if true_label not in cls_list:
                    chosen[field] = cls_list[0]
                elif (row_i + idx) % 3 == 0:
                    pos = cls_list.index(true_label)
                    chosen[field] = cls_list[(pos + 1) % len(cls_list)]
                else:
                    chosen[field] = true_label
            rows.append({
                "audio_file": tr_row["audio_file"],
                "probabilities": _probs_for_chosen(classes, chosen),
            })
        pred_path = preds_dir / f"predictions_test_seed{seed}.json"
        write_predictions_file(
            path=pred_path,
            run_id=run_id,
            model=model,
            split="test",
            seed=seed,
            dataset_version=shared["dataset_version"],
            rows=rows,
            classes_by_field=classes,
        )

    return data_dir, cfg_path, preds_dir, shared, test_csv


def test_evaluate_test_run_succeeds_once_and_refuses_second_call_even_with_alias(
    tmp_path, capsys
):
    data_dir, cfg_path, preds_dir, _, test_csv = _make_synthetic_test_setup(
        tmp_path, run_id="marbert-test-001", model="MARBERTv2", include_unclear=True
    )
    runs_dir = tmp_path / "runs"
    ckpt_sha_1 = "a" * 64

    res = evaluate_test_run(
        data_dir=data_dir,
        runs_dir=runs_dir,
        run_id="marbert-test-001",
        config_path=cfg_path,
        predictions_dir=preds_dir,
        hypothesis="Final frozen test evaluation for MARBERTv2.",
        device="cpu",
        checkpoint_sha256=ckpt_sha_1,
    )

    captured = capsys.readouterr()
    assert TEST_SECRET_MARKER not in captured.out
    assert TEST_SECRET_MARKER not in captured.err

    rec = load_run_record(res["record_path"])
    assert rec["evaluated_split"] == "test"
    expected_test_sha = hashlib.sha256(test_csv.read_bytes()).hexdigest()
    assert rec["config"]["other_hyperparameters"][EVAL_TEST_HASH_KEY] == expected_test_sha
    assert rec["exceptions"][0]["rows_excluded"] == 1
    assert rec["exceptions"][0]["n_scored"] == 2
    assert rec["exceptions"][0]["n_total_rows"] == 3

    log_path = runs_dir / "test_evaluations.json"
    log = read_log(log_path)
    assert len(log["entries"]) == 1
    assert log["entries"][0]["uses"] == 5
    assert log["entries"][0]["test_file_sha256"] == expected_test_sha
    assert log["entries"][0]["checkpoint_sha256"] == ckpt_sha_1

    # No dummy text marker in any written file.
    for fpath in runs_dir.rglob("*.json"):
        assert TEST_SECRET_MARKER not in fpath.read_text(encoding="utf-8")

    # Second call for the same model and dataset_version (different run_id,
    # different checkpoint hash, and "UBC-NLP/MARBERTv2" spelling) is refused.
    _, cfg2_path, preds2_dir, _, _ = _make_synthetic_test_setup(
        tmp_path / "second",
        run_id="marbert-test-002",
        model="UBC-NLP/MARBERTv2",
    )
    with pytest.raises(AlreadyEvaluatedError):
        evaluate_test_run(
            data_dir=data_dir,
            runs_dir=runs_dir,
            run_id="marbert-test-002",
            config_path=cfg2_path,
            predictions_dir=preds2_dir,
            hypothesis="Second attempt with different checkpoint and model spelling.",
            device="cpu",
            checkpoint_sha256="b" * 64,
        )

    # No new record and no new log entry were written.
    assert not (runs_dir / "exp_marbert-test-002").exists()
    assert len(read_log(log_path)["entries"]) == 1


def test_missing_seed_file_is_refused_without_creating_log_entry(tmp_path):
    data_dir, cfg_path, preds_dir, _, _ = _make_synthetic_test_setup(tmp_path)
    (preds_dir / "predictions_test_seed7.json").unlink()
    runs_dir = tmp_path / "runs"

    with pytest.raises(EvaluateRunError, match="seed 7: missing prediction file"):
        evaluate_test_run(
            data_dir=data_dir,
            runs_dir=runs_dir,
            run_id="marbert-test-001",
            config_path=cfg_path,
            predictions_dir=preds_dir,
            hypothesis="Missing seed file must not claim the guard.",
            device="cpu",
        )

    assert not (runs_dir / "test_evaluations.json").exists()
    assert read_log(runs_dir / "test_evaluations.json")["entries"] == []


def test_wrong_header_seed_or_run_id_is_refused_without_creating_log_entry(tmp_path):
    # Case 1: wrong seed in header
    d1, c1, p1, _, _ = _make_synthetic_test_setup(tmp_path / "bad_seed")
    f42 = p1 / "predictions_test_seed42.json"
    payload = json.loads(f42.read_text(encoding="utf-8"))
    payload["seed"] = 1337
    f42.write_text(json.dumps(payload), encoding="utf-8")
    runs1 = tmp_path / "runs1"

    with pytest.raises(EvaluateRunError, match="seed 42: header seed"):
        evaluate_test_run(
            data_dir=d1,
            runs_dir=runs1,
            run_id="marbert-test-001",
            config_path=c1,
            predictions_dir=p1,
            hypothesis="Wrong header seed must not claim the guard.",
            device="cpu",
        )
    assert not (runs1 / "test_evaluations.json").exists()

    # Case 2: wrong run_id in header
    d2, c2, p2, _, _ = _make_synthetic_test_setup(tmp_path / "bad_run_id")
    f99 = p2 / "predictions_test_seed99.json"
    payload2 = json.loads(f99.read_text(encoding="utf-8"))
    payload2["run_id"] = "other-run"
    f99.write_text(json.dumps(payload2), encoding="utf-8")
    runs2 = tmp_path / "runs2"

    with pytest.raises(EvaluateRunError, match="seed 99: header run_id"):
        evaluate_test_run(
            data_dir=d2,
            runs_dir=runs2,
            run_id="marbert-test-001",
            config_path=c2,
            predictions_dir=p2,
            hypothesis="Wrong header run_id must not claim the guard.",
            device="cpu",
        )
    assert not (runs2 / "test_evaluations.json").exists()


def test_existing_run_folder_is_refused_without_creating_log_entry(tmp_path):
    data_dir, cfg_path, preds_dir, _, _ = _make_synthetic_test_setup(tmp_path)
    runs_dir = tmp_path / "runs"
    (runs_dir / "exp_marbert-test-001").mkdir(parents=True)

    with pytest.raises(FileExistsError, match="already exists"):
        evaluate_test_run(
            data_dir=data_dir,
            runs_dir=runs_dir,
            run_id="marbert-test-001",
            config_path=cfg_path,
            predictions_dir=preds_dir,
            hypothesis="Existing folder must not claim the guard.",
            device="cpu",
        )
    assert not (runs_dir / "test_evaluations.json").exists()


def test_config_with_eval_data_sha256_test_already_present_is_refused(tmp_path):
    data_dir, cfg_path, preds_dir, _, _ = _make_synthetic_test_setup(
        tmp_path,
        other_hyperparameters={EVAL_TEST_HASH_KEY: "0" * 64},
    )
    runs_dir = tmp_path / "runs"

    with pytest.raises(EvaluateRunError, match=EVAL_TEST_HASH_KEY):
        evaluate_test_run(
            data_dir=data_dir,
            runs_dir=runs_dir,
            run_id="marbert-test-001",
            config_path=cfg_path,
            predictions_dir=preds_dir,
            hypothesis="Prepopulated eval_data_sha256_test must be refused.",
            device="cpu",
        )
    assert not (runs_dir / "test_evaluations.json").exists()


def test_evaluate_run_still_refuses_test_split(tmp_path):
    data_dir, cfg_path, preds_dir, _, _ = _make_synthetic_test_setup(tmp_path)
    with pytest.raises(EvaluateRunError, match="test split"):
        evaluate_run(
            data_dir=data_dir,
            runs_dir=tmp_path / "runs",
            run_id="marbert-test-001",
            config_path=cfg_path,
            predictions_dir=preds_dir,
            hypothesis="evaluate_run must still refuse test split.",
            device="cpu",
            evaluated_split="test",
        )


def test_evaluate_test_run_with_preclaimed_claim_skips_reclaim_and_validates_claim_and_folder(
    tmp_path,
):
    from infra.once_guard import claim_test_evaluation

    # 1. Valid pre-claim with existing exp_<run_id> holding the 5 test prediction files
    d1, c1, p1, shared1, test_csv1 = _make_synthetic_test_setup(
        tmp_path / "ok", run_id="marbert-test-001", model="MARBERTv2"
    )
    runs1 = tmp_path / "runs_ok"
    exp1 = runs1 / "exp_marbert-test-001"
    exp1.mkdir(parents=True)
    for f in p1.glob("predictions_test_seed*.json"):
        (exp1 / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")

    claim1 = claim_test_evaluation(
        runs1 / "test_evaluations.json",
        model="UBC-NLP/MARBERTv2",
        dataset_version=shared1["dataset_version"],
        run_id="marbert-test-001",
        uses=5,
        test_csv_path=test_csv1,
    )
    res1 = evaluate_test_run(
        data_dir=d1,
        runs_dir=runs1,
        run_id="marbert-test-001",
        config_path=c1,
        predictions_dir=exp1,
        hypothesis="Pre-claimed evaluation must not claim again.",
        device="cpu",
        claim=claim1,
    )
    assert claim1.consumed is True
    assert len(read_log(runs1 / "test_evaluations.json")["entries"]) == 1
    assert (exp1 / "run_record.json").is_file()
    assert res1["summary"]["evaluated_split"] == "test"

    # 2. Claim for another run_id -> refused
    d2, c2, p2, shared2, test_csv2 = _make_synthetic_test_setup(
        tmp_path / "wrong_id", run_id="marbert-test-001", model="MARBERTv2"
    )
    runs2 = tmp_path / "runs_wrong_id"
    claim_wrong_id = claim_test_evaluation(
        runs2 / "test_evaluations.json",
        model="MARBERTv2",
        dataset_version=shared2["dataset_version"],
        run_id="different-run-id",
        uses=5,
        test_csv_path=test_csv2,
    )
    with pytest.raises(EvaluateRunError, match="claim run_id"):
        evaluate_test_run(
            data_dir=d2,
            runs_dir=runs2,
            run_id="marbert-test-001",
            config_path=c2,
            predictions_dir=p2,
            hypothesis="Wrong run_id claim.",
            device="cpu",
            claim=claim_wrong_id,
        )

    # 3. Used claim -> refused
    d3, c3, p3, shared3, test_csv3 = _make_synthetic_test_setup(
        tmp_path / "used", run_id="marbert-test-001", model="MARBERTv2"
    )
    runs3 = tmp_path / "runs_used"
    claim_used = claim_test_evaluation(
        runs3 / "test_evaluations.json",
        model="MARBERTv2",
        dataset_version=shared3["dataset_version"],
        run_id="marbert-test-001",
        uses=5,
        test_csv_path=test_csv3,
    )
    claim_used.consume()
    with pytest.raises(EvaluateRunError, match="unused"):
        evaluate_test_run(
            data_dir=d3,
            runs_dir=runs3,
            run_id="marbert-test-001",
            config_path=c3,
            predictions_dir=p3,
            hypothesis="Used claim.",
            device="cpu",
            claim=claim_used,
        )

    # 4. Existing run folder holding extra files -> refused
    d4, c4, p4, shared4, test_csv4 = _make_synthetic_test_setup(
        tmp_path / "extra", run_id="marbert-test-001", model="MARBERTv2"
    )
    runs4 = tmp_path / "runs_extra"
    exp4 = runs4 / "exp_marbert-test-001"
    exp4.mkdir(parents=True)
    for f in p4.glob("predictions_test_seed*.json"):
        (exp4 / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    (exp4 / "extra.txt").write_text("unexpected", encoding="utf-8")
    claim4 = claim_test_evaluation(
        runs4 / "test_evaluations.json",
        model="MARBERTv2",
        dataset_version=shared4["dataset_version"],
        run_id="marbert-test-001",
        uses=5,
        test_csv_path=test_csv4,
    )
    with pytest.raises(EvaluateRunError, match="must contain exactly"):
        evaluate_test_run(
            data_dir=d4,
            runs_dir=runs4,
            run_id="marbert-test-001",
            config_path=c4,
            predictions_dir=exp4,
            hypothesis="Extra file in run folder.",
            device="cpu",
            claim=claim4,
        )

    # 5. run_record.json already present -> refused
    d5, c5, p5, shared5, test_csv5 = _make_synthetic_test_setup(
        tmp_path / "rec_exists", run_id="marbert-test-001", model="MARBERTv2"
    )
    runs5 = tmp_path / "runs_rec_exists"
    exp5 = runs5 / "exp_marbert-test-001"
    exp5.mkdir(parents=True)
    for f in p5.glob("predictions_test_seed*.json"):
        (exp5 / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    (exp5 / "run_record.json").write_text("{}", encoding="utf-8")
    claim5 = claim_test_evaluation(
        runs5 / "test_evaluations.json",
        model="MARBERTv2",
        dataset_version=shared5["dataset_version"],
        run_id="marbert-test-001",
        uses=5,
        test_csv_path=test_csv5,
    )
    with pytest.raises(FileExistsError, match="already exists"):
        evaluate_test_run(
            data_dir=d5,
            runs_dir=runs5,
            run_id="marbert-test-001",
            config_path=c5,
            predictions_dir=exp5,
            hypothesis="Existing run_record.json.",
            device="cpu",
            claim=claim5,
        )
