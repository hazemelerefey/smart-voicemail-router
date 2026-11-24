import json

import pytest

from infra.harness import evaluate_predictions, load_truth_table
from infra.predictions_file import read_predictions_file, write_predictions_file
from infra.shared_config import load_shared_config
from infra.sweep_table import SweepTableError, format_seed_table, seed_comparison
from infra.tests.test_evaluate_run import _probs_for_chosen
from infra.tests.test_tfidf_baseline import SECRET_MARKER, _make_synthetic_dataset
from infra.tfidf_baseline import CUSTOMER_STATE_EXCLUSIONS, load_classes_by_field


def _write_single_seed_pred(
    path,
    truth,
    classes,
    *,
    run_id="lr-2e5",
    model="MARBERTv2",
    split="val",
    seed=42,
    dataset_version="v2",
    flip_count=0,
):
    rows = []
    for i, tr_row in enumerate(truth):
        chosen = {}
        for field, cls_list in classes.items():
            true_label = tr_row[field]
            if true_label not in cls_list:
                chosen[field] = cls_list[0]
            elif i < flip_count:
                pos = cls_list.index(true_label)
                chosen[field] = cls_list[(pos + 1) % len(cls_list)]
            else:
                chosen[field] = true_label
        rows.append({
            "audio_file": tr_row["audio_file"],
            "probabilities": _probs_for_chosen(classes, chosen),
        })
    write_predictions_file(
        path=path,
        run_id=run_id,
        model=model,
        split=split,
        seed=seed,
        dataset_version=dataset_version,
        rows=rows,
        classes_by_field=classes,
    )
    return path


def _make_sweep_fixture(tmp_path):
    data_dir = _make_synthetic_dataset(tmp_path / "data", include_unclear=True)
    shared = load_shared_config(
        data_dir / "notebooks" / "training" / "shared_config.json"
    )
    classes = load_classes_by_field(data_dir / "final" / "class_weights.json")
    truth = load_truth_table(
        data_dir / "final" / "clean_training_val.csv", "val", list(classes.keys())
    )
    return data_dir, shared, classes, truth


def test_seed_comparison_equals_direct_harness_and_formats_table(tmp_path, capsys):
    data_dir, _, classes, truth = _make_sweep_fixture(tmp_path)
    p_low = _write_single_seed_pred(
        tmp_path / "lr1e5.json",
        truth,
        classes,
        run_id="lr-1e5",
        model="MARBERTv2",
        flip_count=2,
    )
    p_high = _write_single_seed_pred(
        tmp_path / "lr2e5.json",
        truth,
        classes,
        run_id="lr-2e5",
        model="UBC-NLP/MARBERTv2",
        flip_count=0,
    )

    rows = seed_comparison(
        data_dir,
        [("lr=1e-5", p_low), ("lr=2e-5", p_high)],
        seed=42,
    )
    assert len(rows) == 2

    for row, ppath in zip(rows, (p_low, p_high)):
        loaded = read_predictions_file(ppath, classes, expected_split="val")
        direct = evaluate_predictions(
            "val",
            truth,
            loaded["harness_rows"],
            classes,
            exclusions_by_field=CUSTOMER_STATE_EXCLUSIONS,
        )
        assert row["combined_macro_f1"] == direct["combined_macro_f1"]
        for field in classes:
            assert row["macro_f1"][field] == pytest.approx(
                direct["fields"][field]["macro"]["f1"]
            )

    table = format_seed_table(rows)
    assert (
        "single seed (42), no standard deviation: "
        "for choosing a learning rate only, not a final result"
    ) in table
    # Sorted by combined value: lr=2e-5 (flip_count=0) must appear before lr=1e-5 (flip_count=2).
    assert table.index("lr=2e-5") < table.index("lr=1e-5")

    captured = capsys.readouterr()
    assert SECRET_MARKER not in table
    assert SECRET_MARKER not in captured.out
    assert SECRET_MARKER not in captured.err


def test_refuses_file_of_another_seed(tmp_path):
    data_dir, _, classes, truth = _make_sweep_fixture(tmp_path)
    p1337 = _write_single_seed_pred(
        tmp_path / "seed1337.json", truth, classes, seed=1337
    )
    with pytest.raises(SweepTableError, match="header seed is 1337"):
        seed_comparison(data_dir, [("lr=2e-5", p1337)], seed=42)


def test_refuses_files_of_different_models(tmp_path):
    data_dir, _, classes, truth = _make_sweep_fixture(tmp_path)
    p_mar = _write_single_seed_pred(
        tmp_path / "mar.json", truth, classes, model="MARBERTv2"
    )
    p_egy = _write_single_seed_pred(
        tmp_path / "egy.json", truth, classes, model="EgyBERT"
    )
    with pytest.raises(SweepTableError, match="compares one model only"):
        seed_comparison(data_dir, [("marbert", p_mar), ("egybert", p_egy)], seed=42)


def test_refuses_files_of_different_dataset_versions(tmp_path):
    data_dir, _, classes, truth = _make_sweep_fixture(tmp_path)
    p_v2 = _write_single_seed_pred(
        tmp_path / "v2.json", truth, classes, dataset_version="v2"
    )
    p_v3 = _write_single_seed_pred(
        tmp_path / "v3.json", truth, classes, dataset_version="v3"
    )
    with pytest.raises(SweepTableError, match="dataset_version"):
        seed_comparison(data_dir, [("v2", p_v2), ("v3", p_v3)], seed=42)


def test_refuses_test_split_file(tmp_path):
    data_dir, _, classes, truth = _make_sweep_fixture(tmp_path)
    p_test = _write_single_seed_pred(
        tmp_path / "test.json", truth, classes, split="test"
    )
    with pytest.raises(SweepTableError, match="split 'test'"):
        seed_comparison(data_dir, [("test-run", p_test)], seed=42)
