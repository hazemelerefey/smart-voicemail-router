# Smart Voicemail Router

Smart Voicemail Router turns Egyptian Arabic customer voicemails into explainable callback tickets. Each voicemail is transcribed, labeled for complaint category, urgency, customer state, and churn risk, and routed so the right team calls back first with the context in hand. This repo holds the data foundation for that system: the audio, the labels, the preparation notebooks, and the clean training tables.

## The dataset

The raw set is 6,522 voicemails, 12.6 hours of audio, received in 9 formats and standardized to 16 kHz mono WAV. Speech to text produced 6,024 transcripts. Whisper large-v3 was used for transcription; on a 20 row eval it scored WER 0.29 against 0.35 for turbo.

From the 6,522 files, 498 were excluded and 5,881 rows were labeled as train ready. The clean training set is 5,751 rows: 5,662 train ready rows, 62 quarantined rows that were labeled and joined, and 27 recovered rows. 219 garbled rows were excluded from training after a re-transcription check showed re-transcription does not fix garbled audio.

Each row carries four labels:

| Field | Values |
| --- | --- |
| complaint_category | network_and_connectivity, billing_and_charges, balance_and_data, app_and_account, branch_and_staff, no_reply_or_long_wait, cancellation_request, thanks_or_praise, offers_and_packages, sim_services, other, greeting_only |
| complaint_urgency | high, medium, low |
| customer_state | calm, frustrated, mad, satisfied, unclear |
| churn_risk | at_risk, not_at_risk |

Category counts in the clean set: network_and_connectivity 983, billing_and_charges 781, balance_and_data 776, app_and_account 720, thanks_or_praise 711, no_reply_or_long_wait 474, branch_and_staff 453, other 357, offers_and_packages 217, cancellation_request 213, sim_services 66. Urgency: medium 3,431, low 1,764, high 556. State: frustrated 2,517, calm 2,359, satisfied 715, mad 159, unclear 1. Churn: at_risk 32, not_at_risk 5,719. Confidence: high 5,511, low 240. `greeting_only` is an approved value with 0 rows.

The split is 70/20/10. The training tables in `final/` and the audio folders in `dataset/` hold the same corrected split, stratified by complaint category: train 4,031, val 1,136, test 584, and the file set in each folder is identical to the matching training table. Before 2026-11-11 the folders kept the original split (train 4,023, val 1,158, test 570); the original assignment is kept in `rename_mapping.csv` as `old_split` and `old_clean_name`. The rename from intermediate audio names to clean names is recorded in `rename_mapping.csv`, which carries the original file, the old split and old clean name, the intermediate old name, and the new split and new clean name for all 5,751 rows.

## The pipeline

1. **EDA.** `notebooks/data-analysis/data_analysis.ipynb` inventories the audio, the transcripts, and the labels, and measures class balance, duplicates, transcript quality, and the transcription models.
2. **Preprocessing.** `notebooks/data-preprocessing/data_preprocessing.ipynb` standardizes the audio, reconciles the transcripts, applies the quarantine and recovery decisions, and builds the clean training set.
3. **Labeling.** `notebooks/data-labeling/data_labeling.ipynb` labels the 5,881 train ready rows with a TF-IDF vector space model built in the notebook. Labels come from the model throughout; the model is a baseline, and the audit page is what settles the labels. The model agrees with the labeled set at category 0.404, urgency 0.632, state 0.537, churn 0.995. On Hazem's 4 hand labeled rows it matches 10 of 16 fields.
4. **Class weights and the corrected split.** The same preprocessing notebook computes balanced class weights with sklearn `compute_class_weight` and rebuilds the split stratified by complaint category, keeping whole duplicate text groups together with seed 42 and 0 leaked groups. The original split was not stratified by class: category shares moved up to 2.2 points in test. The corrected split holds category within 0.8 points in test and under 0.2 points in train and validation. Churn is not controlled by this split: the corrected test set holds 1 at risk row, so churn must be reported on validation and test pooled (8 at risk rows) or with cross validation, always with the count behind the rate.

Validation of the labels is in `labeling_validation.md`: 113 checks passed, 0 failed. One explained difference is recorded there, a category change on a Hazem hand labeled row caused by the approved `other` bucket relabel, not a labeling error.

## Project structure

```
dataset/
  train/  val/  test/     Audio (16 kHz mono WAV, clean names) plus one labels.csv per split
final/
  clean_training_full.csv       The clean training set, 5,751 rows, corrected split
  clean_training_train.csv      Train split, 4,031 rows
  clean_training_val.csv        Validation split, 1,136 rows
  clean_training_test.csv       Test split, 584 rows
  labeled_full.csv              The labeled train ready set, 5,881 rows
  labeled_by_model.csv          The labeling model output, 5,881 rows
  quarantine_labeled.csv        The 62 quarantined rows that were labeled and joined
  recovered_labeled.csv         The 28 recovered labeled units
  other_relabel.csv             The 796 rows reviewed in the other bucket relabel
  no_label_rows_excluded.csv    The 5 rows with no label, excluded
  low_confidence_review.csv     The 459 low confidence rows, flagged for review
  class_weights.json            Balanced class weights per field
notebooks/
  data-analysis/                EDA notebook and figures
  data-preprocessing/           Preprocessing notebook and figures
  data-labeling/                Labeling notebook and figures
labeling_validation.md          Label validation, 113 checks
rename_mapping.csv              Original file, old split and clean name, intermediate name, new split and clean name, per row
README.md                       This file
```

## Setup and run

Clone this branch (`local-env`). The notebooks run with the project virtual environment:

```
~/workspace/ai-customer-support/.venv-eda/bin/python
```

Run the notebooks in order with Jupyter or nbconvert:

```
~/workspace/ai-customer-support/.venv-eda/bin/python -m jupyter nbconvert --to notebook --execute --inplace notebooks/data-labeling/data_labeling.ipynb
~/workspace/ai-customer-support/.venv-eda/bin/python -m jupyter nbconvert --to notebook --execute --inplace notebooks/data-preprocessing/data_preprocessing.ipynb
~/workspace/ai-customer-support/.venv-eda/bin/python -m jupyter nbconvert --to notebook --execute --inplace notebooks/data-analysis/data_analysis.ipynb
```

Each notebook writes its figures to its own `figures/` folder and finishes with 0 errors. The notebooks read the working data folder at `~/workspace/ai-customer-support/dataset/prepared`; the `WS` path at the top of each notebook is the one place to change if your working folder lives elsewhere. Figures use the matplotlib object oriented API only, no pyplot.

Training reads `final/clean_training_train.csv`, `final/clean_training_val.csv`, and `final/clean_training_test.csv`, with `final/class_weights.json` for the class weights. The `customer_state` weight for `unclear` is 1150.2 from a single row; it is not usable, and that row needs a human decision before the state head trains on it.

## Team

| Area | Owners |
| --- | --- |
| Audio and speech | Hazem and Ebtihal |
| Complaint and customer | Lama and Ahmed |
| Routing and evaluation | Sira and Aya |

## Data use and rights

Rights, consent, and retention for the voicemail audio are still open and are Hazem's decision alone. Raw voice stays local and is never committed outside this repo. Do not share audio or transcripts outside the team.
