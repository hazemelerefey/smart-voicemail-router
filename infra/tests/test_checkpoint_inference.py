"""Synthetic tests for infra/checkpoint_inference.py (no PyTorch required)."""
import json
from pathlib import Path

import pytest

from infra.checkpoint_inference import (
    CheckpointInferenceError,
    classify_parity,
    compare_with_submitted,
    predict_split,
    write_predictions,
)

CLASSES = {
    "complaint_category": ["billing", "network", "other"],
    "complaint_urgency": ["high", "low", "medium"],
    "customer_state": ["calm", "frustrated", "mad", "satisfied"],
    "churn_risk": ["at_risk", "not_at_risk"],
}

SECRET_MARKER = "SYNTHETIC_TRANSCRIPT_MARKER_DO_NOT_LEAK_7391"


def _make_synthetic_data_dir(tmp_path, n_rows=6, val_rows_config=None):
    """Create a minimal synthetic data_dir with shared_config, class_weights, and val CSV."""
    data_dir = tmp_path / "data"
    (data_dir / "notebooks" / "training").mkdir(parents=True)
    (data_dir / "final").mkdir(parents=True)

    shared = {
        "split_seed": 42,
        "experiment_seeds": [42, 1337, 2023, 7, 99],
        "max_seq_len": 128,
        "split_ratio": "70/20/10",
        "dataset_version": "v2",
        "dataset": "synthetic-corpus",
        "train_rows": 10,
        "val_rows": n_rows if val_rows_config is None else val_rows_config,
        "test_rows": 5,
    }
    (data_dir / "notebooks" / "training" / "shared_config.json").write_text(
        json.dumps(shared), encoding="utf-8"
    )

    weights = {
        "weights": {
            field: {cls_name: 1.0 for cls_name in cls_list}
            for field, cls_list in CLASSES.items()
        },
        "churn_weight_cap": 20,
    }
    (data_dir / "final" / "class_weights.json").write_text(
        json.dumps(weights), encoding="utf-8"
    )

    # Deliberately unsorted audio_file names to test CSV order preservation.
    audio_names = [f"clip_{idx:03d}.wav" for idx in [30, 5, 19, 1, 42, 8]][:n_rows]
    cat_labels = ["billing", "network", "other", "billing", "network", "other"]
    urg_labels = ["high", "low", "medium", "high", "low", "medium"]
    # Include one 'unclear' row in customer_state to exercise the exclusion rule.
    state_labels = ["calm", "frustrated", "mad", "satisfied", "unclear", "calm"]
    churn_labels = ["not_at_risk", "at_risk", "not_at_risk", "not_at_risk", "at_risk", "not_at_risk"]

    lines = [
        "audio_file,split,text_norm,complaint_category,complaint_urgency,customer_state,churn_risk"
    ]
    for i, af in enumerate(audio_names):
        lines.append(
            f"{af},val,{SECRET_MARKER}_{i},{cat_labels[i % 6]},{urg_labels[i % 6]},"
            f"{state_labels[i % 6]},{churn_labels[i % 6]}"
        )
    (data_dir / "final" / "clean_training_val.csv").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return data_dir, audio_names


def _make_checkpoints(tmp_path, id2label_overrides=None):
    """Create fake checkpoint directories containing only config.json."""
    ckpt_root = tmp_path / "ckpts"
    ckpt_dirs = {}
    overrides = id2label_overrides or {}
    for field, cls_list in CLASSES.items():
        d = ckpt_root / field
        d.mkdir(parents=True)
        id2label = overrides.get(
            field, {str(i): cls_name for i, cls_name in enumerate(cls_list)}
        )
        (d / "config.json").write_text(
            json.dumps({"id2label": id2label}), encoding="utf-8"
        )
        ckpt_dirs[field] = d
    return ckpt_dirs


def _deterministic_predict_fn(texts, checkpoint_dir):
    """Return deterministic probabilities keyed by the checkpoint's id2label order."""
    cfg = json.loads((Path(checkpoint_dir) / "config.json").read_text(encoding="utf-8"))
    id2label = {int(k): v for k, v in cfg["id2label"].items()}
    ordered_labels = [id2label[i] for i in sorted(id2label)]
    n_cls = len(ordered_labels)
    rows = []
    for i, _text in enumerate(texts):
        # Assign distinct, deterministic probabilities by class name hash/index.
        # Put the highest mass on a deterministic class name so name vs position differs.
        raw = {
            name: 1.0 + ((sum(ord(ch) for ch in name) + i) % 7)
            for name in ordered_labels
        }
        total = sum(raw.values())
        rows.append({name: raw[name] / total for name in ordered_labels})
    return rows


def test_mapping_check_refuses_different_class_set(tmp_path):
    data_dir, _ = _make_synthetic_data_dir(tmp_path)
    bad_ckpts = _make_checkpoints(
        tmp_path,
        id2label_overrides={
            "churn_risk": {"0": "at_risk", "1": "wrong_class_name"}
        },
    )
    with pytest.raises(CheckpointInferenceError, match="churn_risk"):
        predict_split(
            data_dir, bad_ckpts, split="val", predict_fn=_deterministic_predict_fn
        )


def test_reordered_id2label_is_accepted_and_assigned_by_name(tmp_path):
    data_dir, _ = _make_synthetic_data_dir(tmp_path)
    # Reverse id2label order for churn_risk and complaint_category.
    reordered_overrides = {
        "churn_risk": {"0": "not_at_risk", "1": "at_risk"},
        "complaint_category": {"0": "other", "1": "network", "2": "billing"},
    }
    ckpts = _make_checkpoints(tmp_path, id2label_overrides=reordered_overrides)

    def distinct_by_name_predict(texts, checkpoint_dir):
        cfg = json.loads(
            (Path(checkpoint_dir) / "config.json").read_text(encoding="utf-8")
        )
        id2label = {int(k): v for k, v in cfg["id2label"].items()}
        labels_in_ckpt_order = [id2label[i] for i in sorted(id2label)]
        # Give each class a unique fixed probability tied to its NAME.
        fixed = {
            "at_risk": 0.85,
            "not_at_risk": 0.15,
            "billing": 0.70,
            "network": 0.20,
            "other": 0.10,
            "high": 0.50,
            "low": 0.30,
            "medium": 0.20,
            "calm": 0.40,
            "frustrated": 0.30,
            "mad": 0.20,
            "satisfied": 0.10,
        }
        # Dict is emitted in checkpoint's id2label order (reversed for churn_risk & category).
        return [{name: fixed[name] for name in labels_in_ckpt_order} for _ in texts]

    rows = predict_split(
        data_dir, ckpts, split="val", predict_fn=distinct_by_name_predict
    )
    assert rows[0]["probabilities"]["churn_risk"]["at_risk"] == pytest.approx(0.85)
    assert rows[0]["probabilities"]["churn_risk"]["not_at_risk"] == pytest.approx(0.15)
    assert rows[0]["probabilities"]["complaint_category"]["billing"] == pytest.approx(0.70)
    assert rows[0]["probabilities"]["complaint_category"]["other"] == pytest.approx(0.10)


def test_rows_sum_to_one_is_enforced(tmp_path):
    data_dir, _ = _make_synthetic_data_dir(tmp_path)
    ckpts = _make_checkpoints(tmp_path)

    def bad_sum_predict(texts, checkpoint_dir):
        cfg = json.loads(
            (Path(checkpoint_dir) / "config.json").read_text(encoding="utf-8")
        )
        labels = list(cfg["id2label"].values())
        return [{name: 0.6 for name in labels} for _ in texts]

    with pytest.raises(CheckpointInferenceError, match="sum"):
        predict_split(data_dir, ckpts, split="val", predict_fn=bad_sum_predict)


def test_row_order_matches_csv_order(tmp_path):
    data_dir, expected_order = _make_synthetic_data_dir(tmp_path)
    ckpts = _make_checkpoints(tmp_path)
    rows = predict_split(
        data_dir, ckpts, split="val", predict_fn=_deterministic_predict_fn
    )
    assert [r["audio_file"] for r in rows] == expected_order


@pytest.mark.parametrize("bad_split", ["test", "train", "dev", ""])
def test_non_val_split_is_refused(tmp_path, bad_split):
    data_dir, _ = _make_synthetic_data_dir(tmp_path)
    ckpts = _make_checkpoints(tmp_path)
    with pytest.raises(CheckpointInferenceError, match="guarded test evaluation"):
        predict_split(
            data_dir, ckpts, split=bad_split, predict_fn=_deterministic_predict_fn
        )


def test_row_count_mismatch_is_refused(tmp_path):
    data_dir, _ = _make_synthetic_data_dir(tmp_path, n_rows=6, val_rows_config=10)
    ckpts = _make_checkpoints(tmp_path)
    with pytest.raises(CheckpointInferenceError, match="expected 10"):
        predict_split(
            data_dir, ckpts, split="val", predict_fn=_deterministic_predict_fn
        )


def test_no_marker_text_leaked_to_stdout_stderr_or_file(tmp_path, capsys):
    data_dir, _ = _make_synthetic_data_dir(tmp_path)
    ckpts = _make_checkpoints(tmp_path)
    rows = predict_split(
        data_dir, ckpts, split="val", predict_fn=_deterministic_predict_fn
    )
    out_file = tmp_path / "out" / "ours_val_seed42.json"
    write_predictions(
        rows,
        out_file,
        run_id="synthetic-parity",
        model="UBC-NLP/MARBERTv2",
        seed=42,
        dataset_version="v2",
    )
    captured = capsys.readouterr()
    assert SECRET_MARKER not in captured.out
    assert SECRET_MARKER not in captured.err
    assert SECRET_MARKER not in out_file.read_text(encoding="utf-8")


def test_write_predictions_no_overwrite(tmp_path):
    data_dir, _ = _make_synthetic_data_dir(tmp_path)
    ckpts = _make_checkpoints(tmp_path)
    rows = predict_split(
        data_dir, ckpts, split="val", predict_fn=_deterministic_predict_fn
    )
    out_file = tmp_path / "out" / "ours_val_seed42.json"
    write_predictions(
        rows,
        out_file,
        run_id="synthetic-parity",
        model="UBC-NLP/MARBERTv2",
        seed=42,
        dataset_version="v2",
    )
    with pytest.raises(FileExistsError):
        write_predictions(
            rows,
            out_file,
            run_id="synthetic-parity",
            model="UBC-NLP/MARBERTv2",
            seed=42,
            dataset_version="v2",
        )


def test_compare_with_submitted_identical_and_two_diffs(tmp_path, capsys):
    data_dir, _ = _make_synthetic_data_dir(tmp_path)
    ckpts = _make_checkpoints(tmp_path)
    rows = predict_split(
        data_dir, ckpts, split="val", predict_fn=_deterministic_predict_fn
    )

    ours_path = tmp_path / "out" / "ours_val_seed42.json"
    sub_same_path = tmp_path / "out" / "sub_same_val_seed42.json"
    write_predictions(
        rows,
        ours_path,
        run_id="synthetic-ours",
        model="UBC-NLP/MARBERTv2",
        seed=42,
        dataset_version="v2",
    )
    write_predictions(
        rows,
        sub_same_path,
        run_id="synthetic-sub",
        model="UBC-NLP/MARBERTv2",
        seed=42,
        dataset_version="v2",
    )

    sub_map_same = {field: sub_same_path for field in CLASSES}
    res_same = compare_with_submitted(
        ours_path, sub_map_same, CLASSES, data_dir=data_dir
    )
    for field, info in res_same.items():
        assert info["n_rows"] == 6
        assert info["n_argmax_diff"] == 0
        assert info["max_abs_prob_diff"] == 0.0
        assert info["mean_abs_prob_diff"] == 0.0
        assert info["macro_f1_equal"] is True
    assert classify_parity(res_same) == "PARITY"

    # Flip the argmax label on exactly 2 rows for churn_risk.
    modified_rows = json.loads(json.dumps(rows))
    for idx in (0, 2):
        p = modified_rows[idx]["probabilities"]["churn_risk"]
        modified_rows[idx]["probabilities"]["churn_risk"] = {
            "at_risk": p["not_at_risk"],
            "not_at_risk": p["at_risk"],
        }
    sub_diff_path = tmp_path / "out" / "sub_diff_val_seed42.json"
    write_predictions(
        modified_rows,
        sub_diff_path,
        run_id="synthetic-sub-diff",
        model="UBC-NLP/MARBERTv2",
        seed=42,
        dataset_version="v2",
    )
    sub_map_diff = {
        field: (sub_diff_path if field == "churn_risk" else sub_same_path)
        for field in CLASSES
    }
    res_diff = compare_with_submitted(
        ours_path, sub_map_diff, CLASSES, data_dir=data_dir
    )
    assert res_diff["churn_risk"]["n_argmax_diff"] == 2
    assert res_diff["churn_risk"]["max_abs_prob_diff"] > 0.0
    assert res_diff["complaint_category"]["n_argmax_diff"] == 0
    assert classify_parity(res_diff) == "NO PARITY"

    captured = capsys.readouterr()
    assert SECRET_MARKER not in captured.out
    assert SECRET_MARKER not in captured.err


def test_module_contains_no_test_csv_path():
    src = (
        Path(__file__).resolve().parents[1] / "checkpoint_inference.py"
    ).read_text(encoding="utf-8")
    assert "clean_training_test.csv" not in src
