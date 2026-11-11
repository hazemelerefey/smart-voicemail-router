# SVR labeling report v1 — full train-ready set labeled

Date: 2026-11-11. Labeler: AZZAR (coordinator) plus 12 labeling workers, one per chunk. No model was trained, fine-tuned, or evaluated. No source CSV was modified.

## What was labeled

- Scope: the 5,881 train-ready rows only (prep_status == train_ready in transcripts_clean.csv).
- NOT labeled: the 143 quarantined rows and the 498 excluded rows. They are not in labeled_full_v1.csv.
- Calibration batch: 90 of its 100 rows are in the train-ready set and are labeled here. The other 10 are quarantined rows and are out of scope.
- Hazem's 4 ground-truth rows are included with his exact labels. Verified: all 4 match his labels exactly (category, urgency, state, churn, note).

## Method

1. Extracted the 5,881 train-ready rows from transcripts_clean.csv (text and text_norm).
2. Split them into 12 chunks of about 490 rows. Hazem's 4 rows were held aside and merged back with his exact labels, so they could not be overwritten.
3. Each worker labeled its chunk from the transcript wording only, using the approved taxonomy (taxonomy_proposal.md) and the approved annotation guide v1 (annotation_guide_draft.md). Same rules for every chunk: urgency from the complaint only, never from tone; state from the wording only; churn only on explicit leave-the-provider language; cancelling one service alone is not at_risk.
4. Merged the 12 chunk outputs plus Hazem's 4 rows into one file, sorted by the source row order. Validated: 5,881 rows, no missing or duplicate row IDs, file values byte-identical to the source and in the same order, every label value inside the allowed sets, every `other` row and every low-confidence row carries a note.

## Outputs

- `labeled_full_v1.csv` — 5,881 rows. Columns: file, complaint_category, complaint_urgency, customer_state, churn_risk, note, confidence.
- `labeling_summary.json` — counts per field, low-confidence rows, the `other` count, Hazem's 4-row match confirmation, and the full low-confidence list (417 rows with file, labels, and note).

## Distribution (5,881 rows)

complaint_category:
- network_and_connectivity 978 (16.6%)
- other 796 (13.5%)
- billing_and_charges 774 (13.2%)
- balance_and_data 772 (13.1%)
- app_and_account 730 (12.4%)
- thanks_or_praise 705 (12.0%)
- no_reply_or_long_wait 468 (8.0%)
- branch_and_staff 446 (7.6%)
- cancellation_request 212 (3.6%)
- greeting_only 0 (0%)

complaint_urgency: medium 3,396 (57.7%), low 1,943 (33.0%), high 542 (9.2%).

customer_state: frustrated 2,480 (42.2%), calm 2,335 (39.7%), satisfied 709 (12.1%), unclear 197 (3.3%), mad 160 (2.7%).

churn_risk: not_at_risk 5,849 (99.5%), at_risk 32 (0.5%). Every at_risk row carries explicit leave-the-provider or port-out language.

confidence: high 5,464 (92.9%), low 417 (7.1%).

## What the numbers say

- The big general network cluster from the TF-IDF pass (2,424 rows, 41%) did not survive labeling. Only 978 rows stayed in network_and_connectivity. The rest split into billing, balance, app, branch, no-reply, and other, because the transcripts state a narrower theme once read. The weak clustering (silhouette near zero) was a catch-all, not a real category.
- `other` is large: 796 rows (13.5%). The recurring themes inside it are package and offer questions, porting procedures, loyalty points, spam or harassing calls, discounts, SIM questions, and children or family packages. These are real themes, not noise, and they have nowhere to go in the current 10 categories.
- `greeting_only` got zero rows. Every greeting in the set was followed by a question or a complaint, so no transcript was a greeting alone.
- Low confidence is 417 rows (7.1%), almost all garbled Whisper transcripts. Of those, 219 could not be labeled confidently at all (category other or state unclear). The rest got a best-effort label from the readable part of the transcript.

## What needs Hazem's decision

1. The `other` bucket (796 rows). Add new categories for the recurring themes (offers/packages, porting, loyalty, spam), or keep them in `other`? If new categories are added, those 796 rows need re-labeling.
2. `greeting_only` got zero rows. Keep the category for completeness, or drop it?
3. The 219 rows that could not be labeled confidently (garbled transcripts). Exclude them from training, send them for re-transcription, or keep their best-effort labels?
4. The 417 low-confidence rows. Should Hazem or Ebtihal review them before training?
5. The 90 calibration rows in this file still need the team's human labels (from the SVR Data Annotation page) so my labels can be validated against theirs with kappa per field before training. The guide says do not scale on a failing calibration; this file is the agent-labeled set, and the human calibration is the check on it.
6. The 143 quarantined rows, the 498 excluded rows, and the 26 recovered files are not in this file. They need transcription or review before they can join training.
7. No model was trained. Hazem and the team lead the training from this file.
