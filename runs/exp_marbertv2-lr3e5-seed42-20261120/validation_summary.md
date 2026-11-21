# MARBERTv2 validation results for marbertv2-lr3e5-seed42-20261120

Learning rate 3e-05, epoch budget 3.
Single-seed evaluation: between-seed SD is unavailable. Delta compares seed 42 with corrected-text TF-IDF.
Customer state excludes the single unclear row. The other fields score all 1,003 rows.

| Field | 42 | Mean | Sample SD | TF-IDF | Delta | Beats baseline |
|---|---:|---:|---:|---:|---:|---:|
| complaint_category | 0.7924 | 0.7924 | N/A | 0.7605 | +0.0319 | Yes |
| complaint_urgency | 0.7142 | 0.7142 | N/A | 0.6902 | +0.0240 | Yes |
| customer_state | 0.7416 | 0.7416 | N/A | 0.7000 | +0.0416 | Yes |
| churn_risk | 0.8629 | 0.8629 | N/A | 0.8629 | -0.0000 | No |
| combined | 0.7778 | 0.7778 | N/A | 0.7534 | +0.0244 | Yes |

## Error analysis

Confusion counts below sum the predictions from all evaluated seeds. Class support is per seed. Per-class scores are means across seeds.

### complaint_category

| Actual / predicted | app_and_account | balance_and_data | billing_and_charges | branch_and_staff | cancellation_request | network_and_connectivity | no_reply_or_long_wait | offers_and_packages | other | sim_services | thanks_or_praise |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| app_and_account | 103 | 2 | 6 | 2 | 1 | 1 | 0 | 1 | 3 | 0 | 1 |
| balance_and_data | 5 | 91 | 19 | 0 | 1 | 1 | 0 | 9 | 2 | 0 | 1 |
| billing_and_charges | 0 | 11 | 117 | 1 | 4 | 2 | 0 | 2 | 2 | 0 | 0 |
| branch_and_staff | 0 | 0 | 5 | 65 | 0 | 1 | 3 | 1 | 3 | 0 | 0 |
| cancellation_request | 0 | 2 | 1 | 1 | 31 | 0 | 1 | 0 | 4 | 0 | 0 |
| network_and_connectivity | 3 | 9 | 4 | 6 | 0 | 141 | 5 | 2 | 3 | 0 | 0 |
| no_reply_or_long_wait | 1 | 4 | 0 | 3 | 1 | 2 | 69 | 0 | 5 | 0 | 0 |
| offers_and_packages | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 27 | 2 | 0 | 1 |
| other | 5 | 3 | 4 | 8 | 2 | 1 | 1 | 7 | 31 | 0 | 0 |
| sim_services | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 10 | 0 |
| thanks_or_praise | 2 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 129 |

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| app_and_account | 0.8583 | 0.8583 | 0.8583 | 120 |
| balance_and_data | 0.7459 | 0.7054 | 0.7251 | 129 |
| billing_and_charges | 0.7452 | 0.8417 | 0.7905 | 139 |
| branch_and_staff | 0.7558 | 0.8333 | 0.7927 | 78 |
| cancellation_request | 0.7561 | 0.7750 | 0.7654 | 40 |
| network_and_connectivity | 0.9276 | 0.8150 | 0.8677 | 173 |
| no_reply_or_long_wait | 0.8734 | 0.8118 | 0.8415 | 85 |
| offers_and_packages | 0.5510 | 0.8182 | 0.6585 | 33 |
| other | 0.5636 | 0.5000 | 0.5299 | 62 |
| sim_services | 1.0000 | 0.8333 | 0.9091 | 12 |
| thanks_or_praise | 0.9773 | 0.9773 | 0.9773 | 132 |

Most frequent confusions across seeds.

- balance_and_data predicted as billing_and_charges in 19 cases.
- billing_and_charges predicted as balance_and_data in 11 cases.
- network_and_connectivity predicted as balance_and_data in 9 cases.

### complaint_urgency

| Actual / predicted | high | low | medium |
|---|---:|---:|---:|
| high | 66 | 1 | 37 |
| low | 7 | 239 | 69 |
| medium | 73 | 40 | 471 |

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| high | 0.4521 | 0.6346 | 0.5280 | 104 |
| low | 0.8536 | 0.7587 | 0.8034 | 315 |
| medium | 0.8163 | 0.8065 | 0.8114 | 584 |

Most frequent confusions across seeds.

- medium predicted as high in 73 cases.
- low predicted as medium in 69 cases.
- medium predicted as low in 40 cases.

### customer_state

| Actual / predicted | calm | frustrated | mad | satisfied |
|---|---:|---:|---:|---:|
| calm | 268 | 128 | 5 | 2 |
| frustrated | 118 | 303 | 15 | 2 |
| mad | 0 | 7 | 22 | 0 |
| satisfied | 2 | 0 | 0 | 130 |

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| calm | 0.6907 | 0.6650 | 0.6776 | 403 |
| frustrated | 0.6918 | 0.6918 | 0.6918 | 438 |
| mad | 0.5238 | 0.7586 | 0.6197 | 29 |
| satisfied | 0.9701 | 0.9848 | 0.9774 | 132 |

Most frequent confusions across seeds.

- calm predicted as frustrated in 128 cases.
- frustrated predicted as calm in 118 cases.
- frustrated predicted as mad in 15 cases.

### churn_risk

| Actual / predicted | at_risk | not_at_risk |
|---|---:|---:|
| at_risk | 4 | 3 |
| not_at_risk | 0 | 996 |

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| at_risk | 1.0000 | 0.5714 | 0.7273 | 7 |
| not_at_risk | 0.9970 | 1.0000 | 0.9985 | 996 |

Most frequent confusions across seeds.

- at_risk predicted as not_at_risk in 3 cases.

## Churn threshold analysis

Thresholds are optimized and scored on the same validation split. These exploratory scores can be optimistic.
The official prediction files and Macro-F1 comparisons use argmax.

| Seed | Threshold | Average precision | Argmax balanced accuracy | Tuned balanced accuracy | Tuned Macro-F1 | At-risk recall count |
|---:|---:|---:|---:|---:|---:|---:|
| 42 | 0.173428 | 0.7872 | 0.7857 | 0.8571 | 0.9162 | 5/7 |
