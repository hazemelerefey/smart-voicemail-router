# Final test evaluation report: MARBERTv2 (Phase 3)

**Date:** 2026-11-24
**Split:** test (518 rows, frozen). customer_state is scored on all 518 rows (the test split has no `unclear` row).
**Dataset:** version v2 (3,575 train / 1,003 validation / 518 test), transcription-corrected text
**Label status:** the labels come from a model and are still being audited by the team. They are not human-verified until the audit approves them.

## What this report is

The final test evaluation of the five-seed MARBERTv2 run `marbertv2-lr2e5-clean-20261119` (single-task models, learning rate 2e-5, batch 16, 3 epochs, early stopping patience 2). The 20 saved checkpoints (5 seeds × 4 fields, the best validation epoch of each) were run on the test split once, on CPU in fp32, and scored with the project harness. The result is the run `marbertv2-lr2e5-clean-20261119-test`.

How it was run:
- The model, the learning rate, the checkpoints and the thresholds were fixed on the validation split. The test split was not used for any choice.
- The test-once guard wrote its claim (2026-11-24T03:37:27+00:00) before any test text was read. The guard allows one test evaluation per model and dataset version, so this model cannot be evaluated on the test split again for dataset v2.
- All 20 model files match the SHA-256 values of the hand-over manifest. Checkpoint fingerprint: `7b737457c0ed3bebce02964d325e26729049fb5b5eea57712969ab8b8032fbef`.
- Before the claim, the same 20 checkpoints were run on the validation split and compared with the predictions submitted with them. The rehearsal result is NEAR: 18 of 20 (seed, field) pairs have the same predicted class on every row, and the other 2 differ in one row of 1,003 each (2023/customer_state and 99/complaint_category). The largest probability difference is 2.92e-3, which is expected between fp16 on a GPU (training machine) and fp32 on a CPU (this evaluation).
- Environment: CPU (Intel i7-9850H), Python 3.11.9, torch 2.15.0+cpu, transformers 5.24.0.

## Results

Macro-F1 and accuracy, mean ± std over the 5 seeds (ddof = 1). The combined score is the unweighted mean of the four per-field macro-F1 values, computed per seed first. The validation values are those of the same run.

| Field | Test macro-F1 | Test accuracy | Validation macro-F1 |
|---|---|---|---|
| complaint_category | 0.8175 ± 0.0092 | 0.8328 | 0.7872 ± 0.0057 |
| complaint_urgency | 0.7421 ± 0.0153 | 0.8039 | 0.7211 ± 0.0076 |
| customer_state | 0.7558 ± 0.0132 | 0.7320 | 0.7471 ± 0.0055 |
| churn_risk | 0.8999 ± 0.2238 | 0.9996 | 0.8277 ± 0.1238 |
| **Combined** | **0.8038 ± 0.0573** | | 0.7708 ± 0.0336 |

Combined test score per seed (42, 1337, 2023, 7, 99): 0.8222, 0.8320, 0.7015, 0.8324, 0.8310.

The mean of the three fields other than churn_risk is 0.7718 on test and 0.7518 on validation. The two splits contain different rows, and this report does not explain the difference between them.

The reference baseline and EgyBERT were not scored on the test split, so the report makes no comparison with them on test.

## churn_risk

- The test split has **one** `at_risk` row (517 are `not_at_risk`). Four seeds found it, seed 2023 missed it, and no seed had a false positive. For this reason the per-seed macro-F1 is either 1.0 or about 0.4995, and the mean 0.8999 ± 0.2238 is set by one row.
- Seed 2023 also found only 1 of the 7 `at_risk` validation rows. It is the seed with the lowest combined score (0.7015 against 0.8222 to 0.8324 for the others).
- The project metrics list asks for churn on validation and test pooled, with raw counts. Pooled: **8 `at_risk` rows among 1,521** (chance level of average precision 0.0053). The threshold was tuned on the validation rows of each seed and applied to the test rows without change. `at_risk` found at that threshold, per seed (42, 1337, 2023, 7, 99): 6 of 8, 6 of 8, 1 of 8, 6 of 8, 6 of 8. Pooled average precision 0.6421 ± 0.2809.
- The threshold was tuned on the validation rows, so the pooled numbers that use it are not an independent test of the threshold.

## Error analysis (descriptive)

Counts are summed over the 5 seeds (2,590 predictions per field).

| Field | Wrong predictions per seed (42, 1337, 2023, 7, 99) | Rows wrong in all 5 seeds | Rows wrong in none |
|---|---|---|---|
| complaint_category | 88, 88, 91, 81, 85 | 64 | 408 |
| complaint_urgency | 108, 97, 107, 103, 93 | 73 | 377 |
| customer_state | 140, 128, 139, 149, 138 | 81 | 323 |

- **complaint_category:** the largest confusions are billing_and_charges predicted as balance_and_data (52), balance_and_data as billing_and_charges (34) and balance_and_data as app_and_account (25). Weakest classes by F1: other (0.649) and balance_and_data (0.752). F1 of the others: app_and_account 0.8405, billing_and_charges 0.7702, branch_and_staff 0.8020, cancellation_request 0.8913, network_and_connectivity 0.8915, no_reply_or_long_wait 0.8375, offers_and_packages 0.7550, sim_services 0.8077, thanks_or_praise 0.9959.
- **complaint_urgency:** low predicted as medium (157), medium as high (143), medium as low (99), high as medium (89). F1: high 0.561 (precision 0.497), low 0.8288, medium 0.8370.
- **customer_state:** frustrated predicted as calm (354) and calm as frustrated (276) are 630 of the 694 errors. F1: calm 0.7147, frustrated 0.6634, mad 0.651 (17 rows per seed), satisfied 0.996.
- **churn_risk:** the only error is `at_risk` predicted as `not_at_risk` in seed 2023.

Possible explanations that were **not tested**: label noise in the rows that are wrong in all five seeds; overlapping definitions of calm and frustrated and of billing and balance; the weight of the `high` urgency class (3.484); the mixed content of the `other` class.

## What the data cannot support

- churn_risk cannot be judged from the test split: it has one positive row. The pooled count has 8. Differences between seeds or models on this field are not evidence.
- The standard deviation over five seeds measures the randomness of training. It does not measure how much a different set of 518 test rows would change the result. There is one test split and one checkpoint per seed and field.
- The labels are model-generated and under audit. These numbers will change after the audit and the retrain.
- The tested checkpoints are those of the run `marbertv2-lr2e5-clean-20261119`. A later run of the same learning rate (the fair re-run, validation combined 0.7907) has no saved checkpoints and was not scored on the test split.
- Training used fp16 on a GPU and this evaluation used fp32 on a CPU; the validation rehearsal gave NEAR, not identical predictions.
- The evaluation scores each field alone. No end-to-end result (speech to ticket) is measured here.
- The error analysis is descriptive. No cause was tested.

## Files

- `runs/exp_marbertv2-lr2e5-clean-20261119-test/`: five prediction files `predictions_test_seed<seed>.json` (probabilities for the four fields) and `run_record.json`.
- `runs/test_evaluations.json`: the test-once guard log with the claim of this evaluation.

## Open items

- After the audit: retrain on the corrected labels and re-evaluate once on the test split of the new dataset version, with the new results next to these.
- The test predictions are in the prediction files above, in the project prediction format, for the triage evaluation.
- End-to-end latency and the integrated pipeline are measured separately.