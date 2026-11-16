import json

import pytest

from infra.experiment_config import ExperimentConfig, ExperimentConfigError
from infra.run_record import (
    REQUIRED_METRICS,
    RunRecordError,
    build_run_record,
    load_run_record,
    make_seed_result,
    record_path,
    save_run_record,
)

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


def cfg(**overrides):
    base = dict(model="EgyBERT", dataset_version="v2", split="train",
                learning_rate=2e-5, batch_size=16, epochs=3)
    base.update(overrides)
    return ExperimentConfig(**base)


REASON = "unclear has no rows in train, so the model never trains on it (Hazem's decision)."


def exception(**overrides):
    # The shape of one entry of the harness report's `exceptions` list.
    e = {
        "field": "customer_state",
        "excluded_labels": ["unclear"],
        "rows_excluded": 1,
        "n_scored": 1002,
        "n_total_rows": 1003,
        "reason": REASON,
    }
    e.update(overrides)
    return e


def metrics(value=0.7):
    return {name: value for name in REQUIRED_METRICS}


def seed_results(config, run_id="001", split="val", values=None):
    values = values or [0.6, 0.7, 0.8, 0.7, 0.7]
    return [
        make_seed_result(run_id, config, split, seed, metrics(v))
        for seed, v in zip(SHARED["experiment_seeds"], values)
    ]


def build(**overrides):
    config = overrides.pop("config", cfg(model="EgyBERT"))
    args = dict(
        run_id="001",
        hypothesis="EgyBERT beats MARBERTv2 on complaint_category",
        config=config,
        shared_config=SHARED,
        per_seed=seed_results(config),
        evaluated_split="val",
        artifacts={"predictions": ["runs/exp_001/predictions_val.json"]},
        device="cpu",
        exceptions=[exception()],
        reference_config=cfg(model="MARBERTv2"),
        changed_factor="model",
        reference_run_id="002",
        created_utc="2026-11-14T10:00:00+00:00",
    )
    args.update(overrides)
    return build_run_record(**args)


def test_seed_result_has_the_skeleton_shape():
    r = make_seed_result("001", cfg(), "val", 42, metrics())
    assert set(r) == {"run_id", "model", "split", "seed", "metrics"}
    assert r["model"] == "EgyBERT" and r["split"] == "val" and r["seed"] == 42


def test_record_follows_hazems_example():
    rec = build()
    assert rec["run_id"] == "001"
    assert rec["changed_factor"] == "model"
    assert rec["held_constant"] == {
        "dataset_version": "v2", "split": "train",
        "learning_rate": 2e-5, "batch_size": 16, "epochs": 3,
    }
    assert rec["dataset"]["version"] == "v2"
    assert rec["dataset"]["rows"] == {"train": 3575, "val": 1003, "test": 518}
    assert rec["evaluated_split"] == "val"


def test_aggregate_is_computed_with_ddof_recorded():
    rec = build()
    agg = rec["aggregate"]["complaint_category_macro_f1"]
    assert agg["mean"] == pytest.approx(0.7)
    assert agg["ddof"] == 1 and agg["n"] == 5
    assert agg["std"] == pytest.approx(0.07071067811865475)


def test_record_is_json_serializable():
    json.dumps(build())


def test_reference_run_has_no_changed_factor():
    rec = build(reference_config=None, changed_factor=None, reference_run_id=None)
    assert rec["changed_factor"] is None
    assert "model" in rec["held_constant"]


def test_changed_factor_without_reference_is_rejected():
    with pytest.raises(RunRecordError, match="reference_config"):
        build(reference_config=None, changed_factor="model")


def test_more_than_one_factor_changed_is_rejected():
    ref = cfg(model="MARBERTv2", learning_rate=3e-5)
    with pytest.raises(RunRecordError, match="more than one"):
        build(reference_config=ref, changed_factor="model")


def test_nothing_changed_is_rejected():
    with pytest.raises(RunRecordError, match="nothing changed"):
        build(reference_config=cfg(), changed_factor="model")


def test_changed_factor_must_match_the_diff():
    with pytest.raises(RunRecordError, match="changed_factor"):
        build(changed_factor="learning_rate")


def test_all_seeds_are_required_in_order():
    config = cfg()
    missing_one = seed_results(config)[:-1]
    with pytest.raises(RunRecordError, match="all seeds"):
        build(per_seed=missing_one)
    swapped = seed_results(config)
    swapped[0], swapped[1] = swapped[1], swapped[0]
    with pytest.raises(RunRecordError, match="all seeds"):
        build(per_seed=swapped)


def test_seed_result_must_match_the_run():
    config = cfg()
    wrong_split = seed_results(config, split="test")
    with pytest.raises(RunRecordError, match="split"):
        build(per_seed=wrong_split)
    wrong_id = seed_results(config, run_id="999")
    with pytest.raises(RunRecordError, match="run_id"):
        build(per_seed=wrong_id)


def test_missing_required_metric_is_rejected():
    config = cfg()
    results = seed_results(config)
    del results[2]["metrics"]["churn_risk_macro_f1"]
    with pytest.raises(RunRecordError, match="missing metrics"):
        build(per_seed=results)


@pytest.mark.parametrize("bad", [1.2, -0.1, float("nan"), None])
def test_bad_macro_f1_is_rejected(bad):
    config = cfg()
    results = seed_results(config)
    results[0]["metrics"]["customer_state_macro_f1"] = bad
    with pytest.raises(RunRecordError, match="customer_state_macro_f1"):
        build(per_seed=results)


def test_extra_metrics_are_allowed():
    config = cfg()
    results = seed_results(config)
    for r in results:
        r["metrics"]["complaint_category_accuracy"] = 0.8
    rec = build(per_seed=results)
    assert "complaint_category_accuracy" in rec["aggregate"]


def test_dataset_version_must_match_shared_config():
    with pytest.raises(ExperimentConfigError, match="dataset_version"):
        build(config=cfg(dataset_version="v1"), per_seed=seed_results(cfg(dataset_version="v1")))


@pytest.mark.parametrize("bad", ["", "../x", "a b", "a/b", None, 1])
def test_bad_run_id_is_rejected(bad):
    with pytest.raises(RunRecordError, match="run_id"):
        build(run_id=bad)


def test_empty_hypothesis_or_device_is_rejected():
    with pytest.raises(RunRecordError, match="hypothesis"):
        build(hypothesis="  ")
    with pytest.raises(RunRecordError, match="device"):
        build(device="")


@pytest.mark.parametrize(
    "bad",
    ["D:\\work\\runs\\pred.json", "/home/aya/pred.json", "../pred.json", "runs/exp_001/val_transcript_check.json"],
)
def test_bad_artifact_paths_are_rejected(bad):
    with pytest.raises(RunRecordError):
        build(artifacts={"predictions": [bad]})


def test_the_exceptions_are_stored_in_the_record():
    rec = build()
    assert rec["exceptions"] == [exception()]
    assert rec["schema_version"] == 2


def test_an_empty_exceptions_list_is_allowed_but_the_argument_is_required():
    assert build(exceptions=[])["exceptions"] == []
    with pytest.raises(TypeError):
        build_run_record(
            run_id="001", hypothesis="h", config=cfg(), shared_config=SHARED,
            per_seed=seed_results(cfg()), evaluated_split="val", artifacts={}, device="cpu",
        )


@pytest.mark.parametrize(
    "bad",
    [
        "none",                                                   # not a list
        [1],                                                      # not a dict
        [{"field": "customer_state"}],                            # keys missing
        [exception(extra_key=1)],                                 # an extra key
        [exception(field="not_a_field")],                         # no metric for this field
        [exception(), exception()],                               # the same field twice
        [exception(excluded_labels=[])],                          # no labels
        [exception(excluded_labels="unclear")],                   # not a list
        [exception(reason="  ")],                                 # no reason
        [exception(rows_excluded=-1, n_scored=1004)],             # a negative count
        [exception(n_scored=1000)],                               # the counts do not add up
        [exception(n_total_rows=500, n_scored=499)],              # not the size of the split
        [exception(rows_excluded=True, n_scored=1002)],           # a bool is not a count
    ],
)
def test_bad_exceptions_are_rejected(bad):
    with pytest.raises(RunRecordError):
        build(exceptions=bad)


def test_exception_row_counts_follow_the_evaluated_split():
    config = cfg()
    results = seed_results(config, split="test")
    test_exception = exception(rows_excluded=0, n_scored=518, n_total_rows=518)
    rec = build(per_seed=results, evaluated_split="test", exceptions=[test_exception])
    assert rec["exceptions"][0]["n_total_rows"] == 518
    with pytest.raises(RunRecordError, match="shared config"):
        build(per_seed=results, evaluated_split="test", exceptions=[exception()])


def test_load_rejects_the_old_schema(tmp_path):
    rec = build()
    rec["schema_version"] = 1
    path = tmp_path / "old.json"
    path.write_text(json.dumps(rec), encoding="utf-8")
    with pytest.raises(RunRecordError, match="schema_version"):
        load_run_record(path)


def test_save_and_load_round_trip(tmp_path):
    rec = build()
    path = save_run_record(rec, tmp_path / "runs")
    assert path == record_path(tmp_path / "runs", "001")
    assert path.parent.name == "exp_001"
    assert load_run_record(path) == rec


def test_save_never_overwrites(tmp_path):
    rec = build()
    save_run_record(rec, tmp_path)
    with pytest.raises(FileExistsError):
        save_run_record(rec, tmp_path)


def test_load_rejects_bad_files(tmp_path):
    with pytest.raises(RunRecordError, match="not found"):
        load_run_record(tmp_path / "nope.json")
    broken = tmp_path / "bad.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(RunRecordError, match="not valid JSON"):
        load_run_record(broken)
    incomplete = tmp_path / "incomplete.json"
    incomplete.write_text(json.dumps({"run_id": "001"}), encoding="utf-8")
    with pytest.raises(RunRecordError, match="missing keys"):
        load_run_record(incomplete)