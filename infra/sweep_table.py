"""Single-seed validation comparison table for learning-rate sweeps.

Scores single-seed validation prediction files of the SAME normalized model on
the SAME dataset version using the evaluation harness (with the customer_state
exclusion for 'unclear') and formats a sorted comparison table for choosing a
learning rate.

This module never reads or scores the test split, never writes any file, and
never prints audio_file names, probabilities, labels, or transcript text.
"""
from pathlib import Path

from infra.harness import HarnessError, evaluate_predictions, load_truth_table
from infra.once_guard import GuardError, normalize_model_name
from infra.predictions_file import PredictionsFileError, read_predictions_file
from infra.shared_config import load_shared_config
from infra.tfidf_baseline import CUSTOMER_STATE_EXCLUSIONS, load_classes_by_field

FIELDS = (
    "complaint_category",
    "complaint_urgency",
    "customer_state",
    "churn_risk",
)


class SweepTableError(ValueError):
    """The single-seed sweep comparison cannot be built."""


def seed_comparison(data_dir, items, *, seed=42):
    """Score single-seed validation prediction files of one model for LR selection.

    `items` is a non-empty list of (label, predictions_file_path) pairs.
    Refuses any file whose split is not 'val', whose header seed differs from
    `seed`, or whose dataset_version or normalized model name differs across items.
    """
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise SweepTableError(f"seed must be a non-negative integer, got {seed!r}")
    if not isinstance(items, (list, tuple)) or not items:
        raise SweepTableError("items must be a non-empty list of (label, path) pairs")

    data_dir = Path(data_dir)
    shared_config = load_shared_config(
        data_dir / "notebooks" / "training" / "shared_config.json"
    )
    classes_by_field = load_classes_by_field(data_dir / "final" / "class_weights.json")
    fields = list(classes_by_field.keys())

    val_csv_path = data_dir / "final" / "clean_training_val.csv"
    truth_rows = load_truth_table(val_csv_path, "val", fields)
    if len(truth_rows) != shared_config["val_rows"]:
        raise SweepTableError(
            f"val has {len(truth_rows)} rows, expected {shared_config['val_rows']}"
        )

    rows = []
    expected_dataset_version = None
    expected_model_key = None
    expected_model_label = None

    for item in items:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise SweepTableError("every item must be a (label, predictions_file_path) pair")
        label, pred_path = item
        if not isinstance(label, str) or not label.strip():
            raise SweepTableError(f"label must be a non-empty string, got {label!r}")

        try:
            loaded = read_predictions_file(
                Path(pred_path),
                classes_by_field,
                expected_split="val",
            )
        except PredictionsFileError as exc:
            raise SweepTableError(f"{label}: {exc}") from exc

        meta = loaded["meta"]
        if meta["split"] != "val":
            raise SweepTableError(
                f"{label}: split is {meta['split']!r}, only 'val' is allowed"
            )
        if meta["seed"] != seed:
            raise SweepTableError(
                f"{label}: header seed is {meta['seed']!r}, expected {seed!r}"
            )

        try:
            model_key = normalize_model_name(meta["model"])
        except GuardError as exc:
            raise SweepTableError(f"{label}: {exc}") from exc

        if expected_dataset_version is None:
            expected_dataset_version = meta["dataset_version"]
            expected_model_key = model_key
            expected_model_label = meta["model"]
        else:
            if meta["dataset_version"] != expected_dataset_version:
                raise SweepTableError(
                    f"{label}: dataset_version is {meta['dataset_version']!r}, "
                    f"expected {expected_dataset_version!r}"
                )
            if model_key != expected_model_key:
                raise SweepTableError(
                    f"{label}: model {meta['model']!r} (normalized {model_key!r}) "
                    f"differs from {expected_model_label!r} (normalized {expected_model_key!r}); "
                    "a sweep table compares one model only"
                )

        try:
            report = evaluate_predictions(
                split="val",
                truth_rows=truth_rows,
                pred_rows=loaded["harness_rows"],
                classes_by_field=classes_by_field,
                exclusions_by_field=CUSTOMER_STATE_EXCLUSIONS,
            )
        except HarnessError as exc:
            raise SweepTableError(f"{label}: {exc}") from exc

        per_field_f1 = {
            f: float(report["fields"][f]["macro"]["f1"]) for f in fields
        }
        rows.append({
            "label": label,
            "run_id": meta["run_id"],
            "model": meta["model"],
            "model_key": model_key,
            "seed": seed,
            "dataset_version": meta["dataset_version"],
            "macro_f1": per_field_f1,
            "combined_macro_f1": report["combined_macro_f1"],
        })

    return rows


def format_seed_table(rows):
    """Format rows returned by seed_comparison() as a plain-text table sorted by combined macro-F1."""
    if not rows:
        raise SweepTableError("rows must not be empty")
    seed_val = rows[0]["seed"]
    sorted_rows = sorted(
        rows, key=lambda r: r["combined_macro_f1"]["mean"], reverse=True
    )

    lines = [
        f"single seed ({seed_val}), no standard deviation: "
        "for choosing a learning rate only, not a final result",
        "",
    ]
    header = (
        f"{'label':<24} {'complaint_category':<20} {'complaint_urgency':<19} "
        f"{'customer_state':<16} {'churn_risk':<12} {'combined_macro_f1':<18}"
    )
    lines.append(header)
    lines.append("-" * len(header))

    for row in sorted_rows:
        mf = row["macro_f1"]
        comb = row["combined_macro_f1"]["mean"]
        lines.append(
            f"{row['label']:<24} "
            f"{mf['complaint_category']:<20.6f} "
            f"{mf['complaint_urgency']:<19.6f} "
            f"{mf['customer_state']:<16.6f} "
            f"{mf['churn_risk']:<12.6f} "
            f"{comb:<18.6f}"
        )

    return "\n".join(lines)
