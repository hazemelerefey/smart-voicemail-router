"""Guarded final test evaluation and mandatory validation rehearsal.

One process takes the test-once guard claim BEFORE any test text is read, runs
all 20 checkpoints (5 seeds x 4 fields) on the frozen test split, writes the
five per-seed test prediction files, and scores them through evaluate_test_run
using the same claim.

Before running the final test evaluation, rehearse_on_validation must be run on
the validation split to produce a rehearsal report whose checkpoint fingerprint
and dataset_version match the checkpoints being evaluated and whose overall
verdict is PARITY or NEAR.

If an error occurs after the test-once claim is recorded in step 2 of
run_final_test_evaluation, the claim remains in runs_dir/test_evaluations.json;
releasing a claim is a visible manual change to the log that requires Training
Lead approval. That is why the validation rehearsal is required beforehand.

No transcript text, audio_file names, or probability values are printed or logged.
"""
import hashlib
import json
import math
import numbers
import tempfile
from pathlib import Path

import pandas as pd

from infra.checkpoint_inference import (
    CheckpointInferenceError,
    _load_checkpoint_id2label,
    _validate_id2label_against_classes,
    classify_parity,
    compare_with_submitted,
    predict_probabilities,
    predict_split,
    write_predictions,
)
from infra.evaluate_run import EVAL_TEST_HASH_KEY, evaluate_test_run
from infra.experiment_config import load_experiment_config
from infra.once_guard import claim_test_evaluation, file_sha256
from infra.predictions_file import SUM_TOLERANCE, write_predictions_file
from infra.run_record import _check_run_id, record_path
from infra.shared_config import load_shared_config
from infra.tfidf_baseline import load_classes_by_field

_REPO_ROOT = Path(__file__).resolve().parents[1]
_VERDICT_SEVERITY = {"PARITY": 0, "NEAR": 1, "NO PARITY": 2}
_ALLOWED_REHEARSAL_OVERALL = ("PARITY", "NEAR")


class FinalTestEvaluationError(ValueError):
    """The validation rehearsal or final test evaluation cannot proceed."""


def _is_valid_prob(value):
    return (
        isinstance(value, numbers.Real)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0.0 <= float(value) <= 1.0
    )


def _refuse_path_inside_repo(path, label="out_path"):
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(_REPO_ROOT)
    except ValueError:
        return
    raise FinalTestEvaluationError(f"{label} must be outside the repository")


def discover_checkpoints(root, seeds, fields):
    """Find exactly one complete checkpoint directory for every (seed, field).

    Searches root/seed_<seed>/<field>/epoch_* or root/seed_<seed>/<field> itself.
    Every checkpoint directory must contain both config.json and model.safetensors.
    Missing, duplicate, or incomplete checkpoints raise naming the seed and field.
    """
    root = Path(root)
    if not root.is_dir():
        raise FinalTestEvaluationError(f"checkpoint root directory not found: {root}")
    if not seeds:
        raise FinalTestEvaluationError("seeds must be non-empty")
    if not fields:
        raise FinalTestEvaluationError("fields must be non-empty")

    discovered = {}
    for seed in seeds:
        seed_map = {}
        for field in fields:
            field_dir = root / f"seed_{seed}" / field
            if not field_dir.is_dir():
                raise FinalTestEvaluationError(
                    f"seed {seed}, field {field}: missing checkpoint directory under {field_dir}"
                )

            epoch_dirs = sorted(
                p for p in field_dir.iterdir() if p.is_dir() and p.name.startswith("epoch_")
            )
            direct_present = (
                (field_dir / "config.json").exists()
                or (field_dir / "model.safetensors").exists()
            )
            candidates = list(epoch_dirs)
            if direct_present:
                candidates.append(field_dir)

            if not candidates:
                raise FinalTestEvaluationError(
                    f"seed {seed}, field {field}: missing checkpoint in {field_dir}"
                )
            if len(candidates) > 1:
                names = [
                    "." if c == field_dir else c.name for c in candidates
                ]
                raise FinalTestEvaluationError(
                    f"seed {seed}, field {field}: duplicate checkpoints found ({names})"
                )

            chosen = candidates[0]
            has_config = (chosen / "config.json").is_file()
            has_weights = (chosen / "model.safetensors").is_file()
            if not (has_config and has_weights):
                missing_parts = []
                if not has_config:
                    missing_parts.append("config.json")
                if not has_weights:
                    missing_parts.append("model.safetensors")
                raise FinalTestEvaluationError(
                    f"seed {seed}, field {field}: incomplete checkpoint in {chosen} "
                    f"(missing {missing_parts})"
                )
            seed_map[field] = chosen
        discovered[seed] = seed_map

    return discovered


def checkpoint_fingerprint(checkpoint_dirs, hash_fn=file_sha256):
    """Hash model.safetensors for every (seed, field) and combine into one SHA-256."""
    if not isinstance(checkpoint_dirs, dict) or not checkpoint_dirs:
        raise FinalTestEvaluationError("checkpoint_dirs must be a non-empty dict")

    files = {}
    for seed, field_map in checkpoint_dirs.items():
        if not isinstance(field_map, dict) or not field_map:
            raise FinalTestEvaluationError(
                f"seed {seed}: checkpoint mapping must be a non-empty dict"
            )
        for field, ckpt_dir in field_map.items():
            weights_path = Path(ckpt_dir) / "model.safetensors"
            if not weights_path.is_file():
                raise FinalTestEvaluationError(
                    f"seed {seed}, field {field}: model.safetensors not found in {ckpt_dir}"
                )
            files[f"{seed}/{field}"] = str(hash_fn(weights_path))

    sorted_keys = sorted(files)
    ordered_files = {k: files[k] for k in sorted_keys}
    payload = "\n".join(f"{k}:{ordered_files[k]}" for k in sorted_keys)
    combined = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return {"files": ordered_files, "combined": combined}


def _validate_checkpoint_structure_and_labels(
    checkpoint_dirs, expected_seeds, classes_by_field
):
    if not isinstance(checkpoint_dirs, dict):
        raise FinalTestEvaluationError("checkpoint_dirs must be a dict")
    if set(checkpoint_dirs.keys()) != set(expected_seeds):
        raise FinalTestEvaluationError(
            f"checkpoint seeds {sorted(checkpoint_dirs.keys())} do not match "
            f"shared_config experiment_seeds {list(expected_seeds)}"
        )
    expected_fields = set(classes_by_field.keys())
    for seed in expected_seeds:
        field_map = checkpoint_dirs[seed]
        if not isinstance(field_map, dict) or set(field_map.keys()) != expected_fields:
            raise FinalTestEvaluationError(
                f"seed {seed}: checkpoint fields must equal {sorted(expected_fields)}"
            )
        for field, expected_classes in classes_by_field.items():
            ckpt_dir = Path(field_map[field])
            if not (ckpt_dir / "model.safetensors").is_file():
                raise FinalTestEvaluationError(
                    f"seed {seed}, field {field}: model.safetensors not found in {ckpt_dir}"
                )
            try:
                id2label = _load_checkpoint_id2label(ckpt_dir, field)
                _validate_id2label_against_classes(id2label, expected_classes, field)
            except CheckpointInferenceError as exc:
                raise FinalTestEvaluationError(f"seed {seed}: {exc}") from exc


def rehearse_on_validation(
    data_dir,
    checkpoint_dirs,
    submitted_predictions_dir,
    out_path,
    *,
    predict_fn=predict_probabilities,
    hash_fn=file_sha256,
):
    """Run all 20 checkpoints on the validation split and compare with submitted predictions.

    Writes a JSON rehearsal report to out_path (outside the repository, never
    overwriting). Never reads or touches the test split.
    """
    out_path = Path(out_path)
    _refuse_path_inside_repo(out_path, "out_path")
    if out_path.exists():
        raise FileExistsError(
            f"{out_path} already exists; rehearsal reports are not overwritten"
        )

    data_dir = Path(data_dir)
    submitted_predictions_dir = Path(submitted_predictions_dir)
    if not submitted_predictions_dir.is_dir():
        raise FinalTestEvaluationError(
            f"submitted_predictions_dir not found: {submitted_predictions_dir}"
        )

    shared_config = load_shared_config(
        data_dir / "notebooks" / "training" / "shared_config.json"
    )
    classes_by_field = load_classes_by_field(data_dir / "final" / "class_weights.json")
    expected_seeds = list(shared_config["experiment_seeds"])

    _validate_checkpoint_structure_and_labels(
        checkpoint_dirs, expected_seeds, classes_by_field
    )
    fingerprint = checkpoint_fingerprint(checkpoint_dirs, hash_fn=hash_fn)

    results = {}
    worst_verdict = "PARITY"

    with tempfile.TemporaryDirectory(prefix="svr_rehearsal_") as tmp_dir:
        tmp_root = Path(tmp_dir)
        for seed in expected_seeds:
            sub_file = submitted_predictions_dir / f"predictions_val_seed{seed}.json"
            if not sub_file.is_file():
                raise FinalTestEvaluationError(
                    f"seed {seed}: submitted validation predictions not found: {sub_file}"
                )
            rows = predict_split(
                data_dir,
                checkpoint_dirs[seed],
                split="val",
                predict_fn=predict_fn,
            )
            tmp_ours = tmp_root / f"rehearsal_val_seed{seed}.json"
            write_predictions(
                rows,
                tmp_ours,
                run_id=f"rehearsal-seed{seed}",
                model="rehearsal",
                seed=seed,
                dataset_version=shared_config["dataset_version"],
                classes_by_field=classes_by_field,
            )
            sub_by_field = {field: sub_file for field in classes_by_field}
            cmp = compare_with_submitted(
                tmp_ours, sub_by_field, classes_by_field, data_dir=data_dir
            )
            for field, counts in cmp.items():
                verdict = classify_parity({field: counts})
                results[f"{seed}/{field}"] = {"verdict": verdict, **counts}
                if _VERDICT_SEVERITY[verdict] > _VERDICT_SEVERITY[worst_verdict]:
                    worst_verdict = verdict

    report = {
        "checkpoint_fingerprint": fingerprint,
        "dataset_version": shared_config["dataset_version"],
        "results": results,
        "overall": worst_verdict,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _validate_rehearsal_file(rehearsal_path, expected_fingerprint, expected_dataset_version):
    rehearsal_path = Path(rehearsal_path)
    if not rehearsal_path.is_file():
        raise FinalTestEvaluationError(
            f"rehearsal report not found: {rehearsal_path}"
        )
    try:
        rehearsal = json.loads(rehearsal_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FinalTestEvaluationError(
            f"rehearsal report is not valid JSON: {rehearsal_path} ({exc})"
        ) from exc

    if not isinstance(rehearsal, dict):
        raise FinalTestEvaluationError("rehearsal report must be a JSON object")

    if rehearsal.get("dataset_version") != expected_dataset_version:
        raise FinalTestEvaluationError(
            f"rehearsal dataset_version is {rehearsal.get('dataset_version')!r}, "
            f"expected {expected_dataset_version!r}"
        )

    recorded_fp = rehearsal.get("checkpoint_fingerprint")
    if recorded_fp != expected_fingerprint:
        raise FinalTestEvaluationError(
            "rehearsal checkpoint_fingerprint does not match current checkpoints"
        )

    overall = rehearsal.get("overall")
    if overall not in _ALLOWED_REHEARSAL_OVERALL:
        raise FinalTestEvaluationError(
            f"rehearsal overall verdict is {overall!r}; "
            f"must be one of {_ALLOWED_REHEARSAL_OVERALL}"
        )
    return rehearsal


def run_final_test_evaluation(
    data_dir,
    runs_dir,
    run_id,
    config_path,
    checkpoint_dirs,
    rehearsal_path,
    hypothesis,
    device,
    *,
    predict_fn=predict_probabilities,
    hash_fn=file_sha256,
):
    """Run guarded final test evaluation in strict 4-step order and return the summary.

    Step 1: Pre-checks requiring no test data and writing nothing (run folder
        absence, config and shared config, class lists, all 20 checkpoint
        id2label sets, checkpoint fingerprint, and matching PARITY/NEAR
        validation rehearsal). Any failure raises before the claim and leaves
        runs_dir/test_evaluations.json untouched.
    Step 2: Claim the test evaluation via infra.once_guard.claim_test_evaluation
        BEFORE any test text is read.
    Step 3: Read clean_training_test.csv (audio_file and text_norm only, in
        memory), run predict_fn for every (seed, field), validate probability
        sums, and write runs_dir/exp_<run_id>/predictions_test_seed<seed>.json.
    Step 4: Score the five test prediction files via evaluate_test_run(...,
        claim=claim) without claiming again, and return its summary.

    An error occurring after step 2 leaves the claim in
    runs_dir/test_evaluations.json; releasing a claim is a visible manual
    change approved by the Training Lead, which is why the rehearsal is
    required before calling this function.
    """
    # --- Step 1: Pre-checks that touch NO test data and write NOTHING ---
    _check_run_id(run_id)
    data_dir = Path(data_dir)
    runs_dir = Path(runs_dir)

    exp_dir = runs_dir / f"exp_{run_id}"
    rec_file = record_path(runs_dir, run_id)
    if exp_dir.exists() or rec_file.exists():
        raise FileExistsError(
            f"{exp_dir} already exists; existing run folders are not overwritten"
        )

    shared_config = load_shared_config(
        data_dir / "notebooks" / "training" / "shared_config.json"
    )
    config = load_experiment_config(config_path, shared_config=shared_config)
    if EVAL_TEST_HASH_KEY in config.other_hyperparameters:
        raise FinalTestEvaluationError(
            f"submitted config must not contain {EVAL_TEST_HASH_KEY!r}; "
            "it is computed and added during test evaluation"
        )

    classes_by_field = load_classes_by_field(data_dir / "final" / "class_weights.json")
    expected_seeds = list(shared_config["experiment_seeds"])

    _validate_checkpoint_structure_and_labels(
        checkpoint_dirs, expected_seeds, classes_by_field
    )
    fingerprint = checkpoint_fingerprint(checkpoint_dirs, hash_fn=hash_fn)
    _validate_rehearsal_file(
        rehearsal_path,
        expected_fingerprint=fingerprint,
        expected_dataset_version=shared_config["dataset_version"],
    )

    # --- Step 2: Claim BEFORE any test text is read ---
    test_csv_path = data_dir / "final" / "clean_training_test.csv"
    claim = claim_test_evaluation(
        runs_dir / "test_evaluations.json",
        model=config.model,
        dataset_version=shared_config["dataset_version"],
        run_id=run_id,
        uses=len(expected_seeds),
        test_csv_path=test_csv_path,
        checkpoint_sha256=fingerprint["combined"],
    )

    # --- Step 3: Read test text in memory, run 20 checkpoints, write 5 files ---
    try:
        table = pd.read_csv(
            test_csv_path,
            usecols=["audio_file", "text_norm"],
            dtype=str,
            keep_default_na=False,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise FinalTestEvaluationError(f"failed to read test CSV: {exc}") from exc

    expected_rows = shared_config["test_rows"]
    if len(table) != expected_rows:
        raise FinalTestEvaluationError(
            f"test CSV has {len(table)} rows, expected {expected_rows}"
        )

    audio_files = table["audio_file"].tolist()
    texts = table["text_norm"].tolist()

    for seed in expected_seeds:
        per_field_probs = {}
        for field, expected_classes in classes_by_field.items():
            raw_probs = predict_fn(texts, checkpoint_dirs[seed][field])
            if len(raw_probs) != len(audio_files):
                raise FinalTestEvaluationError(
                    f"seed {seed}, field {field}: predict_fn returned "
                    f"{len(raw_probs)} rows, expected {len(audio_files)}"
                )
            expected_set = set(expected_classes)
            cleaned_rows = []
            for idx, prob_map in enumerate(raw_probs):
                if not isinstance(prob_map, dict) or set(prob_map) != expected_set:
                    raise FinalTestEvaluationError(
                        f"seed {seed}, field {field}: row {idx} probability keys "
                        "do not match approved class list"
                    )
                row_clean = {}
                for cls_name in expected_classes:
                    val = prob_map[cls_name]
                    if not _is_valid_prob(val):
                        raise FinalTestEvaluationError(
                            f"seed {seed}, field {field}: row {idx} class "
                            f"{cls_name!r} has invalid probability"
                        )
                    row_clean[cls_name] = float(val)
                total = sum(row_clean.values())
                if abs(total - 1.0) > SUM_TOLERANCE:
                    raise FinalTestEvaluationError(
                        f"seed {seed}, field {field}: row {idx} probabilities "
                        f"sum to {total:.6f}, not 1"
                    )
                cleaned_rows.append(row_clean)
            per_field_probs[field] = cleaned_rows

        rows = [
            {
                "audio_file": af,
                "probabilities": {
                    field: per_field_probs[field][idx] for field in classes_by_field
                },
            }
            for idx, af in enumerate(audio_files)
        ]
        pred_path = exp_dir / f"predictions_test_seed{seed}.json"
        write_predictions_file(
            path=pred_path,
            run_id=run_id,
            model=config.model,
            split="test",
            seed=seed,
            dataset_version=shared_config["dataset_version"],
            rows=rows,
            classes_by_field=classes_by_field,
        )

    # --- Step 4: Score using the existing claim (no second claim) ---
    eval_result = evaluate_test_run(
        data_dir=data_dir,
        runs_dir=runs_dir,
        run_id=run_id,
        config_path=config_path,
        predictions_dir=exp_dir,
        hypothesis=hypothesis,
        device=device,
        checkpoint_sha256=fingerprint["combined"],
        claim=claim,
    )
    return eval_result["summary"]
