SVR local env (clean training data, ready to work)

This branch holds the ready local env after data preparation: the dataset
folder and the notebooks folder, organized so the team can clone it as is
and work directly. No .py scripts (those are dead scripts, not shipped).

Contents
- dataset/labeled/ : train, val, test splits (70/20/10). Each split has the
  audio samples (16 kHz mono WAV, named <customer_state>_<original>.wav) and
  a labels.csv with complaint_category, complaint_urgency, customer_state,
  churn_risk, note, confidence. Total 5,751 rows.
- dataset/prepared/ : the final clean training CSVs (clean_training_full_v1.csv
  and the train/val/test splits), the summary JSON, and the decision files
  (other_relabel, quarantine decisions, recovered transcripts and labels,
  garbled rows excluded, re-transcription experiment).
- dataset/preprocessed/ : transcripts_clean.csv and the split JSONs.
- dataset/screenshots/ : screenshots of the dataset paths and counts.
- notebooks/ : data-analysis, data-preprocessing, data-labeling, each executed
  with 0 errors, with chart figures.

Final counts: 5,751 rows (train 4,023, val 1,158, test 570).
Sources: train ready 5,662, quarantined 62, recovered 27.
Rights, consent, and retention are still open and are Hazem's decision alone.
