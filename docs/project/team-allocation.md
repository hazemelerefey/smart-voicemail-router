# Smart Voicemail Router

## Team Allocation and Delivery Plan

**Document ID:** SVR-TEAM-03  
**Version:** 1.3  
**Updated:** 12 November 2026  
**Formal project kickoff:** 11 November 2026  
**Competition deadline:** Unknown; plan uses relative, gated phases

> **Allocation rule:** Each member owns one role with real work and concrete deliverables, not a title. The dataset is finished and the model selection is settled. From here the team works in parallel phases until the system is done. Hazem reviews and merges all work.

## 1. How this allocation was chosen

The dataset is finished: the SVR Voicemail Corpus, 5,096 clean training rows, corrected stratified split, class weights, and a model selection report that picks EgyBERT and MARBERTv2 for text, wav2vec2 XLS-R 300M for audio, and Whisper large-v3 for transcription. The work that remains follows the system boundaries in SVR-ARCH-02: training, audio and speech, text classification, training infrastructure and evaluation, triage and routing, and system integration and demo. Each role owns one of those boundaries end to end. The team audits the labels in parallel, every day, while training proceeds.

## 2. Role allocation

| Member | Role | Owns | Delivers |
|---|---|---|---|
| **Hazem** | **Training Lead** | The end-to-end training pipeline and the final model. The dataset and the audit corrections. Reviews and merges all work. The retrain on audited labels. | Training notebooks, the final model, the retrained model after the audit. Branch: team/hazem-training-lead |
| **Sira** | **Audio and Speech Engineer** | The audio pipeline: STT verification, audio preprocessing, and XLS-R features. The direct audio classification model. | The audio model and the STT validation. Branch: team/sira-audio-speech |
| **Lama** | **Text Classification Engineer** | The text classifier: EgyBERT and MARBERTv2 fine-tuning, single-task first, then multi-task. The multi-task setup, one shared encoder with four heads. | The text classifier and the fine-tuning results. Branch: team/lama-text-classification |
| **Aya** | **ML Infrastructure and Evaluation Engineer** | The training infrastructure: experiment tracking, hyperparameter sweeps, reproducibility with seeds and configs. The TF-IDF baseline. The evaluation harness, the metrics, and the error analysis. | The baselines, the evaluation reports, and the error analysis. Branch: team/aya-ml-infrastructure-evaluation |
| **Ibthal** | **Triage and Routing Engineer** | The queue priority logic, how the four fields map to callback priority. The callback ticket generation, the explainable ticket. The routing agreement evaluation. | The triage logic, the ticket format, and the routing evaluation. Branch: team/ibthal-triage-routing |
| **Arafa** | **Systems Integration and Demo Engineer** | The end-to-end integration: voicemail to STT to classification to triage to ticket. The latency testing, p95 under 10 seconds. The demo and the API, and the competition deliverables. | The integrated pipeline, the demo, and the latency report. Branch: team/arafa-systems-demo |

Every member audits the labels on the live audit page every day, in parallel with their role work. The audit takes about a month. When it finishes, Hazem applies the corrections to the dataset and the team retrains.

## 3. Shared dataset: done

The dataset work is finished and verified. The SVR Voicemail Corpus holds 6,522 Egyptian Arabic customer voicemails. The clean training set holds 5,096 rows: train 3,575, validation 1,003, test 518, corrected stratified split, seed 42, whole text groups kept together. The 655 worst transcripts (Whisper logprob below -0.30) were excluded from the clean set. Class weights are computed and saved. The labeling notebook shows the model that produced the labels. The model selection report is complete and in the repository under research/ on team/hazem-training-lead.

What remains open on the data side: the team audit of the labels, and the rights, consent, retention, and processing location decisions, which Hazem decides.

## 4. Cross-role contracts

| Producer | Contract delivered | Consumer | Boundary rule |
|---|---|---|---|
| Sira | Audio evidence: local audio reference, transcript and STT confidence/language metadata, audio quality and acoustic evidence; optional voice-state candidate kept separate. | Lama; Ibthal; Arafa | Audio output does not decide complaint urgency or queue route. Raw recordings stay within the approved data boundary. |
| Lama | Structured text analysis with summary, approved complaint category, complaint urgency, customer-state-from-text, customer request, optional churn risk, review flag, and schema/label version. | Ibthal; Arafa | Enum values come only from the agreed data specification; unknown/unclear values remain reviewable. |
| Aya | Evaluation results with per-field metrics, latency, sample counts, failures, and error analysis, tied to a run ID, config, and dataset version. | Hazem; Lama; Sira; Arafa | The test set is evaluated once, after validation is frozen. No re-splitting after results exist. |
| Ibthal | Explainable triage decision with priority, assignment/unassigned status, route reason, contributing rule/config version, and evaluation result. | Arafa; team review | Decision logic consumes separate inputs; no emotion/urgency conflation and no hidden hard-filter bypass. |
| Arafa | Integrated pipeline with a reproducible local run, demo, and latency report. | Team review; competition | The demo runs cleanly under declared conditions; no unmeasured claim is presented. |

Roles can start fixture-first scaffolding, provider-adapter exploration, and isolated tests in parallel. Before production integration, agree stable field names, enum/null/unknown behavior, error states, and versioning. Interface changes require a short written decision and coordinated updates to tests and consumers.

## 5. Relative delivery phases

The competition deadline and weekly time availability are unknown, so the plan uses ordered phases and exit gates instead of calendar estimates. Once the deadline and rubric are confirmed, the team can reprioritize phases without changing their evidence requirements.

| Phase | Main work | Exit gate |
|---|---|---|
| **Phase 1: Foundations** | Hazem sets up the training pipeline. Sira builds the audio pipeline and the XLS-R baseline. Lama sets up single-task fine-tuning. Aya builds the training infrastructure, the TF-IDF baseline, and the evaluation harness. Ibthal writes the triage rules and the ticket format. Arafa builds the end-to-end pipeline skeleton and the demo skeleton. The label audit runs daily in parallel. | Each role demonstrates its inputs and outputs on fixtures; the training pipeline runs end to end on the clean training set. |
| **Phase 2: Core models** | Lama runs single-task fine-tuning for EgyBERT and MARBERTv2 in parallel, then the multi-task model. Sira tests the audio model and audio-text fusion if the data supports it. Aya runs hyperparameter tuning and validation, and picks the winner by validation mean macro-F1, with the tie-break rule from the model selection report. | Validation metrics exist for every field; the winning text model and audio model are named. |
| **Phase 3: Evaluation and integration** | Aya runs the final test evaluation once on the frozen 518-row test set, then the error analysis. Ibthal finalizes the triage logic against the real model outputs. Arafa integrates the full pipeline and measures latency. | One reproducible end-to-end run with real metrics; the demo runs cleanly under declared conditions. |
| **Phase 4: Retrain on audited labels** | After the audit finishes, Hazem applies the corrections to the dataset. The team reruns the training notebooks on the cleaned dataset. Aya re-evaluates. No architecture or hyperparameter changes. | Final dataset with corrected labels; final model retrained and re-evaluated; competition deliverables complete. |

The phases follow their exit gates rather than calendar estimates. Revisit their order at the weekly meeting and record the reason. A blocked data/privacy gate does not permit model work on unapproved material.

## 6. Weekly working cadence and repository flow

- Each member provides a weekly update and pushes validated progress to their own role branch. Smaller, reviewable pushes are welcome; no fixed weekly hour quota is assumed.
- Hold one weekly integration/decision meeting. Each member reports completed deliverables, evidence/tests, experiment changes/results, blockers, and the next dependency.
- Hazem validates pushes and merges accepted work to `develop`. `develop` is the integration line. Hazem merges the final validated result to `master` when the project is ready.
- Branches: team/hazem-training-lead, team/sira-audio-speech, team/lama-text-classification, team/aya-ml-infrastructure-evaluation, team/ibthal-triage-routing, team/arafa-systems-demo. The old pair branches team/audio-speech, team/complaint-analysis, and team/routing-evaluation are deleted.
- Keep merge decisions traceable: each accepted change should state its purpose, tests/evaluation run, and any contract or dataset impact.

### Operating environments

The team has mixed local CPU/GPU computers. Keep a declared CPU-compatible core test and local run path as the reproducible baseline; GPU acceleration is optional and model-dependent. Free cloud plans and Google Colab are optional, not guaranteed or required. Record machine/provider/runtime for each benchmark, and obey the same data permissions in Colab as on local machines. Separate CPU/GPU dependency folders and environment READMEs are part of the repository setup, not this document phase. Training on the VM has no GPU; training runs on team machines, GPU strongly recommended.

## 7. AI-agent work and experiment discipline

AI agents can help with implementation and analysis. Each member owns correctness and review. Add these rules to the agent instructions during the repository setup phase.

### Safe, reviewable implementation

- Give an agent a bounded task, the current schema/version, expected inputs/outputs, tests, and files it may change. If a label, provider permission, or policy is unknown, the agent must stop and surface the decision rather than invent it.
- Never provide secrets, unapproved recordings, or identifying data to an agent or external tool. Use synthetic fixtures for routine development.
- Require a human review of diffs and test/evaluation evidence before accepting generated code. A successful test does not by itself prove that the test matches the product requirement.
- Keep changes cohesive and testable. "One variable at a time" governs **experimental ablations**; code changes may touch several variables or lines.

### Controlled experiments for the ablation study

For a comparison intended to measure causal impact, change one experimental factor at a time (for example, STT provider, normalization setting, or one fusion weight), while holding the dataset snapshot/split, prompt, other config, and evaluation procedure constant as far as possible. Record:

| Required experiment record | What to capture |
|---|---|
| Run ID and hypothesis | Why the change is being tested and what result would support it. |
| Single changed factor | Exact old/new value or provider/model version. |
| Held-constant conditions | Dataset checksum/version and split, other configuration, prompt/schema version, seed where applicable, and runtime environment. |
| Measures | Per-field metrics, latency, sample counts, failures, and relevant qualitative review. |
| Artifacts | Commit/branch reference, config, command, output path, and limitations. |

Do not infer a winning change from a different dataset split or simultaneous changes to several factors. After isolated comparisons, interactions can be studied as separately labeled experiments.

## 8. Success criteria

Treat these values from the v1.0 PRD/allocation as hypotheses until the first baseline confirms them. The old 0.75 "severity" metric is not yet mapped to complaint urgency or customer state; the team must agree which field and metric it measures.

- Complaint-category macro-F1: 0.85 initial hypothesis.
- Old severity macro-F1: 0.75 legacy hypothesis; do not relabel it as complaint-urgency performance. The taxonomy is agreed, but the severity mapping to a field and metric is still open.
- Routing agreement with a documented human-reviewed ideal agent: 80% initial hypothesis.
- End-to-end latency: p95 under 10 seconds for clips up to 60 seconds, measured separately by CPU, GPU, or an approved provider configuration.
- Summary coverage: at least 95% of evaluable test clips; manually review faithfulness on 20 clips where available, and report the actual review count if fewer are available.
- Demo reliability: aim for five consecutive clean runs when the final demo flow is stable and the competition format permits.

Always report dataset size, label counts, split policy, model/config, hardware/provider, actual numbers, and limitations. If the data cannot support a metric, state that plainly rather than claiming success.

## 9. Current open decisions

- Dataset rights, consent, retention period, and processing locations. The repository is public by Hazem's decision, so the voicemails are openly reachable.
- Split freeze: the corrected v2 split (train 3,575, validation 1,003, test 518) is the working split; freezing it is Hazem's decision.
- External API/provider permissions and any quota/budget.
- Exact local CPU/GPU hardware and which experiments, if any, use Colab.
- Competition judging criteria, demo format, and deadline.
- Final dashboard language.
