# MARBERTv2 Single-Task Validation Results

## Experiment Identity

- Run ID: marbertv2-lr2e5-clean-20261119
- Model: UBC-NLP/MARBERTv2
- Architecture: Single-task
- Dataset version: v2
- Evaluation split: Validation
- Learning rate: 2e-5
- Batch size: 16
- Maximum epochs: 3
- Seeds: 42, 1337, 2023, 7, 99
- Validation records: 1003

## Evaluation Methodology

Four independent task models were evaluated per seed.
Predictions use argmax over the saved class probabilities.

The combined score is the unweighted mean of the
four task-level Macro-F1 scores.

The reported overall mean and sample standard deviation
are calculated across five random seeds.

Customer State evaluation excludes one unsupported
unclear label, resulting in 1002 evaluated records.

## Main Results

- Combined mean Macro-F1:
  0.7707815670
- Sample standard deviation:
  0.0335600682
- Best validation seed:
  99
- Best seed Macro-F1:
  0.7943072524

## Task-Level Results

| Task | Mean Macro-F1 | Sample SD |
|---|---:|---:|
| complaint_category | 0.787233 | 0.005719 |
| complaint_urgency | 0.721089 | 0.007608 |
| customer_state | 0.747066 | 0.005462 |
| churn_risk | 0.827738 | 0.123823 |

## Reproducibility

All 20 task-level checks passed.

The recovered validation scores match the original
experiment within numerical floating-point precision.

No model retraining was performed during recovery.

## Limitations

- Results are validation-only.
- The final test set was not accessed during recovery.
- Churn Risk has substantial variation across seeds.
- Churn Risk class imbalance requires careful interpretation.
- Best validation seed does not imply independent test
  superiority or automatic deployment approval.
- The five seeds are repeated runs, not five independent
  datasets.
- No new hyperparameter experiment was performed.

## Checkpoint Availability

Model weights remain stored on Google Drive.

The repository contains lightweight result artifacts
rather than full model weights.

## Integrity

SHA256_MANIFEST.json records the hashes of the files
in this RESULTS directory, excluding the manifest itself.
