"""The experiment configuration format.

Hazem's example config has these fields: model, learning rate, batch size,
epochs, seed, dataset version, split. This module keeps exactly those fields.

One experiment = one config, run once per seed. The seeds are NOT stored in
the config: they come from shared_config.json. for_seed(seed) returns the
per-run config (with the seed added), which is the shape in Hazem's example.

Fields that do not apply to a model are left as None. For example, the TF-IDF
baseline has no learning rate, batch size or epochs. Anything model specific
beyond those three (for example max_features) goes in other_hyperparameters.
"""
import json
import math
from dataclasses import dataclass, field, fields
from pathlib import Path

# Only the train split may be used for training. This protects the test set.
ALLOWED_SPLITS = ("train",)

NAMED_FIELDS = (
    "model",
    "dataset_version",
    "split",
    "learning_rate",
    "batch_size",
    "epochs",
    "other_hyperparameters",
)

# Names that other_hyperparameters must not reuse, so nothing is set twice.
RESERVED_KEYS = frozenset(
    ("seed", "model", "dataset_version", "split", "learning_rate", "batch_size", "epochs")
)


class ExperimentConfigError(ValueError):
    """The experiment config is invalid."""


def _is_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True)
class ExperimentConfig:
    model: str
    dataset_version: str
    split: str = "train"
    learning_rate: float = None
    batch_size: int = None
    epochs: int = None
    other_hyperparameters: dict = field(default_factory=dict)

    def __post_init__(self):
        for name in ("model", "dataset_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ExperimentConfigError(f"{name} must be a non-empty string, got {value!r}")
        if self.split not in ALLOWED_SPLITS:
            raise ExperimentConfigError(
                f"split must be one of {ALLOWED_SPLITS}, got {self.split!r}"
            )
        if self.learning_rate is not None and not (
            _is_number(self.learning_rate) and self.learning_rate > 0
        ):
            raise ExperimentConfigError(
                f"learning_rate must be a positive number or None, got {self.learning_rate!r}"
            )
        for name in ("batch_size", "epochs"):
            value = getattr(self, name)
            if value is not None and not (_is_int(value) and value > 0):
                raise ExperimentConfigError(
                    f"{name} must be a positive integer or None, got {value!r}"
                )
        other = self.other_hyperparameters
        if not isinstance(other, dict) or not all(isinstance(k, str) for k in other):
            raise ExperimentConfigError("other_hyperparameters must be a dict with string keys")
        reused = sorted(RESERVED_KEYS & set(other))
        if reused:
            raise ExperimentConfigError(
                f"other_hyperparameters must not contain {reused}; "
                "use the named fields (the seed comes from shared_config.json)"
            )
        try:
            json.dumps(other)
        except (TypeError, ValueError) as exc:
            raise ExperimentConfigError(f"other_hyperparameters must be JSON serializable: {exc}")

    def to_dict(self):
        return {name: getattr(self, name) for name in NAMED_FIELDS}

    def for_seed(self, seed):
        """The per-run config: the same fields plus the seed."""
        if not _is_int(seed) or seed < 0:
            raise ExperimentConfigError(f"seed must be a non-negative integer, got {seed!r}")
        return {**self.to_dict(), "seed": seed}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ExperimentConfigError("experiment config must be a JSON object")
        if "seed" in data:
            raise ExperimentConfigError(
                "do not put 'seed' in the experiment config: "
                "seeds come from shared_config.json, use for_seed(seed)"
            )
        unknown = sorted(set(data) - {f.name for f in fields(cls)})
        if unknown:
            raise ExperimentConfigError(f"unknown config fields: {unknown}")
        return cls(**data)


def validate_against_shared(config, shared_config):
    """The experiment must use the same dataset version as the team config."""
    if config.dataset_version != shared_config["dataset_version"]:
        raise ExperimentConfigError(
            f"dataset_version {config.dataset_version!r} does not match "
            f"shared_config {shared_config['dataset_version']!r}"
        )


def load_experiment_config(path, shared_config=None):
    path = Path(path)
    if not path.is_file():
        raise ExperimentConfigError(f"experiment config not found: {path}")
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ExperimentConfigError(f"experiment config is not valid JSON: {path} ({exc})")
    config = ExperimentConfig.from_dict(data)
    if shared_config is not None:
        validate_against_shared(config, shared_config)
    return config


def save_experiment_config(config, path, overwrite=False):
    """Write the config as JSON. Refuses to overwrite, so a config never changes silently."""
    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists; configs are not overwritten")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config.to_dict(), indent=2) + "\n", encoding="utf-8")


def changed_fields(a, b):
    """Names of the fields that differ between two configs (sorted).

    Keys inside other_hyperparameters are reported as other_hyperparameters.<key>.
    """
    da, db = a.to_dict(), b.to_dict()
    changed = [n for n in NAMED_FIELDS if n != "other_hyperparameters" and da[n] != db[n]]
    oa, ob = da["other_hyperparameters"], db["other_hyperparameters"]
    for key in set(oa) | set(ob):
        if key not in oa or key not in ob or oa[key] != ob[key]:
            changed.append(f"other_hyperparameters.{key}")
    return sorted(changed)