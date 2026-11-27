# Changelog

## [1.0.0] - 2026-11-27

First tagged release. This is the competition build as it stands: a self-hosted voicemail triage and callback operations pipeline for Egyptian Arabic and code-switched subscriber voicemail.

### Pipeline

- Whisper large-v3 transcription, with an Egyptian fine-tuned CT2 variant for the 6GB GPU profile and a Cohere Arabic ASR INT8 path.
- VoiceGate: a LangGraph gate on Qwen2.5-3B that verifies and repairs transcripts and escalates the uncertain ones.
- Four fine-tuned MARBERTv2 classifiers for complaint category (11 classes), urgency (3), customer state (4 scored) and churn risk (2), with an ONNX INT8 CPU backend.
- Deterministic priority score and routing by skill and live capacity.

### Results

- Combined macro-F1 0.7941 against 0.7113 for the TF-IDF baseline, on the seed_99 validation run (1,003 rows).
- Skill routing agreement 89.33% (896 of 1,003 rows).
- Review rate 8.37%.
- Five-seed mean on the independent fair re-run: 0.7907 combined macro-F1, see docs/MODEL-CARD.md for the per-field breakdown.
- Corpus: 6,522 consented voicemail clips, 12.63 hours, stratified 70/20/10 split.

### Product

- Bilingual console with full RTL, role-based access, audio encrypted at rest with Fernet, an immutable audit log and live updates.
- Separate dataset audit tool for reviewing labels before training (not part of the product).
- One-command Docker deploy on CPU or GPU, including an RTX 3050 6GB profile.
- Prometheus and Grafana observability.

### Documentation

- docs/ARCHITECTURE-AND-DEPLOYMENT.md
- docs/MODEL-CARD.md
- docs/DPIA.md
- docs/BUILD-VERIFICATION.md
- CONTRIBUTING.md and AGENTS.md
