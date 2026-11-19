import hashlib
import json

import pytest

from infra.evaluate_run import EVAL_VAL_HASH_KEY, EvaluateRunError, evaluate_run
from infra.experiment_config import ExperimentConfig, save_experiment_config
from infra.harness import evaluate_predictions, load_truth_table
from infra.metrics import seed_metrics
from infra.predictions_file import read_predictions_file, write_predictions_file
from infra.run_record import RunRecordError, load_run_record
from infra.shared_config import load_shared_config
from infra.tests.test_tfidf_baseline import SECRET_MARKER, _make_synthetic_dataset
from infra.tfidf_baseline import CUSTOMER_STATE_EXCLUSIONS, load_classes_by_field


def _probs_for_chosen(classes_by_field, chosen_by_field, confidence=0.76):
    out = {}
    for field, classes in classes_by_field.items():
        rest = (1.0 - confidence) / (len(classes) - 1)
        chosen = chosen_by_field[field]
        out[field] = {
            c: (confidence if c == chosen else rest) for c in classes
        }
    return out


def _write_synthetic_predictions_and_config(
    tmp_path,
    *,
    include_unclear=False,
    run_id="marbert-001",
    model="MARBERTv2",
    learning_rate=2e-5,
    batch_size=16,
    epochs=3,
):
    data_dir = _make_synthetic_dataset(
        tmp_path / "data", include_unclear=include_unclear
    )
    shared = load_shared_config(
        data_dir / "notebooks" / "training" / "shared_config.json"
    )
    classes = load_classes_by_field(data_dir / "final" / "class_weights.json")
    fields = list(classes.keys())
    truth = load_truth_table(
        data_dir / "final" / "clean_training_val.csv", "val", fields
    )

    cfg = ExperimentConfig(
        model=model,
        dataset_version=shared["dataset_version"],
        split="train",
        learning_rate=learning_rate,
        batch_size=batch_size,
        epochs=epochs,
    )
    cfg_path = tmp_path / "config.json"
    save_experiment_config(cfg, cfg_path)

    preds_dir = tmp_path / "preds"
    preds_dir.mkdir(parents=True, exist_ok=True)

    for idx, seed in enumerate(shared["experiment_seeds"]):
        rows = []
        for row_i, tr_row in enumerate(truth):
            chosen = {}
            for field, cls_list in classes.items():
                true_label = tr_row[field]
                if true_label not in cls_list:
                    chosen[field] = cls_list[0]
                elif (row_i + idx) % 4 == 0:
                    # Flip one row per seed so metrics vary slightly across seeds.
                    pos = cls_list.index(true_label)
                    chosen[field] = cls_list[(pos + 1) % len(cls_list)]
                else:
                    chosen[field] = true_label
            rows.append({
                "audio_file": tr_row["audio_file"],
                "probabilities": _probs_for_chosen(classes, chosen),
            })

        pred_path = preds_dir / f"predictions_val_seed{seed}.json"
        write_predictions_file(
            path=pred_path,
            run_id=run_id,
            model=model,
            split="val",
            seed=seed,
            dataset_version=shared["dataset_version"],
            rows=rows,
            classes_by_field=classes,
        )

    return data_dir, cfg_path, preds_dir, shared, classes, truth


def test_correct_synthetic_run_matches_direct_harness_metrics(tmp_path):
    data_dir, cfg_path, preds_dir, shared, classes, truth = (
        _write_synthetic_predictions_and_config(tmp_path)
    )
    runs_dir = tmp_path / "runs"

    result = evaluate_run(
        data_dir=data_dir,
        runs_dir=runs_dir,
        run_id="marbert-001",
        config_path=cfg_path,
        predictions_dir=preds_dir,
        hypothesis="Single-task MARBERTv2 baseline on synthetic validation fixtures.",
        device="cpu",
    )

    loaded_record = load_run_record(result["record_path"])
    assert loaded_record == result["record"]
    assert loaded_record["run_id"] == "marbert-001"
    assert loaded_record["evaluated_split"] == "val"
    assert [r["seed"] for r in loaded_record["per_seed"]] == shared["experiment_seeds"]

    for seed, seed_entry in zip(shared["experiment_seeds"], loaded_record["per_seed"]):
        pred_file = preds_dir / f"predictions_val_seed{seed}.json"
        loaded_pred = read_predictions_file(
            pred_file, classes, expected_split="val"
        )
        direct_report = evaluate_predictions(
            split="val",
            truth_rows=truth,
            pred_rows=loaded_pred["harness_rows"],
            classes_by_field=classes,
            exclusions_by_field=CUSTOMER_STATE_EXCLUSIONS,
        )
        assert seed_entry["metrics"] == seed_metrics(direct_report["fields"])


def test_customer_state_unclear_exception_excludes_only_customer_state(tmp_path):
    data_dir, cfg_path, preds_dir, _, _, truth = (
        _write_synthetic_predictions_and_config(tmp_path, include_unclear=True)
    )
    runs_dir = tmp_path / "runs"

    result = evaluate_run(
        data_dir=data_dir,
        runs_dir=runs_dir,
        run_id="marbert-001",
        config_path=cfg_path,
        predictions_dir=preds_dir,
        hypothesis="Check unclear customer_state row exclusion.",
        device="cpu",
    )

    n_total = len(truth)
    assert n_total == 5
    expected_exception = [{
        "field": "customer_state",
        "excluded_labels": ["unclear"],
        "rows_excluded": 1,
        "n_scored": n_total - 1,
        "n_total_rows": n_total,
        "reason": CUSTOMER_STATE_EXCLUSIONS["customer_state"]["reason"],
    }]
    assert result["record"]["exceptions"] == expected_exception

    for report in result["seed_reports"]:
        assert report["exceptions"] == expected_exception
        assert report["fields"]["customer_state"]["n"] == n_total - 1
        for other_field in ("complaint_category", "complaint_urgency", "churn_risk"):
            assert report["fields"][other_field]["n"] == n_total


def test_refuses_missing_seed_file(tmp_path):
    data_dir, cfg_path, preds_dir, _, _, _ = _write_synthetic_predictions_and_config(
        tmp_path
    )
    (preds_dir / "predictions_val_seed2023.json").unlink()

    with pytest.raises(EvaluateRunError, match="seed 2023: missing prediction file"):
        evaluate_run(
            data_dir=data_dir,
            runs_dir=tmp_path / "runs",
            run_id="marbert-001",
            config_path=cfg_path,
            predictions_dir=preds_dir,
            hypothesis="Missing seed file test.",
            device="cpu",
        )


def test_refuses_extra_unknown_seed_file(tmp_path):
    data_dir, cfg_path, preds_dir, _, _, _ = _write_synthetic_predictions_and_config(
        tmp_path
    )
    extra = preds_dir / "predictions_val_seed999.json"
    extra.write_text(
        (preds_dir / "predictions_val_seed42.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    with pytest.raises(EvaluateRunError, match="extra unknown seed file"):
        evaluate_run(
            data_dir=data_dir,
            runs_dir=tmp_path / "runs",
            run_id="marbert-001",
            config_path=cfg_path,
            predictions_dir=preds_dir,
            hypothesis="Extra seed file test.",
            device="cpu",
        )


def test_refuses_header_seed_differing_from_file_name(tmp_path):
    data_dir, cfg_path, preds_dir, _, _, _ = _write_synthetic_predictions_and_config(
        tmp_path
    )
    f42 = preds_dir / "predictions_val_seed42.json"
    f1337 = preds_dir / "predictions_val_seed1337.json"
    text42 = f42.read_text(encoding="utf-8")
    text1337 = f1337.read_text(encoding="utf-8")
    f42.write_text(text1337, encoding="utf-8")
    f1337.write_text(text42, encoding="utf-8")

    with pytest.raises(EvaluateRunError, match="seed 42: header seed is 1337"):
        evaluate_run(
            data_dir=data_dir,
            runs_dir=tmp_path / "runs",
            run_id="marbert-001",
            config_path=cfg_path,
            predictions_dir=preds_dir,
            hypothesis="Swapped seed files test.",
            device="cpu",
        )


def test_refuses_header_run_id_mismatch(tmp_path):
    data_dir, cfg_path, preds_dir, _, _, _ = _write_synthetic_predictions_and_config(
        tmp_path
    )
    f7 = preds_dir / "predictions_val_seed7.json"
    payload = json.loads(f7.read_text(encoding="utf-8"))
    payload["run_id"] = "other-run"
    f7.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluateRunError, match="seed 7: header run_id"):
        evaluate_run(
            data_dir=data_dir,
            runs_dir=tmp_path / "runs",
            run_id="marbert-001",
            config_path=cfg_path,
            predictions_dir=preds_dir,
            hypothesis="Header run_id mismatch test.",
            device="cpu",
        )


def test_refuses_header_model_differing_from_config(tmp_path):
    data_dir, cfg_path, preds_dir, _, _, _ = _write_synthetic_predictions_and_config(
        tmp_path
    )
    f99 = preds_dir / "predictions_val_seed99.json"
    payload = json.loads(f99.read_text(encoding="utf-8"))
    payload["model"] = "EgyBERT"
    f99.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluateRunError, match="seed 99: header model"):
        evaluate_run(
            data_dir=data_dir,
            runs_dir=tmp_path / "runs",
            run_id="marbert-001",
            config_path=cfg_path,
            predictions_dir=preds_dir,
            hypothesis="Header model mismatch test.",
            device="cpu",
        )


def test_refuses_header_dataset_version_mismatch(tmp_path):
    data_dir, cfg_path, preds_dir, _, _, _ = _write_synthetic_predictions_and_config(
        tmp_path
    )
    f42 = preds_dir / "predictions_val_seed42.json"
    payload = json.loads(f42.read_text(encoding="utf-8"))
    payload["dataset_version"] = "v1"
    f42.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluateRunError, match="seed 42: header dataset_version"):
        evaluate_run(
            data_dir=data_dir,
            runs_dir=tmp_path / "runs",
            run_id="marbert-001",
            config_path=cfg_path,
            predictions_dir=preds_dir,
            hypothesis="Header dataset_version mismatch test.",
            device="cpu",
        )


def test_refuses_prediction_file_of_test_split(tmp_path):
    data_dir, cfg_path, preds_dir, _, _, _ = _write_synthetic_predictions_and_config(
        tmp_path
    )
    f42 = preds_dir / "predictions_val_seed42.json"
    payload = json.loads(f42.read_text(encoding="utf-8"))
    payload["split"] = "test"
    f42.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluateRunError, match="seed 42:.*split 'test'"):
        evaluate_run(
            data_dir=data_dir,
            runs_dir=tmp_path / "runs",
            run_id="marbert-001",
            config_path=cfg_path,
            predictions_dir=preds_dir,
            hypothesis="File of test split test.",
            device="cpu",
        )


def test_refuses_evaluated_split_test(tmp_path):
    data_dir, cfg_path, preds_dir, _, _, _ = _write_synthetic_predictions_and_config(
        tmp_path
    )
    with pytest.raises(EvaluateRunError, match="test split"):
        evaluate_run(
            data_dir=data_dir,
            runs_dir=tmp_path / "runs",
            run_id="marbert-001",
            config_path=cfg_path,
            predictions_dir=preds_dir,
            hypothesis="Refuse evaluated_split=test.",
            device="cpu",
            evaluated_split="test",
        )


def test_refuses_existing_run_folder(tmp_path):
    data_dir, cfg_path, preds_dir, _, _, _ = _write_synthetic_predictions_and_config(
        tmp_path
    )
    runs_dir = tmp_path / "runs"
    (runs_dir / "exp_marbert-001").mkdir(parents=True)

    with pytest.raises(FileExistsError, match="already exists"):
        evaluate_run(
            data_dir=data_dir,
            runs_dir=runs_dir,
            run_id="marbert-001",
            config_path=cfg_path,
            predictions_dir=preds_dir,
            hypothesis="Refuse existing run folder.",
            device="cpu",
        )


def test_refuses_prediction_of_unclear_for_customer_state(tmp_path):
    data_dir, cfg_path, preds_dir, _, _, _ = _write_synthetic_predictions_and_config(
        tmp_path, include_unclear=True
    )
    f42 = preds_dir / "predictions_val_seed42.json"
    payload = json.loads(f42.read_text(encoding="utf-8"))
    payload["rows"][0]["labels"]["customer_state"] = "unclear"
    f42.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluateRunError, match="seed 42:.*not in the class list"):
        evaluate_run(
            data_dir=data_dir,
            runs_dir=tmp_path / "runs",
            run_id="marbert-001",
            config_path=cfg_path,
            predictions_dir=preds_dir,
            hypothesis="Refuse unclear prediction.",
            device="cpu",
        )


def test_reference_config_changing_two_factors_is_refused(tmp_path):
    data_dir, cfg_path, preds_dir, shared, _, _ = (
        _write_synthetic_predictions_and_config(tmp_path)
    )
    ref_cfg = ExperimentConfig(
        model="MARBERTv2",
        dataset_version=shared["dataset_version"],
        split="train",
        learning_rate=1e-5,
        batch_size=32,
        epochs=3,
    )
    ref_cfg_path = tmp_path / "ref_config.json"
    save_experiment_config(ref_cfg, ref_cfg_path)

    with pytest.raises(RunRecordError, match="more than one factor changed"):
        evaluate_run(
            data_dir=data_dir,
            runs_dir=tmp_path / "runs",
            run_id="marbert-001",
            config_path=cfg_path,
            predictions_dir=preds_dir,
            hypothesis="Two factors changed test.",
            device="cpu",
            reference_config_path=ref_cfg_path,
            changed_factor="learning_rate",
            reference_run_id="marbert-000",
        )


def test_no_validation_text_appears_in_stdout_stderr_or_written_files(
    tmp_path, capsys
):
    data_dir, cfg_path, preds_dir, _, _, _ = _write_synthetic_predictions_and_config(
        tmp_path, include_unclear=True
    )
    runs_dir = tmp_path / "runs"

    result = evaluate_run(
        data_dir=data_dir,
        runs_dir=runs_dir,
        run_id="marbert-001",
        config_path=cfg_path,
        predictions_dir=preds_dir,
        hypothesis="Verify no validation text is printed or written.",
        device="cpu",
    )
    captured = capsys.readouterr()
    assert "run_id: marbert-001" in captured.out
    assert SECRET_MARKER not in captured.out
    assert SECRET_MARKER not in captured.err
    assert "VAL_ONLY_TOKEN_XYZ" not in captured.out
    assert "VAL_ONLY_TOKEN_XYZ" not in captured.err

    written_files = list(runs_dir.rglob("*.json"))
    assert written_files == [result["record_path"]]
    for fpath in written_files:
        text = fpath.read_text(encoding="utf-8")
        assert SECRET_MARKER not in text
        assert "VAL_ONLY_TOKEN_XYZ" not in text


def test_val_hash_is_recorded_in_config_other_hyperparameters(tmp_path):
    data_dir, cfg_path, preds_dir, _, _, _ = _write_synthetic_predictions_and_config(
        tmp_path
    )
    runs_dir = tmp_path / "runs"
    result = evaluate_run(
        data_dir=data_dir,
        runs_dir=runs_dir,
        run_id="marbert-001",
        config_path=cfg_path,
        predictions_dir=preds_dir,
        hypothesis="Record validation file SHA-256 in config.other_hyperparameters.",
        device="cpu",
    )
    expected_val_sha = hashlib.sha256(
        (data_dir / "final" / "clean_training_val.csv").read_bytes()
    ).hexdigest()
    rec = load_run_record(result["record_path"])
    assert rec["config"]["other_hyperparameters"][EVAL_VAL_HASH_KEY] == expected_val_sha
    assert (
        rec["held_constant"][f"other_hyperparameters.{EVAL_VAL_HASH_KEY}"]
        == expected_val_sha
    )


def test_submitted_config_with_eval_data_sha256_val_is_refused(tmp_path):
    data_dir, _, preds_dir, shared, _, _ = _write_synthetic_predictions_and_config(
        tmp_path
    )
    bad_cfg = ExperimentConfig(
        model="MARBERTv2",
        dataset_version=shared["dataset_version"],
        split="train",
        learning_rate=2e-5,
        batch_size=16,
        epochs=3,
        other_hyperparameters={EVAL_VAL_HASH_KEY: "prepopulated_hash"},
    )
    bad_cfg_path = tmp_path / "bad_config.json"
    save_experiment_config(bad_cfg, bad_cfg_path)

    with pytest.raises(EvaluateRunError, match=EVAL_VAL_HASH_KEY):
        evaluate_run(
            data_dir=data_dir,
            runs_dir=tmp_path / "runs",
            run_id="marbert-001",
            config_path=bad_cfg_path,
            predictions_dir=preds_dir,
            hypothesis="Submitted config with eval_data_sha256_val must be refused.",
            device="cpu",
        )


def test_reference_record_with_different_val_hash_is_refused(tmp_path):
    data_dir, cfg_path, preds_dir, shared, _, _ = (
        _write_synthetic_predictions_and_config(
            tmp_path, run_id="marbert-002", learning_rate=3e-5
        )
    )
    runs_dir = tmp_path / "runs"

    ref_cfg = ExperimentConfig(
        model="MARBERTv2",
        dataset_version=shared["dataset_version"],
        split="train",
        learning_rate=2e-5,
        batch_size=16,
        epochs=3,
    )
    ref_cfg_path = tmp_path / "ref_config.json"
    save_experiment_config(ref_cfg, ref_cfg_path)

    # First create a valid reference run record on the same val file, then alter its stored hash.
    _, _, ref_preds_dir, _, _, _ = _write_synthetic_predictions_and_config(
        tmp_path / "ref_setup", run_id="marbert-001", learning_rate=2e-5
    )
    ref_res = evaluate_run(
        data_dir=data_dir,
        runs_dir=runs_dir,
        run_id="marbert-001",
        config_path=ref_cfg_path,
        predictions_dir=ref_preds_dir,
        hypothesis="Reference run.",
        device="cpu",
    )
    ref_record_data = json.loads(ref_res["record_path"].read_text(encoding="utf-8"))
    ref_record_data["config"]["other_hyperparameters"][EVAL_VAL_HASH_KEY] = (
        "0" * 64
    )
    ref_res["record_path"].write_text(
        json.dumps(ref_record_data, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(EvaluateRunError, match="differs from current validation file"):
        evaluate_run(
            data_dir=data_dir,
            runs_dir=runs_dir,
            run_id="marbert-002",
            config_path=cfg_path,
            predictions_dir=preds_dir,
            hypothesis="Compare against reference run with different val hash.",
            device="cpu",
            reference_config_path=ref_cfg_path,
            changed_factor="learning_rate",
            reference_run_id="marbert-001",
        )


def test_reference_record_with_same_val_hash_is_accepted(tmp_path):
    data_dir, cfg_path, preds_dir, shared, _, _ = (
        _write_synthetic_predictions_and_config(
            tmp_path, run_id="marbert-002", learning_rate=3e-5
        )
    )
    runs_dir = tmp_path / "runs"

    ref_cfg = ExperimentConfig(
        model="MARBERTv2",
        dataset_version=shared["dataset_version"],
        split="train",
        learning_rate=2e-5,
        batch_size=16,
        epochs=3,
    )
    ref_cfg_path = tmp_path / "ref_config.json"
    save_experiment_config(ref_cfg, ref_cfg_path)

    _, _, ref_preds_dir, _, _, _ = _write_synthetic_predictions_and_config(
        tmp_path / "ref_setup", run_id="marbert-001", learning_rate=2e-5
    )
    evaluate_run(
        data_dir=data_dir,
        runs_dir=runs_dir,
        run_id="marbert-001",
        config_path=ref_cfg_path,
        predictions_dir=ref_preds_dir,
        hypothesis="Reference run.",
        device="cpu",
    )

    result = evaluate_run(
        data_dir=data_dir,
        runs_dir=runs_dir,
        run_id="marbert-002",
        config_path=cfg_path,
        predictions_dir=preds_dir,
        hypothesis="Compare against reference run with same val hash.",
        device="cpu",
        reference_config_path=ref_cfg_path,
        changed_factor="learning_rate",
        reference_run_id="marbert-001",
    )
    rec = load_run_record(result["record_path"])
    assert rec["changed_factor"] == "learning_rate"
    assert rec["reference_run_id"] == "marbert-001"


def test_missing_reference_record_is_accepted(tmp_path):
    data_dir, cfg_path, preds_dir, shared, _, _ = (
        _write_synthetic_predictions_and_config(
            tmp_path, run_id="marbert-002", learning_rate=3e-5
        )
    )
    runs_dir = tmp_path / "runs"

    ref_cfg = ExperimentConfig(
        model="MARBERTv2",
        dataset_version=shared["dataset_version"],
        split="train",
        learning_rate=2e-5,
        batch_size=16,
        epochs=3,
    )
    ref_cfg_path = tmp_path / "ref_config.json"
    save_experiment_config(ref_cfg, ref_cfg_path)

    result = evaluate_run(
        data_dir=data_dir,
        runs_dir=runs_dir,
        run_id="marbert-002",
        config_path=cfg_path,
        predictions_dir=preds_dir,
        hypothesis="Compare against a reference config whose run record is not on disk.",
        device="cpu",
        reference_config_path=ref_cfg_path,
        changed_factor="learning_rate",
        reference_run_id="marbert-001",
    )
    rec = load_run_record(result["record_path"])
    assert rec["changed_factor"] == "learning_rate"
    assert rec["reference_run_id"] == "marbert-001"
