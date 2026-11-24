---
title: "Metrics for imbalanced classification and how to report them"
tags: [training, metrics, evaluation, imbalanced, svr]
source_url: "https://futureagi.com/blog/f1-score-evaluating-classifiers-2025/"
---

# Metrics for imbalanced classification and how to report them

Sources: F1 score guide (https://futureagi.com/blog/f1-score-evaluating-classifiers-2025/), imbalanced dataset reporting guide (http://umatechnology.org/how-to-deal-with-imbalanced-datasets-class-weights-smote-metrics-and-honest-evaluation/), and the micro versus macro averaging analysis (https://medium.com/@rcprati/micro-macro-and-the-hidden-0-0-three-ways-an-imbalanced-data-report-can-mislead-10f92f496bca). All checked November 2026.

## Why accuracy is not the metric for SVR

Accuracy is the fraction of correct predictions. On imbalanced data it is misleading because a model that always predicts the majority class scores high accuracy while doing nothing useful. The standard example: a fraud detector that is 99 percent accurate but catches zero fraud has 0 percent recall on the class that matters. SVR has the same shape: churn at_risk is 0.5 percent (32 rows of 5,751), mad is 2.7 percent, high urgency is 9.2 percent. A model that never predicts at_risk would still score about 99.5 percent accuracy on churn. Accuracy may be reported for context, but it must never be the acceptance criterion.

## The metric set to report per field

For each of the four fields (complaint_category, complaint_urgency, customer_state, churn_risk), report:

1. Macro-F1 as the primary headline metric. Macro-F1 averages per-class F1 with every class weighted equally, so a rare class counts as much as a common one. In scikit-learn this is average="macro".
2. Macro-precision and macro-recall alongside macro-F1, since the F1 alone hides which side fails.
3. Per-class precision, recall, and F1 for every class, with the support (row count) of each class in the evaluated split. Never report an average without the per-class table behind it.
4. Accuracy as context only.
5. The confusion matrix (counts, not only percentages) for each field.
6. Weighted-F1 as a secondary number if stakeholders ask for an overall correctness view, but label it clearly: weighted-F1 weights classes by frequency, so it stays high when the majority class dominates.

Micro-F1 must not be reported as if it were a separate insight: on single-label multi-class problems micro-precision, micro-recall, and micro-F1 are all the same number, and that number equals accuracy. Reporting it next to accuracy double counts one fact.

## Extra metrics for the rare churn class

Churn is binary with an extreme imbalance ratio of about 200 to 1 (5,719 not at risk versus 32 at risk). For churn, add:

- Precision, recall, and F1 for the at_risk class specifically, plus the raw counts (true positives, false positives, false negatives). Counts are more honest than rates when the denominator is tiny.
- Average precision (area under the precision-recall curve) and the precision-recall curve itself. For rare positives, average precision is more informative than ROC-AUC, because ROC-AUC can look good while precision on the rare class is poor. The chance level for average precision is the prevalence (0.005), not 0.5.
- Balanced accuracy (mean of per-class recalls) as a check: a constant majority classifier scores 0.5 on it, so it exposes degenerate models.
- Matthews correlation coefficient (MCC) as a single robust summary if the team wants one. Note the warning from the averaging analysis: micro MCC can fall outside the range of per-class values, so report per-class MCC with care and prefer the binary MCC for churn.
- Threshold tuning: the default 0.5 decision threshold is almost always wrong for a rare class. Tune the churn threshold on the validation set using the precision-recall curve, picking the threshold that maximizes at_risk F1 (or that meets a stated recall target, for example recall at least 0.8 with the best precision available). Threshold tuning needs no retraining. Fix the chosen threshold before touching the test set.

## The test set problem for churn, and the fix

The test set holds only 1 at-risk row. Test-only recall for churn can only be 0 or 1, and test-only precision is equally meaningless. Reporting "churn recall 100 percent on test" or "churn recall 0 percent on test" from a single row is noise, not a result. The literature-consistent fix:

1. Report churn metrics on validation plus test pooled (1,136 plus 584 rows, about 7 at-risk rows). State the pooled support explicitly so readers know the denominator.
2. Prefer stratified cross-validation for the churn estimate: 5-fold stratified cross-validation over the full clean set gives about 6 to 7 at-risk rows per fold and about 32 across folds, which is the only way to get a churn recall estimate with any stability.
3. Always report the raw counts next to any churn rate (for example "recall 5 of 7"), never a percentage alone.
4. Do not re-split the frozen test set to fix this. Pooling val plus test for the churn report is a reporting decision, not a data change; model selection still uses validation only, and the test set is still evaluated once.

## Class weights, focal loss, and resampling (for the report, not the metric)

Class weights are already saved for SVR (churn at_risk 89.859, mad 7.234) and are the first remedy to try: they are implemented as per-class weights in cross-entropy loss (PyTorch CrossEntropyLoss weight argument), with the balanced heuristic weight equal to n divided by (K times n_c). Resampling (oversampling the minority or undersampling the majority) must be applied to the training set only, never to validation or test, or the reported numbers stop reflecting production. Focal loss is an option if class weights alone leave churn recall at zero, but it is second line, not first. Whichever remedy is used, judge it with the metrics above, not with accuracy.

## Assessment for SVR

Macro-F1 per field is the headline metric. The report for each field carries the per-class precision, recall, F1, support counts, and confusion matrix. Churn gets its own section with pooled val plus test counts, average precision, and the tuned threshold. Any single-number summary across the four tasks must be labeled as the mean of the four macro-F1 values, with all four visible next to it.
