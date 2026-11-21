# MARBERTv2 validation results for marbertv2-lr1e5-seed42-20261120

Learning rate 1e-05, epoch budget 3.
Single-seed evaluation: between-seed SD is unavailable. Delta compares seed 42 with corrected-text TF-IDF.
Customer state excludes the single unclear row. The other fields score all 1,003 rows.

| Field | 42 | Mean | Sample SD | TF-IDF | Delta | Beats baseline |
|---|---:|---:|---:|---:|---:|---:|
| complaint_category | 0.7549 | 0.7549 | N/A | 0.7605 | -0.0056 | No |
| complaint_urgency | 0.7132 | 0.7132 | N/A | 0.6902 | +0.0230 | Yes |
| customer_state | 0.7377 | 0.7377 | N/A | 0.7000 | +0.0377 | Yes |
| churn_risk | 0.4982 | 0.4982 | N/A | 0.8629 | -0.3647 | No |
| combined | 0.6760 | 0.6760 | N/A | 0.7534 | -0.0774 | No |

## Error analysis

Confusion counts below sum the predictions from all evaluated seeds. Class support is per seed. Per-class scores are means across seeds.

### complaint_category

| Actual / predicted | app_and_account | balance_and_data | billing_and_charges | branch_and_staff | cancellation_request | network_and_connectivity | no_reply_or_long_wait | offers_and_packages | other | sim_services | thanks_or_praise |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| app_and_account | 108 | 2 | 4 | 1 | 1 | 2 | 0 | 0 | 1 | 0 | 1 |
| balance_and_data | 5 | 91 | 24 | 0 | 1 | 2 | 0 | 5 | 0 | 0 | 1 |
| billing_and_charges | 1 | 19 | 106 | 2 | 4 | 1 | 2 | 2 | 2 | 0 | 0 |
| branch_and_staff | 0 | 0 | 4 | 58 | 0 | 2 | 13 | 0 | 1 | 0 | 0 |
| cancellation_request | 2 | 2 | 1 | 0 | 32 | 0 | 1 | 0 | 2 | 0 | 0 |
| network_and_connectivity | 5 | 7 | 6 | 2 | 0 | 138 | 12 | 1 | 2 | 0 | 0 |
| no_reply_or_long_wait | 1 | 4 | 1 | 5 | 0 | 2 | 71 | 0 | 1 | 0 | 0 |
| offers_and_packages | 2 | 0 | 1 | 1 | 2 | 0 | 0 | 25 | 1 | 0 | 1 |
| other | 5 | 3 | 8 | 4 | 3 | 3 | 6 | 9 | 20 | 1 | 0 |
| sim_services | 0 | 0 | 0 | 0 | 1 | 2 | 0 | 0 | 0 | 9 | 0 |
| thanks_or_praise | 3 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 128 |

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| app_and_account | 0.8182 | 0.9000 | 0.8571 | 120 |
| balance_and_data | 0.7109 | 0.7054 | 0.7082 | 129 |
| billing_and_charges | 0.6839 | 0.7626 | 0.7211 | 139 |
| branch_and_staff | 0.7945 | 0.7436 | 0.7682 | 78 |
| cancellation_request | 0.7273 | 0.8000 | 0.7619 | 40 |
| network_and_connectivity | 0.9020 | 0.7977 | 0.8466 | 173 |
| no_reply_or_long_wait | 0.6762 | 0.8353 | 0.7474 | 85 |
| offers_and_packages | 0.5952 | 0.7576 | 0.6667 | 33 |
| other | 0.6667 | 0.3226 | 0.4348 | 62 |
| sim_services | 0.9000 | 0.7500 | 0.8182 | 12 |
| thanks_or_praise | 0.9771 | 0.9697 | 0.9734 | 132 |

Most frequent confusions across seeds.

- balance_and_data predicted as billing_and_charges in 24 cases.
- billing_and_charges predicted as balance_and_data in 19 cases.
- branch_and_staff predicted as no_reply_or_long_wait in 13 cases.

### complaint_urgency

| Actual / predicted | high | low | medium |
|---|---:|---:|---:|
| high | 74 | 0 | 30 |
| low | 7 | 240 | 68 |
| medium | 94 | 37 | 453 |

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| high | 0.4229 | 0.7115 | 0.5305 | 104 |
| low | 0.8664 | 0.7619 | 0.8108 | 315 |
| medium | 0.8221 | 0.7757 | 0.7982 | 584 |

Most frequent confusions across seeds.

- medium predicted as high in 94 cases.
- low predicted as medium in 68 cases.
- medium predicted as low in 37 cases.

### customer_state

| Actual / predicted | calm | frustrated | mad | satisfied |
|---|---:|---:|---:|---:|
| calm | 276 | 120 | 5 | 2 |
| frustrated | 110 | 302 | 25 | 1 |
| mad | 0 | 5 | 24 | 0 |
| satisfied | 3 | 0 | 0 | 129 |

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| calm | 0.7095 | 0.6849 | 0.6970 | 403 |
| frustrated | 0.7073 | 0.6895 | 0.6983 | 438 |
| mad | 0.4444 | 0.8276 | 0.5783 | 29 |
| satisfied | 0.9773 | 0.9773 | 0.9773 | 132 |

Most frequent confusions across seeds.

- calm predicted as frustrated in 120 cases.
- frustrated predicted as calm in 110 cases.
- frustrated predicted as mad in 25 cases.

### churn_risk

| Actual / predicted | at_risk | not_at_risk |
|---|---:|---:|
| at_risk | 0 | 7 |
| not_at_risk | 0 | 996 |

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| at_risk | 0.0000 | 0.0000 | 0.0000 | 7 |
| not_at_risk | 0.9930 | 1.0000 | 0.9965 | 996 |

Most frequent confusions across seeds.

- at_risk predicted as not_at_risk in 7 cases.

## Churn threshold analysis

Thresholds are optimized and scored on the same validation split. These exploratory scores can be optimistic.
The official prediction files and Macro-F1 comparisons use argmax.

| Seed | Threshold | Average precision | Argmax balanced accuracy | Tuned balanced accuracy | Tuned Macro-F1 | At-risk recall count |
|---:|---:|---:|---:|---:|---:|---:|
| 42 | 0.0128956 | 0.1004 | 0.5000 | 0.5709 | 0.6094 | 1/7 |
