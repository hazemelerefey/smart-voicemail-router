# Phase 2 Real Validation reproduction

Reproduction ID phase2-real-validation-20261124T174111068Z-b5e6421a.

This separately authorized rerun used the gated loader and five approved Validation exports. The metrics below were recomputed from the persisted result objects.

| Seed | Assigned | Routing Unassigned | Invalid approved | Missing approved | Rejected | Input coverage | Manifest coverage | Assignment rate | Human Review | Releases |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | 1003 | 0 | 0 | 0 | 0 | 100% | 100% | 100% | 46 | 1003 |
| 42 | 1003 | 0 | 0 | 0 | 0 | 100% | 100% | 100% | 48 | 1003 |
| 99 | 1003 | 0 | 0 | 0 | 0 | 100% | 100% | 100% | 45 | 1003 |
| 1337 | 1003 | 0 | 0 | 0 | 0 | 100% | 100% | 100% | 63 | 1003 |
| 2023 | 1003 | 0 | 0 | 0 | 0 | 100% | 100% | 100% | 56 | 1003 |

Each seed reconciled to 1,003 approved rows and returned Agent State to baseline.
Every compared metric matches the historical summary.

## Provenance and scope

- Runner Git commit 66b691409b0fc9a1fd0c60dfe0f444b76a5e314d, branch team/ibthal-triage-routing, exact notebook SHA-256 3131e1911363f00f35479f46f6892b932d7a2aa73652e7cf1e595bec81beb730.
- Pinned Arafa commit fe695befbb9bd8769273cc7ea2e8dffc84518820. All input digests and manifest identity are in [run metadata](run-metadata.json).
- MARBERTv2, fair-marbertv2-lr2e5, dataset v2, Validation split val. The separate synthetic preflight passed 67 tests.
- Result objects include source row identifiers and runner fields with corrected transcript text omitted. Reader and release observations were recorded during this run. No historical per-ticket evidence was reconstructed.
- The assignments measure routing at sequential capacity. They do not measure classification accuracy or concurrent capacity. Human Review uses threshold 0.5. Scripts remain pending Hazem's customer-facing approval. Final Test was outside scope.

## Evidence

- [Full execution log](run.jsonl) and [SHA-256 inventory](SHA256SUMS.txt).
- [Executed notebook snapshot](runner-source.ipynb), [adapter code](adapter-code.py), and [capture script](capture.py).

The capture script reads the checked-out notebook. Use the recorded revision and verify its notebook SHA-256 before any independently authorized reproduction. Run it in a new evidence directory from the project root with an explicit authorization argument.

- Seed 7 [result](seed-7-result.json) and [log](seed-7.jsonl).
- Seed 42 [result](seed-42-result.json) and [log](seed-42.jsonl).
- Seed 99 [result](seed-99-result.json) and [log](seed-99.jsonl).
- Seed 1337 [result](seed-1337-result.json) and [log](seed-1337.jsonl).
- Seed 2023 [result](seed-2023-result.json) and [log](seed-2023.jsonl).
