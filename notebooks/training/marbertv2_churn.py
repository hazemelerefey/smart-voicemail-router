"""Exploratory validation-only churn decision threshold."""
import math

from sklearn.metrics import average_precision_score

from infra.metrics import evaluate_field


def churn_analysis(truth, probabilities, classes):
    actual = [row["churn_risk"] for row in truth]
    scores = [probabilities[row["audio_file"]]["churn_risk"]["at_risk"] for row in truth]
    argmax = [max(classes, key=probabilities[row["audio_file"]]["churn_risk"].__getitem__)
              for row in truth]
    original = evaluate_field(actual, argmax, classes)
    candidates = set(scores) | {0.5, math.nextafter(max(scores), math.inf)}

    def ranked(threshold):
        predicted = ["at_risk" if p >= threshold else "not_at_risk" for p in scores]
        result = evaluate_field(actual, predicted, classes)
        return (result["macro"]["f1"], -abs(threshold - 0.5), threshold), result

    rank, best = max(map(ranked, candidates), key=lambda item: item[0])
    at_risk = best["per_class"]["at_risk"]
    i = classes.index("at_risk")
    return {
        "threshold": rank[-1],
        "average_precision": float(average_precision_score([x == "at_risk" for x in actual], scores)),
        "argmax_balanced_accuracy": original["macro"]["recall"],
        "tuned_balanced_accuracy": best["macro"]["recall"],
        "tuned_macro_f1": best["macro"]["f1"],
        "true_positive": best["confusion_matrix"]["counts"][i][i],
        "at_risk_support": at_risk["support"],
        "tuned_per_class": best["per_class"],
        "tuned_confusion_matrix": best["confusion_matrix"],
    }
