# Official Phase 2 Real Validation Results

**Archival record from the previously observed Codex execution summary.** The authorized run completed successfully. No Validation was rerun to prepare these files.

Each seed independently assigned all 1,003 approved Validation rows. The rejection ledgers were empty. Each seed reconciled to 1,003, and Agent State returned to baseline.

| Seed | Assigned | Valid routing-Unassigned | Invalid approved | Missing approved | Rejected | Input coverage | Manifest coverage | Assignment Rate | Human Review | Agent State |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | 1003 | 0 | 0 | 0 | 0 | 100% | 100% | 100% | 46 | Restored |
| 42 | 1003 | 0 | 0 | 0 | 0 | 100% | 100% | 100% | 48 | Restored |
| 99 | 1003 | 0 | 0 | 0 | 0 | 100% | 100% | 100% | 45 | Restored |
| 1337 | 1003 | 0 | 0 | 0 | 0 | 100% | 100% | 100% | 63 | Restored |
| 2023 | 1003 | 0 | 0 | 0 | 0 | 100% | 100% | 100% | 56 | Restored |

Assignment Rate equals assigned rows divided by 1,003 per seed. The execution processed one ticket at a time and released each reservation exactly once. The separate synthetic preflight recorded **67 passed, 0 failed, 0 errors, 0 skipped**.

## Provenance

- Run ID `fair-marbertv2-lr2e5`, model `MARBERTv2`, dataset version `v2`, wire split `val`, wire schema version `1`.
- Approved manifest `C:/Users/RC/svr-data/final/clean_training_val.csv`.
- Manifest revision `32e32436854cd214346ff87e7dc856897645eae0` and tracked Git blob `b1adfcc118a766a44bdc1fbe60f372829b2dc720`.
- Manifest SHA-256 `50df253ad6506b70a262b512eff1f79562f2cd65d58143127899025ad707cb18` authenticates the Windows CRLF file bytes. The tracked Git blob identifies the LF-normalized content.
- Pinned official Arafa commit `fe695befbb9bd8769273cc7ea2e8dffc84518820`.
- Prediction directory `C:/Users/RC/svr-data/runs/exp_fair-marbertv2-lr2e5`.

| Seed | Prediction export | SHA-256 |
| --- | --- | --- |
| 7 | `predictions_val_seed7.json` | `8c560479b2b71441eca9ed8011dc1adfe68e1c3e8029293917841d75d0853036` |
| 42 | `predictions_val_seed42.json` | `8caa187812034242a56ef9f3fa33a6417bcbc797a9b9b94065b2f3c3f9a038c7` |
| 99 | `predictions_val_seed99.json` | `8c4fcfbca9eab8ed0dc6418ca035a98ba996378957c0a15add30cef170877225` |
| 1337 | `predictions_val_seed1337.json` | `05525ece42b95db58ca1f4d1f71fe580e6d349ecdbfc1b3e8c973ff69771befc` |
| 2023 | `predictions_val_seed2023.json` | `e6948b2150dd7af0682d21ac897ca0cb5eb968960b08abcca5ed9de398bc3f51` |

## Interpretation and evidence limits

- The completed run evaluated only Validation (val). The Final Test Set was outside scope.
- Assignment Rate measures successful routing assignments per approved Validation row. It does not measure model classification accuracy.
- Sequential assignment and exactly-once release do not measure concurrent production capacity.
- Suggested Script Templates are pending Hazem's customer-facing approval.
- Human Review counts use the confidence threshold of 0.5.
- Only aggregate results and provenance were retained in the observed execution summary. Original result objects, a local raw execution log, and per-ticket records were unavailable for this archive.

For a separately authorized reproduction, use the verified source bytes and pinned runtime, then follow the [existing gated procedure](../../docs/project/triage-routing-phase2.md#separately-authorized-real-validation-execution) in a fresh isolated Python process. Preserve the five per-seed reports with the exact runner revision or digest and a timestamped execution log if independent audit of that reproduction is needed.

Companion records are the [CSV](phase2-real-validation.csv) and [JSON](phase2-real-validation.json). CSV and JSON rates use fractions from 0 to 1.
