"""TF-IDF + logistic regression baseline (Phase 1, Aya's deliverable).

Permanent location (confirmed by Hazem): infra/tfidf_baseline.py (kept inside infra/ so it can be
imported and tested alongside the evaluation harness and run record modules).

All model and vectorizer settings come from Hazem's reference notebook
(phase-1-examples/aya_infrastructure_and_baseline.ipynb) and are stored in
ExperimentConfig.other_hyperparameters so nothing is hard-coded outside the
config. This module never reads or scores the test split, and never prints,
logs, or writes any transcript text to disk.
"""
import json
from pathlib import Path

import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from infra.experiment_config import ExperimentConfig
from infra.harness import evaluate_predictions
from infra.metrics import combine_macro_f1, seed_metrics
from infra.predictions_file import (
    predictions_path,
    read_predictions_file,
    write_predictions_file,
)
from infra.run_record import build_run_record, make_seed_result, save_run_record
from infra.seeds import run_over_seeds
from infra.shared_config import load_shared_config

DEFAULT_RUN_ID = "tfidf-001"
MODEL_NAME = "tfidf-logreg"

DEFAULT_HYPOTHESIS = (
    "Reference baseline with the settings of Hazem's notebook, run on the "
    "updated data (3575 train, 1003 val), customer_state scored on 4 classes; "
    "these numbers replace the old reference computed on the old data."
)

CUSTOMER_STATE_EXCLUSION_REASON = (
    "Hazem's decision: customer_state is scored on 4 classes; the unclear rows "
    "(no rows in train) are left out of customer_state only and still count in "
    "the other fields."
)

CUSTOMER_STATE_EXCLUSIONS = {
    "customer_state": {
        "labels": ["unclear"],
        "reason": CUSTOMER_STATE_EXCLUSION_REASON,
    }
}

# Reference validation macro-F1 numbers from Hazem's notebook on the old dataset
# (4,031 train, 1,136 val, customer_state scored on 5 classes with unclear = 0).
OLD_REFERENCE_MACRO_F1 = {
    "complaint_category": 0.7261,
    "complaint_urgency": 0.6789,
    "customer_state": 0.5561,
    "churn_risk": 0.8840,
    "mean": 0.7113,
}


class BaselineError(ValueError):
    """The TF-IDF baseline cannot be configured, trained, or evaluated."""


def _refuse_test_split(split):
    if split == "test":
        raise BaselineError("the TF-IDF baseline never reads or scores the test split")
    if split not in ("train", "val"):
        raise BaselineError(f"split must be 'train' or 'val', got {split!r}")


def load_classes_by_field(class_weights_path):
    """Read the class list of each field from the keys of weights in class_weights.json.

    The weight values in the file are NOT used: the TF-IDF baseline uses
    scikit-learn's class_weight='balanced' computed on the train labels.
    """
    path = Path(class_weights_path)
    if not path.is_file():
        raise BaselineError(f"class_weights.json not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    weights = data.get("weights")
    if not isinstance(weights, dict) or not weights:
        raise BaselineError(f"class_weights.json has no valid 'weights' mapping: {path}")
    classes_by_field = {}
    for field, class_map in weights.items():
        if not isinstance(class_map, dict) or not class_map:
            raise BaselineError(f"field {field!r} in class_weights.json has no classes")
        classes_by_field[field] = list(class_map.keys())
    return classes_by_field


def build_baseline_config(dataset_version):
    """Build the ExperimentConfig with Hazem's exact settings plus sklearn defaults.

    Settings explicitly set in Hazem's notebook:
    - tfidf_text_column = 'text_norm'
    - tfidf_max_features = 5000
    - tfidf_ngram_range = [1, 2]
    - tfidf_fit_scope = 'once_on_train_for_all_fields'
    - logreg_class_weight = 'balanced'
    - logreg_max_iter = 1000

    The remaining keys starting with tfidf_default_ and logreg_default_ are
    the defaults of the installed scikit-learn version, read at run time from
    TfidfVectorizer().get_params() and LogisticRegression().get_params() (they
    are not written in Hazem's notebook).
    """
    tfidf_defaults = TfidfVectorizer().get_params()
    logreg_defaults = LogisticRegression().get_params()

    other_hyperparameters = {
        "tfidf_text_column": "text_norm",
        "tfidf_max_features": 5000,
        "tfidf_ngram_range": [1, 2],
        "tfidf_fit_scope": "once_on_train_for_all_fields",
        "logreg_class_weight": "balanced",
        "logreg_max_iter": 1000,
        # Installed scikit-learn defaults (not written in Hazem's notebook):
        "sklearn_version": sklearn.__version__,
        "tfidf_default_min_df": tfidf_defaults["min_df"],
        "tfidf_default_max_df": tfidf_defaults["max_df"],
        "tfidf_default_sublinear_tf": tfidf_defaults["sublinear_tf"],
        "tfidf_default_lowercase": tfidf_defaults["lowercase"],
        "tfidf_default_analyzer": tfidf_defaults["analyzer"],
        "tfidf_default_norm": tfidf_defaults["norm"],
        "logreg_C": logreg_defaults["C"],
        "logreg_l1_ratio": logreg_defaults["l1_ratio"],
        "logreg_default_solver": logreg_defaults["solver"],
        "logreg_regularization_note": (
            "effective regularization is L2: l1_ratio=0; the penalty parameter "
            "is deprecated since scikit-learn 1.8 and removed in 1.10"
        ),
    }
    return ExperimentConfig(
        model=MODEL_NAME,
        dataset_version=dataset_version,
        split="train",
        other_hyperparameters=other_hyperparameters,
    )


def load_split_table(csv_path, expected_split, text_column, fields):
    """Read audio_file, split, text_column, and label columns into memory only.

    Uses dtype=str and keep_default_na=False, which is equivalent to Hazem's
    fillna('') because the training skeleton verifies there are no empty
    text_norm rows. Refuses the test split.

    Returns (texts_by_audio_file, label_rows) where label_rows holds only
    audio_file and the four label columns (no transcript text).
    """
    _refuse_test_split(expected_split)
    path = Path(csv_path)
    if not path.is_file():
        raise BaselineError(f"split CSV not found: {path}")
    columns = ["audio_file", "split", text_column, *fields]
    try:
        table = pd.read_csv(path, usecols=columns, dtype=str, keep_default_na=False)
    except ValueError as exc:
        raise BaselineError(f"{path}: {exc}") from exc

    if table.empty:
        raise BaselineError(f"{path}: table is empty")

    wrong_splits = sorted(set(table["split"]) - {expected_split})
    if wrong_splits:
        raise BaselineError(
            f"{path}: the split column has {wrong_splits}, expected only {expected_split!r}"
        )

    audio_files = table["audio_file"].tolist()
    if any(not isinstance(a, str) or not a.strip() for a in audio_files):
        raise BaselineError(f"{path}: empty audio_file found")
    if len(set(audio_files)) != len(audio_files):
        raise BaselineError(f"{path}: duplicate audio_file found in split {expected_split!r}")

    texts = table[text_column].tolist()
    if any(not isinstance(t, str) or not t.strip() for t in texts):
        raise BaselineError(f"{path}: empty {text_column} row found")

    texts_by_audio = dict(zip(audio_files, texts))
    label_rows = table[["audio_file", *fields]].to_dict("records")
    return texts_by_audio, label_rows


def fit_and_predict_probabilities(
    config,
    train_texts_by_audio,
    train_label_rows,
    val_texts_by_audio,
    val_label_rows,
    classes_by_field,
    seed,
):
    """Train TF-IDF + LogisticRegression per field for one seed and return val probability rows.

    - Reads all hyperparameters from config.other_hyperparameters.
    - Fits TfidfVectorizer ONCE on the train texts only; val texts are only transformed.
    - Passes random_state=seed explicitly to LogisticRegression (per infra/seeds.py).
      Note: Hazem's notebook does not pass random_state; with the default lbfgs
      solver, random_state has no effect on the fitted weights.
    - Maps predict_proba columns to class names using the class list order after
      checking that clf.classes_ equals the field's class list.
    """
    hp = config.other_hyperparameters
    max_features = hp["tfidf_max_features"]
    ngram_range = tuple(hp["tfidf_ngram_range"])
    class_weight = hp["logreg_class_weight"]
    max_iter = hp["logreg_max_iter"]

    train_order = [r["audio_file"] for r in train_label_rows]
    val_order = [r["audio_file"] for r in val_label_rows]
    if len(set(train_order)) != len(train_order) or set(train_order) != set(train_texts_by_audio):
        raise BaselineError("train audio_file keys do not match between text and labels")
    if len(set(val_order)) != len(val_order) or set(val_order) != set(val_texts_by_audio):
        raise BaselineError("val audio_file keys do not match between text and labels")

    train_texts = [train_texts_by_audio[a] for a in train_order]
    val_texts = [val_texts_by_audio[a] for a in val_order]

    vectorizer = TfidfVectorizer(max_features=max_features, ngram_range=ngram_range)
    x_train = vectorizer.fit_transform(train_texts)
    x_val = vectorizer.transform(val_texts)

    per_field_probs = {}
    for field, classes in classes_by_field.items():
        classes = list(classes)
        y_train = [r[field] for r in train_label_rows]
        present = set(y_train)
        missing_in_train = [c for c in classes if c not in present]
        if missing_in_train:
            raise BaselineError(
                f"field {field!r}: classes {missing_in_train} have no rows in train"
            )
        unlisted_in_train = sorted(present - set(classes))
        if unlisted_in_train:
            raise BaselineError(
                f"field {field!r}: train has labels outside the class list: {unlisted_in_train}"
            )

        # Hazem's notebook does not pass random_state. We pass random_state=seed
        # per infra/seeds.py; with the default lbfgs solver it has no effect.
        clf = LogisticRegression(
            class_weight=class_weight,
            max_iter=max_iter,
            random_state=seed,
        )
        clf.fit(x_train, y_train)

        fitted_classes = [str(c) for c in clf.classes_.tolist()]
        if fitted_classes != classes:
            raise BaselineError(
                f"field {field!r}: clf.classes_ {fitted_classes} does not equal "
                f"the class list {classes}"
            )

        probs_matrix = clf.predict_proba(x_val)
        col_index = {c: idx for idx, c in enumerate(fitted_classes)}
        per_field_probs[field] = [
            {c: float(probs_matrix[row_idx, col_index[c]]) for c in classes}
            for row_idx in range(len(val_order))
        ]

    prob_rows = []
    for row_idx, audio_file in enumerate(val_order):
        prob_rows.append({
            "audio_file": audio_file,
            "probabilities": {
                field: per_field_probs[field][row_idx]
                for field in classes_by_field
            },
        })
    return prob_rows


def run_tfidf_baseline(
    data_dir,
    runs_dir,
    *,
    run_id=DEFAULT_RUN_ID,
    evaluated_split="val",
    device="cpu",
    hypothesis=DEFAULT_HYPOTHESIS,
):
    """Run the 5-seed TF-IDF baseline on train and evaluate on val only.

    Writes one predictions file per seed and one run record under
    runs_dir/exp_<run_id>/. Returns a dict with the run record, the per-seed
    harness reports, and the relative artifact paths.
    """
    if evaluated_split != "val":
        _refuse_test_split(evaluated_split)
        raise BaselineError(f"evaluated_split must be 'val', got {evaluated_split!r}")

    data_dir = Path(data_dir)
    runs_dir = Path(runs_dir)

    shared_config = load_shared_config(
        data_dir / "notebooks" / "training" / "shared_config.json"
    )
    classes_by_field = load_classes_by_field(data_dir / "final" / "class_weights.json")
    config = build_baseline_config(shared_config["dataset_version"])
    text_column = config.other_hyperparameters["tfidf_text_column"]
    fields = list(classes_by_field.keys())

    train_texts_by_audio, train_label_rows = load_split_table(
        data_dir / "final" / "clean_training_train.csv",
        "train",
        text_column,
        fields,
    )
    val_texts_by_audio, val_label_rows = load_split_table(
        data_dir / "final" / "clean_training_val.csv",
        "val",
        text_column,
        fields,
    )

    if len(train_label_rows) != shared_config["train_rows"]:
        raise BaselineError(
            f"train has {len(train_label_rows)} rows, expected {shared_config['train_rows']}"
        )
    if len(val_label_rows) != shared_config["val_rows"]:
        raise BaselineError(
            f"val has {len(val_label_rows)} rows, expected {shared_config['val_rows']}"
        )

    seed_reports = []
    prediction_rel_paths = []

    def _one_seed(seed):
        prob_rows = fit_and_predict_probabilities(
            config=config,
            train_texts_by_audio=train_texts_by_audio,
            train_label_rows=train_label_rows,
            val_texts_by_audio=val_texts_by_audio,
            val_label_rows=val_label_rows,
            classes_by_field=classes_by_field,
            seed=seed,
        )
        pred_path = predictions_path(runs_dir, run_id, "val", seed)
        write_predictions_file(
            path=pred_path,
            run_id=run_id,
            model=config.model,
            split="val",
            seed=seed,
            dataset_version=shared_config["dataset_version"],
            rows=prob_rows,
            classes_by_field=classes_by_field,
        )
        prediction_rel_paths.append(f"runs/exp_{run_id}/{pred_path.name}")

        loaded = read_predictions_file(
            pred_path,
            classes_by_field,
            expected_split="val",
        )
        report = evaluate_predictions(
            split="val",
            truth_rows=val_label_rows,
            pred_rows=loaded["harness_rows"],
            classes_by_field=classes_by_field,
            exclusions_by_field=CUSTOMER_STATE_EXCLUSIONS,
        )
        seed_reports.append(report)
        return seed_metrics(report["fields"])

    over_seeds = run_over_seeds(_one_seed, shared_config["experiment_seeds"])
    per_seed = [
        make_seed_result(run_id, config, "val", r["seed"], r["result"])
        for r in over_seeds
    ]

    record = build_run_record(
        run_id=run_id,
        hypothesis=hypothesis,
        config=config,
        shared_config=shared_config,
        per_seed=per_seed,
        evaluated_split="val",
        artifacts={"predictions": prediction_rel_paths},
        device=device,
        exceptions=seed_reports[0]["exceptions"],
        reference_config=None,
        changed_factor=None,
        reference_run_id=None,
    )
    record_file = save_run_record(record, runs_dir)

    return {
        "record": record,
        "record_path": record_file,
        "seed_reports": seed_reports,
        "combined_macro_f1": combine_macro_f1(seed_reports[0]["fields"]),
    }
