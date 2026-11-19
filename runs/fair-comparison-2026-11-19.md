# Fair comparison: EgyBERT vs MARBERTv2 (Phase 2, 2026-11-19)

## Winner: MARBERTv2

MARBERTv2 wins Phase 2 by validation mean macro-F1. The decision is by the
project rule (highest validation mean macro-F1); no tie-break was needed.

## How it was run

Both models were re-run from scratch under the exact same protocol, on
Google Colab (Tesla T4), so the comparison isolates the model, not the
setup:
- Learning rate 2e-5, batch 16, epochs 3 (max 5, early stopping patience 2),
  warmup 0.1, weight decay 0.01, max sequence length 128, AdamW, dropout 0.1
- Class weights from train only, applied in the loss for all 4 fields
  (including churn_risk)
- Input text_norm only; frozen split train 3,575 / validation 1,003
- 5 seeds: 42, 1337, 2023, 7, 99; mean plus sample std (ddof=1)
- customer_state scored on 4 classes only (calm, frustrated, mad,
  satisfied); the single unclear validation row excluded from that field
- Test split never loaded, never touched
- Environment: Python 3.13.16, torch 2.14.1+cu130, transformers 5.22.1,
  scikit-learn 1.6.1 (Colab preinstalled; not the pinned 2.8.0 / 4.56.2,
  but identical for both models, so the comparison is fair)

## Results (validation macro-F1, mean plus/minus std over 5 seeds)

| Field | EgyBERT | MARBERTv2 | TF-IDF baseline (tfidf-002) |
|---|---|---|---|
| complaint_category | 0.7180 ± 0.0069 | 0.7895 ± 0.0070 | 0.7605 |
| complaint_urgency | 0.7038 ± 0.0098 | 0.7250 ± 0.0076 | 0.6902 |
| customer_state | 0.7422 ± 0.0086 | 0.7442 ± 0.0021 | 0.7000 |
| churn_risk | 0.5233 ± 0.0560 | 0.9041 ± 0.0616 | 0.8629 |
| Combined mean | 0.6718 | 0.7907 | 0.7534 |

MARBERTv2 beats EgyBERT on every field and on the combined mean
(0.7907 vs 0.6718, difference 0.1189).

## Verification

All 40 field-seed values (4 fields x 5 seeds x 2 models) were recomputed
independently from the prediction files against the validation truth table.
Every value matches its run record exactly (difference 0). Prediction
files carry probabilities for all 4 fields, summing to 1, with no text or
transcript. The class weights were checked to align with the correct
classes (at_risk carries 89.375).

## Why EgyBERT churn collapsed

EgyBERT catches 0 or 1 of the 7 at-risk validation rows in every seed
(macro-F1 0.5233), while MARBERTv2 catches 3 to 6 of 7 (0.9041). This is a
real difference between the models under the protocol's class-weights
loss, not a setup error. The earlier 0.9162 for EgyBERT came from a
different technique (oversampling the minority class), not from the
protocol.

## Artifacts

- runs/exp_fair-egybert-lr2e5/ (run_record.json + 5 prediction files)
- runs/exp_fair-marbertv2-lr2e5/ (run_record.json + 5 prediction files)
- runs/fair-comparison-2026-11-19/train_fair.py (the training script)

## What happens next

Sira continues with MARBERTv2 for multi-task training. Ibthal validates
on the MARBERTv2 validation predictions
(runs/exp_fair-marbertv2-lr2e5/predictions_val_seed{42,1337,2023,7,99}.json).
