import csv

import pytest

from infra.experiment_config import ExperimentConfig
from infra.harness import (
    DEFAULT_LABEL_STATUS,
    HarnessError,
    evaluate_predictions,
    load_truth_table,
)
from infra.metrics import seed_metrics
from infra.mock_predictions import make_mock_predictions
from infra.once_guard import claim_test_evaluation
from infra.run_record import build_run_record, make_seed_result
from infra.seeds import run_over_seeds

# Synthetic fixture, small enough to check by hand.
#   field_x: classes a, b           field_y: classes p, q
# Row r7 has the true label "unclear" in field_y. "unclear" is not a class of
# field_y: it is excluded from field_y's score (and only from field_y's score).
CLASSES = {"field_x": ["a", "b"], "field_y": ["p", "q"]}
REASON = "unclear has no rows in train, so the model never trains on it (Hazem's decision)."
EXCLUSIONS = {"field_y": {"labels": ["unclear"], "reason": REASON}}
TRUTH = [
    {"audio_file": "r1.wav", "field_x": "a", "field_y": "p"},
    {"audio_file": "r2.wav", "field_x": "a", "field_y": "p"},
    {"audio_file": "r3.wav", "field_x": "a", "field_y": "q"},
    {"audio_file": "r4.wav", "field_x": "b", "field_y": "q"},
    {"audio_file": "r5.wav", "field_x": "b", "field_y": "p"},
    {"audio_file": "r6.wav", "field_x": "b", "field_y": "q"},
    {"audio_file": "r7.wav", "field_x": "a", "field_y": "unclear"},
]
# wrong_every=3 turns rows 3 and 6 into the next class.
#   field_x (all 7 rows count): true a,a,a,b,b,b,a   predicted a,a,b,b,b,a,a
#       confusion [[3, 1], [1, 2]]  precision/recall a 3/4, b 2/3  F1 0.75 and 2/3
#       macro-F1 = (0.75 + 2/3) / 2 = 0.708333   accuracy 5/7
#   field_y (r7 is left out, 6 rows count): true p,p,q,q,p,q   predicted p,p,p,q,p,p
#       confusion [[3, 0], [2, 1]]  p: precision 3/5, recall 1, F1 0.75
#                                   q: precision 1, recall 1/3, F1 0.5
#       macro-F1 = 0.625   accuracy 4/6
#   combined mean = (0.708333 + 0.625) / 2 = 2/3


def evaluate(pred_rows=None, **overrides):
    args = dict(
        split="val",
        truth_rows=TRUTH,
        pred_rows=pred_rows
        if pred_rows is not None
        else make_mock_predictions(TRUTH, CLASSES, exclusions_by_field=EXCLUSIONS),
        classes_by_field=CLASSES,
        exclusions_by_field=EXCLUSIONS,
    )
    args.update(overrides)
    return evaluate_predictions(**args)


def mock(**kwargs):
    return make_mock_predictions(TRUTH, CLASSES, exclusions_by_field=EXCLUSIONS, **kwargs)


def test_perfect_mock_predictions():
    r = evaluate()
    assert r["fields"]["field_x"]["macro"]["f1"] == pytest.approx(1.0)
    assert r["fields"]["field_y"]["macro"]["f1"] == pytest.approx(1.0)
    assert r["combined_macro_f1"]["mean"] == pytest.approx(1.0)


def test_mock_errors_match_the_hand_calculation():
    r = evaluate(mock(wrong_every=3))
    x, y = r["fields"]["field_x"], r["fields"]["field_y"]
    assert x["confusion_matrix"]["counts"] == [[3, 1], [1, 2]]
    assert x["macro"]["f1"] == pytest.approx((0.75 + 2 / 3) / 2)
    assert x["accuracy"] == pytest.approx(5 / 7)
    assert y["confusion_matrix"]["counts"] == [[3, 0], [2, 1]]
    assert y["per_class"]["p"]["precision"] == pytest.approx(0.6)
    assert y["per_class"]["q"]["recall"] == pytest.approx(1 / 3)
    assert y["macro"]["f1"] == pytest.approx(0.625)
    assert y["accuracy"] == pytest.approx(4 / 6)
    assert r["combined_macro_f1"]["mean"] == pytest.approx(2 / 3)


def test_the_excluded_row_is_left_out_of_that_field_only():
    r = evaluate(mock(wrong_every=3))
    assert r["n"] == 7
    assert r["fields"]["field_x"]["n"] == 7 and r["fields"]["field_x"]["n_excluded"] == 0
    assert r["fields"]["field_y"]["n"] == 6 and r["fields"]["field_y"]["n_excluded"] == 1


def test_the_exclusion_is_written_as_an_exception():
    r = evaluate()
    assert r["exceptions"] == [{
        "field": "field_y",
        "excluded_labels": ["unclear"],
        "rows_excluded": 1,
        "n_scored": 6,
        "n_total_rows": 7,
        "reason": REASON,
    }]


def test_an_exclusion_that_removes_no_rows_is_still_written():
    truth = [row for row in TRUTH if row["field_y"] != "unclear"]
    preds = make_mock_predictions(truth, CLASSES, exclusions_by_field=EXCLUSIONS)
    r = evaluate(preds, truth_rows=truth)
    assert r["exceptions"][0]["rows_excluded"] == 0
    assert r["exceptions"][0]["n_scored"] == 6 and r["exceptions"][0]["n_total_rows"] == 6


def test_without_the_exclusion_an_unlisted_true_label_is_an_error():
    preds = make_mock_predictions(TRUTH, CLASSES, exclusions_by_field=EXCLUSIONS)
    with pytest.raises(HarnessError, match="field field_y"):
        evaluate(preds, exclusions_by_field=None)


def test_report_shape_and_label_status():
    r = evaluate()
    assert list(r) == [
        "schema_version", "split", "n", "label_status", "fields", "exceptions", "combined_macro_f1",
    ]
    assert r["schema_version"] == 2
    assert r["split"] == "val"
    assert list(r["fields"]) == ["field_x", "field_y"]
    assert r["label_status"] == DEFAULT_LABEL_STATUS
    assert "model" in r["label_status"] and "not human-verified" in r["label_status"]
    assert set(r["combined_macro_f1"]["values"]) == {"field_x", "field_y"}


def test_the_label_status_can_be_replaced():
    r = evaluate(label_status="The labels were approved by the audit on a date.")
    assert r["label_status"].startswith("The labels were approved")


def test_row_order_does_not_matter():
    preds = mock(wrong_every=3)
    assert evaluate(list(reversed(preds))) == evaluate(preds)


def test_only_val_and_test_can_be_scored():
    with pytest.raises(HarnessError, match="split"):
        evaluate(split="train")


def test_missing_and_extra_predictions_are_rejected():
    preds = mock()
    with pytest.raises(HarnessError, match="no prediction"):
        evaluate(preds[:-1])
    extra = preds + [{"audio_file": "r8.wav", "field_x": "a", "field_y": "p"}]
    with pytest.raises(HarnessError, match="no true row"):
        evaluate(extra)


def test_repeated_rows_are_rejected():
    preds = mock()
    with pytest.raises(HarnessError, match="more than once"):
        evaluate(preds + [preds[0]])
    with pytest.raises(HarnessError, match="more than once"):
        evaluate(truth_rows=TRUTH + [TRUTH[0]])


def test_a_missing_field_is_rejected():
    preds = mock()
    del preds[2]["field_y"]
    with pytest.raises(HarnessError, match="missing fields"):
        evaluate(preds)


def test_a_label_outside_the_class_list_names_the_field():
    preds = mock()
    preds[0]["field_y"] = "not_a_class"
    with pytest.raises(HarnessError, match="field field_y"):
        evaluate(preds)


def test_a_prediction_on_an_excluded_row_must_still_be_a_real_class():
    preds = mock()
    preds[6]["field_y"] = "unclear"  # r7: its true label is excluded, but "unclear" is not a class
    with pytest.raises(HarnessError, match="field field_y"):
        evaluate(preds)


def test_the_same_names_in_two_splits_are_scored_separately(tmp_path):
    val_truth = [{"audio_file": "calm_0001.wav", "field_x": "a", "field_y": "p"}]
    test_truth = [{"audio_file": "calm_0001.wav", "field_x": "b", "field_y": "q"}]
    claim = claim_test_evaluation(
        tmp_path / "test_evaluations.json",
        model="mock",
        dataset_version="v2",
        run_id="001",
        uses=1,
    )
    val = evaluate_predictions("val", val_truth, make_mock_predictions(val_truth, CLASSES), CLASSES)
    test = evaluate_predictions(
        "test", test_truth, make_mock_predictions(test_truth, CLASSES), CLASSES, test_claim=claim
    )
    assert val["split"] == "val" and test["split"] == "test"
    assert val["n"] == 1 and test["n"] == 1
    assert val["exceptions"] == []


def test_test_split_requires_valid_claim_consumes_uses_and_val_refuses_claim(tmp_path):
    truth = [{"audio_file": "r1.wav", "field_x": "a", "field_y": "p"}]
    preds = make_mock_predictions(truth, CLASSES)

    # Split "test" without a claim is refused.
    with pytest.raises(HarnessError, match="test-once guard"):
        evaluate_predictions("test", truth, preds, CLASSES)

    # Split "test" with a valid claim scores and consumes one use.
    claim = claim_test_evaluation(
        tmp_path / "test_evaluations.json",
        model="mock-model",
        dataset_version="v2",
        run_id="t01",
        uses=2,
    )
    assert claim.remaining == 2
    evaluate_predictions("test", truth, preds, CLASSES, test_claim=claim)
    assert claim.remaining == 1
    evaluate_predictions("test", truth, preds, CLASSES, test_claim=claim)
    assert claim.remaining == 0 and claim.consumed

    # After all uses are gone, split "test" is refused.
    with pytest.raises(HarnessError, match="no uses left"):
        evaluate_predictions("test", truth, preds, CLASSES, test_claim=claim)

    # Split "val" with a claim is refused.
    fresh_claim = claim_test_evaluation(
        tmp_path / "test_evaluations.json",
        model="other-model",
        dataset_version="v2",
        run_id="t02",
        uses=1,
    )
    with pytest.raises(HarnessError, match="test_claim must be None"):
        evaluate_predictions("val", truth, preds, CLASSES, test_claim=fresh_claim)


def test_bad_exclusions_are_rejected():
    ok = {"labels": ["unclear"], "reason": REASON}
    for bad in [
        {"nope": ok},                                                    # not a field
        {"field_y": {"labels": ["unclear"]}},                            # no reason
        {"field_y": {"labels": ["unclear"], "reason": "  "}},            # empty reason
        {"field_y": {"labels": [], "reason": REASON}},                   # no labels
        {"field_y": {"labels": "unclear", "reason": REASON}},            # not a list
        {"field_y": {"labels": ["q"], "reason": REASON}},                # also a class
        {"field_y": {"labels": ["unclear"], "reason": REASON, "x": 1}},  # extra key
        ["field_y"],                                                     # not a dict
    ]:
        with pytest.raises(HarnessError):
            evaluate(exclusions_by_field=bad)


def test_excluding_every_row_of_a_field_is_an_error():
    truth = [{"audio_file": "r1.wav", "field_x": "a", "field_y": "unclear"}]
    preds = make_mock_predictions(truth, CLASSES, exclusions_by_field=EXCLUSIONS)
    with pytest.raises(HarnessError, match="field field_y"):
        evaluate(preds, truth_rows=truth)


def test_mock_predictions_are_validated():
    with pytest.raises(HarnessError, match="wrong_every"):
        make_mock_predictions(TRUTH, CLASSES, wrong_every=0, exclusions_by_field=EXCLUSIONS)
    with pytest.raises(HarnessError, match="wrong_every"):
        make_mock_predictions(TRUTH, CLASSES, wrong_every=True, exclusions_by_field=EXCLUSIONS)
    bad = [{"audio_file": "r1.wav", "field_x": "zzz", "field_y": "p"}]
    with pytest.raises(HarnessError, match="not in"):
        make_mock_predictions(bad, CLASSES)
    with pytest.raises(HarnessError, match="not in"):
        make_mock_predictions(TRUTH, CLASSES)  # r7 has an unlisted label and no exclusion given


def test_mock_wrong_labels_are_real_classes_and_differ():
    preds = mock(wrong_every=3)
    for i, (t, p) in enumerate(zip(TRUTH, preds), start=1):
        for field, classes in CLASSES.items():
            assert p[field] in classes
            if t[field] in classes:
                assert (p[field] != t[field]) == (i % 3 == 0)


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_load_truth_table_reads_labels_only(tmp_path):
    path = tmp_path / "clean_training_val.csv"
    write_csv(path, [
        {"audio_file": "r1.wav", "split": "val", "text": "SECRET TEXT", "field_x": "a", "field_y": "p"},
        {"audio_file": "r2.wav", "split": "val", "text": "MORE TEXT", "field_x": "b", "field_y": "unclear"},
    ])
    rows = load_truth_table(path, "val", ["field_x", "field_y"])
    assert rows == [
        {"audio_file": "r1.wav", "field_x": "a", "field_y": "p"},
        {"audio_file": "r2.wav", "field_x": "b", "field_y": "unclear"},
    ]
    assert "SECRET" not in str(rows)


def test_load_truth_table_asks_pandas_for_only_the_label_columns(tmp_path):
    import pandas as pd

    path = tmp_path / "clean_training_val.csv"
    write_csv(path, [{"audio_file": "r1.wav", "split": "val", "text": "SECRET", "field_x": "a"}])
    seen = {}
    original = pd.read_csv

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return original(*args, **kwargs)

    pd.read_csv = spy
    try:
        load_truth_table(path, "val", ["field_x"])
    finally:
        pd.read_csv = original
    assert seen["usecols"] == ["audio_file", "split", "field_x"]


def test_load_truth_table_rejects_a_wrong_split_or_missing_column(tmp_path):
    path = tmp_path / "t.csv"
    write_csv(path, [{"audio_file": "r1.wav", "split": "train", "field_x": "a"}])
    with pytest.raises(HarnessError, match="split"):
        load_truth_table(path, "val", ["field_x"])
    with pytest.raises(HarnessError, match="field_y"):
        load_truth_table(path, "train", ["field_x", "field_y"])


def test_harness_output_feeds_the_run_record():
    shared = {
        "split_seed": 42, "experiment_seeds": [42, 1337, 2023, 7, 99], "max_seq_len": 128,
        "split_ratio": "70/20/10", "dataset_version": "v2", "dataset": "x",
        "train_rows": 70, "val_rows": 10, "test_rows": 20,
    }
    classes = {
        "complaint_category": ["a", "b"],
        "complaint_urgency": ["a", "b"],
        "customer_state": ["calm", "mad"],
        "churn_risk": ["a", "b"],
    }
    exclusions = {"customer_state": {"labels": ["unclear"], "reason": REASON}}
    truth = [
        {"audio_file": f"r{i}.wav", **{f: ("a" if i % 2 else "b") for f in classes if f != "customer_state"},
         "customer_state": "unclear" if i == 3 else ("calm" if i % 2 else "mad")}
        for i in range(1, 11)
    ]
    config = ExperimentConfig(model="mock", dataset_version="v2")
    reports = []

    def evaluate_one_seed(seed):
        preds = make_mock_predictions(truth, classes, wrong_every=2 + seed % 3, exclusions_by_field=exclusions)
        report = evaluate_predictions("val", truth, preds, classes, exclusions)
        reports.append(report)
        return seed_metrics(report["fields"])

    results = run_over_seeds(evaluate_one_seed, shared["experiment_seeds"])
    per_seed = [make_seed_result("001", config, "val", r["seed"], r["result"]) for r in results]
    record = build_run_record(
        run_id="001", hypothesis="the harness output is accepted by the run record",
        config=config, shared_config=shared, per_seed=per_seed, evaluated_split="val",
        artifacts={}, device="cpu", exceptions=reports[0]["exceptions"],
    )
    assert "customer_state_macro_f1" in record["aggregate"]
    assert record["aggregate"]["churn_risk_macro_f1"]["n"] == 5
    assert record["exceptions"] == [{
        "field": "customer_state",
        "excluded_labels": ["unclear"],
        "rows_excluded": 1,
        "n_scored": 9,
        "n_total_rows": 10,
        "reason": REASON,
    }]