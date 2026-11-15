"""Metrics for one field (one classification task), from labels only.

Follows the metrics listed in the project documents (training-metrics-imbalanced.md,
recommendations.md): macro-F1 is the headline; every field also reports macro
precision and recall, per-class precision / recall / F1 with the support, the
confusion matrix as counts, and accuracy for context. Micro-F1 is not reported on
its own: on single-label data it equals accuracy.

Two things are never guessed here:
- The class list is always passed in explicitly. It is not inferred from the data,
  so a class that has no rows in a split (for example `unclear` in some splits) is
  visible and reported instead of silently disappearing.
- How classes without any rows count in the macro average (`macro_over`) has no
  default. The caller must say which one it is using, and the result records it.
"""
import numpy as np

MACRO_OVER = ("all_classes", "classes_with_support")


class MetricsError(ValueError):
    """The labels cannot be scored."""


def _check_labels(name, labels, allowed):
    unknown = sorted({str(x) for x in labels if not isinstance(x, str) or x not in allowed})
    if unknown:
        raise MetricsError(f"{name} has labels outside the class list: {unknown[:5]}")


def confusion_matrix(y_true, y_pred, classes):
    """Counts. Rows are the true class, columns are the predicted class, in `classes` order."""
    index = {c: i for i, c in enumerate(classes)}
    matrix = np.zeros((len(classes), len(classes)), dtype=np.int64)
    for t, p in zip(y_true, y_pred):
        matrix[index[t], index[p]] += 1
    return matrix


def _safe_divide(numerator, denominator):
    return float(numerator) / float(denominator) if denominator > 0 else 0.0


def evaluate_field(y_true, y_pred, classes, macro_over):
    y_true, y_pred, classes = list(y_true), list(y_pred), list(classes)
    if macro_over not in MACRO_OVER:
        raise MetricsError(f"macro_over must be one of {MACRO_OVER}, got {macro_over!r}")
    if not classes or not all(isinstance(c, str) and c for c in classes):
        raise MetricsError("classes must be a non-empty list of non-empty strings")
    if len(set(classes)) != len(classes):
        raise MetricsError(f"classes has duplicates: {classes}")
    if len(y_true) != len(y_pred):
        raise MetricsError(f"y_true has {len(y_true)} labels but y_pred has {len(y_pred)}")
    if not y_true:
        raise MetricsError("there are no labels to score")
    allowed = set(classes)
    _check_labels("y_true", y_true, allowed)
    _check_labels("y_pred", y_pred, allowed)

    matrix = confusion_matrix(y_true, y_pred, classes)
    tp = np.diag(matrix)
    support = matrix.sum(axis=1)
    predicted = matrix.sum(axis=0)

    per_class = {}
    for i, c in enumerate(classes):
        precision = _safe_divide(tp[i], predicted[i])
        recall = _safe_divide(tp[i], support[i])
        f1 = _safe_divide(2 * precision * recall, precision + recall)
        per_class[c] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": int(support[i]),
        }

    included = [c for c in classes if macro_over == "all_classes" or per_class[c]["support"] > 0]
    macro = {
        key: float(np.mean([per_class[c][key] for c in included]))
        for key in ("precision", "recall", "f1")
    }
    return {
        "n": len(y_true),
        "macro_over": macro_over,
        "classes": classes,
        "classes_without_support": [c for c in classes if per_class[c]["support"] == 0],
        "accuracy": float(tp.sum()) / len(y_true),
        "macro": macro,
        "per_class": per_class,
        "confusion_matrix": {
            "rows_are": "true",
            "columns_are": "predicted",
            "labels": classes,
            "counts": matrix.tolist(),
        },
    }


def combine_macro_f1(field_reports):
    """The unweighted mean of the per-field macro-F1 values, never alone.

    The four values are always returned next to the mean, and the mean is labelled,
    so a failing field cannot hide behind a good average.
    """
    if not field_reports:
        raise MetricsError("field_reports must not be empty")
    values = {field: r["macro"]["f1"] for field, r in field_reports.items()}
    return {
        "label": "unweighted mean of the per-field macro-F1 values",
        "mean": float(np.mean(list(values.values()))),
        "values": values,
    }


def seed_metrics(field_reports):
    """Flat metrics for one seed, named as in the run record (<field>_macro_f1, <field>_accuracy)."""
    flat = {}
    for field, r in field_reports.items():
        flat[f"{field}_macro_f1"] = r["macro"]["f1"]
        flat[f"{field}_accuracy"] = r["accuracy"]
    return flat