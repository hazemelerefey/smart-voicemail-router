"""Compare validation run records and report which run is ahead by the selection rule.

Phase 2 comparison tool: loads two or more validation run records, verifies that
they are comparable (same split 'val', dataset version, row counts, seed order,
excluded rows per field, and validation file SHA-256 when recorded), computes
each run's per-field and combined macro-F1 summary (mean and std with ddof=1,
always keeping the four per-field values alongside the combined score), and
applies the model-selection tie-break rule.

This tool reports which run is ahead by the rule and the numbers behind it; the
decision itself is recorded in the evaluation report. It reads only run record
JSON files, never reads or prints transcript text or CSV rows, and never
compares test split results.
"""
from pathlib import Path

from infra.metrics import combine_macro_f1
from infra.run_record import (
    RunRecordError,
    _check_run_id,
    load_run_record,
    record_path,
)
from infra.seeds import summarize

FIELDS = (
    "complaint_category",
    "complaint_urgency",
    "customer_state",
    "churn_risk",
)

VAL_HASH_KEYS = ("eval_data_sha256_val", "data_sha256_val")
SUPPORTED_TIE_RULES = ("larger_std",)


class CompareError(ValueError):
    """The runs cannot be loaded or compared."""


def _extract_val_hash(record):
    hp = record.get("config", {}).get("other_hyperparameters", {})
    if not isinstance(hp, dict):
        return None
    eval_hash = hp.get("eval_data_sha256_val")
    data_hash = hp.get("data_sha256_val")
    if eval_hash is not None and data_hash is not None and eval_hash != data_hash:
        raise CompareError(
            f"run {record.get('run_id')!r}: conflicting validation hashes "
            f"eval_data_sha256_val={eval_hash!r} and data_sha256_val={data_hash!r}"
        )
    return eval_hash if eval_hash is not None else data_hash


def _normalized_exceptions(record):
    """Return the structural exception fields (excluding prose reason differences)."""
    out = []
    for entry in record.get("exceptions", []):
        out.append({
            "field": entry.get("field"),
            "excluded_labels": entry.get("excluded_labels"),
            "rows_excluded": entry.get("rows_excluded"),
            "n_scored": entry.get("n_scored"),
            "n_total_rows": entry.get("n_total_rows"),
        })
    return out


def load_runs(runs_dir, run_ids):
    """Load a list of run records from runs_dir/exp_<run_id>/run_record.json."""
    if not isinstance(run_ids, (list, tuple)) or not run_ids:
        raise CompareError("run_ids must be a non-empty list of run IDs")
    runs_dir = Path(runs_dir)
    records = []
    for rid in run_ids:
        try:
            _check_run_id(rid)
        except RunRecordError as exc:
            raise CompareError(f"run {rid!r}: {exc}") from exc
        path = record_path(runs_dir, rid)
        if not path.is_file():
            raise CompareError(f"run {rid!r}: run record not found at {path}")
        try:
            rec = load_run_record(path)
        except RunRecordError as exc:
            raise CompareError(f"run {rid!r}: {exc}") from exc
        if rec.get("run_id") != rid:
            raise CompareError(
                f"run {rid!r}: record file has run_id {rec.get('run_id')!r}"
            )
        records.append(rec)
    return records


def check_comparable(records):
    """Verify that two or more validation run records can be fairly compared.

    Returns a list of warning strings (for example when a record does not store
    a validation-file SHA-256 hash). Raises CompareError if any comparability
    requirement is violated.
    """
    if not isinstance(records, (list, tuple)) or len(records) < 2:
        count = len(records) if isinstance(records, (list, tuple)) else 0
        raise CompareError(
            f"at least two runs are required to compare, got {count}"
        )

    seen_ids = set()
    for rec in records:
        rid = rec.get("run_id")
        if rid in seen_ids:
            raise CompareError(f"duplicate run_id {rid!r} cannot be compared")
        seen_ids.add(rid)

    splits = [rec.get("evaluated_split") for rec in records]
    if len(set(splits)) > 1:
        raise CompareError(
            f"runs differ in evaluated_split: {splits}"
        )
    if splits[0] != "val":
        raise CompareError(
            f"compare_runs compares validation results only ('val'), "
            f"got evaluated_split={splits[0]!r}"
        )

    base = records[0]
    base_id = base["run_id"]
    base_ds = base.get("dataset", {})
    base_version = base_ds.get("version")
    base_rows = base_ds.get("rows")
    base_seeds = [s.get("seed") for s in base.get("per_seed", [])]
    base_exceptions = _normalized_exceptions(base)

    for rec in records[1:]:
        rid = rec["run_id"]
        ds = rec.get("dataset", {})
        if ds.get("version") != base_version:
            raise CompareError(
                f"dataset.version differs between {base_id!r} ({base_version!r}) "
                f"and {rid!r} ({ds.get('version')!r})"
            )
        if ds.get("rows") != base_rows:
            raise CompareError(
                f"dataset.rows differs between {base_id!r} ({base_rows}) "
                f"and {rid!r} ({ds.get('rows')})"
            )
        seeds = [s.get("seed") for s in rec.get("per_seed", [])]
        if seeds != base_seeds:
            raise CompareError(
                f"per_seed seed list differs between {base_id!r} ({base_seeds}) "
                f"and {rid!r} ({seeds})"
            )
        if _normalized_exceptions(rec) != base_exceptions:
            raise CompareError(
                f"exceptions differ between {base_id!r} and {rid!r}"
            )

    warnings = []
    recorded_hashes = {}
    for rec in records:
        rid = rec["run_id"]
        val_hash = _extract_val_hash(rec)
        if val_hash is None:
            warnings.append(
                f"run {rid}: no validation-file hash recorded: "
                "the data version cannot be checked"
            )
        else:
            recorded_hashes[rid] = val_hash

    if len(set(recorded_hashes.values())) > 1:
        raise CompareError(
            f"runs were scored on different validation files (hash mismatch): "
            f"{recorded_hashes}"
        )

    return warnings


def summarize_run(record):
    """Extract per-field macro-F1, accuracy means, and 5-seed combined macro-F1 (ddof=1).

    The four per-field macro-F1 values are always kept alongside the combined
    value, together with the model name and changed_factor.
    """
    agg = record["aggregate"]
    macro_f1 = {}
    accuracy_mean = {}
    for field in FIELDS:
        f1_stat = agg[f"{field}_macro_f1"]
        macro_f1[field] = {
            "mean": float(f1_stat["mean"]),
            "std": float(f1_stat["std"]),
            "ddof": f1_stat["ddof"],
            "n": f1_stat["n"],
        }
        acc_key = f"{field}_accuracy"
        accuracy_mean[field] = (
            float(agg[acc_key]["mean"]) if acc_key in agg else None
        )

    per_seed_combined = []
    for seed_entry in record["per_seed"]:
        metrics = seed_entry["metrics"]
        seed_field_reports = {
            field: {"macro": {"f1": float(metrics[f"{field}_macro_f1"])}}
            for field in FIELDS
        }
        per_seed_combined.append(combine_macro_f1(seed_field_reports)["mean"])

    combined_stats = summarize(per_seed_combined, ddof=1)
    per_field_means = {field: macro_f1[field]["mean"] for field in FIELDS}

    return {
        "run_id": record["run_id"],
        "model": record["config"]["model"],
        "changed_factor": record["changed_factor"],
        "reference_run_id": record.get("reference_run_id"),
        "macro_f1": macro_f1,
        "accuracy_mean": accuracy_mean,
        "combined_macro_f1": {
            "label": "unweighted mean of the per-field macro-F1 values",
            "mean": combined_stats["mean"],
            "std": combined_stats["std"],
            "ddof": combined_stats["ddof"],
            "n": combined_stats["n"],
            "per_seed": per_seed_combined,
            "values": per_field_means,
        },
    }


def compare(runs_dir, run_ids):
    """Load, validate comparability, summarize, and sort runs by combined mean (highest first)."""
    if not isinstance(run_ids, (list, tuple)) or len(run_ids) < 2:
        count = len(run_ids) if isinstance(run_ids, (list, tuple)) else 0
        raise CompareError(
            f"at least two runs are required to compare, got {count}"
        )
    if len(set(run_ids)) != len(run_ids):
        raise CompareError(f"duplicate run_id in {list(run_ids)}")

    records = load_runs(runs_dir, run_ids)
    warnings = check_comparable(records)
    rows = [summarize_run(rec) for rec in records]
    rows.sort(key=lambda r: r["combined_macro_f1"]["mean"], reverse=True)
    return {
        "warnings": warnings,
        "rows": rows,
    }


def format_table(result):
    """Format the output of compare() as a plain-text table with field and combined mean +- std."""
    rows = result.get("rows", [])
    warnings = result.get("warnings", [])

    header = (
        f"{'run_id':<14} {'model':<14} {'changed_factor':<18} "
        f"{'complaint_category':<21} {'complaint_urgency':<21} "
        f"{'customer_state':<21} {'churn_risk':<21} {'combined_macro_f1':<21}"
    )
    sep = "-" * len(header)
    lines = [header, sep]

    for row in rows:
        cf = str(row["changed_factor"]) if row["changed_factor"] is not None else "-"
        cells = []
        for field in FIELDS:
            st = row["macro_f1"][field]
            cells.append(f"{st['mean']:.6f}+-{st['std']:.6f}")
        comb = row["combined_macro_f1"]
        comb_str = f"{comb['mean']:.6f}+-{comb['std']:.6f}"
        lines.append(
            f"{row['run_id']:<14} {row['model']:<14} {cf:<18} "
            f"{cells[0]:<21} {cells[1]:<21} {cells[2]:<21} {cells[3]:<21} {comb_str:<21}"
        )

    if warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in warnings:
            lines.append(f"- {w}")

    return "\n".join(lines)


def pick_by_rule(row_a, row_b, *, tie_rule, tie_preference):
    """Report which of two model runs is ahead by the model-selection rule and the numbers behind it.

    The tool reports which run is ahead by the rule and the numbers behind it;
    the decision itself is recorded in the evaluation report.

    Model-selection rule:
    - The higher combined mean macro-F1 wins.
    - If the two runs are within one standard deviation according to `tie_rule`,
      the preferred model (`tie_preference`) wins.
    - `tie_rule` has no default: the caller must specify the definition of
      "within one standard deviation". Currently supported:
      `tie_rule="larger_std"`, which defines a tie as
      `abs(mean_a - mean_b) <= max(std_a, std_b)`.
    """
    if tie_rule not in SUPPORTED_TIE_RULES:
        raise CompareError(
            f"unsupported tie_rule {tie_rule!r}; supported: {SUPPORTED_TIE_RULES}"
        )

    if "combined_macro_f1" not in row_a:
        row_a = summarize_run(row_a)
    if "combined_macro_f1" not in row_b:
        row_b = summarize_run(row_b)

    model_a = row_a["model"]
    model_b = row_b["model"]
    if model_a == model_b:
        raise CompareError(
            f"pick_by_rule requires two different models, got {model_a!r} for both rows"
        )
    if tie_preference not in (model_a, model_b):
        raise CompareError(
            f"tie_preference {tie_preference!r} must be one of the two models "
            f"{(model_a, model_b)}"
        )

    mean_a = float(row_a["combined_macro_f1"]["mean"])
    std_a = float(row_a["combined_macro_f1"]["std"])
    mean_b = float(row_b["combined_macro_f1"]["mean"])
    std_b = float(row_b["combined_macro_f1"]["std"])

    difference = abs(mean_a - mean_b)
    tie_threshold = max(std_a, std_b)

    if difference <= tie_threshold:
        winner = tie_preference
        reason = "tie_preference"
    else:
        winner = model_a if mean_a > mean_b else model_b
        reason = "higher_mean"

    return {
        "winner": winner,
        "reason": reason,
        "difference": difference,
        "tie_threshold": tie_threshold,
        "rule": tie_rule,
    }
