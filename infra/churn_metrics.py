"""Extra metrics for the churn_risk field, from labels and probabilities only.

churn_risk has about 20 training rows of the positive class (at_risk), so the per-field
macro-F1 alone is not enough. This module adds what the project metrics list asks for:
- at_risk precision, recall and F1 with the raw counts (for example "6 of 8 found");
- average precision (the area under the precision-recall curve) with its chance level,
  which is the share of at_risk rows in the data;
- balanced accuracy, the mean of the recall of the two classes;
- a decision threshold tuned on the VALIDATION split, and the same metrics at the default
  threshold 0.5 for comparison;
- pooled counts over several splits at one fixed threshold (validation plus test), which
  is how churn is reported when the test split has only one or two at_risk rows.

Rules:
- The threshold is tuned on validation only. It is never tuned on test: for a test split
  the caller passes the validation threshold explicitly. A report with a tuned threshold is
  marked "tuned_on_this_data": the numbers are optimistic, because the threshold was chosen
  on the same rows, and the report says so.
- The class names are passed in (the two classes of the field) and the positive class is
  named explicitly. Nothing is guessed.
- A split with no at_risk row, or no other row, cannot be scored: the metrics are undefined.
- Predicting the positive class means probability >= threshold.

This module reads no files and no text. It uses only numpy.
"""
import numpy as np

DEFAULT_THRESHOLD = 0.5


class ChurnMetricsError(ValueError):
    """The labels or the probabilities cannot be scored."""


def _prepare(y_true, scores, classes, positive_class):
    y_true, scores, classes = list(y_true), list(scores), list(classes)
    if len(classes) != 2 or len(set(classes)) != 2 or not all(isinstance(c, str) and c for c in classes):
        raise ChurnMetricsError(f"classes must be two different non-empty strings, got {classes!r}")
    if positive_class not in classes:
        raise ChurnMetricsError(f"positive_class {positive_class!r} is not in the classes {classes}")
    if not y_true:
        raise ChurnMetricsError("there are no labels to score")
    if len(y_true) != len(scores):
        raise ChurnMetricsError(f"y_true has {len(y_true)} labels but there are {len(scores)} probabilities")
    outside = sorted({str(x) for x in y_true if x not in classes})
    if outside:
        raise ChurnMetricsError(f"y_true has labels outside the class list: {outside[:5]}")
    for s in scores:
        ok = isinstance(s, (int, float, np.floating, np.integer)) and not isinstance(s, bool)
        if not ok or not np.isfinite(s) or not 0.0 <= float(s) <= 1.0:
            raise ChurnMetricsError(f"every probability must be a number between 0 and 1, got {s!r}")
    y = np.array([1 if label == positive_class else 0 for label in y_true], dtype=np.int64)
    s = np.array(scores, dtype=np.float64)
    if y.sum() == 0:
        raise ChurnMetricsError(f"there is no {positive_class!r} row: the metrics are undefined")
    if y.sum() == len(y):
        raise ChurnMetricsError("there is no row of the other class: the metrics are undefined")
    return y, s


def _counts(y, s, threshold):
    pred = s >= threshold
    positive = y == 1
    tp = int(np.sum(pred & positive))
    fp = int(np.sum(pred & ~positive))
    fn = int(np.sum(~pred & positive))
    tn = int(np.sum(~pred & ~positive))
    return tp, fp, fn, tn


def _divide(a, b):
    return float(a) / float(b) if b > 0 else 0.0


def _f1(precision, recall):
    return _divide(2 * precision * recall, precision + recall)


def _at_threshold(y, s, threshold):
    tp, fp, fn, tn = _counts(y, s, threshold)
    precision, recall = _divide(tp, tp + fp), _divide(tp, tp + fn)
    neg_precision, neg_recall = _divide(tn, tn + fn), _divide(tn, tn + fp)
    f1_pos, f1_neg = _f1(precision, recall), _f1(neg_precision, neg_recall)
    return {
        "threshold": float(threshold),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "positives_found": tp,
        "positives_total": tp + fn,
        "precision": precision,
        "recall": recall,
        "f1": f1_pos,
        "balanced_accuracy": (recall + neg_recall) / 2.0,
        "macro_f1": (f1_pos + f1_neg) / 2.0,
    }


def average_precision(y, s):
    """Area under the precision-recall curve, step by step (no interpolation).

    Equal probabilities are one threshold, so the result does not depend on the row order.
    """
    y, s = np.asarray(y, dtype=np.int64), np.asarray(s, dtype=np.float64)
    n_pos = int(y.sum())
    if n_pos == 0:
        raise ChurnMetricsError("average precision is undefined without a positive row")
    order = np.argsort(-s, kind="mergesort")
    s_sorted, y_sorted = s[order], y[order]
    last_of_each_value = np.r_[np.where(np.diff(s_sorted))[0], y_sorted.size - 1]
    tps = np.cumsum(y_sorted)[last_of_each_value]
    fps = (1 + last_of_each_value) - tps
    precision = tps / (tps + fps)
    recall = tps / n_pos
    recall_before = np.r_[0.0, recall[:-1]]
    return float(np.sum((recall - recall_before) * precision))


def _candidate_thresholds(s):
    values = np.unique(s)
    middles = (values[:-1] + values[1:]) / 2.0 if values.size > 1 else np.array([])
    return np.unique(np.r_[middles, DEFAULT_THRESHOLD])


def tune_threshold(y, s):
    """The threshold with the highest macro-F1 of the two classes.

    Candidates are the middles between neighbouring distinct probabilities, and 0.5.
    A tie goes to the threshold closest to 0.5, then to the larger one.
    """
    best = None
    for t in _candidate_thresholds(np.asarray(s, dtype=np.float64)):
        row = _at_threshold(y, s, t)
        key = (row["macro_f1"], -abs(t - DEFAULT_THRESHOLD), t)
        if best is None or key > best[0]:
            best = (key, row)
    return best[1]


def churn_report(y_true, scores, classes, positive_class, *, threshold=None):
    """All churn metrics for one split.

    scores are the probabilities of the positive class. If threshold is None it is tuned
    on these rows (validation); otherwise the given threshold is used as it is (test).
    """
    y, s = _prepare(y_true, scores, classes, positive_class)
    tuned = threshold is None
    if tuned:
        chosen = tune_threshold(y, s)
    else:
        if not isinstance(threshold, (int, float, np.floating)) or isinstance(threshold, bool) \
                or not np.isfinite(threshold) or not 0.0 <= float(threshold) <= 1.0:
            raise ChurnMetricsError(f"threshold must be a number between 0 and 1, got {threshold!r}")
        chosen = _at_threshold(y, s, float(threshold))
    n_pos = int(y.sum())
    return {
        "positive_class": positive_class,
        "n": int(y.size),
        "n_positive": n_pos,
        "n_negative": int(y.size - n_pos),
        "average_precision": average_precision(y, s),
        "average_precision_chance": n_pos / y.size,
        "threshold_source": "tuned_on_this_data" if tuned else "given",
        "tuned_on_this_data": tuned,
        "at_threshold": chosen,
        "at_default_threshold": _at_threshold(y, s, DEFAULT_THRESHOLD),
    }


def pooled_report(parts, classes, positive_class, *, threshold):
    """Churn metrics over several splits together (for example validation plus test).

    `parts` is a list of (y_true, scores). The threshold must be given and must come from
    the validation split: the pooled rows are never used to tune it.
    """
    if not isinstance(parts, (list, tuple)) or len(parts) < 2:
        raise ChurnMetricsError("pooled_report needs at least two parts")
    y_all, s_all = [], []
    for part in parts:
        if not isinstance(part, (list, tuple)) or len(part) != 2:
            raise ChurnMetricsError("every part must be a pair (y_true, scores)")
        y_all.extend(part[0])
        s_all.extend(part[1])
    if threshold is None:
        raise ChurnMetricsError("the pooled report needs the validation threshold; it never tunes one")
    return churn_report(y_all, s_all, classes, positive_class, threshold=threshold)


def summarize_seeds(reports):
    """Mean and std (ddof=1) over the per-seed reports of one run."""
    if not isinstance(reports, (list, tuple)) or len(reports) < 2:
        raise ChurnMetricsError("at least two seed reports are needed for a standard deviation")
    counts = {(r["n"], r["n_positive"]) for r in reports}
    if len(counts) != 1:
        raise ChurnMetricsError("the seed reports must be on the same rows")

    def stats(values):
        values = np.array(values, dtype=np.float64)
        return {"mean": float(values.mean()), "std": float(values.std(ddof=1)), "n": int(values.size)}

    return {
        "n": reports[0]["n"],
        "n_positive": reports[0]["n_positive"],
        "average_precision": stats([r["average_precision"] for r in reports]),
        "average_precision_chance": reports[0]["average_precision_chance"],
        "threshold": stats([r["at_threshold"]["threshold"] for r in reports]),
        "macro_f1_at_threshold": stats([r["at_threshold"]["macro_f1"] for r in reports]),
        "macro_f1_at_default_threshold": stats([r["at_default_threshold"]["macro_f1"] for r in reports]),
        "balanced_accuracy_at_threshold": stats([r["at_threshold"]["balanced_accuracy"] for r in reports]),
        "positives_found_at_threshold": [r["at_threshold"]["positives_found"] for r in reports],
        "false_positives_at_threshold": [r["at_threshold"]["fp"] for r in reports],
    }