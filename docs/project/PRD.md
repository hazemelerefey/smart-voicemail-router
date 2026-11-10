# Smart Voicemail Router

## Product Requirements Document

**Document ID:** SVR-PRD-01  
**Version:** 1.2  
**Status:** Draft for team review, with dataset taxonomy and evaluation protocol pending EDA  
**Updated:** 10 November 2026  
**Formal project kickoff:** 11 November 2026  
**Competition deadline:** Not yet known

> **Project purpose:** Prove, with permitted data and measured results, that a voicemail can become an understandable, explainable callback ticket. The deliverable is a competition prototype; production telecom features are out of scope.

### Revision notes

Version 1.2 sets a local-first privacy boundary, separates complaint urgency from customer state, and leaves label values pending shared EDA and team agreement. The Team Allocation Plan uses relative, gated phases because the competition deadline and weekly capacity are unknown.

---

## 1. Executive summary

Customer-care teams often handle voicemail in arrival order. A time-sensitive service failure can wait behind a routine question, while the agent who eventually calls back must listen to the whole message before understanding the issue.

Smart Voicemail Router accepts a single-speaker voicemail in Egyptian Arabic, including English telecom terms. It produces a transcript and a concise callback brief, identifies **what the complaint is about**, estimates **how urgent the complaint is**, and separately records **the customer's state**. Where the data and a validated model support it, voice cues may contribute evidence about customer state; they are not treated as ground truth. The system then produces an explainable queue priority and routes the ticket to an available agent whose approved skills fit the complaint.

## 2. Problem and intended outcome

The prototype addresses four problems:

- Arrival-order queues can hide time-sensitive complaints.
- Voicemail is unstructured, so agents spend time discovering the issue before they can help.
- Text alone can miss tone, while voice-only emotion estimates can be unreliable; the system should show separate evidence rather than collapse these into one unexplained label.
- A callback can start cold if the agent has no summary, customer request, or routing rationale.

The supervisor reviews the source transcript, separate model outputs, decision logic, assigned agent, and any human-review flag. When no agent qualifies, the ticket gives the reason.

## 3. Core concepts and boundaries

These are different product fields and must not be used as synonyms:

| Field | Meaning | How it affects the system | Status of labels |
|---|---|---|---|
| **Complaint category** | The type of problem being reported (for example, a network or billing issue). | Helps identify which agent skills are relevant. | Candidate values exist in v1.0, but final values require EDA and team agreement. |
| **Complaint urgency** | How time-sensitive or impact-heavy the complaint itself is. | Can affect queue priority and escalation rules. It is not a mood. | Class set and annotation rules are pending the dataset review. |
| **Customer state** | The customer's interaction/emotional state (for example, calm, dissatisfied, or angry, if supported by the data). | Gives the callback agent context. Text and validated voice cues may provide separate evidence. | Class set is pending the dataset review; no final labels are approved yet. |
| **Churn risk** | Evidence that the customer may leave the service, if this dimension proves useful and can be labeled consistently. | May be a separate business-risk signal. A cancellation threat is evidence to assess, not an automatic urgency label. | Retain only after EDA and team agreement. |
| **Queue priority** | A system-generated ordering score or bucket combining approved operational signals and waiting time. | Sorts the queue; it is not itself complaint urgency or customer state. | Formula and weights are provisional until labels and policy are agreed. |

The label values must come from the shared dataset review and annotation policy. Until then, model implementations must not invent or silently freeze classes. Ambiguous or unsupported results must be marked for human review.

## 4. Goals and non-goals

### Competition MVP goals

1. Convert one valid voicemail into a structured ticket with an explainable result.
2. Return separate complaint category, complaint urgency, and customer-state fields, with an agreed label set and evidence for each.
3. Use audio evidence only as a qualified signal; show uncertainty and allow human review.
4. Recommend a suitable, available agent using agreed skills and capacity rules, with a plain-language routing reason.
5. Give the agent a concise, faithful summary, the customer's request, and a suggested opening line that does not invent facts.
6. Evaluate the system on a documented, permitted dataset and report actual results and limitations.
7. Prefer local processing and storage for voice data. Use external providers only when competition rules, data rights, privacy constraints, and the team explicitly permit that use.

### Explicit non-goals for this competition prototype

- Real telephony, SIP, CRM, SMTP, or production voicemail ingestion.
- Automatic callbacks or other customer-facing actions.
- A production-grade security, compliance, availability, or multi-tenant claim.
- Authentication, authorization, and multi-role access control; use a single demo-user mode.
- Building or fine-tuning a speech model from scratch as a default plan.
- On-premises delivery is a future commercial direction after the prototype demonstrates value; it requires a separate implementation and security review.
- Finalized label values before the dataset has been inspected and the team has agreed on annotation rules.

## 5. Users

| User | Need | Prototype support |
|---|---|---|
| Callback agent | Understand the issue and how to start the callback. | Summary, customer request, transcript, separate urgency/state fields, suggested opening, and audio access where permitted. |
| Supervisor / queue manager | See what needs attention and why. | Prioritized queue, assigned agent, route reason, review flag, and manual correction/reassignment capability if time allows. |
| Competition judge | Understand the product and judge whether it works. | Live walkthrough, transparent decision evidence, and measured results with dataset size and limitations. |
| Future telecom IT/security stakeholder | Understand the commercial path without mistaking the prototype for a production system. | Clear provider boundaries, data-handling assumptions, and a separately scoped future on-premises direction. |

## 6. Scope

### Required for the demonstrable core

- Accept WAV, MP3, and M4A files up to 25 MB and up to 60 seconds; recommend 15 to 60 second clips for the MVP. Do not reject a shorter valid clip solely for being under 15 seconds unless the dataset review establishes a minimum.
- Keep original voice recordings within the approved local data boundary by default. Preprocess a working copy for analysis.
- Produce a transcript and language-mix indication; normalize telecom terms only under a documented glossary.
- Produce a structured text analysis with separate complaint category, complaint urgency, and customer-state fields. Final label values are gated on EDA.
- Compute and expose audio quality/acoustic evidence. A voice-state/emotion label is included only if the team validates the model and annotation approach for the available data.
- Fuse approved signals into a transparent priority and routing recommendation; record the inputs and reason.
- Store tickets, seeded demo agents, assignments, and audit events locally for the prototype.
- Provide a dashboard for upload and browser-based live recording, live queue, ticket details, evidence, and callback brief. Hazem will name the UI implementer(s) after the first integrated fixture run and before demo-readiness. His implementation role remains open.
- Provide a reproducible evaluation path and report actual results.

### Lower-priority or deferred

- WebSocket updates, manual reassignment, analytics, and production packaging may be sequenced after the core data contract and end-to-end pipeline are stable.
- External cloud inference, if used at all, is an opt-in experiment under the privacy gate below, not the default path.
- Hazem will name the deployment/packaging implementer(s) after the first integrated fixture run and before demo-readiness. No pair is pre-assigned solely to this work, and Hazem's implementation role remains open.

## 7. User stories and acceptance criteria

| ID | User story | Acceptance evidence |
|---|---|---|
| US-1 | As a supervisor, I upload or record a voicemail so it becomes a ticket. | Upload and browser recording are supported; invalid format/size/duration produces a clear error; a valid submission appears in the queue as `processing` within 2 seconds. |
| US-2 | As an agent, I understand the problem without first replaying the entire message. | A faithful summary is present for at least 95% of evaluable test clips; manually review faithfulness on 20 clips where available, otherwise report the actual review count. The ticket also contains the customer request, transcript, and human-review status. |
| US-3 | As a supervisor, I can distinguish the complaint from the customer's state. | Complaint category, complaint urgency, and customer state appear as separate fields. Their labels and annotation rules match the team-approved data specification. |
| US-4 | As a supervisor, I can see why the ticket has its queue position. | The system displays the approved contributing signals, a readable reason, and the priority result; no unexplained score is shown. |
| US-5 | As a supervisor, I can see why a ticket was assigned to an agent. | The route reason identifies relevant skill/category, availability/capacity, and any approved escalation factor. If no eligible agent exists, the ticket stays unassigned and requests review. |
| US-6 | As an agent, I receive a useful opening line. | The suggestion is polite, refers only to facts in the ticket, and is not sent to the customer automatically. |
| US-7 | As a judge, I can inspect the decision. | The ticket view shows transcript, separate text and voice evidence, fused outputs where validated, routing rationale, and uncertainty/review flags. |
| US-8 | As a team, we can measure what changed. | Evaluation runs record dataset version/split, model/provider/config, per-stage latency, metrics, and result artifacts. |
| US-9 | As a project team, we protect recordings. | Raw voice is not sent to third-party AI by default; data permissions and any approved external processing are documented. |

## 8. Analysis contract

Pairs may start independent EDA, fixture-first scaffolding, provider adapters, and unit tests before the final contract is frozen. Agree stable field names and null/error behavior before production integration. The following is a **shape proposal**, not a final class taxonomy. Placeholder labels must be replaced by the approved enum values after EDA; they must not be passed to production code as free-form predictions.

```json
{
  "summary": "Customer reports a service problem and requests a callback.",
  "complaint_category": "<approved_category_label>",
  "complaint_urgency": "<approved_urgency_label>",
  "customer_state_text": "<approved_customer_state_label>",
  "churn_risk": "<approved_label_or_omitted_after_EDA>",
  "keywords": [],
  "customer_request": "<faithful, concise request>",
  "language_mix": "<approved_language_mix_value>",
  "suggested_script": "<polite, grounded opening line>",
  "confidence": 0.0,
  "needs_human_review": false
}
```

Audio analysis is a separate result, not an LLM text label. It may contain preprocessing quality, acoustic features, a candidate voice-state label and confidence. The fusion/decision layer combines only fields the team has validated. Preserve the distinction between `customer_state_text`, voice evidence, and any later fused customer-state result.

The system-level ticket additionally carries `priority_score` (or an agreed alternative), `route_reason`, assignment status, per-stage status/timing, and audit events. Those fields are not necessarily part of the LLM response.

## 9. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | Validate WAV/MP3/M4A inputs; enforce the 25 MB limit and 60-second maximum; recommend 15 to 60 second clips but do not reject shorter valid clips without a data-backed minimum; return clear errors. | P0 |
| FR-02 | Create a local working audio copy with the agreed sample rate/channel and documented trimming/normalization; retain the original only according to the approved retention rule. | P0 |
| FR-03 | Transcribe Egyptian Arabic with English telecom terms and report language-mix/uncertainty where supported. | P0 |
| FR-04 | Apply an agreed Arabic/English telecom glossary and local identifier masking before any permitted external text-model call. | P0 |
| FR-05 | Validate structured text output against a versioned schema; reject unsupported labels; send ambiguous results to human review. | P0 |
| FR-06 | Extract audio quality/acoustic features. Add a voice-state estimate only after model/data validation; display its confidence and limitations. | P0 for features; conditional for voice-state label |
| FR-07 | Keep complaint category, complaint urgency, and customer state independent through storage, UI, and evaluation. | P0 |
| FR-08 | Calculate an explainable queue priority using only approved signals. Formula, ranges, thresholds, and weights are frozen only after data and policy review. | P0 |
| FR-09 | Recommend an eligible agent by approved skill/category, shift/availability, capacity, and language fit; define unassigned/manual-review behavior. | P0 |
| FR-10 | Persist local prototype records for voicemails, tickets, agents, assignments, processing status, and audit events. | P0 |
| FR-11 | Provide REST endpoints for upload/recording submission and ticket review; provide a WebSocket stream for live queue/status updates. | P0 |
| FR-12 | Provide a dashboard for upload and browser-based live recording, queue, ticket evidence, playback where permitted, routing, and callback brief. Hazem names the UI implementer(s) after the first integrated fixture run and before demo-readiness; his own implementation role remains open. | P0 |
| FR-13 | Store per-stage timing and errors for evaluation and debugging. | P1 |
| FR-14 | Support manual reassignment/status change if time and demo needs permit; write audit events. | P1 |
| FR-15 | Define provider interfaces; do not claim that a config switch alone delivers an on-premises system. | P1 |
| FR-16 | Provide an evaluation command/path for transcription, each approved classification task, routing, and latency. | P1 |
| FR-17 | Permit cached results only for exact, preapproved demo clips, clearly marked as cached; never substitute another clip's result. | P1 |
| FR-18 | Support Arabic right-to-left transcript display where present. | P1 |
| FR-19 | Add an analytics page only after core ticket flow and evaluation are stable. | P2 |
| FR-20 | Before any external text call, require a durable approval record tied to purpose, basis/scope, approver/time, provider/model, exact payload reference/class, retention terms, and transfer ID; block calls without an exact valid match. This record does not authorize raw-audio transfer. | P0 if external text processing is enabled |
|
## 10. Non-functional requirements and privacy

### Performance

The inherited target is **under 10 seconds at p95 for a clip up to 60 seconds**. Treat it as a hypothesis, not a promise. Measure and report the exact machine, provider/model, data path, and clip set. Benchmark CPU, GPU, and any permitted external provider separately; do not claim comparable results without controlling the conditions.

### Accuracy and explainability

Initial reference targets from v1.0 remain hypotheses only: category macro-F1 0.85, the old severity macro-F1 0.75 (not yet mapped to complaint urgency or customer state), routing agreement with a human-reviewed ideal agent 80%, and p95 latency under 10 seconds for a 60-second clip. Reconfirm or replace each target after EDA, taxonomy agreement, and the first baseline. For summaries, retain the source target of at least 95% coverage on evaluable clips and manually review 20 clips where available; if fewer are available, report the actual count and limitation. Aim for five consecutive clean demo runs once the demo flow is stable. Report class counts, split size, confidence/limitations, and actual results even when below target.

Every priority and routing decision must show the signals used and a readable reason. Voice-state inference is uncertain evidence, not a diagnosis. A missing eligible agent, low confidence, unclear audio, or unsupported label must result in an explicit review state, not a fabricated answer.

### Privacy and data handling

- Use only data whose collection, license, consent, and competition rules permit the planned use. Prefer synthetic or explicitly consented recordings for demos.
- Keep raw voice local by default. A voice recording can identify a person and may reveal sensitive information; masking names in a transcript does **not** anonymize the voice recording.
- Local processing/storage is the recommended default for this prototype where practical. De-identification helps reduce exposure but does not make external processing equivalent to local/on-premises processing.
- Do not send raw voice to a third-party AI service by default. Any external audio processing requires an explicit project decision after reviewing competition rules, dataset rights, provider retention/terms, and the data subjects' permissions; record it as a limitation in results.
- If an approved external text model is used, mask direct identifiers locally first, minimize the payload, and record a durable pre-transfer approval tied to the exact payload/provider/purpose; the adapter must reject a missing or mismatched approval. This text-transfer approval does not authorize raw-audio transfer. Keep API keys in environment variables. Never put secrets or recordings in code, logs, public notebooks, or agent prompts.
- Store originals and transcripts only as long as the team needs for the approved experiment. The exact retention/deletion period is an open decision and must be documented before dataset ingestion.
- Do not claim production-grade security, compliance certification, or enterprise readiness.

### Portability and quality

Keep business logic separate from provider implementations. Preserve CPU execution for core tests; make GPU acceleration optional and model-dependent. Pin dependencies and environment notes in the later repository phase. Use type hints, unit tests for schema/fusion/routing, prompts as versioned files, and reproducible evaluation records.

## 11. Dataset and evaluation plan

The v1.0 estimate was 50 to 100 telecom-style recordings. The dataset and access method are not yet known; it may be unlabeled, and some proposed classes may not exist.

Before finalizing labels or model comparisons, **each of the three pairs** will independently inspect the same authorized dataset snapshot and prepare an EDA note. At the earliest weekly comparison meeting, the team will reconcile findings and agree one shared data dictionary, label/annotation guide, privacy boundary, and split protocol.

EDA must cover, at minimum: license/consent and data origin; file count, duration, format, and quality; language mix; missingness and duplicates; existing labels and class counts; label ambiguity; potential speaker/recording leakage; PII and retention risks; and a proposed train/dev/test strategy. The test set should be separated by speaker/source where feasible so near-duplicate or same-speaker material does not inflate results.

Report only metrics appropriate to the agreed labels and reference data:

- WER on clips with human-verified reference transcripts, with Egyptian Arabic and mixed Arabic/English results separated where sample size allows.
- Per-field precision/recall/F1 and confusion matrices for approved complaint category, urgency, and customer-state tasks. Mark small or absent classes; do not hide imbalance behind accuracy alone.
- Routing agreement against a documented, human-reviewed target assignment.
- p50/p95 end-to-end and per-stage latency by runtime configuration.
- Qualitative review of summaries/openers, uncertainty handling, and cases where voice evidence changes a decision, only where labels and evidence support the claim.

## 12. Assumptions and dependencies

- The competition prototype receives a single customer speaker, not a live multi-party call; diarization is out of scope.
- Official project kickoff is 11 November 2026. The competition deadline and weekly time capacity are unknown, so the plan uses relative phases and exit gates rather than invented dates or durations.
- Team pairs are Hazem & Ibthal, Lama & Ahmed, and Sira & Aya. Workstream proposals are in the Team Allocation Plan; they are based on architecture boundaries, not on unprovided skill profiles.
- Team members have a mix of CPU/GPU computers; free cloud plans and Colab may be available but are optional. Do not make them a required dependency.
- External API use and dataset rights still require confirmation against competition rules and actual dataset terms.
- On-premises delivery is a possible future commercial direction after validation, not a current product promise.

## 13. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Dataset is inaccessible, unlicensed, unconsented, or too small | Blocks valid model evaluation and may create privacy risk. | Verify rights/access before ingestion; use permitted/synthetic alternatives; keep a clear limitation log. |
| Labels are missing or inconsistent | Invalid metrics and unstable model contract. | Three independent EDA passes on one snapshot; compare at the earliest meeting; approve one annotation guide before training/evaluation. |
| Complaint urgency is confused with customer emotion | Wrong queue decisions and misleading demo. | Keep independent fields in schema, code, UI, routing, and evaluation; test the distinction. |
| Voice model fails on Egyptian Arabic or phone-quality audio | Misleading state inference. | Treat voice as optional evidence, validate on relevant data, expose uncertainty, and fall back to human review. |
| Cloud provider receives identifiable voice/data | Privacy, consent, or competition-policy issue. | No raw audio to external services by default; require a documented approval gate; prefer local processing. |
| Provider outage or rate limits | Demo failure. | Local path and exact-clip cached demo fallback; pre-recorded backup; do not cache arbitrary inputs. |
| Latency target is not met on mixed hardware | Overclaiming performance. | Measure by environment/provider and report actual p50/p95 with conditions. |
| Scope expands before core proof | Unfinished pipeline. | Gate work by the relative phases; reserve UI/deployment ownership for Hazem after core work is assessed. |

## 14. Open decisions

1. Dataset access, permissions, actual size, labels, and the agreed annotation guide.
2. Final complaint-category, complaint-urgency, customer-state, and optional churn-risk labels.
3. Whether external providers are allowed by the competition and the dataset terms; exact approved providers and budget/quota.
4. Retention/deletion period and who can access local recordings.
5. Which models/providers meet the data, language, hardware, and latency constraints after benchmark.
6. Final dashboard language and competition demo format/judging criteria.
7. Competition deadline and any changes needed to phase priority once known.
8. Exact division of frontend and deployment assignments, which Hazem will decide after core progress is assessed.

## Appendix A. Glossary

- **Complaint category:** what kind of issue the customer reports.
- **Complaint urgency:** how time-sensitive or impact-heavy resolving that issue is.
- **Customer state:** the customer's interaction/emotional state, assessed under agreed label definitions.
- **Speech-to-text (STT):** converting voice recording to text.
- **Acoustic feature:** measurable property of the sound, such as energy, pauses, or pitch; not by itself an emotion label.
- **Churn risk:** estimated risk the customer may leave the service; separate from complaint urgency.
- **WER:** word error rate, measured against a human-verified transcript.
- **Macro-F1:** unweighted average of per-class F1 scores, useful when class counts differ.
- **On-premises:** future deployment inside a company's own infrastructure; not a capability delivered by this competition prototype.
