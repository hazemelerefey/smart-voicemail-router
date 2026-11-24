"""Phase 2 artifact assembly using Aya's validation infrastructure."""
import hashlib
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from infra.experiment_config import ExperimentConfig, save_experiment_config
from infra.harness import evaluate_predictions
from infra.metrics import seed_metrics
from infra.predictions_file import predictions_path, read_predictions_file, write_predictions_file
from infra.run_record import build_run_record, load_run_record, make_seed_result, save_run_record
from infra.seeds import summarize
from infra.shared_config import load_shared_config

MODEL = "UBC-NLP/MARBERTv2"
REVISION = "a2a02c120b294eec3f1298e4cb5a8b111c7e3de8"
BASELINE = {
    "complaint_category": 0.7605,
    "complaint_urgency": 0.6902,
    "customer_state": 0.7000,
    "churn_risk": 0.8629,
    "combined": 0.7534,
}
FIELDS = tuple(BASELINE)[:-1]
EXCLUSIONS = {"customer_state": {
    "labels": ["unclear"],
    "reason": "unclear has 0 train rows and 1 validation row. Excluded from customer_state scoring only by Hazem's decision.",
}}
# Git blob IDs from the synchronized ready worktree, insensitive to CRLF checkout conversion.
BLOBS = {
    "train": "2e9a58d5c988f2253a12c0d46e3f43a2b55be0c7",
    "val": "b1adfcc118a766a44bdc1fbe60f372829b2dc720",
    "weights": "6a1c1e069fdfd7341e699b4658c20220a9576438",
}


def verify_blob(path, key):
    payload = path.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest()
    if digest != BLOBS[key]:
        raise ValueError(f"{path} differs from the committed {key} snapshot")


@dataclass
class Inputs:
    shared: dict
    weights: dict
    classes: dict
    train: list
    validation: list
    truth: list


def read_inputs(shared_path, train_path, val_path, weights_path):
    shared = load_shared_config(shared_path)
    if (shared["dataset_version"], shared["train_rows"], shared["val_rows"], shared["max_seq_len"],
        shared["experiment_seeds"], shared["split_seed"]) != ("v2", 3575, 1003, 128, [42, 1337, 2023, 7, 99], 42):
        raise ValueError("Shared config does not match the Phase 2 protocol")
    for key, path in (("train", train_path), ("val", val_path), ("weights", weights_path)):
        verify_blob(path, key)
    source = read_json(weights_path)
    weights = source["weights"]
    classes = {field: list(weights[field]) for field in FIELDS}
    if source["rows"] != shared["train_rows"] or [len(v) for v in classes.values()] != [11, 3, 4, 2]:
        raise ValueError("Unexpected class weight metadata")

    tables = []
    for split, path in (("train", train_path), ("val", val_path)):
        table = pd.read_csv(path, usecols=["audio_file", "split", "text_norm", *FIELDS],
                            dtype=str, keep_default_na=False)
        if set(table["split"]) != {split} or len(table) != shared[f"{split}_rows"]:
            raise ValueError(f"Unexpected split or row count in {path}")
        if table["audio_file"].duplicated().any() or not table["audio_file"].str.strip().all():
            raise ValueError(f"Missing or repeated audio_file in {split}")
        if not table["text_norm"].str.strip().all():
            raise ValueError(f"Empty text_norm in {split}")
        for field, labels in classes.items():
            expected = set(labels)
            if split == "val" and field == "customer_state":
                expected.add("unclear")
                if sum(table[field] == "unclear") != 1:
                    raise ValueError("Expected exactly one unclear validation row")
            if set(table[field]) != expected:
                raise ValueError(f"Unexpected label mapping for {split}/{field}")
        tables.append(table.drop(columns="split").to_dict("records"))
    train, validation = tables
    truth = [{key: row[key] for key in ("audio_file", *FIELDS)} for row in validation]
    return Inputs(shared, weights, classes, train, validation, truth)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    if path.exists():
        if read_json(path) != value:
            raise FileExistsError(f"{path} exists with different content")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=path.parent) as staging:
        staged = Path(staging) / path.name
        staged.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        staged.rename(path)


def configure(data, learning_rate, epochs):
    if learning_rate not in (1e-5, 2e-5, 3e-5) or epochs not in (3, 5):
        raise ValueError("Use the approved learning-rate and epoch settings")
    return ExperimentConfig(MODEL, data.shared["dataset_version"], learning_rate=learning_rate,
        batch_size=16, epochs=epochs, other_hyperparameters={
            "model_revision": REVISION, "max_seq_len": data.shared["max_seq_len"],
            "optimizer": "AdamW", "scheduler": "linear", "warmup_ratio": 0.1,
            "weight_decay": 0.01, "dropout": 0.1, "gradient_clip_norm": 1.0,
            "early_stopping_patience": 2, "precision": "fp16_amp",
            "churn_weight_cap": 20, "weights_blob": BLOBS["weights"],
            "train_blob": BLOBS["train"], "validation_blob": BLOBS["val"],
            "input_column": "text_norm", "tasks": list(FIELDS), "architecture": "single_task",
        })


def experiment_dir(runs_dir, run_id, config):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise ValueError("Use letters, digits, underscores or hyphens in run_id")
    folder = runs_dir / f"exp_{run_id}"
    path = folder / "config.json"
    if path.exists():
        if read_json(path) != config.to_dict():
            raise ValueError("Use a new run_id for a different configuration")
    else:
        with TemporaryDirectory(dir=runs_dir) as staging:
            staged = Path(staging) / path.name
            save_experiment_config(config, staged)
            folder.mkdir(exist_ok=True)
            staged.rename(path)
    return folder


def score(data, fields, predictions):
    return evaluate_predictions("val", data.truth, predictions,
        {field: data.classes[field] for field in fields},
        {field: EXCLUSIONS[field] for field in fields if field in EXCLUSIONS})


def task_dir(folder, seed, field):
    return folder / "checkpoints" / f"seed_{seed}" / field


def combine_seed(data, runs_dir, folder, run_id, seed, config):
    parts = {field: read_json(task_dir(folder, seed, field) / "result.json") for field in FIELDS}
    expected_ids = {row["audio_file"] for row in data.truth}
    for field, part in parts.items():
        if (part["field"] != field or part["config"] != config.for_seed(seed)
            or set(part["probabilities"]) != expected_ids
            or not (folder.parent.parent / part["checkpoint"] / "training.pt").is_file()):
            raise ValueError(f"Invalid task result for {seed}/{field}")
    rows = [{"audio_file": key, "probabilities": {
        field: parts[field]["probabilities"][key] for field in FIELDS
    }} for key in (row["audio_file"] for row in data.truth)]
    path = predictions_path(runs_dir, run_id, "val", seed)
    if not path.exists():
        with TemporaryDirectory(dir=folder) as staging:
            staged = Path(staging) / path.name
            write_predictions_file(staged, run_id, config.model, "val", seed,
                                   config.dataset_version, rows, data.classes)
            staged.rename(path)
    loaded = read_predictions_file(path, data.classes, expected_split="val")
    expected_meta = {"run_id": run_id, "model": config.model, "split": "val",
                     "seed": seed, "dataset_version": config.dataset_version}
    if any(loaded["meta"][key] != value for key, value in expected_meta.items()) or any(
        loaded["probabilities"][row["audio_file"]] != row["probabilities"] for row in rows
    ):
        raise ValueError(f"Existing prediction file differs from the completed tasks: {path}")
    report = score(data, FIELDS, loaded["harness_rows"])
    from marbertv2_churn import churn_analysis
    report["churn_analysis"] = churn_analysis(data.truth, loaded["probabilities"], data.classes["churn_risk"])
    metrics_path = folder / f"metrics_val_seed{seed}.json"
    write_json(metrics_path, report)
    return path, metrics_path, report, parts


def finalize(data, runs_dir, folder, run_id, config, reference_run_id):
    is_single_seed_sweep = (
        config.model == "UBC-NLP/MARBERTv2"
        and (
            config.learning_rate in (1e-5, 3e-5)
            or (
                config.learning_rate == 2e-5
                and "seed42-rebuild" in run_id
            )
        )
    )
    seeds = [42] if is_single_seed_sweep else data.shared["experiment_seeds"]
    ready = [seed for seed in seeds if all(
        (task_dir(folder, seed, field) / "result.json").is_file() for field in FIELDS)]
    results = [combine_seed(data, runs_dir, folder, run_id, seed, config) for seed in ready]
    missing = [(seed, field) for seed in seeds for field in FIELDS
               if not (task_dir(folder, seed, field) / "result.json").is_file()]
    if missing:
        print(f"Validation files ready for seeds {ready}. Pending task/seed pairs: {missing}")
        return

    reference = None
    if config.learning_rate != 2e-5:
        if not reference_run_id or not re.fullmatch(r"[A-Za-z0-9_-]+", reference_run_id):
            raise ValueError("Provide the completed 2e-5 reference run ID for this sweep")
        reference_path = runs_dir / f"exp_{reference_run_id}" / "run_record.json"
        reference = ExperimentConfig.from_dict(load_run_record(reference_path)["config"])
        if reference != replace(config, learning_rate=2e-5):
            raise ValueError("Sweep reference must differ only in learning_rate")
    elif reference_run_id is not None:
        raise ValueError("The reference experiment does not take a reference run ID")

    per_seed = [make_seed_result(run_id, config, "val", seed, {
        **seed_metrics(report["fields"]), "combined_macro_f1": report["combined_macro_f1"]["mean"],
    }) for seed, (_, _, report, _) in zip(seeds, results)]
    artifacts = {
        "predictions": [path.relative_to(runs_dir.parent).as_posix() for path, _, _, _ in results],
        "metrics": [path.relative_to(runs_dir.parent).as_posix() for _, path, _, _ in results],
        "checkpoints": [parts[field]["checkpoint"] for _, _, _, parts in results for field in FIELDS],
        "summary": [(folder / "validation_summary.md").relative_to(runs_dir.parent).as_posix()],
    }
    devices = sorted({part["device"] for _, _, _, parts in results for part in parts.values()})
    record = build_run_record(run_id, "MARBERTv2 improves validation Macro-F1 over the corrected-text TF-IDF baseline",
        config, data.shared, per_seed, "val", artifacts, ", ".join(devices), results[0][2]["exceptions"],
        reference_config=reference, changed_factor="learning_rate" if reference else None,
        reference_run_id=reference_run_id,
        ddof=0 if is_single_seed_sweep else 1)
    # A single seed cannot estimate between-seed variability.
    # Preserve the aggregate schema, but mark SD as unavailable.
    if is_single_seed_sweep:
        for metric in record["aggregate"].values():
            if metric["n"] != 1:
                raise ValueError("Expected exactly one seed")
            metric["std"] = None

    summary = validation_summary(record, results)
    summary_path = folder / "validation_summary.md"
    if summary_path.exists():
        if summary_path.read_text(encoding="utf-8") != summary:
            raise FileExistsError(f"{summary_path} differs from the completed run")
    else:
        with TemporaryDirectory(dir=folder) as staging:
            staged = Path(staging) / summary_path.name
            staged.write_text(summary, encoding="utf-8")
            staged.rename(summary_path)
    destination = folder / "run_record.json"
    if destination.exists():
        existing = load_run_record(destination)
        for key in record.keys() - {"environment", "created_utc"}:
            if existing[key] != record[key]:
                raise FileExistsError(f"Existing run record differs in {key}")
    else:
        with TemporaryDirectory(dir=folder) as staging:
            save_run_record(record, staging).rename(destination)
    print(summary)


def validation_summary(record, results):
    lines = [
        f"# MARBERTv2 validation results for {record['run_id']}", "",
        f"Learning rate {record['config']['learning_rate']:g}, epoch budget {record['config']['epochs']}.",
        (
            "Single-seed evaluation: between-seed SD is unavailable. "
            "Delta compares seed 42 with corrected-text TF-IDF."
            if len(record["per_seed"]) == 1 else
            "Sample standard deviation uses ddof=1. Delta compares the mean with corrected-text TF-IDF."
        ),
        "Customer state excludes the single unclear row. The other fields score all 1,003 rows.", "",
        "| Field | " + " | ".join(str(row["seed"]) for row in record["per_seed"])
        + " | Mean | Sample SD | TF-IDF | Delta | Beats baseline |",
        "|---|" + "---:|" * (len(record["per_seed"]) + 5),
    ]
    for field, baseline in BASELINE.items():
        metric = f"{field}_macro_f1"
        agg = record["aggregate"][metric]
        values = " | ".join(f"{row['metrics'][metric]:.4f}" for row in record["per_seed"])
        std_text = "N/A" if len(record["per_seed"]) == 1 else f"{agg['std']:.4f}"
        lines.append(f"| {field} | {values} | {agg['mean']:.4f} | {std_text} | "
                     f"{baseline:.4f} | {agg['mean'] - baseline:+.4f} | "
                     f"{'Yes' if agg['mean'] > baseline else 'No'} |")
    lines += ["", "## Error analysis", "",
              "Confusion counts below sum the predictions from all evaluated seeds. Class support is per seed. "
              "Per-class scores are means across seeds.", ""]
    for field in FIELDS:
        reports = [result[2]["fields"][field] for result in results]
        labels = reports[0]["classes"]
        matrix = [[sum(rep["confusion_matrix"]["counts"][i][j] for rep in reports)
                   for j in range(len(labels))] for i in range(len(labels))]
        lines += [f"### {field}", "", "| Actual / predicted | " + " | ".join(labels) + " |",
                  "|---|" + "---:|" * len(labels)]
        for label, row in zip(labels, matrix):
            lines.append(f"| {label} | " + " | ".join(map(str, row)) + " |")
        lines += ["", "| Class | Precision | Recall | F1 | Support |", "|---|---:|---:|---:|---:|"]
        for label in labels:
            means = [summarize(
                    [rep["per_class"][label][key] for rep in reports],
                    ddof=0 if len(reports) == 1 else 1
                )["mean"]
                     for key in ("precision", "recall", "f1")]
            lines.append(f"| {label} | " + " | ".join(f"{v:.4f}" for v in means)
                         + f" | {reports[0]['per_class'][label]['support']} |")
        errors = sorted(((n, labels[i], labels[j]) for i, row in enumerate(matrix)
                         for j, n in enumerate(row) if i != j and n), reverse=True)[:3]
        lines += ["", "Most frequent confusions across seeds.", ""]
        lines += [f"- {actual} predicted as {predicted} in {count} cases."
                  for count, actual, predicted in errors] or ["- No off-diagonal predictions."]
        lines.append("")
    lines += ["## Churn threshold analysis", "",
              "Thresholds are optimized and scored on the same validation split. These exploratory scores can be optimistic.",
              "The official prediction files and Macro-F1 comparisons use argmax.", "",
              "| Seed | Threshold | Average precision | Argmax balanced accuracy | Tuned balanced accuracy | Tuned Macro-F1 | At-risk recall count |",
              "|---:|---:|---:|---:|---:|---:|---:|"]
    for entry, result in zip(record["per_seed"], results):
        churn = result[2]["churn_analysis"]
        lines.append(f"| {entry['seed']} | {churn['threshold']:.6g} | {churn['average_precision']:.4f} | "
                     f"{churn['argmax_balanced_accuracy']:.4f} | {churn['tuned_balanced_accuracy']:.4f} | "
                     f"{churn['tuned_macro_f1']:.4f} | {churn['true_positive']}/{churn['at_risk_support']} |")
    return "\n".join(lines) + "\n"
