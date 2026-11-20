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

## Open items

- Final test evaluation of the winning model: once, after the winner is confirmed. Not started.
- Learning-rate sweep on MARBERTv2: not covered by this report.