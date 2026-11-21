# Validation evaluation report: Phase 2 text models

**Date:** 2026-11-20
**Split:** validation (1,003 rows; customer_state is scored on 1,002 rows)
**Dataset:** version v2 (3,575 train / 1,003 validation / 518 test), transcription-corrected text
**Label status:** the labels come from a model and are still being audited by the team. They are not human-verified until the audit approves them.

## What this report is

We re-scored the submitted validation predictions of four runs with the project evaluation harness (`infra/evaluate_run.py`) and compared the runs with `infra/compare_runs.py`. We did not retrain anything. Every run has five seeds (42, 1337, 2023, 7, 99). The test split was not used.

## Do the numbers reproduce?

Yes. For all four runs, every macro-F1 and accuracy mean and standard deviation computed by the harness equals the submitted run record (difference 0.000000). The exceptions agree: customer_state leaves out 1 row (`unclear`) and scores 1,002 of 1,003. All four runs were scored against the same validation file (SHA-256 starts with 50DF253AD6506B70), so the comparison is on identical data.

## Results

Validation macro-F1, mean ± std over 5 seeds (ddof = 1). The combined score is the unweighted mean of the four per-field values, computed per seed first.

| Run | Model | Learning rate | complaint_category | complaint_urgency | customer_state | churn_risk | Combined |
|---|---|---|---|---|---|---|---|
| fair-marbertv2-lr2e5 | MARBERTv2 | 2e-5 | 0.7895 ± 0.0070 | 0.7250 ± 0.0076 | 0.7442 ± 0.0021 | 0.9041 ± 0.0616 | 0.7907 ± 0.0160 |
| 001 (arafa-systems-demo) | EgyBERT | 3e-5 | 0.7513 ± 0.0188 | 0.7200 ± 0.0125 | 0.7438 ± 0.0041 | 0.9162 ± 0.0000 | 0.7828 ± 0.0051 |
| marbertv2-lr2e5-clean-20261119 | MARBERTv2 | 2e-5 | 0.7872 ± 0.0057 | 0.7211 ± 0.0076 | 0.7471 ± 0.0055 | 0.8277 ± 0.1238 | 0.7708 ± 0.0336 |
| tfidf-002 (reference baseline) | TF-IDF + logistic regression | not applicable | 0.7605 ± 0.0000 | 0.6910 ± 0.0000 | 0.6988 ± 0.0000 | 0.8629 ± 0.0000 | 0.7533 ± 0.0000 |
| fair-egybert-lr2e5 | EgyBERT | 2e-5 | 0.7180 ± 0.0069 | 0.7038 ± 0.0098 | 0.7422 ± 0.0086 | 0.5233 ± 0.0560 | 0.6718 ± 0.0140 |

The baseline has no standard deviation because its solver is deterministic: all five seeds give the same result.

## Rule applied

The higher combined mean is ahead. If the difference between the two means is at most the larger of the two standard deviations, the result is a tie, and the preferred model (MARBERTv2) is ahead.

| Comparison | Difference | Tie threshold | Result |
|---|---|---|---|
| fair-marbertv2-lr2e5 vs fair-egybert-lr2e5 (same learning rate, 2e-5) | 0.118899 | 0.015982 | MARBERTv2 ahead, by the higher mean |
| fair-marbertv2-lr2e5 vs 001 (EgyBERT, 3e-5) | 0.007885 | 0.015982 | tie; MARBERTv2 ahead by the preference |

This report gives which run is ahead by the rule and the numbers behind it. The decision itself is recorded by the Training Lead.

## Reading the numbers

- Against the reference baseline (combined 0.7533), MARBERTv2 is above on all four fields. EgyBERT at 3e-5 is above on urgency, state and churn, and below on category (0.7513 against 0.7605). EgyBERT at 2e-5 is below the baseline on category and churn, and below on the combined score by 0.0815.
- The two EgyBERT runs use different learning rates (3e-5 and 2e-5), so they are not a like-for-like pair. Most of the gap of the 2e-5 run comes from churn_risk (0.5233 against 0.9162). On the other three fields the two runs differ by at most 0.034.
- On customer_state the three neural runs in the rule comparisons are within 0.002 of each other (0.7422 to 0.7442).
- The combined standard deviation is driven by churn_risk (0.0616 for MARBERTv2, 0.0560 for EgyBERT at 2e-5, 0.1238 for the earlier MARBERTv2 run).

## What the data cannot support

- churn_risk has very few `at_risk` rows in the validation split, so its macro-F1 moves in large steps when one row changes class (accuracy is about 0.997 for the baseline and 0.9966 for the earlier MARBERTv2 run). A standard deviation of 0 (run 001, the baseline) means every seed got the same rows right. It does not mean the estimate is precise.
- The comparison rests on one validation split of 1,003 rows. A difference smaller than the seed standard deviation is not evidence of a better model.
- The labels are model-generated and under audit. These numbers will change after the audit and the retrain.
- The training environments are as reported by the people who ran them. We scored their predictions and did not retrain.
- The run marbertv2-lr2e5-clean-20261119 was trained with a different pipeline. It is listed for reference and is not used in the rule comparisons.
- These are validation results only. The test split has not been evaluated.

## Churn risk: extra metrics (validation)

churn_risk has 7 `at_risk` rows among the 1,003 validation rows (0.70 percent), so one row is worth 1/7 of the recall. The metrics below were computed with `infra/churn_metrics.py` and `infra/churn_run_report.py` on the same prediction files as the main table, one value per seed, then mean ± std over the 5 seeds (ddof = 1).

- **Average precision** is the area under the precision-recall curve. Its chance level is the share of `at_risk` rows: 0.0070.
- **Balanced accuracy** is the mean of the recall of the two classes.
- **Tuned threshold:** the probability threshold with the highest macro-F1 of the two classes on the validation rows (candidates: the middles between neighbouring probabilities, and 0.5; a tie goes to the one closest to 0.5). **It is tuned on the same rows it is scored on, so the tuned numbers are optimistic.** The values at the default threshold 0.5 are given next to them. At 0.5, the macro-F1 equals the churn_risk value of the main table for every run.

| Run | Average precision | Balanced accuracy (tuned / at 0.5) | macro-F1 (tuned / at 0.5) | `at_risk` found out of 7, per seed (42, 1337, 2023, 7, 99) |
|---|---|---|---|---|
| EgyBERT 3e-5 (001) | 0.7945 ± 0.0518 | 0.8714 ± 0.0319 / 0.8571 ± 0.0000 | 0.9252 ± 0.0202 / 0.9162 ± 0.0000 | 5, 5, 5, 6, 5 |
| fair-marbertv2-lr2e5 | 0.7792 ± 0.0758 | 0.8854 ± 0.0392 / 0.8570 ± 0.0874 | 0.9156 ± 0.0380 / 0.9041 ± 0.0616 | 5, 6, 6, 5, 5 |
| tfidf-002 (baseline) | 0.6921 ± 0.0000 | 0.7857 / 0.7857 | 0.8629 / 0.8629 | 4, 4, 4, 4, 4 |
| marbertv2-lr2e5-clean-20261119 | 0.6256 ± 0.2592 | 0.7997 ± 0.1276 / 0.7713 ± 0.1277 | 0.8392 ± 0.1231 / 0.8277 ± 0.1238 | 5, 5, 1, 5, 5 |
| fair-egybert-lr2e5 | 0.1186 ± 0.0696 | 0.5703 ± 0.0022 / 0.5143 ± 0.0319 | 0.6063 ± 0.0312 / 0.5233 ± 0.0560 | 1, 1, 1, 1, 1 |

### Reading the numbers

- The large gap between the two EgyBERT runs is the churn field. At 2e-5 the model finds 1 of the 7 `at_risk` rows in every seed and its average precision (0.12) is far below the other runs, though still above the chance level (0.007). At 3e-5 it finds 5 or 6 of 7 (average precision 0.79). On churn_risk alone, EgyBERT at 3e-5 is not behind MARBERTv2 at 2e-5 (0.7945 against 0.7792, and the difference is smaller than the seed standard deviations).
- Threshold tuning changes the macro-F1 by at most 0.0125 for the two best runs, which is smaller than their seed standard deviations. The baseline does not change at all.
- The tuned threshold is not stable: for the same run it moves between seeds (for example 0.0007 to 0.5 for fair-marbertv2-lr2e5). A threshold chosen on 7 rows should not be treated as an operating point.
- At the tuned threshold the models sometimes add false alarms (for example 2 for one seed of fair-marbertv2-lr2e5 and 10 for one seed of fair-egybert-lr2e5).

### What the data cannot support

- With 7 positive rows, one row changes the recall by 0.14. Differences between runs smaller than that are not evidence.
- The tuned numbers use the validation rows twice (to choose the threshold and to score it). They say how well a threshold could work, not how well it will work on new data.
- **Not done:** the churn result pooled over validation and test with raw counts (for example "6 of 8"), which the project metrics list asks for. It needs the test predictions of the final model, which are scored once in the final evaluation. The 5-fold stratified cross-validation estimate was also not computed: it needs retraining and cannot be made from prediction files.

## Open items

- Final test evaluation of the winning model: once, after the winner is confirmed. Not started.
- Learning-rate sweep on MARBERTv2: not covered by this report.
- Churn risk pooled over validation and test, with the validation threshold: after the final test evaluation.
- 5-fold stratified cross-validation for churn_risk: not planned unless the team asks for it.