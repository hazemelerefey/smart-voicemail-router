import pytest

from infra.metrics import (
    MetricsError,
    combine_macro_f1,
    confusion_matrix,
    evaluate_field,
    seed_metrics,
)

# Synthetic fixture with a known answer, worked out by hand.
#   true: a a a b b c      predicted: a a b b c c
# Confusion matrix (rows = true, columns = predicted):
#        a  b  c
#   a    2  1  0
#   b    0  1  1
#   c    0  0  1
# precision a 2/2, b 1/2, c 1/2   recall a 2/3, b 1/2, c 1/1
# f1 a 0.8, b 0.5, c 2/3          macro-F1 = (0.8 + 0.5 + 2/3) / 3
CLASSES = ["a", "b", "c"]
Y_TRUE = ["a", "a", "a", "b", "b", "c"]
Y_PRED = ["a", "a", "b", "b", "c", "c"]


def report(**overrides):
    args = dict(y_true=Y_TRUE, y_pred=Y_PRED, classes=CLASSES)
    args.update(overrides)
    return evaluate_field(**args)


def test_confusion_matrix_counts():
    assert confusion_matrix(Y_TRUE, Y_PRED, CLASSES).tolist() == [[2, 1, 0], [0, 1, 1], [0, 0, 1]]


def test_per_class_metrics_match_the_hand_calculation():
    r = report()
    pc = r["per_class"]
    assert pc["a"]["precision"] == pytest.approx(1.0)
    assert pc["b"]["precision"] == pytest.approx(0.5)
    assert pc["c"]["precision"] == pytest.approx(0.5)
    assert pc["a"]["recall"] == pytest.approx(2 / 3)
    assert pc["b"]["recall"] == pytest.approx(0.5)
    assert pc["c"]["recall"] == pytest.approx(1.0)
    assert pc["a"]["f1"] == pytest.approx(0.8)
    assert pc["b"]["f1"] == pytest.approx(0.5)
    assert pc["c"]["f1"] == pytest.approx(2 / 3)
    assert [pc[c]["support"] for c in CLASSES] == [3, 2, 1]


def test_macro_and_accuracy_match_the_hand_calculation():
    r = report()
    assert r["macro"]["f1"] == pytest.approx((0.8 + 0.5 + 2 / 3) / 3)
    assert r["macro"]["precision"] == pytest.approx((1.0 + 0.5 + 0.5) / 3)
    assert r["macro"]["recall"] == pytest.approx((2 / 3 + 0.5 + 1.0) / 3)
    assert r["accuracy"] == pytest.approx(4 / 6)
    assert r["n"] == 6


def test_result_shape():
    r = report()
    assert r["confusion_matrix"] == {
        "rows_are": "true",
        "columns_are": "predicted",
        "labels": CLASSES,
        "counts": [[2, 1, 0], [0, 1, 1], [0, 0, 1]],
    }
    assert "macro_over" not in r
    assert r["classes_without_support"] == []
    assert "micro" not in str(r.keys()) and "micro_f1" not in r


def test_perfect_predictions():
    r = report(y_pred=Y_TRUE)
    assert r["macro"]["f1"] == pytest.approx(1.0)
    assert r["accuracy"] == pytest.approx(1.0)


def test_a_class_with_no_rows_counts_as_zero_in_the_macro_and_is_reported():
    classes = ["a", "b", "unclear"]
    y = ["a", "a", "b", "b"]
    r = evaluate_field(y, y, classes)
    assert r["macro"]["f1"] == pytest.approx(2 / 3)  # unclear counts as F1 = 0
    assert r["classes_without_support"] == ["unclear"]
    assert r["per_class"]["unclear"] == {
        "precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 0,
    }


def test_a_class_left_out_of_the_list_is_not_in_the_macro():
    # The caller leaves "unclear" out of the class list, so the macro is over a and b only.
    y = ["a", "a", "b", "b"]
    r = evaluate_field(y, y, ["a", "b"])
    assert r["macro"]["f1"] == pytest.approx(1.0)
    assert r["classes"] == ["a", "b"]
    assert r["classes_without_support"] == []


def test_predicting_a_class_with_no_rows_is_still_an_error_for_the_others():
    classes = ["a", "b", "unclear"]
    y_true = ["a", "b", "a", "b"]
    y_pred = ["a", "b", "unclear", "b"]
    r = evaluate_field(y_true, y_pred, classes)
    assert r["per_class"]["a"]["recall"] == pytest.approx(0.5)
    assert r["per_class"]["unclear"]["precision"] == 0.0
    assert r["accuracy"] == pytest.approx(0.75)
    assert r["confusion_matrix"]["counts"][0] == [1, 0, 1]


def test_labels_outside_the_class_list_are_rejected():
    with pytest.raises(MetricsError, match="y_pred"):
        report(y_pred=["a", "a", "b", "b", "c", "zzz"])
    with pytest.raises(MetricsError, match="y_true"):
        report(y_true=["a", "a", "a", "b", "b", "zzz"])


def test_missing_labels_are_rejected():
    with pytest.raises(MetricsError, match="y_pred"):
        report(y_pred=["a", "a", "b", "b", "c", None])
    with pytest.raises(MetricsError, match="y_pred"):
        report(y_pred=["a", "a", "b", "b", "c", float("nan")])


def test_length_mismatch_and_empty_input_are_rejected():
    with pytest.raises(MetricsError, match="labels"):
        report(y_pred=Y_PRED[:-1])
    with pytest.raises(MetricsError, match="no labels"):
        report(y_true=[], y_pred=[])


def test_bad_class_lists_are_rejected():
    with pytest.raises(MetricsError, match="duplicates"):
        report(classes=["a", "b", "b", "c"])
    with pytest.raises(MetricsError, match="classes"):
        report(classes=[])
    with pytest.raises(MetricsError, match="classes"):
        report(classes=["a", "", "c"])


def test_classes_are_not_inferred_from_the_data():
    # "c" never appears in the labels but is in the class list, so it is reported.
    r = evaluate_field(["a", "b"], ["a", "b"], ["a", "b", "c"])
    assert r["classes"] == ["a", "b", "c"]
    assert r["classes_without_support"] == ["c"]
    assert len(r["confusion_matrix"]["counts"]) == 3


def test_agrees_with_scikit_learn():
    sk = pytest.importorskip("sklearn.metrics")
    y_true = ["a", "b", "c", "a", "b", "c", "a", "a", "b", "c", "c", "b"]
    y_pred = ["a", "c", "c", "b", "b", "a", "a", "a", "c", "c", "b", "b"]
    r = evaluate_field(y_true, y_pred, CLASSES)
    p, rec, f1, sup = sk.precision_recall_fscore_support(
        y_true, y_pred, labels=CLASSES, average=None, zero_division=0
    )
    for i, c in enumerate(CLASSES):
        assert r["per_class"][c]["precision"] == pytest.approx(float(p[i]))
        assert r["per_class"][c]["recall"] == pytest.approx(float(rec[i]))
        assert r["per_class"][c]["f1"] == pytest.approx(float(f1[i]))
        assert r["per_class"][c]["support"] == int(sup[i])
    assert r["macro"]["f1"] == pytest.approx(
        sk.f1_score(y_true, y_pred, labels=CLASSES, average="macro", zero_division=0)
    )
    assert r["accuracy"] == pytest.approx(sk.accuracy_score(y_true, y_pred))
    assert r["confusion_matrix"]["counts"] == sk.confusion_matrix(y_true, y_pred, labels=CLASSES).tolist()


def test_combined_score_is_never_alone():
    reports = {
        "field_one": report(),
        "field_two": report(y_pred=Y_TRUE),
    }
    combined = combine_macro_f1(reports)
    assert combined["values"] == {
        "field_one": reports["field_one"]["macro"]["f1"],
        "field_two": 1.0,
    }
    assert combined["mean"] == pytest.approx((reports["field_one"]["macro"]["f1"] + 1.0) / 2)
    assert "unweighted" in combined["label"]
    with pytest.raises(MetricsError, match="empty"):
        combine_macro_f1({})


def test_seed_metrics_use_the_run_record_names():
    flat = seed_metrics({"complaint_category": report(), "churn_risk": report(y_pred=Y_TRUE)})
    assert set(flat) == {
        "complaint_category_macro_f1", "complaint_category_accuracy",
        "churn_risk_macro_f1", "churn_risk_accuracy",
    }
    assert flat["churn_risk_macro_f1"] == pytest.approx(1.0)
    assert flat["complaint_category_accuracy"] == pytest.approx(4 / 6)