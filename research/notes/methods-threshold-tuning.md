---
title: "Threshold tuning and evaluation metrics for severely imbalanced classification"
tags: [class-imbalance, threshold-tuning, evaluation, precision-recall, churn]
source_url: "https://www.geeksforgeeks.org/machine-learning/handling-imbalanced-data-for-classification/"
---

# Threshold tuning and evaluation metrics for severely imbalanced classification

## What it is

A classifier outputs a probability and applies a decision threshold, by default 0.5, to turn it into a label. With severe imbalance, 0.5 is almost never the right operating point: the model has learned that the minority class is rare, so its probabilities for that class stay low even when it is the best guess. Threshold tuning moves the cutoff after training, without retraining, to trade precision against recall. Lowering the threshold catches more positives (recall up, precision down); raising it does the opposite. For multi-class heads such as ours, the equivalent is per-class threshold tuning on the softmax probabilities, or equivalently adjusting the decision rule per class.

## How to tune

Take the predicted probabilities on the validation set, not the test set, and scan thresholds (for example 0.05 to 0.95 in steps of 0.02 or 0.05). For each threshold compute the metric that matches the business cost, usually F1 for a balanced view or recall at a minimum precision floor. Pick the threshold that maximizes that metric on validation, then freeze it and evaluate once on test. The precision-recall curve is the right tool for imbalanced data; ROC-AUC can look strong while precision is terrible, because the large negative class dominates the false positive rate. Report PR-AUC alongside macro-F1. A 2026 shared-task system (WomenHelp 2026, CEUR-WS) reported that per-label threshold optimization added an absolute macro-F1 gain of 0.017 on the development set on top of focal loss and weighted loss training.

## Metrics that matter

Accuracy is misleading under imbalance: a model that always predicts the majority class scores 99 percent accuracy on a 99:1 task while catching nothing. Use per-class precision, recall and F1, macro-averaged F1 (which weights all classes equally), and PR-AUC. For churn specifically, report recall at a stated precision floor, because the operational question is how many at-risk callers we catch and how many false alarms the callback team can tolerate. Keep the split stratified so every fold holds the class ratio, and never tune the threshold on the test set.

## Interaction with the other methods

Threshold tuning is complementary to everything else in this research set: it works after class weights, focal loss, oversampling or augmentation, and it costs nothing but a validation pass. It is especially useful for churn because the class is so small that training-time methods alone may still leave the predicted probabilities below 0.5 for most true churn cases. It also exposes the real trade-off to the team: a threshold that catches 80 percent of churn may flag 5 percent of ordinary callers, and that is a product decision, not a modeling one.

## Assessment for SVR

Threshold tuning is mandatory for the churn head and recommended for the mad class. It is the cheapest reliable gain available and the only method that directly sets the operating point the callback team will live with. Tune the churn threshold on the validation set to maximize F1, and also report the threshold that reaches 80 percent recall so the team can choose. Re-tune the threshold whenever the model or the training data changes, because a static threshold degrades silently as the score distribution shifts. Do not report churn performance at the default 0.5 threshold as the headline number.
