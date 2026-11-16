"""The predictions file: what a model hands to the evaluation harness.

One JSON file per seed and per split. The format was agreed with Hazem:
- the header: run_id, model, split, seed and dataset_version;
- `rows`: for every audio_file the predicted label of each field, and the
  probability of every class of every field. Probabilities are forced for ALL four
  fields, none is optional (the churn threshold and the average precision need them).
- the labels are class names from the approved lists only. There is no text and no
  transcript in the file, and a key that is not in the format is rejected.

A row is keyed by (split, audio_file). The split is written once in the header, and
audio_file is unique inside the file, because the same name can appear in different
splits.

The class lists are never guessed: they are passed in (customer_state has the 4
classes calm, frustrated, mad and satisfied, so `unclear` is not a class here). The
probabilities of a field must name exactly the classes of that field.

The label of a row is the class with the highest probability. The writer computes it
from the probabilities, so a file cannot say one thing in `labels` and another in
`probabilities`. The reader checks that they agree.

The reader gives back rows the harness can score directly, and the probabilities
separately. What is predicted for a row whose true customer_state is `unclear` is
still one of the 4 classes, as the harness requires.
"""
import json
import math
import numbers
import re
from pathlib import Path

SCHEMA_VERSION = 1
PREDICTED_SPLITS = ("val", "test")
SUM_TOLERANCE = 1e-4  # probabilities of one field must add up to 1 within this

TOP_LEVEL_KEYS = (
    "schema_version", "run_id", "model", "split", "seed", "dataset_version", "rows",
)
ROW_KEYS = ("audio_file", "labels", "probabilities")

_RUN_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class PredictionsFileError(ValueError):
    """The predictions file is invalid."""


def _is_text(value):
    return isinstance(value, str) and bool(value.strip())


def _is_number(value):
    return (
        isinstance(value, numbers.Real)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _check_classes_by_field(classes_by_field):
    if not isinstance(classes_by_field, dict) or not classes_by_field:
        raise PredictionsFileError("classes_by_field must be a non-empty dict of field -> class list")
    for field, classes in classes_by_field.items():
        if not _is_text(field):
            raise PredictionsFileError(f"field names must be non-empty strings, got {field!r}")
        if not isinstance(classes, (list, tuple)) or not classes or not all(_is_text(c) for c in classes):
            raise PredictionsFileError(f"classes of {field} must be a non-empty list of strings")
        if len(set(classes)) != len(classes):
            raise PredictionsFileError(f"classes of {field} has duplicates: {list(classes)}")


def _check_header(run_id, model, split, seed, dataset_version):
    if not isinstance(run_id, str) or not _RUN_ID.match(run_id):
        raise PredictionsFileError(
            f"run_id must be letters, digits, '-' or '_' (for example '001'), got {run_id!r}"
        )
    if not _is_text(model):
        raise PredictionsFileError("model must be a non-empty string")
    if split not in PREDICTED_SPLITS:
        raise PredictionsFileError(f"split must be one of {PREDICTED_SPLITS}, got {split!r}")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise PredictionsFileError(f"seed must be a non-negative integer, got {seed!r}")
    if not _is_text(dataset_version):
        raise PredictionsFileError("dataset_version must be a non-empty string")


def _check_row(i, row, classes_by_field):
    if not isinstance(row, dict) or set(row) != set(ROW_KEYS):
        raise PredictionsFileError(
            f"rows[{i}] must have exactly the keys {list(ROW_KEYS)} "
            f"(no text or transcript is allowed in the file)"
        )
    name = row["audio_file"]
    if not _is_text(name):
        raise PredictionsFileError(f"rows[{i}] needs a non-empty string 'audio_file'")
    where = f"rows[{i}] ({name})"
    fields = set(classes_by_field)
    labels, probabilities = row["labels"], row["probabilities"]
    if not isinstance(labels, dict) or set(labels) != fields:
        raise PredictionsFileError(f"{where}: labels must have exactly the fields {sorted(fields)}")
    if not isinstance(probabilities, dict) or set(probabilities) != fields:
        raise PredictionsFileError(
            f"{where}: probabilities are forced for every field, exactly {sorted(fields)}"
        )
    for field, classes in classes_by_field.items():
        label = labels[field]
        if label not in classes:
            raise PredictionsFileError(
                f"{where}: label {label!r} is not in the class list of {field} {list(classes)}"
            )
        p = probabilities[field]
        if not isinstance(p, dict) or set(p) != set(classes):
            raise PredictionsFileError(
                f"{where}: probabilities of {field} must name exactly the classes {list(classes)}"
            )
        for c, value in p.items():
            if not _is_number(value) or not 0.0 <= value <= 1.0:
                raise PredictionsFileError(
                    f"{where}: probability of {field}/{c} must be a number between 0 and 1, got {value!r}"
                )
        total = sum(p.values())
        if abs(total - 1.0) > SUM_TOLERANCE:
            raise PredictionsFileError(
                f"{where}: probabilities of {field} add up to {total:.6f}, not 1"
            )
        if p[label] < max(p.values()):
            raise PredictionsFileError(
                f"{where}: label {label!r} of {field} is not the most probable class"
            )


def _check_rows(rows, classes_by_field):
    if not isinstance(rows, list) or not rows:
        raise PredictionsFileError("rows must be a non-empty list")
    seen = set()
    for i, row in enumerate(rows):
        _check_row(i, row, classes_by_field)
        if row["audio_file"] in seen:
            raise PredictionsFileError(f"the audio_file {row['audio_file']!r} appears more than once")
        seen.add(row["audio_file"])


def predictions_path(runs_dir, run_id, split, seed):
    """runs_dir/exp_<run_id>/predictions_<split>_seed<seed>.json"""
    _check_header(run_id, "model", split, seed, "dataset_version")
    return Path(runs_dir) / f"exp_{run_id}" / f"predictions_{split}_seed{seed}.json"


def write_predictions_file(path, run_id, model, split, seed, dataset_version, rows, classes_by_field):
    """Write the file. `rows` is a list of {"audio_file": ..., "probabilities": {field: {class: p}}}.

    The labels are computed here as the most probable class of each field (the first
    one in the class list if two are equal). Never overwrites an existing file.
    """
    _check_classes_by_field(classes_by_field)
    _check_header(run_id, model, split, seed, dataset_version)
    if not isinstance(rows, list):
        raise PredictionsFileError("rows must be a list")
    full_rows = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"audio_file", "probabilities"}:
            raise PredictionsFileError(f"rows[{i}] must have exactly 'audio_file' and 'probabilities'")
        probabilities = row["probabilities"]
        if not isinstance(probabilities, dict) or set(probabilities) != set(classes_by_field):
            raise PredictionsFileError(
                f"rows[{i}] ({row['audio_file']}): probabilities are forced for every field, "
                f"exactly {sorted(classes_by_field)}"
            )
        labels, clean = {}, {}
        for field, classes in classes_by_field.items():
            p = probabilities[field]
            if not isinstance(p, dict) or set(p) != set(classes):
                raise PredictionsFileError(
                    f"rows[{i}] ({row['audio_file']}): probabilities of {field} must name exactly "
                    f"the classes {list(classes)}"
                )
            if not all(_is_number(v) for v in p.values()):
                raise PredictionsFileError(
                    f"rows[{i}] ({row['audio_file']}): probabilities of {field} must be finite numbers"
                )
            clean[field] = {c: float(p[c]) for c in classes}
            labels[field] = max(classes, key=lambda c: clean[field][c])  # first class wins a tie
        full_rows.append({"audio_file": row["audio_file"], "labels": labels, "probabilities": clean})

    data = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "model": model,
        "split": split,
        "seed": seed,
        "dataset_version": dataset_version,
        "rows": full_rows,
    }
    _check_rows(data["rows"], classes_by_field)  # the same checks the reader makes

    path = Path(path)
    if path.exists():
        raise FileExistsError(f"{path} already exists; predictions files are not overwritten")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")
    return path


def read_predictions_file(path, classes_by_field, *, expected_split):
    """Read and check a predictions file.

    `expected_split` has no default: the caller says which split it is scoring, so a
    file of one split is never scored as another.

    Returns {"meta": header, "harness_rows": [{"audio_file", <field>: label, ...}],
    "probabilities": {audio_file: {field: {class: p}}}}.
    """
    _check_classes_by_field(classes_by_field)
    if expected_split not in PREDICTED_SPLITS:
        raise PredictionsFileError(f"expected_split must be one of {PREDICTED_SPLITS}, got {expected_split!r}")
    path = Path(path)
    if not path.is_file():
        raise PredictionsFileError(f"predictions file not found: {path}")
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise PredictionsFileError(f"predictions file is not valid JSON: {path} ({exc})")
    if not isinstance(data, dict):
        raise PredictionsFileError("predictions file must be a JSON object")
    if set(data) != set(TOP_LEVEL_KEYS):
        extra = sorted(set(data) - set(TOP_LEVEL_KEYS))
        missing = sorted(set(TOP_LEVEL_KEYS) - set(data))
        raise PredictionsFileError(
            f"predictions file must have exactly the keys {list(TOP_LEVEL_KEYS)}: "
            f"missing {missing}, not allowed {extra}"
        )
    if data["schema_version"] != SCHEMA_VERSION:
        raise PredictionsFileError(f"unsupported schema_version {data['schema_version']!r}")
    _check_header(data["run_id"], data["model"], data["split"], data["seed"], data["dataset_version"])
    if data["split"] != expected_split:
        raise PredictionsFileError(
            f"this file is for split {data['split']!r} but {expected_split!r} was expected"
        )
    _check_rows(data["rows"], classes_by_field)

    harness_rows = [{"audio_file": r["audio_file"], **r["labels"]} for r in data["rows"]]
    probabilities = {r["audio_file"]: r["probabilities"] for r in data["rows"]}
    meta = {k: data[k] for k in TOP_LEVEL_KEYS if k != "rows"}
    meta["n_rows"] = len(data["rows"])
    return {"meta": meta, "harness_rows": harness_rows, "probabilities": probabilities}