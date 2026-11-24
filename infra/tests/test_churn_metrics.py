import numpy as np
import pytest

from infra.churn_metrics import (
    ChurnMetricsError,
    average_precision,
    churn_report,
    pooled_report,
    summarize_seeds,
    tune_threshold,
)

CLASSES = ["at_risk", "not_at_risk"]
POS = "at_risk"
NEG = "not_at_risk"


def labels(*ones):
    """A label list from 1 (at_risk) and 0 (not_at_risk)."""
    return [POS if x else NEG for x in ones]


def report(y, s, **kw):
    return churn_report(labels(*y), s, CLASSES, POS, **kw)


# ---------- average precision ----------

def test_average_precision_by_hand():
    # ranks: 0.9 (positive), 0.8 (negative), 0.7 (positive), 0.6 (negative)
    # precision at the two positives: 1 and 2/3; each adds half of the recall
    assert average_precision([1, 0, 1, 0], [0.9, 0.8, 0.7, 0.6]) == pytest.approx(0.5 * 1 + 0.5 * 2 / 3)


def test_average_precision_of_a_perfect_ranking_is_one():
    assert average_precision([1, 1, 0, 0, 0], [0.9, 0.8, 0.3, 0.2, 0.1]) == pytest.approx(1.0)


def test_equal_probabilities_give_the_chance_level():
    assert average_precision([1, 0, 0, 0], [0.5, 0.5, 0.5, 0.5]) == pytest.approx(0.25)


def test_the_row_order_does_not_change_average_precision():
    y = [1, 0, 0, 1, 0, 0, 0, 1]
    s = [0.4, 0.4, 0.9, 0.4, 0.1, 0.4, 0.2, 0.7]
    order = [7, 3, 0, 5, 2, 6, 1, 4]
    assert average_precision(y, s) == pytest.approx(average_precision([y[i] for i in order], [s[i] for i in order]))


def test_average_precision_agrees_with_scikit_learn_including_ties():
    sk = pytest.importorskip("sklearn.metrics")
    rng = np.random.default_rng(0)
    for _ in range(25):
        n = int(rng.integers(20, 200))
        y = (rng.random(n) < 0.1).astype(int)
        if y.sum() == 0:
            y[0] = 1
        s = np.round(rng.random(n), 1)  # rounding creates many ties
        assert average_precision(y, s) == pytest.approx(sk.average_precision_score(y, s))


def test_balanced_accuracy_and_counts_agree_with_scikit_learn():
    sk = pytest.importorskip("sklearn.metrics")
    rng = np.random.default_rng(1)
    y = (rng.random(300) < 0.08).astype(int)
    y[:3] = 1
    s = np.clip(rng.normal(0.2 + 0.5 * y, 0.25), 0, 1)
    r = report(y, s, threshold=0.4)["at_threshold"]
    pred = (s >= 0.4).astype(int)
    assert r["balanced_accuracy"] == pytest.approx(sk.balanced_accuracy_score(y, pred))
    assert r["precision"] == pytest.approx(sk.precision_score(y, pred, zero_division=0))
    assert r["recall"] == pytest.approx(sk.recall_score(y, pred, zero_division=0))
    assert r["f1"] == pytest.approx(sk.f1_score(y, pred, zero_division=0))
    assert r["macro_f1"] == pytest.approx(sk.f1_score(y, pred, average="macro", zero_division=0))
    assert [r["tn"], r["fp"], r["fn"], r["tp"]] == sk.confusion_matrix(y, pred).ravel().tolist()


# ---------- the report ----------

def test_the_report_counts_and_the_found_of_total_wording():
    y = [1] * 8 + [0] * 92
    s = [0.9] * 6 + [0.1] * 2 + [0.1] * 90 + [0.8] * 2  # 6 of 8 found, 2 false alarms
    r = report(y, s, threshold=0.5)
    t = r["at_threshold"]
    assert (t["tp"], t["fn"], t["fp"], t["tn"]) == (6, 2, 2, 90)
    assert t["positives_found"] == 6 and t["positives_total"] == 8
    assert t["recall"] == pytest.approx(6 / 8) and t["precision"] == pytest.approx(6 / 8)
    assert r["n"] == 100 and r["n_positive"] == 8 and r["n_negative"] == 92
    assert r["average_precision_chance"] == pytest.approx(0.08)
    assert r["threshold_source"] == "given" and r["tuned_on_this_data"] is False


def test_a_tuned_threshold_is_marked_as_tuned_on_the_same_data():
    r = report([1, 1, 0, 0, 0], [0.9, 0.7, 0.4, 0.2, 0.1])
    assert r["tuned_on_this_data"] is True and r["threshold_source"] == "tuned_on_this_data"


def test_tuning_finds_a_threshold_between_the_classes():
    r = report([1, 1, 0, 0, 0], [0.9, 0.7, 0.4, 0.2, 0.1])["at_threshold"]
    assert r["macro_f1"] == pytest.approx(1.0)
    assert 0.4 < r["threshold"] <= 0.7


def test_a_tie_between_thresholds_goes_to_the_one_closest_to_one_half():
    # every threshold between 0.30 and 0.80 separates the classes perfectly
    r = report([1, 1, 0, 0], [0.9, 0.8, 0.3, 0.2])["at_threshold"]
    assert r["macro_f1"] == pytest.approx(1.0)
    assert r["threshold"] == pytest.approx(0.5)
    # here only the middle between 0.7 and 0.9 separates the classes, and 0.5 does not
    r2 = report([1, 1, 0, 0], [0.95, 0.9, 0.7, 0.6])["at_threshold"]
    assert r2["macro_f1"] == pytest.approx(1.0)
    assert r2["threshold"] == pytest.approx(0.8)


def test_the_default_threshold_is_always_reported_for_comparison():
    r = report([1, 1, 0, 0, 0], [0.45, 0.4, 0.2, 0.1, 0.05])
    assert r["at_default_threshold"]["threshold"] == 0.5
    assert r["at_default_threshold"]["tp"] == 0  # nothing reaches 0.5
    assert r["at_threshold"]["macro_f1"] > r["at_default_threshold"]["macro_f1"]


def test_the_probability_equal_to_the_threshold_predicts_the_positive_class():
    r = report([1, 0, 0], [0.5, 0.2, 0.1], threshold=0.5)["at_threshold"]
    assert r["tp"] == 1 and r["fn"] == 0


def test_the_threshold_is_not_tuned_when_it_is_given():
    r = report([1, 1, 0, 0, 0], [0.45, 0.4, 0.2, 0.1, 0.05], threshold=0.5)
    assert r["at_threshold"]["threshold"] == 0.5 and r["at_threshold"]["tp"] == 0


# ---------- refusals ----------

def test_a_split_without_a_positive_row_is_refused():
    with pytest.raises(ChurnMetricsError, match="no 'at_risk' row"):
        report([0, 0, 0], [0.1, 0.2, 0.3])


def test_a_split_without_a_negative_row_is_refused():
    with pytest.raises(ChurnMetricsError, match="other class"):
        report([1, 1], [0.9, 0.8])


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(classes=["at_risk"]),
        dict(classes=["at_risk", "at_risk"]),
        dict(classes=["at_risk", ""]),
        dict(positive_class="mad"),
    ],
)
def test_bad_classes_are_refused(kwargs):
    args = dict(y_true=labels(1, 0, 0), scores=[0.9, 0.2, 0.1], classes=CLASSES, positive_class=POS)
    args.update(kwargs)
    with pytest.raises(ChurnMetricsError):
        churn_report(**args)


def test_labels_outside_the_class_list_are_refused():
    with pytest.raises(ChurnMetricsError, match="outside"):
        churn_report([POS, "calm", NEG], [0.9, 0.2, 0.1], CLASSES, POS)


def test_empty_input_and_a_length_mismatch_are_refused():
    with pytest.raises(ChurnMetricsError, match="no labels"):
        churn_report([], [], CLASSES, POS)
    with pytest.raises(ChurnMetricsError, match="probabilities"):
        churn_report(labels(1, 0), [0.9], CLASSES, POS)


@pytest.mark.parametrize("bad", [-0.1, 1.1, float("nan"), float("inf"), None, True, "0.5"])
def test_bad_probabilities_are_refused(bad):
    with pytest.raises(ChurnMetricsError, match="probability"):
        churn_report(labels(1, 0, 0), [0.9, bad, 0.1], CLASSES, POS)


@pytest.mark.parametrize("bad", [-0.1, 1.1, float("nan"), True, "0.5"])
def test_a_bad_given_threshold_is_refused(bad):
    with pytest.raises(ChurnMetricsError, match="threshold"):
        churn_report(labels(1, 0, 0), [0.9, 0.2, 0.1], CLASSES, POS, threshold=bad)


# ---------- pooled validation plus test ----------

def test_the_pooled_report_adds_the_counts_and_uses_the_given_threshold():
    val = (labels(1, 1, 1, 1, 1, 1, 1, 0, 0, 0), [0.9, 0.9, 0.9, 0.9, 0.9, 0.2, 0.2, 0.1, 0.1, 0.1])  # 5 of 7
    test = (labels(1, 0, 0), [0.8, 0.1, 0.1])  # 1 of 1
    p = pooled_report([val, test], CLASSES, POS, threshold=0.5)
    t = p["at_threshold"]
    assert p["n"] == 13 and p["n_positive"] == 8
    assert (t["positives_found"], t["positives_total"]) == (6, 8)
    assert t["threshold"] == 0.5 and p["tuned_on_this_data"] is False


def test_the_pooled_report_never_tunes_a_threshold():
    parts = [(labels(1, 0), [0.9, 0.1]), (labels(1, 0), [0.8, 0.2])]
    with pytest.raises(ChurnMetricsError, match="never tunes"):
        pooled_report(parts, CLASSES, POS, threshold=None)
    with pytest.raises(TypeError):
        pooled_report(parts, CLASSES, POS)


def test_the_pooled_report_needs_two_well_formed_parts():
    with pytest.raises(ChurnMetricsError, match="at least two"):
        pooled_report([(labels(1, 0), [0.9, 0.1])], CLASSES, POS, threshold=0.5)
    with pytest.raises(ChurnMetricsError, match="pair"):
        pooled_report([(labels(1, 0), [0.9, 0.1]), "x"], CLASSES, POS, threshold=0.5)


# ---------- the seeds of one run ----------

def test_the_seed_summary_has_mean_and_sample_std():
    reports = [
        report([1, 1, 0, 0, 0], [0.9, 0.7, 0.4, 0.2, 0.1]),
        report([1, 1, 0, 0, 0], [0.8, 0.5, 0.6, 0.2, 0.1]),
        report([1, 1, 0, 0, 0], [0.9, 0.4, 0.3, 0.2, 0.1]),
    ]
    s = summarize_seeds(reports)
    aps = [r["average_precision"] for r in reports]
    assert s["average_precision"]["mean"] == pytest.approx(np.mean(aps))
    assert s["average_precision"]["std"] == pytest.approx(np.std(aps, ddof=1))
    assert s["average_precision"]["n"] == 3 and s["n_positive"] == 2
    assert len(s["positives_found_at_threshold"]) == 3


def test_the_seed_summary_refuses_one_seed_or_different_rows():
    a = report([1, 1, 0, 0, 0], [0.9, 0.7, 0.4, 0.2, 0.1])
    with pytest.raises(ChurnMetricsError, match="at least two"):
        summarize_seeds([a])
    b = report([1, 0, 0, 0, 0], [0.9, 0.7, 0.4, 0.2, 0.1])
    with pytest.raises(ChurnMetricsError, match="same rows"):
        summarize_seeds([a, b])


def test_the_threshold_search_is_deterministic():
    rng = np.random.default_rng(3)
    y = np.array([1] * 6 + [0] * 94)
    s = np.round(rng.random(100), 2)
    assert tune_threshold(y, s) == tune_threshold(y, s)