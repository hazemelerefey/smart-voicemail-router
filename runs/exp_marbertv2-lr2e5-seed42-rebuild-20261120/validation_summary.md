# MARBERTv2 validation results for marbertv2-lr2e5-seed42-rebuild-20261120

Learning rate 2e-05, epoch budget 3.
Single-seed evaluation: between-seed SD is unavailable. Delta compares seed 42 with corrected-text TF-IDF.
Customer state excludes the single unclear row. The other fields score all 1,003 rows.

| Field | 42 | Mean | Sample SD | TF-IDF | Delta | Beats baseline |
|---|---:|---:|---:|---:|---:|---:|
| complaint_category | 0.7922 | 0.7922 | N/A | 0.7605 | +0.0317 | Yes |
| complaint_urgency | 0.7172 | 0.7172 | N/A | 0.6902 | +0.0270 | Yes |
| customer_state | 0.7558 | 0.7558 | N/A | 0.7000 | +0.0558 | Yes |
| churn_risk | 0.7990 | 0.7990 | N/A | 0.8629 | -0.0639 | No |
| combined | 0.7661 | 0.7661 | N/A | 0.7534 | +0.0127 | Yes |

## Error analysis

Confusion counts below sum the predictions from all evaluated seeds. Class support is per seed. Per-class scores are means across seeds.

### complaint_category

| Actual / predicted | app_and_account | balance_and_data | billing_and_charges | branch_and_staff | cancellation_request | network_and_connectivity | no_reply_or_long_wait | offers_and_packages | other | sim_services | thanks_or_praise |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| app_and_account | 106 | 2 | 4 | 2 | 1 | 0 | 0 | 1 | 3 | 0 | 1 |
| balance_and_data | 5 | 87 | 22 | 0 | 1 | 1 | 0 | 8 | 4 | 0 | 1 |
| billing_and_charges | 0 | 8 | 119 | 1 | 4 | 2 | 1 | 2 | 2 | 0 | 0 |
| branch_and_staff | 0 | 0 | 6 | 65 | 0 | 1 | 3 | 1 | 2 | 0 | 0 |
| cancellation_request | 0 | 1 | 2 | 0 | 32 | 0 | 1 | 0 | 4 | 0 | 0 |
| network_and_connectivity | 5 | 6 | 4 | 6 | 0 | 141 | 5 | 2 | 4 | 0 | 0 |
| no_reply_or_long_wait | 2 | 4 | 0 | 9 | 1 | 2 | 64 | 0 | 3 | 0 | 0 |
| offers_and_packages | 2 | 0 | 0 | 0 | 1 | 0 | 0 | 27 | 2 | 0 | 1 |
| other | 4 | 2 | 5 | 6 | 3 | 2 | 1 | 6 | 33 | 0 | 0 |
| sim_services | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 10 | 0 |
| thanks_or_praise | 2 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 129 |

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| app_and_account | 0.8413 | 0.8833 | 0.8618 | 120 |
| balance_and_data | 0.7909 | 0.6744 | 0.7280 | 129 |
| billing_and_charges | 0.7346 | 0.8561 | 0.7907 | 139 |
| branch_and_staff | 0.7303 | 0.8333 | 0.7784 | 78 |
| cancellation_request | 0.7442 | 0.8000 | 0.7711 | 40 |
| network_and_connectivity | 0.9276 | 0.8150 | 0.8677 | 173 |
| no_reply_or_long_wait | 0.8533 | 0.7529 | 0.8000 | 85 |
| offers_and_packages | 0.5745 | 0.8182 | 0.6750 | 33 |
| other | 0.5789 | 0.5323 | 0.5546 | 62 |
| sim_services | 1.0000 | 0.8333 | 0.9091 | 12 |
| thanks_or_praise | 0.9773 | 0.9773 | 0.9773 | 132 |

Most frequent confusions across seeds.

- balance_and_data predicted as billing_and_charges in 22 cases.
- no_reply_or_long_wait predicted as branch_and_staff in 9 cases.
- billing_and_charges predicted as balance_and_data in 8 cases.

### complaint_urgency

| Actual / predicted | high | low | medium |
|---|---:|---:|---:|
| high | 66 | 1 | 37 |
| low | 7 | 244 | 64 |
| medium | 76 | 38 | 470 |

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| high | 0.4430 | 0.6346 | 0.5217 | 104 |
| low | 0.8622 | 0.7746 | 0.8161 | 315 |
| medium | 0.8231 | 0.8048 | 0.8139 | 584 |

Most frequent confusions across seeds.

- medium predicted as high in 76 cases.
- low predicted as medium in 64 cases.
- medium predicted as low in 38 cases.

### customer_state

| Actual / predicted | calm | frustrated | mad | satisfied |
|---|---:|---:|---:|---:|
| calm | 251 | 146 | 4 | 2 |
| frustrated | 88 | 340 | 10 | 0 |
| mad | 0 | 9 | 20 | 0 |
| satisfied | 2 | 0 | 0 | 130 |

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| calm | 0.7361 | 0.6228 | 0.6747 | 403 |
| frustrated | 0.6869 | 0.7763 | 0.7288 | 438 |
| mad | 0.5882 | 0.6897 | 0.6349 | 29 |
| satisfied | 0.9848 | 0.9848 | 0.9848 | 132 |

Most frequent confusions across seeds.

- calm predicted as frustrated in 146 cases.
- frustrated predicted as calm in 88 cases.
- frustrated predicted as mad in 10 cases.

### churn_risk

| Actual / predicted | at_risk | not_at_risk |
|---|---:|---:|
| at_risk | 3 | 4 |
| not_at_risk | 0 | 996 |

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| at_risk | 1.0000 | 0.4286 | 0.6000 | 7 |
| not_at_risk | 0.9960 | 1.0000 | 0.9980 | 996 |

Most frequent confusions across seeds.

- at_risk predicted as not_at_risk in 4 cases.

## Churn threshold analysis

Thresholds are optimized and scored on the same validation split. These exploratory scores can be optimistic.
The official prediction files and Macro-F1 comparisons use argmax.

| Seed | Threshold | Average precision | Argmax balanced accuracy | Tuned balanced accuracy | Tuned Macro-F1 | At-risk recall count |
|---:|---:|---:|---:|---:|---:|---:|
| 42 | 0.0135061 | 0.6890 | 0.7143 | 0.8561 | 0.8561 | 5/7 |
