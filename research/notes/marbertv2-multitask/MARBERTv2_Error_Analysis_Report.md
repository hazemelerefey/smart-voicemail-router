# MARBERTv2 Multi-Task — Error Analysis, Root-Cause Hypotheses & Remediation

**Run ID:** `marbertv2-multitask-kendall-lr2e5-confirmation-v1`
**Generated (UTC):** 2026-11-24T00:00:30.911067+00:00
**Evaluation:** Validation set only
**Seeds:** 42, 1337, 2023, 7, 99

## 1. Executive Summary

- Total task-level evaluations: 20,055.
- Incorrect task-level evaluations: 3,701.
- Unique task/sample error pairs: 992.
- Persistent errors across all five seeds: 510.
- Repeated seed evaluations are not independent samples.
- Root causes are not established by observational error analysis alone.

## 2. Task-Level Error Statistics

| task               |   evaluations |   errors |   error_rate |   persistent_errors |
|:-------------------|--------------:|---------:|-------------:|--------------------:|
| churn_risk         |          5015 |       20 |       0.0040 |                   3 |
| complaint_category |          5015 |     1016 |       0.2026 |                 147 |
| complaint_urgency  |          5015 |     1206 |       0.2405 |                 171 |
| customer_state     |          5010 |     1459 |       0.2912 |                 189 |

## 3. Per-Class Performance

| task               | class                    |   support_per_seed |   precision_mean |   recall_mean |   f1_mean |   f1_sd |
|:-------------------|:-------------------------|-------------------:|-----------------:|--------------:|----------:|--------:|
| complaint_category | other                    |                 62 |           0.5745 |        0.4710 |    0.5170 |  0.0301 |
| customer_state     | mad                      |                 29 |           0.3829 |        0.8483 |    0.5252 |  0.0383 |
| complaint_urgency  | high                     |                104 |           0.4100 |        0.7808 |    0.5370 |  0.0157 |
| complaint_category | offers_and_packages      |                 33 |           0.5242 |        0.8000 |    0.6325 |  0.0418 |
| churn_risk         | at_risk                  |                  7 |           0.8600 |        0.5143 |    0.6424 |  0.0919 |
| customer_state     | frustrated               |                438 |           0.7052 |        0.6356 |    0.6674 |  0.0195 |
| customer_state     | calm                     |                403 |           0.6804 |        0.6898 |    0.6841 |  0.0102 |
| complaint_category | balance_and_data         |                129 |           0.7364 |        0.6930 |    0.7140 |  0.0132 |
| complaint_category | branch_and_staff         |                 78 |           0.7285 |        0.8179 |    0.7687 |  0.0199 |
| complaint_category | billing_and_charges      |                139 |           0.7627 |        0.7928 |    0.7767 |  0.0082 |
| complaint_category | cancellation_request     |                 40 |           0.7593 |        0.8150 |    0.7854 |  0.0205 |
| complaint_category | no_reply_or_long_wait    |                 85 |           0.7689 |        0.8047 |    0.7862 |  0.0100 |
| complaint_urgency  | medium                   |                584 |           0.8348 |        0.7568 |    0.7938 |  0.0064 |
| complaint_urgency  | low                      |                315 |           0.8677 |        0.7575 |    0.8088 |  0.0040 |
| complaint_category | network_and_connectivity |                173 |           0.9326 |        0.7815 |    0.8503 |  0.0058 |
| complaint_category | sim_services             |                 12 |           0.9600 |        0.7667 |    0.8519 |  0.0374 |
| complaint_category | app_and_account          |                120 |           0.8274 |        0.8883 |    0.8564 |  0.0143 |
| complaint_category | thanks_or_praise         |                132 |           0.9772 |        0.9758 |    0.9765 |  0.0032 |
| customer_state     | satisfied                |                132 |           0.9788 |        0.9788 |    0.9788 |  0.0021 |
| churn_risk         | not_at_risk              |                996 |           0.9966 |        0.9994 |    0.9980 |  0.0005 |

## 4. Churn Risk — Seven Positive Cases

The validation set contains seven at-risk cases. Their detection outcomes are:

| audio_file          | complaint_category       |   correct_seeds |   missed_seeds |   mean_at_risk_probability |
|:--------------------|:-------------------------|----------------:|---------------:|---------------------------:|
| frustrated_0030.wav | billing_and_charges      |               0 |              5 |                     0.1729 |
| frustrated_0066.wav | billing_and_charges      |               0 |              5 |                     0.2716 |
| frustrated_0443.wav | billing_and_charges      |               0 |              5 |                     0.1056 |
| frustrated_0241.wav | branch_and_staff         |               3 |              2 |                     0.4435 |
| calm_0246.wav       | other                    |               5 |              0 |                     0.9247 |
| frustrated_0416.wav | network_and_connectivity |               5 |              0 |                     0.7488 |
| mad_0031.wav        | network_and_connectivity |               5 |              0 |                     0.7759 |

### Case-Level Observations

- `frustrated_0030.wav`: billing complaint with loss of trust but no explicit cancellation or switching statement.
- `frustrated_0066.wav`: explicitly considers changing provider; missed by all five seeds.
- `frustrated_0443.wav`: explicitly considers stopping service; missed by all five seeds.
- `frustrated_0241.wav`: conditional switching statement; correct in three of five seeds.
- `calm_0246.wav`: direct switching inquiry; correct in all five seeds.
- `frustrated_0416.wav`: network-related switching intent; correct in all five seeds.
- `mad_0031.wav`: service disruption and explicit leaving intent; correct in all five seeds.

### Interpretation

The observed errors suggest that churn detection may vary by complaint context. This is an exploratory hypothesis, not evidence of a confirmed causal mechanism.

## 5. Root-Cause Hypotheses

### H01 — Minority-class imbalance in churn detection

**Observed evidence:** Only 7 at-risk validation samples versus 996 not-at-risk samples.

**Hypothesis:** Limited minority-class representation may reduce sensitivity to churn indicators.

**How to verify:** Inspect training class counts, compare per-class learning behavior, and evaluate controlled class-balancing interventions.

**Proposed remediation:** Consider targeted annotation, minority-class sampling, or loss adjustments. Change one factor at a time.

**Priority:** HIGH

### H02 — Context-dependent churn detection

**Observed evidence:** Three persistent false negatives occur in billing_and_charges, including explicit switching or cancellation language.

**Hypothesis:** The model may under-recognize churn signals when embedded in billing complaints.

**How to verify:** Audit training examples by churn label and complaint category; compare matched examples with similar churn expressions.

**Proposed remediation:** Collect and annotate diverse billing-related churn examples, then run controlled experiments.

**Priority:** HIGH

### H03 — Potential annotation ambiguity

**Observed evidence:** frustrated_0030.wav is labeled at_risk but does not contain an explicit intention to leave.

**Hypothesis:** The annotation policy may include implicit trust-loss indicators, creating a broader definition than explicit cancellation intent.

**How to verify:** Review original annotation guidelines and obtain blinded independent annotation.

**Proposed remediation:** Clarify the operational definition of at_risk and adjudicate ambiguous cases without using model predictions as ground truth.

**Priority:** HIGH

### H04 — High-urgency false positives

**Observed evidence:** High urgency has mean precision approximately 0.410 and recall approximately 0.781.

**Hypothesis:** The classifier may favor recall over precision for high urgency.

**How to verify:** Inspect confusion pairs, decision margins, training distribution, and label criteria.

**Proposed remediation:** Evaluate validation-only threshold or decision-rule adjustments against a predefined precision-recall objective.

**Priority:** MEDIUM

### H05 — Confusion between emotional states

**Observed evidence:** mad has mean precision approximately 0.383 and recall approximately 0.848.

**Hypothesis:** Expressions of frustration may overlap linguistically with anger.

**How to verify:** Review true/predicted confusion pairs and conduct blinded annotation review.

**Proposed remediation:** Refine class definitions and test targeted examples with consistent annotation.

**Priority:** MEDIUM

### H06 — Potential ASR sensitivity

**Observed evidence:** Some original and Whisper transcripts differ, but the exact model input column has not yet been independently confirmed.

**Hypothesis:** Transcription errors could influence predictions for certain complaints.

**How to verify:** Confirm the tokenization input column and perform a controlled ASR-input ablation.

**Proposed remediation:** Improve transcription quality only if a controlled experiment demonstrates benefit.

**Priority:** MEDIUM

## 6. Controlled Remediation Plan

| experiment   | change                                    | type                | primary_metric                                           | constraint                                                          |
|:-------------|:------------------------------------------|:--------------------|:---------------------------------------------------------|:--------------------------------------------------------------------|
| E01          | Audit training minority-class counts      | DATA_AUDIT          | Class support and label consistency                      | No training or test-set changes                                     |
| E02          | Independent churn-label adjudication      | ANNOTATION_AUDIT    | Inter-annotator agreement                                | Review without revealing model predictions                          |
| E03          | Churn class-balancing strategy            | CONTROLLED_TRAINING | At-risk recall, precision, F1, PR-AUC                    | Fixed splits, five seeds, and all other hyperparameters             |
| E04          | Validation-only churn threshold selection | DECISION_RULE       | At-risk recall with predefined false-positive constraint | No test-set tuning; report validation selection optimism            |
| E05          | Targeted billing-context augmentation     | CONTROLLED_TRAINING | At-risk recall by complaint category                     | Training-only additions; preserve held-out validation and test sets |
| E06          | Original-versus-ASR text ablation         | INPUT_ABLATION      | Macro F1 and per-class recall                            | Confirm baseline text pipeline first; hold other factors fixed      |

## 7. Evaluation Integrity & Limitations

- Customer-state label `unclear` has zero training examples and one validation example; it is excluded from customer-state scoring only.
- The churn-positive validation support is only seven, so recall estimates are statistically unstable.
- Model probabilities have not been demonstrated to be calibrated.
- Existing validation analysis is exploratory and cannot establish generalization to unseen data.
- Thresholds or model configurations must not be selected using independent test results.
- Proposed changes require separately identified experiment runs with immutable baseline artifacts.

## 8. Recommended Next Steps

1. Verify the training text column and class distributions.
2. Audit ambiguous annotations independently.
3. Freeze the baseline and define evaluation objectives.
4. Run one-factor-at-a-time experiments under fixed splits.
5. Evaluate the selected final configuration once on the independent test set.

## 9. Conclusion

The validation results identify persistent, operationally relevant false negatives in churn-risk detection, including complaints with explicit switching and service-cancellation language. The evidence motivates targeted investigation but does not independently prove class imbalance, context bias, annotation inconsistency, or ASR errors as causal explanations.
