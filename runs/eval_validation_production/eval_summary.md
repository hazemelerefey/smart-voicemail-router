# SVR Production Evaluation Summary (validation)

- **Generated UTC:** `2026-11-24T21:04:49+00:00`
- **Split:** `validation` (`1003` rows, dataset version `v2`)
- **Model version:** `UBC-NLP/MARBERTv2:single-task-lr2e5-shaa92e68685217`
- **Checkpoint SHA-256 (combined):** `0ea433c589f414572f4adf5c28c570bab84f8ffebc1871c979c84721f00f5adb`
- **Database EvalRun ID:** `08a8409c-9738-4398-9a2c-18b1427a8581`

## 1. Classification Macro-F1 & AI9 Release Gates

| Field | Live Macro-F1 | AI9 Gate | Status | Sira Val Ref | Fair 5-Seed Mean +/- Std | Scored Rows |
|---|---:|---:|---|---:|---|---:|
| `complaint_category` | **0.7922** | >= 0.75 | PASS | 0.7872 | 0.7895 +/- 0.0070 | 1003 (excl 0) |
| `complaint_urgency` | **0.7168** | >= 0.70 | PASS | 0.7211 | 0.7250 +/- 0.0076 | 1003 (excl 0) |
| `customer_state` | **0.7550** | >= 0.70 | PASS | 0.7471 | 0.7442 +/- 0.0021 | 1002 (excl 1) |
| `churn_risk` | **0.7990** | >= 0.80 | FAIL | 0.8277 | 0.9041 +/- 0.0616 | 1003 (excl 0) |
| **Combined (unweighted mean)** | **0.7657** | >= 0.75 | PASS | 0.7708 | 0.7907 +/- 0.0160 | 1003 |

### Churn Risk Fragility Note (AI9)

- True `at_risk` rows in `validation`: **7** of 1003
- Predicted `at_risk` rows: **3** (TP: 3, FP: 0, FN: 4)
- `at_risk` precision: 1.0000, recall: 0.4286, F1: 0.6000
- Because validation contains only 7 `at_risk` rows, a single flipped prediction changes churn macro-F1 substantially. Always inspect per-seed churn values below alongside the mean.

### 5-Seed Breakdown (`runs/exp_fair-marbertv2-lr2e5/run_record.json`)

| Seed | Category F1 | Urgency F1 | State F1 | Churn F1 | Combined F1 |
|---:|---:|---:|---:|---:|---:|
| 42 | 0.7835 | 0.7305 | 0.7415 | 0.7990 | 0.7636 |
| 1337 | 0.7987 | 0.7212 | 0.7428 | 0.9613 | 0.8060 |
| 2023 | 0.7815 | 0.7133 | 0.7466 | 0.9281 | 0.7924 |
| 7 | 0.7923 | 0.7294 | 0.7443 | 0.9162 | 0.7955 |
| 99 | 0.7914 | 0.7307 | 0.7459 | 0.9162 | 0.7960 |

## 2. Routing Agreement (FR20 Telecom Skill Mapping)

- **Routing Agreement:** **88.73%** (890/1003 rows) - AI9 Gate >= 80.00%: **PASS**
- **Exact 11-Category Match Rate:** 81.06%
- **Priority Bucket Agreement:** 76.85% (1002 scored, 1 unclear excluded)
- **Human Review Rate (threshold 0.50):** 13.06% (131/1003, AI10 target <= 20.00%)

| Telecom Skill | Ideal Agent | Support | Predicted | Agreed | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|---:|---:|
| Network | Network Care Specialist | 270 | 237 | 224 | 0.9451 | 0.8296 | 0.8836 |
| Billing | Billing & Bundles Specialist | 301 | 319 | 273 | 0.8558 | 0.9070 | 0.8806 |
| General | Subscriber Care Specialist | 432 | 447 | 393 | 0.8792 | 0.9097 | 0.8942 |

## 3. Whisper large-v3 STT Sample & Per-Stage Latency

- **Real WAVs Transcribed:** 10 from `dataset/val/`
- **10-Column STT v1 Schema Valid:** 10/10 (errors: 0)
- **Hardware:** `Windows-10-10.0.26300-SP0`, CPUs: `8`, Classifier device: `cpu`, STT: `cpu` (`int8`)
- **Hardware Note:** Measured on local CPU hardware; PRD <= 10s p95 latency target assumes a production GPU server (PRD L8/R3).

| Stage | Samples (n) | p50 (ms) | p95 (ms) | Mean (ms) | Max (ms) |
|---|---:|---:|---:|---:|---:|
| `transcribe` | 10 | 15317.20 | 19020.71 | 15910.00 | 19615.59 |
| `classify` | 30 | 286.13 | 381.69 | 298.53 | 649.18 |
| `priority` | 30 | 0.02 | 0.03 | 0.02 | 0.03 |
| `route` | 30 | 1.29 | 1.45 | 1.30 | 3.35 |
| `brief` | 30 | 0.00 | 0.00 | 0.00 | 0.00 |
| `end_to_end` | 10 | 15614.76 | 19359.02 | 16244.48 | 19953.06 |

## 4. Exceptions & Provenance

- Label status: The labels come from a model and are still being audited by the team. They are not human-verified until the audit approves them.
- Exception on `customer_state`: excluded `['unclear']` (1 row(s), scored 1002/1003). Reason: unclear has 0 rows in train (1 in val, 0 in test), so the model never trains on it; excluded from customer_state macro-F1 only (Hazem's decision).
