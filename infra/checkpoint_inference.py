"""Validation-only inference from local Hugging Face checkpoints and parity checks.

This module handles the validation split ('val') only. Any other split is refused
because the test split is scored only through the guarded test evaluation path.

Rules enforced:
- No model downloads: local_files_only=True is always passed when loading checkpoints.
- No transcript text, audio_file names, or probability values are printed or logged.
- Checkpoint id2label class names are compared against the approved class list as
  sets; probabilities are always assigned by class name, never by positional index.
- torch and transformers are imported lazily inside predict_probabilities so this
  module can be imported and tested in environments without PyTorch installed.
"""
import json
import math
import numbers
from pathlib import Path

import pandas as pd

from infra.harness import HarnessError, evaluate_predictions, load_truth_table
from infra.predictions_file import (
    SUM_TOLERANCE,
    PredictionsFileError,
    read_predictions_file,
    write_predictions_file,
)
from infra.shared_config import load_shared_config
from infra.tfidf_baseline import CUSTOMER_STATE_EXCLUSIONS, load_classes_by_field

MACRO_F1_TOLERANCE = 1e-9
NEAR_MAX_DIFF_RATE = 0.01
NEAR_MAX_F1_DIFF = 0.005

_REPO_ROOT = Path(__file__).resolve().parents[1]


class CheckpointInferenceError(ValueError):
    """Checkpoint inference or parity comparison cannot proceed."""


def _refuse_non_val_split(split):
    if split != "val":
        raise CheckpointInferenceError(
            f"only split 'val' is supported (got {split!r}); "
            "the test split is scored only by the guarded test evaluation"
        )


def _is_valid_prob(value):
    return (
        isinstance(value, numbers.Real)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0.0 <= float(value) <= 1.0
    )


def _load_checkpoint_id2label(checkpoint_dir, field):
    config_path = Path(checkpoint_dir) / "config.json"
    if not config_path.is_file():
        raise CheckpointInferenceError(
            f"field {field}: checkpoint config.json not found in {checkpoint_dir}"
        )
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CheckpointInferenceError(
            f"field {field}: invalid JSON in {config_path} ({exc})"
        ) from exc

    raw_id2label = data.get("id2label")
    if not isinstance(raw_id2label, dict) or not raw_id2label:
        raise CheckpointInferenceError(
            f"field {field}: checkpoint config.json has no valid 'id2label' mapping"
        )

    id2label = {}
    for key, label in raw_id2label.items():
        try:
            idx = int(key)
        except (TypeError, ValueError) as exc:
            raise CheckpointInferenceError(
                f"field {field}: non-integer id2label key {key!r}"
            ) from exc
        if not isinstance(label, str) or not label.strip():
            raise CheckpointInferenceError(
                f"field {field}: invalid id2label class name {label!r}"
            )
        id2label[idx] = label

    if len(set(id2label.values())) != len(id2label):
        raise CheckpointInferenceError(
            f"field {field}: duplicate class names in checkpoint id2label"
        )
    return id2label


def _validate_id2label_against_classes(id2label, expected_classes, field):
    checkpoint_classes = set(id2label.values())
    approved_classes = set(expected_classes)
    if checkpoint_classes != approved_classes:
        missing = sorted(approved_classes - checkpoint_classes)
        extra = sorted(checkpoint_classes - approved_classes)
        raise CheckpointInferenceError(
            f"field {field}: checkpoint id2label classes do not match approved class list "
            f"(missing={missing}, extra={extra})"
        )


def predict_probabilities(texts, checkpoint_dir, *, batch_size=32, max_length=128):
    """Run local CPU inference for one checkpoint and return [{class_name: prob}]."""
    if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size <= 0:
        raise CheckpointInferenceError(f"batch_size must be a positive integer, got {batch_size!r}")
    if not isinstance(max_length, int) or isinstance(max_length, bool) or max_length <= 0:
        raise CheckpointInferenceError(f"max_length must be a positive integer, got {max_length!r}")
    if not texts:
        return []

    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    ckpt_path = Path(checkpoint_dir)
    device = torch.device("cpu")
    tokenizer = AutoTokenizer.from_pretrained(ckpt_path, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        ckpt_path, local_files_only=True
    )
    model.to(device)
    model.eval()

    id2label = {int(k): str(v) for k, v in model.config.id2label.items()}
    num_labels = len(id2label)

    results = []
    with torch.inference_mode():
        for start in range(0, len(texts), batch_size):
            batch = list(texts[start : start + batch_size])
            inputs = tokenizer(
                batch,
                truncation=True,
                max_length=max_length,
                padding=True,
                return_tensors="pt",
            )
            inputs = {k: v.to(device) for k, v in inputs.items()}
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1).cpu()
            for row_probs in probs:
                if len(row_probs) != num_labels:
                    raise CheckpointInferenceError(
                        f"checkpoint output width {len(row_probs)} does not match "
                        f"id2label size {num_labels}"
                    )
                results.append(
                    {id2label[idx]: float(row_probs[idx].item()) for idx in range(num_labels)}
                )
    return results


def predict_split(
    data_dir,
    checkpoint_dirs_by_field,
    *,
    split,
    predict_fn=predict_probabilities,
):
    """Predict class probabilities for all fields on the validation split only."""
    _refuse_non_val_split(split)

    data_dir = Path(data_dir)
    shared_config = load_shared_config(
        data_dir / "notebooks" / "training" / "shared_config.json"
    )
    classes_by_field = load_classes_by_field(data_dir / "final" / "class_weights.json")

    if not isinstance(checkpoint_dirs_by_field, dict) or set(checkpoint_dirs_by_field) != set(
        classes_by_field
    ):
        raise CheckpointInferenceError(
            "checkpoint_dirs_by_field must provide a checkpoint directory for every field: "
            f"expected {sorted(classes_by_field)}, got {sorted(checkpoint_dirs_by_field) if isinstance(checkpoint_dirs_by_field, dict) else type(checkpoint_dirs_by_field).__name__}"
        )

    for field, expected_classes in classes_by_field.items():
        id2label = _load_checkpoint_id2label(checkpoint_dirs_by_field[field], field)
        _validate_id2label_against_classes(id2label, expected_classes, field)

    val_csv_path = data_dir / "final" / "clean_training_val.csv"
    try:
        table = pd.read_csv(
            val_csv_path,
            usecols=["audio_file", "text_norm"],
            dtype=str,
            keep_default_na=False,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise CheckpointInferenceError(f"failed to read validation CSV: {exc}") from exc

    expected_rows = shared_config["val_rows"]
    if len(table) != expected_rows:
        raise CheckpointInferenceError(
            f"validation CSV has {len(table)} rows, expected {expected_rows}"
        )

    audio_files = table["audio_file"].tolist()
    texts = table["text_norm"].tolist()

    per_field_probs = {}
    for field, expected_classes in classes_by_field.items():
        raw_probs = predict_fn(texts, checkpoint_dirs_by_field[field])
        if len(raw_probs) != len(audio_files):
            raise CheckpointInferenceError(
                f"field {field}: predict_fn returned {len(raw_probs)} rows, "
                f"expected {len(audio_files)}"
            )
        expected_set = set(expected_classes)
        cleaned_rows = []
        for idx, prob_map in enumerate(raw_probs):
            if not isinstance(prob_map, dict) or set(prob_map) != expected_set:
                raise CheckpointInferenceError(
                    f"field {field}: row {idx} probability keys do not match approved class list"
                )
            row_clean = {}
            for cls_name in expected_classes:
                val = prob_map[cls_name]
                if not _is_valid_prob(val):
                    raise CheckpointInferenceError(
                        f"field {field}: row {idx} class {cls_name!r} has invalid probability"
                    )
                row_clean[cls_name] = float(val)
            total = sum(row_clean.values())
            if abs(total - 1.0) > SUM_TOLERANCE:
                raise CheckpointInferenceError(
                    f"field {field}: row {idx} probabilities sum to {total:.6f}, not 1"
                )
            cleaned_rows.append(row_clean)
        per_field_probs[field] = cleaned_rows

    rows = []
    for idx, audio_file in enumerate(audio_files):
        rows.append(
            {
                "audio_file": audio_file,
                "probabilities": {
                    field: per_field_probs[field][idx] for field in classes_by_field
                },
            }
        )
    return rows


def write_predictions(
    rows,
    out_path,
    *,
    run_id,
    model,
    seed,
    dataset_version,
    classes_by_field=None,
):
    """Write validation predictions outside the repository without overwriting."""
    out_path = Path(out_path)
    resolved_out = out_path.resolve()
    try:
        resolved_out.relative_to(_REPO_ROOT)
    except ValueError:
        pass
    else:
        raise CheckpointInferenceError(
            "out_path must be outside the repository"
        )

    if not isinstance(rows, list) or not rows:
        raise CheckpointInferenceError("rows must be a non-empty list")

    if classes_by_field is None:
        first_probs = rows[0].get("probabilities")
        if not isinstance(first_probs, dict) or not first_probs:
            raise CheckpointInferenceError(
                "rows[0] must contain non-empty 'probabilities' mapping"
            )
        classes_by_field = {
            field: list(prob_map.keys()) for field, prob_map in first_probs.items()
        }

    return write_predictions_file(
        path=out_path,
        run_id=run_id,
        model=model,
        split="val",
        seed=seed,
        dataset_version=dataset_version,
        rows=rows,
        classes_by_field=classes_by_field,
    )


def compare_with_submitted(
    ours_path,
    submitted_path_by_field,
    class_lists,
    *,
    data_dir=None,
    truth_rows=None,
):
    """Compare our validation predictions against per-field submitted prediction files."""
    if not isinstance(class_lists, dict) or not class_lists:
        raise CheckpointInferenceError("class_lists must be a non-empty dict")
    if not isinstance(submitted_path_by_field, dict) or set(submitted_path_by_field) != set(
        class_lists
    ):
        raise CheckpointInferenceError(
            "submitted_path_by_field must have the exact same fields as class_lists"
        )

    fields = list(class_lists.keys())
    if truth_rows is None:
        if data_dir is None:
            raise CheckpointInferenceError(
                "either data_dir or truth_rows must be provided"
            )
        val_csv_path = Path(data_dir) / "final" / "clean_training_val.csv"
        truth_rows = load_truth_table(val_csv_path, "val", fields)

    try:
        ours = read_predictions_file(
            Path(ours_path), class_lists, expected_split="val"
        )
    except PredictionsFileError as exc:
        raise CheckpointInferenceError(f"ours_path: {exc}") from exc

    exclusions = {}
    if "customer_state" in class_lists:
        exclusions["customer_state"] = CUSTOMER_STATE_EXCLUSIONS["customer_state"]

    try:
        ours_report = evaluate_predictions(
            split="val",
            truth_rows=truth_rows,
            pred_rows=ours["harness_rows"],
            classes_by_field=class_lists,
            exclusions_by_field=exclusions,
        )
    except HarnessError as exc:
        raise CheckpointInferenceError(f"evaluating ours_path failed: {exc}") from exc

    ours_labels_by_audio = {row["audio_file"]: row for row in ours["harness_rows"]}
    ours_probs_by_audio = ours["probabilities"]

    submitted_cache = {}
    submitted_reports = {}
    for field, sub_path in submitted_path_by_field.items():
        key = str(Path(sub_path).resolve())
        if key not in submitted_cache:
            try:
                loaded_sub = read_predictions_file(
                    Path(sub_path), class_lists, expected_split="val"
                )
            except PredictionsFileError as exc:
                raise CheckpointInferenceError(f"submitted ({field}): {exc}") from exc
            try:
                sub_report = evaluate_predictions(
                    split="val",
                    truth_rows=truth_rows,
                    pred_rows=loaded_sub["harness_rows"],
                    classes_by_field=class_lists,
                    exclusions_by_field=exclusions,
                )
            except HarnessError as exc:
                raise CheckpointInferenceError(
                    f"evaluating submitted ({field}) failed: {exc}"
                ) from exc
            submitted_cache[key] = loaded_sub
            submitted_reports[key] = sub_report

    results = {}
    for field, classes in class_lists.items():
        key = str(Path(submitted_path_by_field[field]).resolve())
        sub = submitted_cache[key]
        sub_report = submitted_reports[key]

        sub_labels_by_audio = {row["audio_file"]: row for row in sub["harness_rows"]}
        sub_probs_by_audio = sub["probabilities"]

        if set(ours_labels_by_audio) != set(sub_labels_by_audio):
            raise CheckpointInferenceError(
                f"field {field}: audio_file sets do not match between ours and submitted"
            )

        audio_files = list(ours_labels_by_audio.keys())
        n_rows = len(audio_files)
        n_argmax_diff = 0
        max_abs_diff = 0.0
        sum_abs_diff = 0.0
        n_probs = 0

        for af in audio_files:
            if ours_labels_by_audio[af][field] != sub_labels_by_audio[af][field]:
                n_argmax_diff += 1
            ours_p = ours_probs_by_audio[af][field]
            sub_p = sub_probs_by_audio[af][field]
            for cls_name in classes:
                diff = abs(float(ours_p[cls_name]) - float(sub_p[cls_name]))
                if diff > max_abs_diff:
                    max_abs_diff = diff
                sum_abs_diff += diff
                n_probs += 1

        ours_f1 = float(ours_report["fields"][field]["macro"]["f1"])
        sub_f1 = float(sub_report["fields"][field]["macro"]["f1"])
        f1_diff = abs(ours_f1 - sub_f1)

        results[field] = {
            "n_rows": n_rows,
            "n_argmax_diff": n_argmax_diff,
            "max_abs_prob_diff": max_abs_diff,
            "mean_abs_prob_diff": sum_abs_diff / n_probs if n_probs else 0.0,
            "ours_macro_f1": ours_f1,
            "submitted_macro_f1": sub_f1,
            "macro_f1_diff": f1_diff,
            "macro_f1_equal": f1_diff <= MACRO_F1_TOLERANCE,
        }

    return results


def classify_parity(per_field_results):
    """Classify overall parity as PARITY, NEAR, or NO PARITY."""
    if not per_field_results:
        raise CheckpointInferenceError("per_field_results must not be empty")
    if all(
        r["n_argmax_diff"] == 0 and r["macro_f1_equal"]
        for r in per_field_results.values()
    ):
        return "PARITY"
    if all(
        (r["n_argmax_diff"] / r["n_rows"] <= NEAR_MAX_DIFF_RATE)
        and (r["macro_f1_diff"] < NEAR_MAX_F1_DIFF)
        for r in per_field_results.values()
    ):
        return "NEAR"
    return "NO PARITY"
