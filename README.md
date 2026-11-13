# Smart Voicemail Router

A local-first competition prototype that turns a single-speaker Egyptian Arabic voicemail, including English telecom terms, into an explainable callback ticket.

> **Project status:** the dataset is finished: the SVR Voicemail Corpus, 6,522 Egyptian Arabic customer voicemails, with 5,751 clean training rows. The taxonomy is approved and the model selection is settled (EgyBERT and MARBERTv2 for text, wav2vec2 XLS-R 300M for audio, Whisper large-v3 for transcription). The labels are being audited by the team. The category count is still to be confirmed by Hazem (9 in the model report, 10 approved, 11 in the audit app, 12 in the dataset tables); see Open decisions. This branch, `team/arafa-systems-demo`, carries the Role 6 Phase 1 pipeline skeleton with mocks, API, and demo: 86 tests passing, verified live. Project documents and environment guidance live on `master`.

## What it does

A voicemail comes in, and the pipeline produces a transcript, a callback brief, separate complaint and customer context fields, an explainable queue decision, and an agent-routing reason. Audio-derived customer-state evidence is conditional on validation. The prototype is not a production telecom system and does not make automatic callbacks.

Pipeline, in order:

```text
voicemail
  -> intake (validate WAV / MP3 / M4A, 25 MB, 60 s max)
  -> STT (mock in Phase 1; Whisper large-v3 in Phase 2)
  -> text classification (mock in Phase 1; EgyBERT / MARBERTv2 in Phase 2)
  -> voice evidence (skipped in Phase 1; wav2vec2 XLS-R 300M in Phase 2)
  -> triage and routing (mock in Phase 1)
  -> ticket
```

Latency target: p95 under 10 seconds for clips up to 60 seconds, measured separately by CPU, GPU, or approved provider configuration, with hardware recorded.

The core fields are deliberately distinct:

- **Complaint category** describes the kind of issue. 10 values are approved.
- **Complaint urgency** describes how time-sensitive or impact-heavy the issue is. High, medium, low.
- **Customer state** describes the customer's interaction state under definitions agreed by the team. Calm, frustrated, mad, satisfied, unclear.
- **Churn risk** is a separate flag, set only on explicit leave-the-provider words.
- **Queue priority** is a separate system decision based on approved signals. Its weights are not fixed until the team agrees the policy.

Unclear or unsupported outputs stay reviewable rather than being guessed. A null label is a correct output; a guessed label is a defect.

## Data boundary

The design keeps raw voice local by default. A transcript approval does not authorize audio transfer. Any permitted external text experiment requires prior, durable approval for the exact provider, purpose, and payload, with local identifier masking first. Dataset source, rights, consent, retention, and allowed processing locations still need to be confirmed before any data is used.

No recordings or transcripts are committed on this branch. The `.gitignore` excludes dataset directories at any depth and common dataset export formats by default. Ignore rules are a safeguard, not permission to use or share data. Never force-add private recordings or transcripts. Only reviewed, approved derived summaries may be considered for a later commit, after the team confirms that the specific content and processing are permitted.

## Repository structure, this branch

```text
.
├── .gitignore
├── README.md
├── GATES.md
├── docs/
│   └── superpowers/plans/        # 2026-11-10 plans: dataset preparation, EDA, preprocessing
├── eda/                          # Audio and speech EDA, summary, figures, tests
├── notebooks/
│   ├── data-analysis/
│   ├── data-labeling/
│   └── data-preprocessing/
├── preparation/                  # Taxonomy, Label Studio config, labeling, readiness
├── preprocessing/                # Audio standardization, transcript cleaning, splits
├── research/
│   └── svr-model-selection-report.md   # EgyBERT + MARBERTv2, XLS-R 300M, 14 papers
├── src/
│   └── svr/                     # Role 6 Phase 1 pipeline skeleton, API, demo
└── tests/                        # API, pipeline, schema, and store tests (86 passing)
```

Project documents (PRD, architecture, team allocation, roles guide) and environment setup (CPU, GPU, Colab) live on [`master`](https://github.com/hazemelerefey/smart-voicemail-router/tree/master). The dataset and model work live on the `local-env` and team role branches.

## Role 6, this branch

Owner: Ahmed Gamal Arfa ([@AhmdArFa](https://github.com/AhmdArFa)), Systems Integration and Demo Engineer.

`src/svr/` is the end-to-end pipeline skeleton with mocks, built on SVR Contracts v1.0 (`schema_version: 1`, `label_version: "taxonomy-2026-11-11"`). Full detail, including what is mock vs real, the API, and the open decisions, is in [`src/svr/README.md`](src/svr/README.md).

Quick start, Python 3.11 or newer (developed on 3.12.3), from the repo root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r src/svr/requirements.txt
bash src/svr/run_api.sh        # API at http://127.0.0.1:8000, HTML demo at /
bash src/svr/run_demo.sh       # Gradio demo at http://127.0.0.1:7860
.venv/bin/python -m pytest tests/ -q   # 86 tests
```

Phase 1 persists no audio: uploads are validated and measured, then the bytes are discarded, and the pipeline runs on metadata only. Phase 2 swaps the mocks for real components as they land (Sira audio pipeline, Lama text model, Ibthal ticket generator), one at a time, each tested in isolation. Phase 3 integrates everything, measures p95 latency, and runs the demo five consecutive times cleanly.

## Team

Six individual roles, Team Allocation v1.3, approved by Hazem, 12 November 2026. Kickoff 11 November 2026.

| Member | Role | Branch |
|---|---|---|
| Hazem Elerefy | Training Lead | `team/hazem-training-lead` |
| Sira (Esraa Al-azzawy) | Audio and Speech | `team/sira-audio-speech` |
| Lama Hisham | Text Classification | `team/lama-text-classification` |
| Aya | ML Infrastructure and Evaluation | `team/aya-ml-infrastructure-evaluation` |
| Ibthal Ahmed | Triage and Routing | `team/ibthal-triage-routing` |
| Ahmed Gamal Arfa | Systems Integration and Demo | `team/arafa-systems-demo` |

Work happens on the role branches. Accepted work is integrated by the Training Lead. Competition deadline is not yet announced.

## Dataset

SVR Voicemail Corpus: 6,522 voicemails, 12.6 hours, 6,024 transcripts (Whisper large-v3, WER 0.29 vs turbo 0.35 on a 20-row eval). Clean training rows: 5,751, split train 4,031, validation 1,136, test 584, stratified, seed 42, whole duplicate-text groups kept together. Labels come from a TF-IDF model and are being audited by the team in the shared audit app; agreement on the current labels is category 0.404, urgency 0.632, state 0.537, churn 0.995.

Key sources on this branch: [`research/svr-model-selection-report.md`](research/svr-model-selection-report.md), [`preparation/taxonomy_proposal.md`](preparation/taxonomy_proposal.md), [`preparation/labeling_config.xml`](preparation/labeling_config.xml), [`eda/eda_summary.json`](eda/eda_summary.json), [`preprocessing/preprocessing_summary.json`](preprocessing/preprocessing_summary.json).

## Open decisions, do not guess

- **Complaint category count.** Approved taxonomy lists 10 values. The model selection report says 9. The audit app offers 11, including `offers_and_packages`. The dataset tables use 12, adding `sim_services`. Hazem to confirm the approved list. Until then, outputs using the two extra labels land in `needs_review`.
- **Priority formula, ranges, thresholds, weights.** Undefined. Owner Ibthal, Hazem approves.
- **`language_mix` values.** Undefined. Producers send null.
- **Skill-to-category mapping and tier policy.** Undefined.
- **Fusion rules for customer state.** Undefined. The field stays null until agreed.
- **Dataset rights, consent, retention, processing locations.** Hazem.
- **Competition deadline, judging criteria, demo format.** Hazem.
