import json

import pytest

from infra.shared_config import SharedConfigError, load_shared_config

# A test fixture shaped like Hazem's shared_config.json. It is only used by
# these tests. The real values are always read from the real file.
VALID = {
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


def write(tmp_path, data):
    p = tmp_path / "shared_config.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_valid_config_loads(tmp_path):
    cfg = load_shared_config(write(tmp_path, VALID))
    assert cfg["experiment_seeds"] == [42, 1337, 2023, 7, 99]
    assert cfg["split_seed"] == 42


def test_missing_file_raises(tmp_path):
    with pytest.raises(SharedConfigError, match="not found"):
        load_shared_config(tmp_path / "nope.json")


def test_invalid_json_raises(tmp_path):
    p = tmp_path / "shared_config.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(SharedConfigError, match="not valid JSON"):
        load_shared_config(p)


def test_missing_key_raises(tmp_path):
    data = {k: v for k, v in VALID.items() if k != "test_rows"}
    with pytest.raises(SharedConfigError, match="test_rows"):
        load_shared_config(write(tmp_path, data))


def test_duplicate_seeds_raise(tmp_path):
    data = dict(VALID, experiment_seeds=[42, 42, 7])
    with pytest.raises(SharedConfigError, match="duplicates"):
        load_shared_config(write(tmp_path, data))


def test_non_integer_seed_raises(tmp_path):
    data = dict(VALID, experiment_seeds=[42, "1337"])
    with pytest.raises(SharedConfigError, match="experiment_seeds"):
        load_shared_config(write(tmp_path, data))


def test_bool_is_not_an_integer(tmp_path):
    data = dict(VALID, split_seed=True)
    with pytest.raises(SharedConfigError, match="split_seed"):
        load_shared_config(write(tmp_path, data))