# Dataset readiness report

Audio and speech pair (Hazem and Ebtihal). The dataset is mechanically
clean but not training-ready. This report states the verdict per track,
the status of all 13 issues, and exactly what the user must decide next.

## Verdicts

### Track A: ASR fine-tuning (audio plus transcript pairs) - BLOCKED

Usable pairs: 5,881 train-ready files, 16 kHz mono, with transcripts.
Blockers:
- transcript quality unverified beyond 20 reference rows (WER directional only)
- rights, consent, retention and processing locations unconfirmed
- dup_text_size fix still proposed, not confirmed by the reviewer
- clipping treatment undecided (recommendation: tolerate)
Owner: Hazem (reviewer) and Ebtihal.
Unblock: confirm rights; human-check a transcript verification sample; confirm dup fix; decide clipping treatment.

### Track B: router and classifier (needs labels) - BLOCKED

Blockers:
- no labels: category, urgency, customer state and churn are empty everywhere
- taxonomy is a candidate proposal, not approved
- annotation guide is a draft, calibration not run
- no annotators or adjudicator named
Owner: Hazem (reviewer) and Ebtihal.
Unblock: approve taxonomy; approve guide; name annotators; run 100-row calibration to kappa 0.7 per field.

## Issue status (all 13)

- 1. No labels - blocked. category, urgency, state, churn empty everywhere; taxonomy proposed, annotation not started.
- 2. Quarantine, 133 flagged - open. review queue built (133 flagged + 26 recovered awaiting transcription); human review not done.
- 3. Recoverable files, 26 - fixed. all 26 recovered and verified; 25 WAVs + 1 chunked long file; all need transcription.
- 4. Duration drift, 82 files - fixed. corrected inventory written; residual drift 0; 2,110 rows changed by more than 0.01 s.
- 5. Clipping, 320 rows - open. recommendation: tolerate. All 320 rows under 1 pct, max 0.5 pct, no confidence gap vs clean rows.
- 6. Low SNR, 22 files - fixed. 18 denoised with afftdn, HF floor drop verified; 0 low-SNR files in the training pool.
- 7. Long file, 125.92 s - fixed. chunk map with 3 segments (60, 60, 5.922 s); segments need transcription before use.
- 8. Speaker awareness - open, residual risk. no speaker IDs; leakage cannot be measured; mitigation is 0 audio duplicates in train-ready.
- 9. Transcript quality - blocked. WER directional only on 20 reference rows; verification sample needed before fine-tuning.
- 10. dup_text_size fix - proposed. 3 rows fixed in the derived file; reviewer confirmation pending.
- 11. Rights and consent - blocked. consent, retention and processing locations unconfirmed; local work only.
- 12. Telecom glossary - open. Latin terms and Arabic words counted; no agreed glossary yet.
- 13. Normalization edge cases - open. 5,751 of 6,024 rows differ between text and text_norm; spelling variants unexamined.

## What the user must decide next

1. confirm the recomputed dup_text_size values as canonical
2. freeze the 70/20/10 split
3. confirm rights, consent, retention and processing locations
4. approve or revise the taxonomy candidates
5. approve the annotation guide draft and name annotators and adjudicator
6. decide the clipping treatment (recommendation: tolerate)
7. approve transcription of the 26 recovered files

## Reproduction

Venv: ~/workspace/ai-customer-support/.venv-eda/bin/python
Notebook: preparation/dataset_preparation.ipynb (executed, outputs saved)
Tests: python -m pytest preparation/test_preparation.py -v
Gates: node ~/workspace/custom-skills/local-unlazy/scripts/gate-check.mjs --status preparation/GATES.md
Canonical files: sha256sum -c ~/workspace/ai-customer-support/dataset/prepared/run_log_hashes.txt

## Headline numbers (all recomputed by the notebook)

- Files: 6,522. Transcripts: 6,024. Train-ready: 5,881. Quarantine: 143. Excluded: 498.
- Split train/val/test 70/20/10: 4,117 / 1,176 / 588, 0 leaked groups.
- Recovered: 26 of 26 candidates. Corrected durations: 2,110 rows changed by more than 0.01 s.
- Clusters: 10 candidates on 5,881 rows, silhouette 0.0127 at k=10 (weak separation).
- Calibration batch: 100 rows. Review queue: 159 items.
