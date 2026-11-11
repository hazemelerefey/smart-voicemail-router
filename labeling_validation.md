# Labeling validation

Date: 2026-11-11. Dataset: `dataset/train/`, `dataset/val/`, `dataset/test/` in this repo. Each split holds its audio files plus one `labels.csv`. Full detail and the code that computed every number here live in `notebooks/data-labeling/data_labeling.ipynb`, section 9. The notebook was run with the venv Python at `~/workspace/ai-customer-support/.venv-eda/bin/python` and finished with 0 errors.

## The dataset in short

The model is multi-task: it predicts all four fields at once, complaint_category, complaint_urgency, customer_state and churn_risk. The file name carries the client state as its prefix, then a 4 digit index, then `.wav` only, for example `calm_0001.wav`. The `labels.csv` beside the audio is the source of truth, with one row per audio file and columns file, original_file, complaint_category, complaint_urgency, customer_state, churn_risk, note, confidence. The rename from the old intermediate names to the clean names is recorded in `rename_mapping.csv` at the repo root. Every delivered file is a 16 kHz mono WAV. The original file name and folder are kept in the `original_file` column, so the original formats are still on record: m4a 1,771, mp4 1,459, ogg 929, mpeg 636, aac 522, mp3 393, wav 23, opus 13, ogx 5.

## a. Coverage: every audio file has exactly one label row

| Split | Audio files on disk | Label rows | Missing labels | Orphan files | Duplicate rows |
| --- | --- | --- | --- | --- | --- |
| train | 4,023 | 4,023 | 0 | 0 | 0 |
| val | 1,158 | 1,158 | 0 | 0 | 0 |
| test | 570 | 570 | 0 | 0 | 0 |
| total | 5,751 | 5,751 | 0 | 0 | 0 |

Pass. One original file appears twice in `labels.csv` on purpose: the long call `1757.mp4` was split into two chunks, `satisfied_0137.wav` and `satisfied_0138.wav` (chunks 0 and 1). That is one original file with two labeled chunks, not a duplicate label.

## b. Allowed values: every label value is in the approved set

complaint_category has 12 approved values: network_and_connectivity, billing_and_charges, balance_and_data, app_and_account, branch_and_staff, no_reply_or_long_wait, cancellation_request, thanks_or_praise, offers_and_packages, sim_services, other, greeting_only. Eleven are in use; greeting_only has 0 rows because it was approved and then dropped. complaint_urgency is high, medium or low. customer_state is calm, frustrated, mad, satisfied or unclear. churn_risk is at_risk or not_at_risk. Values outside the approved sets: 0 in all four fields.

Final counts: category network_and_connectivity 983, billing_and_charges 781, balance_and_data 776, app_and_account 720, thanks_or_praise 711, no_reply_or_long_wait 474, branch_and_staff 453, other 357, offers_and_packages 217, cancellation_request 213, sim_services 66. Urgency medium 3,431, low 1,764, high 556. State frustrated 2,517, calm 2,359, satisfied 715, mad 159, unclear 1. Churn not_at_risk 5,719, at_risk 32. Confidence high 5,511, low 240. The single unclear row is `unclear_0001.wav` in train, a recovered row with a heavily garbled transcript and low confidence.

Pass.

## c. Name prefix matches customer_state

The file name prefix (the part before the underscore) matches the customer_state value in `labels.csv` for all 5,751 rows. Mismatches: 0.

Pass.

## d. Counts reconcile

Per split: train 4,023, val 1,158, test 570, total 5,751. Sources, found by original file name: train ready 5,662 (5,881 labeled rows minus 219 garbled rows), quarantined 62, recovered 27. The three sources add to 5,751. Garbled rows in the final set: 0. Unknown rows: 0. Sources by split: train ready 3,961 train, 1,141 val, 560 test; quarantined 43 train, 12 val, 7 test; recovered 19 train, 5 val, 3 test.

The rename mapping agrees with the labels: per split the mapping has the same rows and the same new names as `labels.csv` (4,023, 1,158, 570), the mapping old names match the clean training audio files (5,751), and all four label fields plus the original file agree through the mapping on 5,751 of 5,751 rows.

Pass.

## e. Hazem's 4 hand labeled rows

Each row was found in the final `labels.csv` by its original file name and cross checked through `rename_mapping.csv`. The mapping agrees on all 4.

| Row | Original file | Clean file | Split | Hazem | Final | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | WhatsApp Audio 2025-12-09 at 4.40.18 PM (1).ogg | calm_1511.wav | train | network_and_connectivity, low, calm, not_at_risk | network_and_connectivity, low, calm, not_at_risk | Pass, exact match |
| 2 | WhatsApp Audio 2025-11-25 at 11.25.14 PM (2).mp4 | mad_0059.wav | train | billing_and_charges, medium, mad, not_at_risk | billing_and_charges, medium, mad, not_at_risk | Pass, exact match |
| 3 | AUDIO-2025-11-27-17-03-55.m4a | calm_0770.wav | train | other, low, calm, not_at_risk | offers_and_packages, low, calm, not_at_risk | Category changed, explained below |
| 4 | 0296.mp4 | frustrated_0013.wav | test | billing_and_charges, medium, frustrated, at_risk | billing_and_charges, medium, frustrated, at_risk | Pass, exact match |

Row 3 differs on category only. Urgency, state and churn still match. The reason is the approved other bucket relabel: the row was moved from other to the new offers_and_packages category, using Hazem's own note as the evidence ("He is inquiring about subscribing to an internet package for children that includes a content filter, and is asking if this is available?"). When Hazem labeled it, offers_and_packages did not exist yet, so other was the right label then. Under the current taxonomy the row belongs in offers_and_packages. The old claim that all 4 rows match exactly was true against the pre-relabel file `labeled_full_v1.csv` and is no longer true against the final `labels.csv`. That is a taxonomy change, not a labeling error.

## f. Verdict

The labeling is right. Checks passed: 24. Checks failed: 0. Explained differences that are not failures: 1 (Hazem row 3 category, other to offers_and_packages, approved other bucket relabel). Unexplained failures: 0.
