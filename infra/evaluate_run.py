"""Score the validation predictions of a trained model and write its run record.

Phase 2 evaluation tool: takes the 5 per-seed validation prediction files of a
trained model and its experiment config JSON, validates every file header and
row against the shared config and class_weights.json, scores each seed with the
evaluation harness (applying the customer_state exclusion for 'unclear'), and
writes one run record under runs_dir/exp_<run_id>/run_record.json.

This module never reads or scores the test split, never loads any transcript
text column from the validation CSV, and never modifies or copies the
prediction files.
"""
import json
from pathlib import Path, PurePosixPath

from infra.experiment_config import ExperimentConfig, load_experiment_config
from infra.harness import HarnessError, evaluate_predictions, load_truth_table
from infra.metrics import combine_macro_f1, seed_metrics
from infra.predictions_file import PredictionsFileError, read_predictions_file
from infra.run_record import (
    _check_run_id,
    build_run_record,
    load_run_record,
    make_seed_result,
    record_path,
    save_run_record,
)
from infra.shared_config import load_shared_config
from infra.tfidf_baseline import (
    CUSTOMER_STATE_EXCLUSIONS,
    _file_sha256,
    load_classes_by_field,
)

EVAL_VAL_HASH_KEY = "eval_data_sha256_val"


class EvaluateRunError(ValueError):
    """The run predictions cannot be evaluated or recorded."""


def _with_eval_val_hash(config, val_sha256):
    data = config.to_dict()
    data["other_hyperparameters"] = {
        **data["other_hyperparameters"],
        EVAL_VAL_HASH_KEY: val_sha256,
    }
    return ExperimentConfig.from_dict(data)


def _refuse_non_val_split(evaluated_split):
    if evaluated_split == "test":
        raise EvaluateRunError("evaluate_run never reads or scores the test split")
    if evaluated_split != "val":
        raise EvaluateRunError(
            f"evaluated_split must be 'val', got {evaluated_split!r}"
        )


def _relative_artifact_path(pred_file, predictions_dir, runs_dir):
    """Build a safe relative POSIX path for the run record artifacts entry."""
    pred_dir_path = Path(predictions_dir)
    if (
        not pred_dir_path.is_absolute()
        and ".." not in PurePosixPath(pred_dir_path.as_posix()).parts
    ):
        return (pred_dir_path / pred_file.name).as_posix()

    try:
        rel_to_runs = pred_file.resolve().relative_to(Path(runs_dir).resolve())
        return (Path("runs") / rel_to_runs).as_posix()
    except ValueError:
        pass

    folder_name = pred_dir_path.name
    if folder_name and folder_name not in (".", ".."):
        return f"{folder_name}/{pred_file.name}"
    return pred_file.name


def _format_summary(run_id, model, fields, aggregate, combined, exceptions, saved_path):
    lines = [
        f"run_id: {run_id}",
        f"model: {model}",
    ]
    for field in fields:
        stat = aggregate[f"{field}_macro_f1"]
        lines.append(
            f"{field}_macro_f1: {stat['mean']:.6f} +- {stat['std']:.6f} "
            f"(ddof={stat['ddof']}, n={stat['n']})"
        )
    vals_str = ", ".join(f"{f}={v:.6f}" for f, v in combined["values"].items())
    lines.append(f"combined_macro_f1: {combined['mean']:.6f} ({vals_str})")
    lines.append(f"exceptions: {json.dumps(exceptions)}")
    lines.append(f"record_path: {saved_path}")
    return "\n".join(lines)


def evaluate_run(
    data_dir,
    runs_dir,
    run_id,
    config_path,
    predictions_dir,
    hypothesis,
    device,
    *,
    evaluated_split="val",
    reference_config_path=None,
    changed_factor=None,
    reference_run_id=None,
):
    """Score the 5-seed validation predictions of a trained model and save its run record.

    Never overwrites an existing run folder or run record. Never reads or scores
    the test split. Never loads transcript text columns.
    """
    _refuse_non_val_split(evaluated_split)
    _check_run_id(run_id)

    data_dir = Path(data_dir)
    runs_dir = Path(runs_dir)
    predictions_dir = Path(predictions_dir)

    exp_dir = runs_dir / f"exp_{run_id}"
    rec_file = record_path(runs_dir, run_id)
    if exp_dir.exists() or rec_file.exists():
        raise FileExistsError(
            f"{exp_dir} already exists; existing run folders are not overwritten"
        )

    if not predictions_dir.is_dir():
        raise EvaluateRunError(f"predictions_dir not found: {predictions_dir}")

    shared_config = load_shared_config(
        data_dir / "notebooks" / "training" / "shared_config.json"
    )
    classes_by_field = load_classes_by_field(data_dir / "final" / "class_weights.json")
    fields = list(classes_by_field.keys())

    config = load_experiment_config(config_path, shared_config=shared_config)
    if EVAL_VAL_HASH_KEY in config.other_hyperparameters:
        raise EvaluateRunError(
            f"submitted config must not contain {EVAL_VAL_HASH_KEY!r}; "
            "it is computed and added by evaluate_run"
        )
    reference_config = (
        load_experiment_config(reference_config_path, shared_config=shared_config)
        if reference_config_path is not None
        else None
    )

    val_csv_path = data_dir / "final" / "clean_training_val.csv"
    truth_rows = load_truth_table(val_csv_path, "val", fields)
    if len(truth_rows) != shared_config["val_rows"]:
        raise EvaluateRunError(
            f"val has {len(truth_rows)} rows, expected {shared_config['val_rows']}"
        )
    val_sha256 = _file_sha256(val_csv_path)

    if reference_run_id is not None:
        _check_run_id(reference_run_id)
        ref_record_file = record_path(runs_dir, reference_run_id)
        if ref_record_file.is_file():
            ref_record = load_run_record(ref_record_file)
            ref_hp = ref_record.get("config", {}).get("other_hyperparameters", {})
            ref_val_sha256 = ref_hp.get(EVAL_VAL_HASH_KEY)
            if ref_val_sha256 is not None and ref_val_sha256 != val_sha256:
                raise EvaluateRunError(
                    f"reference run {reference_run_id!r} was scored on validation "
                    f"file {ref_val_sha256!r}, which differs from current "
                    f"validation file {val_sha256!r}"
                )

    config = _with_eval_val_hash(config, val_sha256)
    if reference_config is not None:
        ref_cfg_hash = reference_config.other_hyperparameters.get(EVAL_VAL_HASH_KEY)
        if ref_cfg_hash is not None and ref_cfg_hash != val_sha256:
            raise EvaluateRunError(
                f"reference config has {EVAL_VAL_HASH_KEY}={ref_cfg_hash!r}, "
                f"which differs from current validation file {val_sha256!r}"
            )
        reference_config = _with_eval_val_hash(reference_config, val_sha256)

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
            raise EvaluateRunError(
                f"test split prediction file is not allowed in {predictions_dir}: {extra_files}"
            )
        raise EvaluateRunError(
            f"extra unknown seed file(s) in {predictions_dir}: {extra_files}"
        )

    seed_reports = []
    per_seed = []
    prediction_rel_paths = []

    for seed in expected_seeds:
        pred_file = predictions_dir / f"predictions_val_seed{seed}.json"
        if not pred_file.is_file():
            raise EvaluateRunError(
                f"seed {seed}: missing prediction file {pred_file}"
            )
        try:
            loaded = read_predictions_file(
                pred_file,
                classes_by_field,
                expected_split="val",
            )
        except PredictionsFileError as exc:
            raise EvaluateRunError(f"seed {seed}: {exc}") from exc

        meta = loaded["meta"]
        if meta["run_id"] != run_id:
            raise EvaluateRunError(
                f"seed {seed}: header run_id is {meta['run_id']!r}, expected {run_id!r}"
            )
        if meta["model"] != config.model:
            raise EvaluateRunError(
                f"seed {seed}: header model is {meta['model']!r}, expected {config.model!r}"
            )
        if meta["seed"] != seed:
            raise EvaluateRunError(
                f"seed {seed}: header seed is {meta['seed']!r}, expected {seed!r}"
            )
        if meta["dataset_version"] != shared_config["dataset_version"]:
            raise EvaluateRunError(
                f"seed {seed}: header dataset_version is {meta['dataset_version']!r}, "
                f"expected {shared_config['dataset_version']!r}"
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
            raise EvaluateRunError(f"seed {seed}: {exc}") from exc

        seed_reports.append(report)
        flat_metrics = seed_metrics(report["fields"])
        per_seed.append(
            make_seed_result(run_id, config, "val", seed, flat_metrics)
        )
        prediction_rel_paths.append(
            _relative_artifact_path(pred_file, predictions_dir, runs_dir)
        )

    first_exceptions = seed_reports[0]["exceptions"]
    for seed, report in zip(expected_seeds[1:], seed_reports[1:]):
        if report["exceptions"] != first_exceptions:
            raise EvaluateRunError(
                f"seed {seed}: exceptions {report['exceptions']} do not match "
                f"first seed exceptions {first_exceptions}"
            )

    record = build_run_record(
        run_id=run_id,
        hypothesis=hypothesis,
        config=config,
        shared_config=shared_config,
        per_seed=per_seed,
        evaluated_split="val",
        artifacts={"predictions": prediction_rel_paths},
        device=device,
        exceptions=first_exceptions,
        reference_config=reference_config,
        changed_factor=changed_factor,
        reference_run_id=reference_run_id,
    )
    saved_path = save_run_record(record, runs_dir)

    mean_field_reports = {
        field: {"macro": {"f1": record["aggregate"][f"{field}_macro_f1"]["mean"]}}
        for field in fields
    }
    combined = combine_macro_f1(mean_field_reports)

    summary_text = _format_summary(
        run_id=run_id,
        model=config.model,
        fields=fields,
        aggregate=record["aggregate"],
        combined=combined,
        exceptions=first_exceptions,
        saved_path=saved_path,
    )
    print(summary_text)

    summary = {
        "run_id": run_id,
        "model": config.model,
        "evaluated_split": "val",
        "macro_f1": {
            field: record["aggregate"][f"{field}_macro_f1"] for field in fields
        },
        "combined_macro_f1": combined,
        "exceptions": first_exceptions,
        "record_path": str(saved_path),
    }
    return {
        "record": record,
        "record_path": saved_path,
        "seed_reports": seed_reports,
        "combined_macro_f1": combined,
        "summary": summary,
    }
