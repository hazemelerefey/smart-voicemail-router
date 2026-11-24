import pytest

from infra.experiment_config import (
    ExperimentConfig,
    ExperimentConfigError,
    changed_fields,
    load_experiment_config,
    save_experiment_config,
    validate_against_shared,
)

SHARED = {"dataset_version": "v2"}


def neural(**overrides):
    base = dict(
        model="EgyBERT",
        dataset_version="v2",
        split="train",
        learning_rate=2e-5,
        batch_size=16,
        epochs=3,
    )
    base.update(overrides)
    return ExperimentConfig(**base)


def test_neural_config_matches_hazems_fields():
    cfg = neural()
    assert cfg.for_seed(42) == {
        "model": "EgyBERT",
        "dataset_version": "v2",
        "split": "train",
        "learning_rate": 2e-5,
        "batch_size": 16,
        "epochs": 3,
        "other_hyperparameters": {},
        "seed": 42,
    }


def test_baseline_config_leaves_neural_fields_empty():
    cfg = ExperimentConfig(
        model="tfidf-logreg",
        dataset_version="v2",
        other_hyperparameters={"max_features": 20000, "C": 1.0},
    )
    assert cfg.learning_rate is None and cfg.batch_size is None and cfg.epochs is None


def test_test_split_is_rejected():
    with pytest.raises(ExperimentConfigError, match="split"):
        neural(split="test")
    with pytest.raises(ExperimentConfigError, match="split"):
        neural(split="val")


@pytest.mark.parametrize("bad", [0, -1e-5, "2e-5", True, float("nan"), float("inf")])
def test_bad_learning_rate_is_rejected(bad):
    with pytest.raises(ExperimentConfigError, match="learning_rate"):
        neural(learning_rate=bad)


@pytest.mark.parametrize("bad", [0, -4, 1.5, "16", True])
def test_bad_batch_size_is_rejected(bad):
    with pytest.raises(ExperimentConfigError, match="batch_size"):
        neural(batch_size=bad)


def test_bad_epochs_is_rejected():
    with pytest.raises(ExperimentConfigError, match="epochs"):
        neural(epochs=0)


def test_empty_model_is_rejected():
    with pytest.raises(ExperimentConfigError, match="model"):
        neural(model="  ")


def test_other_hyperparameters_cannot_reuse_named_keys():
    with pytest.raises(ExperimentConfigError, match="seed"):
        neural(other_hyperparameters={"seed": 1})
    with pytest.raises(ExperimentConfigError, match="learning_rate"):
        neural(other_hyperparameters={"learning_rate": 1e-3})


def test_other_hyperparameters_must_be_json_serializable():
    with pytest.raises(ExperimentConfigError, match="JSON"):
        neural(other_hyperparameters={"x": object()})


def test_for_seed_rejects_a_bad_seed():
    with pytest.raises(ExperimentConfigError, match="seed"):
        neural().for_seed(-1)
    with pytest.raises(ExperimentConfigError, match="seed"):
        neural().for_seed("42")


def test_from_dict_rejects_seed_and_unknown_fields():
    with pytest.raises(ExperimentConfigError, match="shared_config"):
        ExperimentConfig.from_dict({"model": "m", "dataset_version": "v2", "seed": 42})
    with pytest.raises(ExperimentConfigError, match="unknown"):
        ExperimentConfig.from_dict({"model": "m", "dataset_version": "v2", "lr": 1})


def test_dataset_version_must_match_shared_config():
    validate_against_shared(neural(), SHARED)
    with pytest.raises(ExperimentConfigError, match="dataset_version"):
        validate_against_shared(neural(dataset_version="v1"), SHARED)


def test_save_and_load_round_trip(tmp_path):
    cfg = neural(other_hyperparameters={"warmup_ratio": 0.1})
    path = tmp_path / "runs" / "exp_001" / "config.json"
    save_experiment_config(cfg, path)
    assert load_experiment_config(path, shared_config=SHARED) == cfg


def test_save_refuses_to_overwrite(tmp_path):
    path = tmp_path / "config.json"
    save_experiment_config(neural(), path)
    with pytest.raises(FileExistsError):
        save_experiment_config(neural(epochs=5), path)


def test_load_checks_dataset_version(tmp_path):
    path = tmp_path / "config.json"
    save_experiment_config(neural(dataset_version="v1"), path)
    with pytest.raises(ExperimentConfigError, match="dataset_version"):
        load_experiment_config(path, shared_config=SHARED)


def test_load_missing_file(tmp_path):
    with pytest.raises(ExperimentConfigError, match="not found"):
        load_experiment_config(tmp_path / "nope.json")


def test_changed_fields():
    base = neural()
    assert changed_fields(base, neural()) == []
    assert changed_fields(base, neural(learning_rate=3e-5)) == ["learning_rate"]
    assert changed_fields(base, neural(model="MARBERTv2")) == ["model"]
    two = neural(learning_rate=3e-5, batch_size=8)
    assert changed_fields(base, two) == ["batch_size", "learning_rate"]


def test_changed_fields_sees_other_hyperparameters():
    a = neural(other_hyperparameters={"warmup_ratio": 0.1})
    b = neural(other_hyperparameters={"warmup_ratio": 0.06})
    c = neural(other_hyperparameters={})
    assert changed_fields(a, b) == ["other_hyperparameters.warmup_ratio"]
    assert changed_fields(a, c) == ["other_hyperparameters.warmup_ratio"]