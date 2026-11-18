import csv
import hashlib
import json

import pytest
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from infra.run_record import load_run_record
from infra.tfidf_baseline import (
    CUSTOMER_STATE_EXCLUSIONS,
    DEFAULT_RUN_ID,
    MODEL_NAME,
    BaselineError,
    build_baseline_config,
    fit_and_predict_probabilities,
    load_classes_by_field,
    load_split_table,
    run_tfidf_baseline,
)

# Synthetic class lists (never using real data in unit tests).
# Keys are in alphabetical order, matching class_weights.json and sklearn classes_.
SYNTHETIC_WEIGHTS = {
    "rows": 12,
    "method": "synthetic fixture",
    "weights": {
        "complaint_category": {
            "app_and_account": 1.0,
            "billing_and_charges": 1.0,
            "network_and_connectivity": 1.0,
        },
        "complaint_urgency": {
            "high": 1.0,
            "low": 1.0,
            "medium": 1.0,
        },
        "customer_state": {
            "calm": 1.0,
            "frustrated": 1.0,
            "mad": 1.0,
            "satisfied": 1.0,
        },
        "churn_risk": {
            "at_risk": 2.0,
            "not_at_risk": 0.5,
        },
    },
}

SECRET_MARKER = "DUMMY_SECRET_TRANSCRIPT_TOKEN_998877"


def _make_synthetic_dataset(root_dir, include_unclear=False):
    """Write a complete synthetic data_dir with shared_config, class_weights, train and val CSVs."""
    nb_dir = root_dir / "notebooks" / "training"
    final_dir = root_dir / "final"
    nb_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)

    train_rows = [
        {
            "audio_file": f"tr_{i:02d}.wav",
            "split": "train",
            "text_norm": (
                f"{SECRET_MARKER} cat_app urg_high state_calm churn_yes"
                if i % 4 == 0
                else f"{SECRET_MARKER} cat_bill urg_low state_frustrated churn_no"
                if i % 4 == 1
                else f"{SECRET_MARKER} cat_net urg_med state_mad churn_no"
                if i % 4 == 2
                else f"{SECRET_MARKER} cat_app urg_low state_satisfied churn_no"
            ),
            "complaint_category": (
                "app_and_account"
                if i % 4 in (0, 3)
                else "billing_and_charges"
                if i % 4 == 1
                else "network_and_connectivity"
            ),
            "complaint_urgency": (
                "high" if i % 4 == 0 else "low" if i % 4 in (1, 3) else "medium"
            ),
            "customer_state": (
                "calm"
                if i % 4 == 0
                else "frustrated"
                if i % 4 == 1
                else "mad"
                if i % 4 == 2
                else "satisfied"
            ),
            "churn_risk": "at_risk" if i % 4 == 0 else "not_at_risk",
        }
        for i in range(12)
    ]

    # Validation has 5 rows; row 4 has true customer_state = 'unclear' and a val-only token.
    val_rows = [
        {
            "audio_file": "va_00.wav",
            "split": "val",
            "text_norm": f"{SECRET_MARKER} cat_app urg_high state_calm churn_yes",
            "complaint_category": "app_and_account",
            "complaint_urgency": "high",
            "customer_state": "calm",
            "churn_risk": "at_risk",
        },
        {
            "audio_file": "va_01.wav",
            "split": "val",
            "text_norm": f"{SECRET_MARKER} cat_bill urg_low state_frustrated churn_no",
            "complaint_category": "billing_and_charges",
            "complaint_urgency": "low",
            "customer_state": "frustrated",
            "churn_risk": "not_at_risk",
        },
        {
            "audio_file": "va_02.wav",
            "split": "val",
            "text_norm": f"{SECRET_MARKER} cat_net urg_med state_mad churn_no",
            "complaint_category": "network_and_connectivity",
            "complaint_urgency": "medium",
            "customer_state": "mad",
            "churn_risk": "not_at_risk",
        },
        {
            "audio_file": "va_03.wav",
            "split": "val",
            "text_norm": f"{SECRET_MARKER} cat_app urg_low state_satisfied churn_no",
            "complaint_category": "app_and_account",
            "complaint_urgency": "low",
            "customer_state": "satisfied",
            "churn_risk": "not_at_risk",
        },
        {
            "audio_file": "va_04.wav",
            "split": "val",
            "text_norm": f"{SECRET_MARKER} VAL_ONLY_TOKEN_XYZ cat_bill urg_low state_frustrated churn_no",
            "complaint_category": "billing_and_charges",
            "complaint_urgency": "low",
            "customer_state": "unclear" if include_unclear else "frustrated",
            "churn_risk": "not_at_risk",
        },
    ]

    shared = {
        "split_seed": 42,
        "experiment_seeds": [42, 1337, 2023, 7, 99],
        "max_seq_len": 128,
        "split_ratio": "70/20/10",
        "dataset_version": "v2",
        "dataset": "svr-voicemail-corpus",
        "train_rows": len(train_rows),
        "val_rows": len(val_rows),
        "test_rows": 3,
    }
    (nb_dir / "shared_config.json").write_text(json.dumps(shared), encoding="utf-8")
    (final_dir / "class_weights.json").write_text(
        json.dumps(SYNTHETIC_WEIGHTS), encoding="utf-8"
    )

    for split_name, rows in (("train", train_rows), ("val", val_rows)):
        csv_path = final_dir / f"clean_training_{split_name}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    return root_dir


def test_settings_in_config_match_reference_notebook():
    cfg = build_baseline_config(
        "v2",
        data_sha256_train="abc123train",
        data_sha256_val="def456val",
    )
    assert cfg.model == MODEL_NAME
    assert cfg.dataset_version == "v2"
    assert cfg.split == "train"
    assert cfg.learning_rate is None
    assert cfg.batch_size is None
    assert cfg.epochs is None

    hp = cfg.other_hyperparameters
    assert hp["tfidf_text_column"] == "text_norm"
    assert hp["tfidf_max_features"] == 5000
    assert hp["tfidf_ngram_range"] == [1, 2]
    assert hp["tfidf_fit_scope"] == "once_on_train_for_all_fields"
    assert hp["logreg_class_weight"] == "balanced"
    assert hp["logreg_max_iter"] == 1000

    # Installed scikit-learn defaults must also be recorded:
    t_def = TfidfVectorizer().get_params()
    l_def = LogisticRegression().get_params()
    assert hp["sklearn_version"] == sklearn.__version__
    assert hp["tfidf_default_min_df"] == t_def["min_df"]
    assert hp["tfidf_default_sublinear_tf"] == t_def["sublinear_tf"]
    assert hp["tfidf_default_lowercase"] == t_def["lowercase"]
    assert hp["tfidf_default_analyzer"] == t_def["analyzer"]
    assert hp["logreg_C"] == l_def["C"]
    assert hp["logreg_l1_ratio"] == l_def["l1_ratio"]
    assert hp["logreg_default_solver"] == l_def["solver"]
    assert hp["logreg_regularization_note"] == (
        "effective regularization is L2: l1_ratio=0; the penalty parameter "
        "is deprecated since scikit-learn 1.8 and removed in 1.10"
    )
    assert hp["data_sha256_train"] == "abc123train"
    assert hp["data_sha256_val"] == "def456val"
    assert "penalty" not in hp and not any("penalty" in k for k in hp)


def test_vectorizer_is_fitted_once_on_train_text_only(tmp_path, monkeypatch):
    data_dir = _make_synthetic_dataset(tmp_path / "data")
    classes = load_classes_by_field(data_dir / "final" / "class_weights.json")
    cfg = build_baseline_config("v2")
    tr_texts, tr_labels = load_split_table(
        data_dir / "final" / "clean_training_train.csv", "train", "text_norm", list(classes)
    )
    va_texts, va_labels = load_split_table(
        data_dir / "final" / "clean_training_val.csv", "val", "text_norm", list(classes)
    )

    fit_calls = []
    transform_calls = []
    orig_fit_transform = TfidfVectorizer.fit_transform
    orig_transform = TfidfVectorizer.transform

    def spy_fit_transform(self, raw_documents, y=None):
        docs = list(raw_documents)
        fit_calls.append((self, docs))
        return orig_fit_transform(self, docs, y=y)

    def spy_transform(self, raw_documents):
        docs = list(raw_documents)
        transform_calls.append(docs)
        return orig_transform(self, docs)

    monkeypatch.setattr(TfidfVectorizer, "fit_transform", spy_fit_transform)
    monkeypatch.setattr(TfidfVectorizer, "transform", spy_transform)

    fit_and_predict_probabilities(cfg, tr_texts, tr_labels, va_texts, va_labels, classes, seed=42)

    # Fitted exactly once across all four fields, on the 12 train texts only:
    assert len(fit_calls) == 1
    vec_instance, fitted_docs = fit_calls[0]
    assert len(fitted_docs) == 12
    assert all("VAL_ONLY_TOKEN_XYZ" not in d for d in fitted_docs)
    assert "val_only_token_xyz" not in vec_instance.vocabulary_
    assert len(transform_calls) == 1
    assert len(transform_calls[0]) == 5


def test_same_seed_gives_identical_probabilities_and_rows_sum_to_one(tmp_path):
    data_dir = _make_synthetic_dataset(tmp_path / "data")
    classes = load_classes_by_field(data_dir / "final" / "class_weights.json")
    cfg = build_baseline_config("v2")
    tr_texts, tr_labels = load_split_table(
        data_dir / "final" / "clean_training_train.csv", "train", "text_norm", list(classes)
    )
    va_texts, va_labels = load_split_table(
        data_dir / "final" / "clean_training_val.csv", "val", "text_norm", list(classes)
    )

    run_a = fit_and_predict_probabilities(cfg, tr_texts, tr_labels, va_texts, va_labels, classes, seed=42)
    run_b = fit_and_predict_probabilities(cfg, tr_texts, tr_labels, va_texts, va_labels, classes, seed=42)
    assert run_a == run_b

    for row in run_a:
        for field, cls_list in classes.items():
            probs = row["probabilities"][field]
            assert list(probs.keys()) == cls_list
            assert sum(probs.values()) == pytest.approx(1.0, abs=1e-6)


def test_probability_columns_map_to_the_right_class_names(tmp_path):
    data_dir = _make_synthetic_dataset(tmp_path / "data")
    classes = load_classes_by_field(data_dir / "final" / "class_weights.json")
    cfg = build_baseline_config("v2")
    tr_texts, tr_labels = load_split_table(
        data_dir / "final" / "clean_training_train.csv", "train", "text_norm", list(classes)
    )
    va_texts, va_labels = load_split_table(
        data_dir / "final" / "clean_training_val.csv", "val", "text_norm", list(classes)
    )

    prob_rows = fit_and_predict_probabilities(
        cfg, tr_texts, tr_labels, va_texts, va_labels, classes, seed=42
    )
    by_audio = {r["audio_file"]: r["probabilities"] for r in prob_rows}

    # Each validation row 0..3 has distinct keywords matching its true class in every field.
    for row in va_labels[:4]:
        af = row["audio_file"]
        for field, cls_list in classes.items():
            expected_class = row[field]
            p_dict = by_audio[af][field]
            best_class = max(cls_list, key=lambda c: p_dict[c])
            assert best_class == expected_class, (
                f"row {af} field {field}: expected highest prob on {expected_class!r}, got {best_class!r}"
            )


def test_test_split_is_refused(tmp_path):
    data_dir = _make_synthetic_dataset(tmp_path / "data")
    classes = load_classes_by_field(data_dir / "final" / "class_weights.json")
    with pytest.raises(BaselineError, match="test split"):
        load_split_table(
            data_dir / "final" / "clean_training_val.csv", "test", "text_norm", list(classes)
        )
    with pytest.raises(BaselineError, match="test split"):
        run_tfidf_baseline(data_dir, tmp_path / "runs", evaluated_split="test")


def test_no_transcript_text_in_stdout_or_written_files(tmp_path, capsys):
    data_dir = _make_synthetic_dataset(tmp_path / "data")
    runs_dir = tmp_path / "runs"

    result = run_tfidf_baseline(data_dir, runs_dir)
    captured = capsys.readouterr()
    assert SECRET_MARKER not in captured.out
    assert SECRET_MARKER not in captured.err

    exp_dir = runs_dir / f"exp_{DEFAULT_RUN_ID}"
    written_files = list(exp_dir.rglob("*.json"))
    assert len(written_files) == 6  # 5 seed prediction files + 1 run_record.json
    for fpath in written_files:
        content = fpath.read_text(encoding="utf-8")
        assert SECRET_MARKER not in content
        assert "VAL_ONLY_TOKEN_XYZ" not in content

    rec = load_run_record(result["record_path"])
    assert rec["run_id"] == DEFAULT_RUN_ID
    expected_train_sha = hashlib.sha256(
        (data_dir / "final" / "clean_training_train.csv").read_bytes()
    ).hexdigest()
    expected_val_sha = hashlib.sha256(
        (data_dir / "final" / "clean_training_val.csv").read_bytes()
    ).hexdigest()
    rec_hp = rec["config"]["other_hyperparameters"]
    assert rec_hp["data_sha256_train"] == expected_train_sha
    assert rec_hp["data_sha256_val"] == expected_val_sha
    assert not (data_dir / "final" / "clean_training_test.csv").exists()

    with pytest.raises(FileExistsError):
        run_tfidf_baseline(data_dir, runs_dir)


def test_unclear_row_in_val_is_excluded_from_customer_state_only(tmp_path):
    data_dir = _make_synthetic_dataset(tmp_path / "data", include_unclear=True)
    runs_dir = tmp_path / "runs"

    result = run_tfidf_baseline(data_dir, runs_dir)
    report = result["seed_reports"][0]
    n_total = report["n"]
    assert n_total == 5

    assert report["exceptions"] == [{
        "field": "customer_state",
        "excluded_labels": ["unclear"],
        "rows_excluded": 1,
        "n_scored": n_total - 1,
        "n_total_rows": n_total,
        "reason": CUSTOMER_STATE_EXCLUSIONS["customer_state"]["reason"],
    }]
    assert report["fields"]["customer_state"]["n"] == n_total - 1
    for other_field in ("complaint_category", "complaint_urgency", "churn_risk"):
        assert report["fields"][other_field]["n"] == n_total


def test_class_with_zero_train_rows_raises_error(tmp_path):
    data_dir = _make_synthetic_dataset(tmp_path / "data")
    classes = load_classes_by_field(data_dir / "final" / "class_weights.json")
    classes["churn_risk"].append("extra_class_with_no_rows")
    cfg = build_baseline_config("v2")
    tr_texts, tr_labels = load_split_table(
        data_dir / "final" / "clean_training_train.csv", "train", "text_norm", list(classes)
    )
    va_texts, va_labels = load_split_table(
        data_dir / "final" / "clean_training_val.csv", "val", "text_norm", list(classes)
    )
    with pytest.raises(BaselineError, match="no rows in train"):
        fit_and_predict_probabilities(cfg, tr_texts, tr_labels, va_texts, va_labels, classes, seed=42)


def test_duplicate_audio_file_or_wrong_split_column_raises_error(tmp_path):
    data_dir = _make_synthetic_dataset(tmp_path / "data")
    classes = load_classes_by_field(data_dir / "final" / "class_weights.json")
    bad_csv = tmp_path / "dup.csv"
    rows = [
        {
            "audio_file": "same.wav",
            "split": "train",
            "text_norm": "hello",
            "complaint_category": "app_and_account",
            "complaint_urgency": "high",
            "customer_state": "calm",
            "churn_risk": "at_risk",
        },
        {
            "audio_file": "same.wav",
            "split": "train",
            "text_norm": "world",
            "complaint_category": "billing_and_charges",
            "complaint_urgency": "low",
            "customer_state": "mad",
            "churn_risk": "not_at_risk",
        },
    ]
    with bad_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(BaselineError, match="duplicate"):
        load_split_table(bad_csv, "train", "text_norm", list(classes))
    with pytest.raises(BaselineError, match="split column"):
        load_split_table(bad_csv, "val", "text_norm", list(classes))
