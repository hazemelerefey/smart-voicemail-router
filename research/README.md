# Research: the AI agent knowledge source

This folder is the main knowledge source for the AI agent working on the Smart Voicemail Router. Read it before training, before choosing a model, and before changing a hyperparameter.

## Read first

1. `recommendations.md`: the recommendations from the literature research, kept current. Recommended models (EgyBERT first, MARBERTv2 in parallel), speech model (XLS-R 300M, Whisper large-v3 for transcription), multi-task setup, imbalance handling, hyperparameters, training phases, metrics, and practical constraints. Start here.
2. `svr-model-selection-report.md`: the full literature research document. Part 1 is the recommendations. Part 2 is the 14 picked papers, each with an official direct link. Note: the report was written on 12 November 2026 when the clean set was 5,751 rows. The clean set was reduced to 5,096 rows on 13 November 2026 (train 3,575, validation 1,003, test 518). The numbers in the report refer to the 5,751 row set. `recommendations.md` has the current numbers.

## Supporting notes

`research/notes/` holds 46 notes from the literature research, grouped by topic:

- `models-*.md`: candidate models (EgyBERT, MARBERTv2, AraBERT, CAMeLBERT, AraModernBERT, AraRoBERTa-EGY, Jais, AceGPT, ALLaM, AraT5, XLS-R, Whisper, WavLM, HuBERT, Arabic speech) and two comparison notes (text, speech).
- `methods-*.md`: methods (class weights and resampling, focal loss, GradNorm, multi-task MT-DNN, SMOTE on text, text augmentation, threshold tuning, uncertainty weighting).
- `training-*.md`: training practice (BERT paper, RoBERTa paper, Hugging Face Trainer guide, MARBERT in Arabic, metrics for imbalanced data, training phases for multi-task, fine-tuning stability).
- `papers-*.md`: the picked papers, one note each.

Every factual claim in the recommendations traces to a note here or to a fetched source in the report.

## Rules for the agent

- The dataset numbers in `recommendations.md` are current. Do not use the report's old counts (5,751 rows, train 4,031, test 584) for training decisions.
- The text route (transcript classification) is the main route and must be built first. The audio route is an experiment.
- The transcription and the words are the main signal. The voicemails are simulated, so the audio emotion model must prove it adds signal over text alone, or it is dropped.
- Never tune on test. The test set (518 rows) is touched once, in Phase 5, after the winner is picked on validation.
- Keep this folder current. When the dataset or the recommendations change, update `recommendations.md` first, then the report.
