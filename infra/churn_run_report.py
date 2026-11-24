"""Connect churn_metrics to the 5-seed validation prediction files of a run.

Loads shared_config.json, class_weights.json, validation truth labels for the
target binary field only (never loading transcript text), and the five
validation prediction files in seed order. Computes per-seed churn metrics with
validation-tuned thresholds and summarizes them across seeds.

This module never reads or scores the test split, never writes any file, and
never prints audio_file names, probabilities, labels, or transcript text.
"""
from pathlib import Path

from infra.churn_metrics import ChurnMetricsError, churn_report, summarize_seeds
from infra.harness import load_truth_table
from infra.predictions_file import PredictionsFileError, read_predictions_file
from infra.seeds import summarize
from infra.shared_config import load_shared_config
from infra.tfidf_baseline import load_classes_by_field

OPTIMISTIC_THRESHOLD_NOTE = (
    "the threshold was tuned on these same validation rows, "
    "so these numbers are optimistic"
)


class ChurnRunReportError(ValueError):
    """The validation churn report cannot be computed from these run files."""


def churn_run_report(
    data_dir,
    predictions_dir,
    *,
    positive_class,
    field="churn_risk",
):
    """Compute 5-seed validation churn metrics from prediction files (validation only)."""
    data_dir = Path(data_dir)
    predictions_dir = Path(predictions_dir)
    if not predictions_dir.is_dir():
        raise ChurnRunReportError(f"predictions_dir not found: {predictions_dir}")

    shared_config = load_shared_config(
        data_dir / "notebooks" / "training" / "shared_config.json"
    )
    classes_by_field = load_classes_by_field(data_dir / "final" / "class_weights.json")

    if field not in classes_by_field:
        raise ChurnRunReportError(
            f"field {field!r} is not in class_weights.json ({list(classes_by_field)})"
        )
    field_classes = list(classes_by_field[field])
    if len(field_classes) != 2:
        raise ChurnRunReportError(
            f"field {field!r} must have exactly 2 classes for churn_run_report, "
            f"got {len(field_classes)}: {field_classes}"
        )
    if positive_class not in field_classes:
        raise ChurnRunReportError(
            f"positive_class {positive_class!r} is not in the classes of {field!r}: {field_classes}"
        )

    val_csv_path = data_dir / "final" / "clean_training_val.csv"
    truth_rows = load_truth_table(val_csv_path, "val", [field])
    if len(truth_rows) != shared_config["val_rows"]:
        raise ChurnRunReportError(
            f"val has {len(truth_rows)} rows, expected {shared_config['val_rows']}"
        )

    expected_seeds = list(shared_config["experiment_seeds"])
    expected_filenames = {
        f"predictions_val_seed{seed}.json" for seed in expected_seeds
    }
    present_pred_files = {
        p.name for p in predictions_dir.glob("predictions_*.json") if p.is_file()
    }
    extra_files = sorted(present_pred_files - expected_filenames)
    if extra_files:
        if any(name.startswith("predictions_test_") for name in extra_files):
            raise ChurnRunReportError(
                f"test split prediction file is not allowed in {predictions_dir}: {extra_files}"
            )
        raise ChurnRunReportError(
            f"extra unknown seed file(s) in {predictions_dir}: {extra_files}"
        )

    truth_audio_order = [r["audio_file"] for r in truth_rows]
    truth_audio_set = set(truth_audio_order)
    y_true = [r[field] for r in truth_rows]

    per_seed = []
    raw_reports = []
    validation_threshold_per_seed = {}
    first_run_id = None
    first_model = None

    for seed in expected_seeds:
        pred_file = predictions_dir / f"predictions_val_seed{seed}.json"
        if not pred_file.is_file():
            raise ChurnRunReportError(
                f"seed {seed}: missing prediction file {pred_file}"
            )
        try:
            loaded = read_predictions_file(
                pred_file,
                classes_by_field,
                expected_split="val",
            )
        except PredictionsFileError as exc:
            raise ChurnRunReportError(f"seed {seed}: {exc}") from exc

        meta = loaded["meta"]
        if meta["seed"] != seed:
            raise ChurnRunReportError(
                f"seed {seed}: header seed is {meta['seed']!r}, expected {seed!r}"
            )
        if meta["dataset_version"] != shared_config["dataset_version"]:
            raise ChurnRunReportError(
                f"seed {seed}: header dataset_version is {meta['dataset_version']!r}, "
                f"expected {shared_config['dataset_version']!r}"
            )
        if first_run_id is None:
            first_run_id = meta["run_id"]
            first_model = meta["model"]
        else:
            if meta["run_id"] != first_run_id:
                raise ChurnRunReportError(
                    f"seed {seed}: header run_id is {meta['run_id']!r}, expected {first_run_id!r}"
                )
            if meta["model"] != first_model:
                raise ChurnRunReportError(
                    f"seed {seed}: header model is {meta['model']!r}, expected {first_model!r}"
                )

        probs_by_audio = loaded["probabilities"]
        if set(probs_by_audio) != truth_audio_set:
            raise ChurnRunReportError(
                f"seed {seed}: audio_file set in predictions does not match validation truth"
            )

        scores = [
            probs_by_audio[af][field][positive_class] for af in truth_audio_order
        ]
        try:
            report = churn_report(
                y_true,
                scores,
                field_classes,
                positive_class,
            )
        except ChurnMetricsError as exc:
            raise ChurnRunReportError(f"seed {seed}: {exc}") from exc

        raw_reports.append(report)
        per_seed.append({"seed": seed, **report})
        validation_threshold_per_seed[seed] = report["at_threshold"]["threshold"]

    summary = summarize_seeds(raw_reports)
    summary["balanced_accuracy_at_default_threshold"] = summarize(
        [r["at_default_threshold"]["balanced_accuracy"] for r in raw_reports],
        ddof=1,
    )

    return {
        "run_id": first_run_id,
        "model": first_model,
        "field": field,
        "positive_class": positive_class,
        "per_seed": per_seed,
        "summary": summary,
        "validation_threshold_per_seed": validation_threshold_per_seed,
    }


def format_churn_report(result):
    """Format the output of churn_run_report as a short plain-text summary."""
    summary = result["summary"]
    per_seed = result["per_seed"]
    thresholds = result["validation_threshold_per_seed"]
    pos_cls = result.get("positive_class", "at_risk")

    ap = summary["average_precision"]
    bal_tuned = summary["balanced_accuracy_at_threshold"]
    bal_def = summary["balanced_accuracy_at_default_threshold"]
    f1_tuned = summary["macro_f1_at_threshold"]
    f1_def = summary["macro_f1_at_default_threshold"]

    thresh_str = ", ".join(
        f"seed {s}={thresholds[s]:.4f}" for s in thresholds
    )
    counts_str = ", ".join(
        f"seed {r['seed']}={r['at_threshold']['positives_found']}/"
        f"{r['at_threshold']['positives_total']} (fp={r['at_threshold']['fp']})"
        for r in per_seed
    )

    lines = [
        f"run_id: {result.get('run_id')} | model: {result.get('model')} | field: {result.get('field')}",
        f"{pos_cls} rows: {summary['n_positive']}/{summary['n']} | AP chance level: {summary['average_precision_chance']:.6f}",
        f"average_precision: {ap['mean']:.6f} +- {ap['std']:.6f} (ddof=1, n={ap['n']})",
        f"balanced_accuracy (tuned): {bal_tuned['mean']:.6f} +- {bal_tuned['std']:.6f} | (at 0.5): {bal_def['mean']:.6f} +- {bal_def['std']:.6f}",
        f"macro_f1 (tuned): {f1_tuned['mean']:.6f} +- {f1_tuned['std']:.6f} | (at 0.5): {f1_def['mean']:.6f} +- {f1_def['std']:.6f}",
        f"tuned threshold per seed: {thresh_str}",
        f"positives found / total (false positives) per seed: {counts_str}",
        f"Note: {OPTIMISTIC_THRESHOLD_NOTE}.",
    ]
    return "\n".join(lines)
