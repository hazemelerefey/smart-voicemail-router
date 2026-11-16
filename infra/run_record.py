"""The run record: one JSON file per experiment.

Hazem's run record has: run ID, hypothesis, changed factor, held-constant
conditions, measures (macro-F1 per field), and artifacts. This module builds
exactly that, plus the environment and the dataset version, so any number can
be traced and reproduced.

What is computed, not typed by hand:
- held_constant is derived from the config (everything except the changed factor).
- aggregate (mean and std over seeds) is computed from the per-seed results.
- the check that exactly one factor changed compares against a reference config.

`exceptions` lists every rule that left rows out of a field's score (for example the
`unclear` rows of customer_state). It is taken from the harness report, and it is
required: pass an empty list when nothing was left out, so it is never forgotten.
"""
import importlib.metadata
import json
import math
import platform
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath

from infra.experiment_config import changed_fields, validate_against_shared
from infra.seeds import summarize_metrics

SCHEMA_VERSION = 2
EVALUATED_SPLITS = ("val", "test")

# The metric names in Hazem's make_result_record (training pipeline skeleton).
REQUIRED_METRICS = (
    "complaint_category_macro_f1",
    "complaint_urgency_macro_f1",
    "customer_state_macro_f1",
    "churn_risk_macro_f1",
)

TOP_LEVEL_KEYS = (
    "schema_version",
    "run_id",
    "hypothesis",
    "changed_factor",
    "held_constant",
    "reference_run_id",
    "config",
    "dataset",
    "evaluated_split",
    "exceptions",
    "per_seed",
    "aggregate",
    "artifacts",
    "environment",
    "created_utc",
)

_RUN_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class RunRecordError(ValueError):
    """The run record is invalid."""


def _is_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _is_text(value):
    return isinstance(value, str) and bool(value.strip())


def _check_run_id(run_id):
    if not isinstance(run_id, str) or not _RUN_ID.match(run_id):
        raise RunRecordError(
            f"run_id must be letters, digits, '-' or '_' (for example '001'), got {run_id!r}"
        )


def make_seed_result(run_id, config, evaluated_split, seed, metrics):
    """One seed's result, in the shape of make_result_record in the skeleton."""
    return {
        "run_id": run_id,
        "model": config.model,
        "split": evaluated_split,
        "seed": seed,
        "metrics": dict(metrics),
    }


def collect_environment(device):
    if not _is_text(device):
        raise RunRecordError("device must say what hardware was used, for example 'cpu'")
    packages = {}
    for name in ("numpy", "pandas", "scikit-learn", "torch", "transformers"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "device": device,
        "packages": packages,
    }


def _flat_config(config):
    """Config fields as one flat dict, with other_hyperparameters.<key> entries."""
    d = config.to_dict()
    flat = {k: v for k, v in d.items() if k != "other_hyperparameters"}
    for key, value in d["other_hyperparameters"].items():
        flat[f"other_hyperparameters.{key}"] = value
    return flat


def _check_artifacts(artifacts):
    if not isinstance(artifacts, dict):
        raise RunRecordError("artifacts must be a dict of name -> list of relative paths")
    for name, paths in artifacts.items():
        if not isinstance(paths, list) or not all(_is_text(p) for p in paths):
            raise RunRecordError(f"artifacts[{name!r}] must be a list of path strings")
        for p in paths:
            if PurePosixPath(p).is_absolute() or PureWindowsPath(p).is_absolute():
                raise RunRecordError(f"artifact path must be relative, got {p!r}")
            if ".." in PurePosixPath(p.replace("\\", "/")).parts:
                raise RunRecordError(f"artifact path must not contain '..', got {p!r}")
            if "transcript" in p.lower():
                raise RunRecordError(
                    f"artifact name must not contain 'transcript' (git ignores such files "
                    f"and they may hold raw text), got {p!r}"
                )


def _check_per_seed(per_seed, run_id, config, evaluated_split, shared_config):
    if not isinstance(per_seed, list):
        raise RunRecordError("per_seed must be a list of seed results")
    seeds = [r.get("seed") if isinstance(r, dict) else None for r in per_seed]
    if seeds != list(shared_config["experiment_seeds"]):
        raise RunRecordError(
            f"every experiment must run all seeds in order: expected "
            f"{shared_config['experiment_seeds']}, got {seeds}"
        )
    for r in per_seed:
        expected = {"run_id": run_id, "model": config.model, "split": evaluated_split}
        for key, value in expected.items():
            if r.get(key) != value:
                raise RunRecordError(
                    f"seed {r['seed']}: {key} is {r.get(key)!r}, expected {value!r}"
                )
        metrics = r.get("metrics")
        if not isinstance(metrics, dict):
            raise RunRecordError(f"seed {r['seed']}: metrics must be a dict")
        missing = [m for m in REQUIRED_METRICS if m not in metrics]
        if missing:
            raise RunRecordError(f"seed {r['seed']}: missing metrics {missing}")
        for name, value in metrics.items():
            if not _is_number(value):
                raise RunRecordError(f"seed {r['seed']}: {name} must be a finite number, got {value!r}")
            if name.endswith("_macro_f1") and not 0.0 <= value <= 1.0:
                raise RunRecordError(f"seed {r['seed']}: {name} must be between 0 and 1, got {value}")


_EXCEPTION_KEYS = {
    "field", "excluded_labels", "rows_excluded", "n_scored", "n_total_rows", "reason",
}


def _check_exceptions(exceptions, per_seed, evaluated_split, shared_config):
    """Each exception is one entry of the harness report's `exceptions` list."""
    if not isinstance(exceptions, list):
        raise RunRecordError("exceptions must be a list (an empty list when nothing was left out)")
    expected_rows = shared_config[f"{evaluated_split}_rows"]
    metric_names = set(per_seed[0]["metrics"])
    seen = set()
    for e in exceptions:
        if not isinstance(e, dict) or set(e) != _EXCEPTION_KEYS:
            raise RunRecordError(f"each exception needs exactly the keys {sorted(_EXCEPTION_KEYS)}")
        field = e["field"]
        if not _is_text(field) or f"{field}_macro_f1" not in metric_names:
            raise RunRecordError(f"exception for {field!r}: no metric {field}_macro_f1 in this run")
        if field in seen:
            raise RunRecordError(f"more than one exception for {field!r}")
        seen.add(field)
        labels = e["excluded_labels"]
        if not isinstance(labels, list) or not labels or not all(_is_text(x) for x in labels):
            raise RunRecordError(f"exception for {field}: excluded_labels must be a non-empty list of strings")
        if not _is_text(e["reason"]):
            raise RunRecordError(f"exception for {field} needs a reason")
        counts = [e["rows_excluded"], e["n_scored"], e["n_total_rows"]]
        if not all(isinstance(c, int) and not isinstance(c, bool) and c >= 0 for c in counts):
            raise RunRecordError(f"exception for {field}: the row counts must be non-negative integers")
        if e["rows_excluded"] + e["n_scored"] != e["n_total_rows"]:
            raise RunRecordError(
                f"exception for {field}: rows_excluded + n_scored must equal n_total_rows"
            )
        if e["n_total_rows"] != expected_rows:
            raise RunRecordError(
                f"exception for {field}: n_total_rows is {e['n_total_rows']} but the shared config "
                f"has {expected_rows} rows in {evaluated_split}"
            )


def build_run_record(
    run_id,
    hypothesis,
    config,
    shared_config,
    per_seed,
    evaluated_split,
    artifacts,
    device,
    exceptions,
    reference_config=None,
    changed_factor=None,
    reference_run_id=None,
    ddof=1,
    created_utc=None,
):
    _check_run_id(run_id)
    if not _is_text(hypothesis):
        raise RunRecordError("hypothesis must be a non-empty string")
    if evaluated_split not in EVALUATED_SPLITS:
        raise RunRecordError(f"evaluated_split must be one of {EVALUATED_SPLITS}, got {evaluated_split!r}")
    validate_against_shared(config, shared_config)

    # One factor at a time.
    if reference_config is None:
        if changed_factor is not None:
            raise RunRecordError("changed_factor needs a reference_config to check it against")
    else:
        diff = changed_fields(reference_config, config)
        if len(diff) > 1:
            raise RunRecordError(f"more than one factor changed: {diff}")
        if not diff:
            raise RunRecordError("nothing changed compared to the reference config")
        if changed_factor != diff[0]:
            raise RunRecordError(
                f"changed_factor is {changed_factor!r} but the configs differ in {diff[0]!r}"
            )

    _check_per_seed(per_seed, run_id, config, evaluated_split, shared_config)
    _check_exceptions(exceptions, per_seed, evaluated_split, shared_config)
    _check_artifacts(artifacts)
    environment = collect_environment(device)

    held = {k: v for k, v in _flat_config(config).items() if k != changed_factor}
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "hypothesis": hypothesis,
        "changed_factor": changed_factor,
        "held_constant": held,
        "reference_run_id": reference_run_id,
        "config": config.to_dict(),
        "dataset": {
            "version": shared_config["dataset_version"],
            "rows": {
                "train": shared_config["train_rows"],
                "val": shared_config["val_rows"],
                "test": shared_config["test_rows"],
            },
        },
        "evaluated_split": evaluated_split,
        "exceptions": exceptions,
        "per_seed": per_seed,
        "aggregate": summarize_metrics([r["metrics"] for r in per_seed], ddof=ddof),
        "artifacts": artifacts,
        "environment": environment,
        "created_utc": created_utc or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def record_path(runs_dir, run_id):
    return Path(runs_dir) / f"exp_{run_id}" / "run_record.json"


def save_run_record(record, runs_dir):
    """Write runs_dir/exp_<run_id>/run_record.json. Never overwrites."""
    _check_run_id(record.get("run_id"))
    path = record_path(runs_dir, record["run_id"])
    if path.exists():
        raise FileExistsError(f"{path} already exists; run records are not overwritten")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path


def load_run_record(path):
    path = Path(path)
    if not path.is_file():
        raise RunRecordError(f"run record not found: {path}")
    try:
        with path.open(encoding="utf-8") as f:
            record = json.load(f)
    except json.JSONDecodeError as exc:
        raise RunRecordError(f"run record is not valid JSON: {path} ({exc})")
    if not isinstance(record, dict):
        raise RunRecordError("run record must be a JSON object")
    missing = [k for k in TOP_LEVEL_KEYS if k not in record]
    if missing:
        raise RunRecordError(f"run record is missing keys: {missing}")
    if record["schema_version"] != SCHEMA_VERSION:
        raise RunRecordError(f"unsupported schema_version {record['schema_version']!r}")
    return record