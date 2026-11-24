"""Read and validate the team's shared_config.json (defined by Hazem).

This module only READS the file. It never writes it and never keeps its own
copy of the values, so if Hazem changes the file, everyone sees the change.
"""
import json
from pathlib import Path

REQUIRED_KEYS = (
    "split_seed",
    "experiment_seeds",
    "max_seq_len",
    "split_ratio",
    "dataset_version",
    "dataset",
    "train_rows",
    "val_rows",
    "test_rows",
)

INT_KEYS = ("split_seed", "max_seq_len", "train_rows", "val_rows", "test_rows")


class SharedConfigError(ValueError):
    """The shared config is missing, unreadable, or has an invalid value."""


def _is_int(value):
    # bool is a subclass of int in Python, but True/False are not valid numbers here.
    return isinstance(value, int) and not isinstance(value, bool)


def load_shared_config(path):
    path = Path(path)
    if not path.is_file():
        raise SharedConfigError(f"shared config not found: {path}")
    try:
        with path.open(encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as exc:
        raise SharedConfigError(f"shared config is not valid JSON: {path} ({exc})")

    missing = [k for k in REQUIRED_KEYS if k not in cfg]
    if missing:
        raise SharedConfigError(f"shared config is missing keys: {missing}")

    for key in INT_KEYS:
        if not _is_int(cfg[key]):
            raise SharedConfigError(f"{key} must be an integer, got {cfg[key]!r}")

    seeds = cfg["experiment_seeds"]
    if not isinstance(seeds, list) or not seeds or not all(_is_int(s) for s in seeds):
        raise SharedConfigError(
            f"experiment_seeds must be a non-empty list of integers, got {seeds!r}"
        )
    if len(set(seeds)) != len(seeds):
        raise SharedConfigError(f"experiment_seeds has duplicates: {seeds}")

    return cfg