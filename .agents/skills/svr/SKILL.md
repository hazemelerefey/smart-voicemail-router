---
name: svr
description: Work on the Smart Voicemail Router project. Notebook-first, train/validation/test, research folder as knowledge source, no em dashes.
---

# Smart Voicemail Router (SVR)

Private competition prototype, unrelated to VO for Technology. Never call it VO anywhere. Single-speaker Egyptian Arabic voicemail becomes an explainable callback ticket. Repo: `hazemelerefey/smart-voicemail-router`, ready branch `smart-voicemail-router` is the clone source.

## Read first

- `research/README.md` and `research/recommendations.md`: the main AI agent knowledge source. Read recommendations first for current numbers and current model choices.
- `research/svr-model-selection-report.md`: the full literature research, 14 picked papers.
- `docs/project/roles-and-workflow.md`: the six roles, the four phases, the waiting points, the working rules.
- `MEMBER.md` at the repo root: the member name and role for this checkout. Work in that role only.

## Dataset (current)

SVR Voicemail Corpus. 6,522 voicemails, 12.6 hours, 16 kHz mono WAV. 6,024 Whisper large-v3 transcripts. Clean training set 5,096 rows: train 3,575, validation 1,003, test 518, stratified, split seed 42. Clean tables and audio folders are in `final/` and `dataset/` on this branch. Audio files are named by emotion and number (for example calm_0001.wav); the numbering has gaps because the split and the exclusions removed numbers, which is normal and not an error.

Labels per row: complaint_category (11 classes), complaint_urgency (high, medium, low), customer_state (calm, frustrated, mad, satisfied, unclear), churn_risk (at_risk, not_at_risk). Churn at_risk is 0.56 percent, 20 rows in train. Labels are presented as coming from a deep/machine learning model, never from AZZAR or an agent.

Data note: the voicemails are simulated, recorded by people for data collection, not by real customers, and the emotions are acted. The transcription and the words are the main signal. The audio emotion model is an experiment and must prove it adds signal over text alone, or it is dropped.

## Model recommendations (from the research)

Text: EgyBERT first (https://huggingface.co/faisalq/EgyBERT), MARBERTv2 in parallel (https://huggingface.co/UBC-NLP/MARBERTv2). Winner by validation macro-F1. Tie-break: if within one standard deviation on validation mean macro-F1, pick MARBERTv2. Speech: wav2vec2 XLS-R 300M for direct audio classification, Whisper large-v3 stays for transcription, do not fine-tune the full 1.55B Whisper model. Baseline to beat (TF-IDF validation macro-F1): category 0.7261, urgency 0.6789, state 0.5561, churn 0.8840, mean 0.7113.

Hyperparameters: learning rate 2e-5 (sweep 1e-5, 2e-5, 3e-5), effective batch 16, epochs 3 max 5 with early stopping patience 2, warmup 0.1, weight decay 0.01, max sequence length 128, AdamW, 5 seeds (42, 1337, 2023, 7, 99), report mean plus std. Class weights in the loss (churn at_risk 91.0, capped at 10 to 20), plus per-class threshold tuning on validation for the churn head. Multi-task: one shared encoder, four heads, Kendall uncertainty weighting.

## Working rules (do not break these)

1. Notebook-first. All project work lives in Jupyter notebooks until the full project is finalized, only then convert to .py. Notebooks must be executed, outputs saved. Style: professional, organized, simple, effective, fewest cells, shared helpers in one early setup cell, short contents list at top, plain words. Notebooks are written as a data analyst doing the work, present tense, first person. They must NOT read as an agent explaining to the team, NOT say they were made because anyone asked, and must NOT mention AZZAR anywhere.
2. Split names are train, validation, test. Never use "dev".
3. Train on train, evaluate on validation, final check once on test. Never tune on test. Test is touched once, in Phase 5, after the winner is picked.
4. Never write em dashes or en dashes anywhere: not in chat, not in notes, not in code, not in notebooks. Use commas or plain hyphens.
5. Preprocessing does NOT balance the dataset. Class weights are applied at training time in the loss.
6. Raw voice stays local by default. Never force-add private recordings or transcripts. The repo .gitignore excludes data, dataset, csv, audio, transcripts, model artifacts, secrets.
7. Push each finished piece as soon as it is done and verified, never batch for one final push.
8. Never claim work done or verified without live proof measured against the problem as stated. Verify from real output.
9. Arabic content: human, professional Egyptian tone, not stiff formal MSA. Main English technical terms stay in English (train, validation, test, seed, labels, hyperparameters, architecture, text classifier, classification, batch, heads, fine-tuning, encoder, checkpoint, fusion, features, split, run record, model). Wrap English terms mixed in an Arabic line in bidi isolates (U+2066 + text + U+2069).
10. The audit page is https://svr-data-annotation.vercel.app. Firebase Realtime Database is the only source of truth. A save counts only on server acknowledgment. Never write directly to Firebase from a notebook or a script; the page writes through the server API only.

## Roles

Hazem is Training Lead (training pipeline, dataset, final model, reviews and merges everything). Sira is Audio and Speech. Lama is Text Classification. Aya is ML Infrastructure and Evaluation. Ibthal is Triage and Routing. Arafa is Systems Integration and Demo. Work in the role named in MEMBER.md only.

## When in doubt

Ask Hazem. He decides the category count, the split freeze, and rights/consent. He is the only reviewer.
