"""Synthetic tests for infra/final_test_evaluation.py (no real test data or PyTorch)."""
import csv
import hashlib
import json
from pathlib import Path

import pytest

from infra.evaluate_run import EVAL_TEST_HASH_KEY
from infra.experiment_config import ExperimentConfig, save_experiment_config
from infra.final_test_evaluation import (
    FinalTestEvaluationError,
    checkpoint_fingerprint,
    discover_checkpoints,
    rehearse_on_validation,
    run_final_test_evaluation,
)
from infra.once_guard import AlreadyEvaluatedError, read_log
from infra.predictions_file import write_predictions_file
from infra.run_record import load_run_record
from infra.shared_config import load_shared_config
from infra.tests.test_tfidf_baseline import _make_synthetic_dataset
from infra.tfidf_baseline import load_classes_by_field

TEST_TEXT_MARKER = "SYNTHETIC_FINAL_TEST_SECRET_MARKER_88421"
VAL_TEXT_MARKER = "SYNTHETIC_FINAL_VAL_SECRET_MARKER_99104"


def _make_full_synthetic_setup(
    tmp_path,
    *,
    run_id="marbert-final-001",
    model="MARBERTv2",
    include_unclear_test=True,
    use_epoch_subdir=True,
    weights_salt=b"v1",
):
    data_dir = _make_synthetic_dataset(tmp_path / "data", include_unclear=True)
    shared = load_shared_config(
        data_dir / "notebooks" / "training" / "shared_config.json"
    )
    classes = load_classes_by_field(data_dir / "final" / "class_weights.json")
    seeds = list(shared["experiment_seeds"])
    fields = list(classes.keys())

    # Replace val CSV text_norm with VAL_TEXT_MARKER so we can verify no leakage.
    val_csv = data_dir / "final" / "clean_training_val.csv"
    with val_csv.open(encoding="utf-8", newline="") as f:
        val_rows = list(csv.DictReader(f))
    for i, row in enumerate(val_rows):
        row["text_norm"] = f"{VAL_TEXT_MARKER}_{i}"
    with val_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(val_rows[0].keys()))
        writer.writeheader()
        writer.writerows(val_rows)

    # Create synthetic test CSV with TEST_TEXT_MARKER.
    test_rows = [
        {
            "audio_file": "te_00.wav",
            "split": "test",
            "text_norm": f"{TEST_TEXT_MARKER}_0",
            "complaint_category": "app_and_account",
            "complaint_urgency": "high",
            "customer_state": "calm",
            "churn_risk": "at_risk",
        },
        {
            "audio_file": "te_01.wav",
            "split": "test",
            "text_norm": f"{TEST_TEXT_MARKER}_1",
            "complaint_category": "billing_and_charges",
            "complaint_urgency": "low",
            "customer_state": "frustrated",
            "churn_risk": "not_at_risk",
        },
        {
            "audio_file": "te_02.wav",
            "split": "test",
            "text_norm": f"{TEST_TEXT_MARKER}_2",
            "complaint_category": "network_and_connectivity",
            "complaint_urgency": "medium",
            "customer_state": "unclear" if include_unclear_test else "mad",
            "churn_risk": "not_at_risk",
        },
    ]
    assert len(test_rows) == shared["test_rows"]
    test_csv = data_dir / "final" / "clean_training_test.csv"
    with test_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(test_rows[0].keys()))
        writer.writeheader()
        writer.writerows(test_rows)

    # Build 20 tiny checkpoints (5 seeds x 4 fields).
    ckpt_root = tmp_path / "checkpoints"
    for seed in seeds:
        for field in fields:
            target = (
                ckpt_root / f"seed_{seed}" / field / "epoch_02"
                if use_epoch_subdir
                else ckpt_root / f"seed_{seed}" / field
            )
            target.mkdir(parents=True, exist_ok=True)
            id2label = {str(i): cls_name for i, cls_name in enumerate(classes[field])}
            (target / "config.json").write_text(
                json.dumps({"id2label": id2label}), encoding="utf-8"
            )
            (target / "model.safetensors").write_bytes(
                b"dummy-weights-" + weights_salt + f"-{seed}-{field}".encode("utf-8")
            )

    ckpt_dirs = discover_checkpoints(ckpt_root, seeds, fields)

    def fake_predict(texts, ckpt_dir):
        cfg = json.loads((Path(ckpt_dir) / "config.json").read_text(encoding="utf-8"))
        id2label = {int(k): v for k, v in cfg["id2label"].items()}
        labels = [id2label[i] for i in sorted(id2label)]
        seed_tag = Path(ckpt_dir).as_posix()
        out = []
        for idx, _text in enumerate(texts):
            raw = {
                lbl: 1.0 + ((sum(ord(ch) for ch in lbl) + idx + len(seed_tag)) % 7)
                for lbl in labels
            }
            total = sum(raw.values())
            out.append({lbl: raw[lbl] / total for lbl in labels})
        return out

    # Write matching submitted validation predictions for all 5 seeds.
    submitted_val_dir = tmp_path / "submitted_val"
    submitted_val_dir.mkdir(parents=True, exist_ok=True)
    val_texts = [r["text_norm"] for r in val_rows]
    for seed in seeds:
        field_probs = {
            field: fake_predict(val_texts, ckpt_dirs[seed][field])
            for field in fields
        }
        rows = [
            {
                "audio_file": val_rows[i]["audio_file"],
                "probabilities": {f: field_probs[f][i] for f in fields},
            }
            for i in range(len(val_rows))
        ]
        write_predictions_file(
            path=submitted_val_dir / f"predictions_val_seed{seed}.json",
            run_id=f"val-sub-{seed}",
            model=model,
            split="val",
            seed=seed,
            dataset_version=shared["dataset_version"],
            rows=rows,
            classes_by_field=classes,
        )

    cfg = ExperimentConfig(
        model=model,
        dataset_version=shared["dataset_version"],
        split="train",
        learning_rate=2e-5,
        batch_size=16,
        epochs=3,
        other_hyperparameters={},
    )
    cfg_path = tmp_path / "config.json"
    save_experiment_config(cfg, cfg_path)

    return {
        "data_dir": data_dir,
        "shared": shared,
        "classes": classes,
        "seeds": seeds,
        "fields": fields,
        "test_csv": test_csv,
        "ckpt_root": ckpt_root,
        "ckpt_dirs": ckpt_dirs,
        "submitted_val_dir": submitted_val_dir,
        "cfg_path": cfg_path,
        "fake_predict": fake_predict,
        "run_id": run_id,
    }


def test_discover_checkpoints_direct_and_error_cases(tmp_path):
    setup = _make_full_synthetic_setup(tmp_path / "direct", use_epoch_subdir=False)
    discovered = discover_checkpoints(setup["ckpt_root"], setup["seeds"], setup["fields"])
    assert set(discovered.keys()) == set(setup["seeds"])

    # Missing checkpoint
    missing_root = tmp_path / "missing"
    setup_m = _make_full_synthetic_setup(missing_root)
    (setup_m["ckpt_dirs"][42]["churn_risk"] / "model.safetensors").unlink()
    with pytest.raises(FinalTestEvaluationError, match="seed 42, field churn_risk"):
        discover_checkpoints(setup_m["ckpt_root"], setup_m["seeds"], setup_m["fields"])

    # Duplicate epoch_* directories
    dup_root = tmp_path / "dup"
    setup_d = _make_full_synthetic_setup(dup_root)
    extra_epoch = setup_d["ckpt_root"] / "seed_7" / "customer_state" / "epoch_03"
    extra_epoch.mkdir(parents=True)
    (extra_epoch / "config.json").write_text("{}", encoding="utf-8")
    (extra_epoch / "model.safetensors").write_bytes(b"extra")
    with pytest.raises(FinalTestEvaluationError, match="seed 7, field customer_state"):
        discover_checkpoints(setup_d["ckpt_root"], setup_d["seeds"], setup_d["fields"])


def test_claim_is_written_before_first_test_predict_call_and_full_run_succeeds(
    tmp_path, capsys
):
    setup = _make_full_synthetic_setup(tmp_path)
    runs_dir = tmp_path / "runs"
    rehearsal_path = tmp_path / "rehearsal" / "val_rehearsal.json"

    rehearsal = rehearse_on_validation(
        setup["data_dir"],
        setup["ckpt_dirs"],
        setup["submitted_val_dir"],
        rehearsal_path,
        predict_fn=setup["fake_predict"],
    )
    assert rehearsal["overall"] == "PARITY"

    log_path = runs_dir / "test_evaluations.json"
    observed_claim_at_first_call = []

    def spy_predict(texts, ckpt_dir):
        if not observed_claim_at_first_call:
            log = read_log(log_path)
            observed_claim_at_first_call.append(len(log["entries"]))
        return setup["fake_predict"](texts, ckpt_dir)

    summary = run_final_test_evaluation(
        data_dir=setup["data_dir"],
        runs_dir=runs_dir,
        run_id=setup["run_id"],
        config_path=setup["cfg_path"],
        checkpoint_dirs=setup["ckpt_dirs"],
        rehearsal_path=rehearsal_path,
        hypothesis="Final frozen test evaluation for MARBERTv2.",
        device="cpu",
        predict_fn=spy_predict,
    )

    assert observed_claim_at_first_call == [1]
    assert summary["evaluated_split"] == "test"

    exp_dir = runs_dir / f"exp_{setup['run_id']}"
    for seed in setup["seeds"]:
        assert (exp_dir / f"predictions_test_seed{seed}.json").is_file()

    rec = load_run_record(exp_dir / "run_record.json")
    assert rec["evaluated_split"] == "test"
    assert len(rec["per_seed"]) == 5
    expected_test_sha = hashlib.sha256(setup["test_csv"].read_bytes()).hexdigest()
    assert rec["config"]["other_hyperparameters"][EVAL_TEST_HASH_KEY] == expected_test_sha
    assert rec["exceptions"][0]["rows_excluded"] == 1
    assert rec["exceptions"][0]["n_scored"] == 2
    assert rec["exceptions"][0]["n_total_rows"] == 3
    for field in setup["fields"]:
        agg = rec["aggregate"][f"{field}_macro_f1"]
        assert agg["n"] == 5
        assert "mean" in agg and "std" in agg

    fp = checkpoint_fingerprint(setup["ckpt_dirs"])
    log = read_log(log_path)
    assert len(log["entries"]) == 1
    assert log["entries"][0]["uses"] == 5
    assert log["entries"][0]["checkpoint_sha256"] == fp["combined"]
    assert log["entries"][0]["test_file_sha256"] == expected_test_sha

    captured = capsys.readouterr()
    assert TEST_TEXT_MARKER not in captured.out
    assert TEST_TEXT_MARKER not in captured.err
    assert VAL_TEXT_MARKER not in captured.out
    assert VAL_TEXT_MARKER not in captured.err
    for fpath in list(runs_dir.rglob("*.json")) + [rehearsal_path]:
        text = fpath.read_text(encoding="utf-8")
        assert TEST_TEXT_MARKER not in text
        assert VAL_TEXT_MARKER not in text


def test_second_run_same_model_alias_and_different_checkpoints_is_refused(tmp_path):
    setup1 = _make_full_synthetic_setup(
        tmp_path / "run1", run_id="marbert-final-001", model="MARBERTv2", weights_salt=b"v1"
    )
    runs_dir = tmp_path / "runs"
    reh1 = tmp_path / "rehearsal1.json"
    rehearse_on_validation(
        setup1["data_dir"],
        setup1["ckpt_dirs"],
        setup1["submitted_val_dir"],
        reh1,
        predict_fn=setup1["fake_predict"],
    )
    run_final_test_evaluation(
        data_dir=setup1["data_dir"],
        runs_dir=runs_dir,
        run_id=setup1["run_id"],
        config_path=setup1["cfg_path"],
        checkpoint_dirs=setup1["ckpt_dirs"],
        rehearsal_path=reh1,
        hypothesis="First final test evaluation.",
        device="cpu",
        predict_fn=setup1["fake_predict"],
    )

    setup2 = _make_full_synthetic_setup(
        tmp_path / "run2",
        run_id="marbert-final-002",
        model="UBC-NLP/MARBERTv2",
        weights_salt=b"v2",
    )
    reh2 = tmp_path / "rehearsal2.json"
    rehearse_on_validation(
        setup2["data_dir"],
        setup2["ckpt_dirs"],
        setup2["submitted_val_dir"],
        reh2,
        predict_fn=setup2["fake_predict"],
    )

    predict_called = []

    def fail_if_called(texts, ckpt_dir):
        predict_called.append(ckpt_dir)
        return setup2["fake_predict"](texts, ckpt_dir)

    with pytest.raises(AlreadyEvaluatedError):
        run_final_test_evaluation(
            data_dir=setup2["data_dir"],
            runs_dir=runs_dir,
            run_id=setup2["run_id"],
            config_path=setup2["cfg_path"],
            checkpoint_dirs=setup2["ckpt_dirs"],
            rehearsal_path=reh2,
            hypothesis="Second attempt with alias and new checkpoints.",
            device="cpu",
            predict_fn=fail_if_called,
        )

    assert predict_called == []
    assert not (runs_dir / "exp_marbert-final-002").exists()
    assert len(read_log(runs_dir / "test_evaluations.json")["entries"]) == 1


def test_rehearsal_near_passes_and_invalid_rehearsals_refused_before_claim(tmp_path):
    setup = _make_full_synthetic_setup(tmp_path)
    reh_path = tmp_path / "rehearsal.json"
    rehearsal = rehearse_on_validation(
        setup["data_dir"],
        setup["ckpt_dirs"],
        setup["submitted_val_dir"],
        reh_path,
        predict_fn=setup["fake_predict"],
    )

    # 1. Missing rehearsal file -> refused, no log, no run folder
    runs_missing = tmp_path / "runs_missing"
    with pytest.raises(FinalTestEvaluationError, match="rehearsal report not found"):
        run_final_test_evaluation(
            data_dir=setup["data_dir"],
            runs_dir=runs_missing,
            run_id="run-missing",
            config_path=setup["cfg_path"],
            checkpoint_dirs=setup["ckpt_dirs"],
            rehearsal_path=tmp_path / "does_not_exist.json",
            hypothesis="Missing rehearsal.",
            device="cpu",
            predict_fn=setup["fake_predict"],
        )
    assert not (runs_missing / "test_evaluations.json").exists()
    assert not (runs_missing / "exp_run-missing").exists()

    # 2. NO PARITY rehearsal -> refused, no log, no run folder
    no_parity_path = tmp_path / "rehearsal_no_parity.json"
    no_parity = json.loads(json.dumps(rehearsal))
    no_parity["overall"] = "NO PARITY"
    no_parity_path.write_text(json.dumps(no_parity), encoding="utf-8")
    runs_np = tmp_path / "runs_np"
    with pytest.raises(FinalTestEvaluationError, match="NO PARITY"):
        run_final_test_evaluation(
            data_dir=setup["data_dir"],
            runs_dir=runs_np,
            run_id="run-np",
            config_path=setup["cfg_path"],
            checkpoint_dirs=setup["ckpt_dirs"],
            rehearsal_path=no_parity_path,
            hypothesis="NO PARITY rehearsal.",
            device="cpu",
            predict_fn=setup["fake_predict"],
        )
    assert not (runs_np / "test_evaluations.json").exists()
    assert not (runs_np / "exp_run-np").exists()

    # 3. Wrong dataset_version -> refused, no log, no run folder
    bad_ver_path = tmp_path / "rehearsal_bad_ver.json"
    bad_ver = json.loads(json.dumps(rehearsal))
    bad_ver["dataset_version"] = "v999"
    bad_ver_path.write_text(json.dumps(bad_ver), encoding="utf-8")
    runs_bv = tmp_path / "runs_bv"
    with pytest.raises(FinalTestEvaluationError, match="dataset_version"):
        run_final_test_evaluation(
            data_dir=setup["data_dir"],
            runs_dir=runs_bv,
            run_id="run-bv",
            config_path=setup["cfg_path"],
            checkpoint_dirs=setup["ckpt_dirs"],
            rehearsal_path=bad_ver_path,
            hypothesis="Wrong dataset_version.",
            device="cpu",
            predict_fn=setup["fake_predict"],
        )
    assert not (runs_bv / "test_evaluations.json").exists()
    assert not (runs_bv / "exp_run-bv").exists()

    # 4. NEAR rehearsal passes
    near_path = tmp_path / "rehearsal_near.json"
    near = json.loads(json.dumps(rehearsal))
    near["overall"] = "NEAR"
    near_path.write_text(json.dumps(near), encoding="utf-8")
    runs_near = tmp_path / "runs_near"
    summary = run_final_test_evaluation(
        data_dir=setup["data_dir"],
        runs_dir=runs_near,
        run_id="run-near",
        config_path=setup["cfg_path"],
        checkpoint_dirs=setup["ckpt_dirs"],
        rehearsal_path=near_path,
        hypothesis="NEAR rehearsal passes.",
        device="cpu",
        predict_fn=setup["fake_predict"],
    )
    assert summary["evaluated_split"] == "test"

    # 5. One-byte change in one model.safetensors invalidates fingerprint -> refused before claim
    one_model = setup["ckpt_dirs"][99]["churn_risk"] / "model.safetensors"
    orig_bytes = one_model.read_bytes()
    one_model.write_bytes(orig_bytes[:-1] + bytes([orig_bytes[-1] ^ 0x01]))
    runs_fp = tmp_path / "runs_fp"
    with pytest.raises(FinalTestEvaluationError, match="checkpoint_fingerprint"):
        run_final_test_evaluation(
            data_dir=setup["data_dir"],
            runs_dir=runs_fp,
            run_id="run-fp",
            config_path=setup["cfg_path"],
            checkpoint_dirs=setup["ckpt_dirs"],
            rehearsal_path=reh_path,
            hypothesis="Tampered checkpoint byte.",
            device="cpu",
            predict_fn=setup["fake_predict"],
        )
    assert not (runs_fp / "test_evaluations.json").exists()
    assert not (runs_fp / "exp_run-fp").exists()


def test_id2label_mismatch_is_refused_before_claim(tmp_path):
    setup = _make_full_synthetic_setup(tmp_path)
    reh_path = tmp_path / "rehearsal.json"
    rehearse_on_validation(
        setup["data_dir"],
        setup["ckpt_dirs"],
        setup["submitted_val_dir"],
        reh_path,
        predict_fn=setup["fake_predict"],
    )
    bad_cfg = setup["ckpt_dirs"][1337]["complaint_urgency"] / "config.json"
    bad_cfg.write_text(
        json.dumps({"id2label": {"0": "high", "1": "low", "2": "bogus"}}),
        encoding="utf-8",
    )
    runs_dir = tmp_path / "runs"
    with pytest.raises(FinalTestEvaluationError, match="complaint_urgency"):
        run_final_test_evaluation(
            data_dir=setup["data_dir"],
            runs_dir=runs_dir,
            run_id="run-bad-label",
            config_path=setup["cfg_path"],
            checkpoint_dirs=setup["ckpt_dirs"],
            rehearsal_path=reh_path,
            hypothesis="Mismatching id2label.",
            device="cpu",
            predict_fn=setup["fake_predict"],
        )
    assert not (runs_dir / "test_evaluations.json").exists()
    assert not (runs_dir / "exp_run-bad-label").exists()
