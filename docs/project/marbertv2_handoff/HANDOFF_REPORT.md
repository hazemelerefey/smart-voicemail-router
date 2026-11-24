# MARBERTv2 — Five-Seed Checkpoint Handoff

Run ID: `marbertv2-lr2e5-clean-20261119`
Generated (UTC): 2026-11-23T21:47:20.162912+00:00

## Training configuration

- Model: `UBC-NLP/MARBERTv2`
- Learning rate: `2e-05`
- Epochs: `3`
- Batch size: `16`
- Architecture: `single_task`
- Seeds: `[42, 1337, 2023, 7, 99]`
- Tasks: `['complaint_category', 'complaint_urgency', 'customer_state', 'churn_risk']`

## Delivery summary

- Verified task results: **20/20**
- Selected best checkpoints: **20/20**
- SHA-256 model hashes: **20/20**
- Total checkpoint files size: **36.48 GiB**

## Checkpoint inventory

| Seed | Field | Best epoch | Validation Macro-F1 |
|---|---|---:|---:|
| 42 | complaint_category | 2 | 0.7922 |
| 42 | complaint_urgency | 2 | 0.7168 |
| 42 | customer_state | 3 | 0.7550 |
| 42 | churn_risk | 3 | 0.7990 |
| 1337 | complaint_category | 3 | 0.7842 |
| 1337 | complaint_urgency | 3 | 0.7289 |
| 1337 | customer_state | 3 | 0.7432 |
| 1337 | churn_risk | 2 | 0.9162 |
| 2023 | complaint_category | 3 | 0.7786 |
| 2023 | complaint_urgency | 3 | 0.7115 |
| 2023 | customer_state | 3 | 0.7438 |
| 2023 | churn_risk | 1 | 0.6235 |
| 7 | complaint_category | 3 | 0.7903 |
| 7 | complaint_urgency | 3 | 0.7286 |
| 7 | customer_state | 2 | 0.7427 |
| 7 | churn_risk | 3 | 0.8839 |
| 99 | complaint_category | 3 | 0.7909 |
| 99 | complaint_urgency | 3 | 0.7196 |
| 99 | customer_state | 3 | 0.7505 |
| 99 | churn_risk | 2 | 0.9162 |

## Integrity

Each delivered `model.safetensors` was SHA-256 checked against
the selected checkpoint in the original run.
See `SHA256_MANIFEST.csv` for the complete file hashes.

## Important notes

- Checkpoints correspond to the selected best validation epoch.
- No test-set performance is claimed in this report.
- The original run remains separate from this handoff.
- The training configuration is preserved without modification.
