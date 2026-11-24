# Smart Voicemail Router (SVR)

## Product Requirements Document (PRD), Production Rebuild

| Field | Value |
|---|---|
| Product | Smart Voicemail Router (SVR) |
| Document | Product Requirements Document (PRD), Production Rebuild |
| Document ID | SVR-PRD-02 |
| Version | 1.0 |
| Status | Draft |
| Owner | SVR Team |
| Last updated | 2026-11-24 |

### Revision history

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-11-24 | SVR Team | Initial production draft, based on the AI Product PRD template and prototype PRD v1.7. Supersedes the prototype PRD for the production build. |

### Reviewers and approvals

| Role | Name | Decision | Date |
|---|---|---|---|
| Product owner | SVR Team | Pending | |
| Engineering lead | SVR Team | Pending | |
| AI / ML lead | SVR Team | Pending | |

### How this document is used

This PRD is the professional specification of the production SVR system. It defines what the system shall do, the quality it shall meet, and the limits it shall respect. It is the acceptance basis for the production build, and the plan the SVR Team uses to carry that build out. Requirement IDs stay stable so tickets, tests and the timeline can point to them: FR is functional, AI is AI/ML, NFR is non-functional, S is safety, DF is differentiator, US is user story, WF is workflow, L is limitation, A is assumption, D is deliverable, R is risk, Q is open question. A deleted ID is never reused. Wording: "shall" is mandatory, "should" is recommended, "may" is optional. Every requirement is testable: it carries a number or a pass/fail condition. Sections that do not apply say "Not applicable" with a reason. They are never left blank.

### Table of contents

1. Introduction
2. Problem, goals and success metrics
3. Users, workflows and user stories
4. Product overview and AI capabilities
5. Competitive landscape and differentiation
6. MVP and extended features
7. Functional requirements
8. AI / ML requirements
9. Non-functional requirements
10. Responsible AI, safety, privacy and compliance
11. Architecture, integrations and data
12. UX requirements
13. Limitations
14. Assumptions and dependencies
15. Build requirements and resources
16. Deliverables
17. Timeline
18. Key success indicators (KSIs)
19. Cost and pricing
20. Risks
21. Open questions
Appendix

---

## 1. Introduction

### 1.1 Product summary

Smart Voicemail Router (SVR) is a production system that turns a single-speaker Egyptian Arabic voicemail into a structured, explainable callback ticket. It transcribes the voicemail, classifies it on four fields with a validated MARBERTv2 model, computes an explainable queue priority, and routes it to an available agent whose skills fit the complaint. A supervisor sees the prioritized queue, the evidence for every decision, and a human review queue. It is for a telecom customer-care operation. It addresses arrival-order queues that hide urgent complaints, agents who must listen to a whole message before understanding the issue, and callbacks that start cold.

### 1.2 Before and after

- Today: voicemails are handled in arrival order. An agent listens to the whole message before understanding the issue. There is no structured record of what the complaint is, how urgent it is, or who should handle it.
- With SVR: a voicemail becomes a structured ticket in seconds, with a transcript, four classified fields, an explainable priority, and an assigned agent. The supervisor sees why the ticket has its priority and why it went to that agent.

### 1.3 Purpose of this document

This document defines the functional, AI, and non-functional requirements, scope, limitations, constraints and success criteria for the production SVR system. It is the acceptance basis for the production build. It supersedes the prototype PRD v1.7 for the production build. The prototype PRD remains the record of the research and validation work. The validated ML core (the MARBERTv2 single-task model, the dataset, the taxonomy, the routing rules) is carried over from the prototype, not redone. The system is rebuilt around that core.

### 1.4 Scope

- In scope: voicemail intake (upload and browser recording), transcription, text classification on four fields, queue priority, agent routing, tickets, supervisor dashboard, agent view, human review queue, audit log, evaluation and monitoring. Single-tenant, one organization, web application. Egyptian Arabic (single-speaker) with English telecom terms. Local-first processing.
- Out of scope: real telephony, SIP or CRM integration; automatic callbacks or other customer-facing actions; multi-tenancy; a native mobile app; audio emotion inference; the multi-task model (it underperforms the single-task model); on-premises packaging as a separate product.

### 1.5 Definitions and acronyms

| Term | Meaning |
|---|---|
| SVR | Smart Voicemail Router, this product |
| Voicemail | A single-speaker Egyptian Arabic voice message, up to 60 seconds |
| Ticket | The structured callback record produced from one voicemail |
| Complaint category | What kind of issue the customer reports (11 values) |
| Complaint urgency | How time-sensitive or impact-heavy the complaint itself is (high, medium, low, judged from the complaint only, never from tone) |
| Customer state | The customer's interaction state (calm, frustrated, mad, satisfied, unclear), judged from the words |
| Churn risk | Evidence the customer may leave the service (at_risk, not_at_risk, only on explicit departure language) |
| Queue priority | A system-generated ordering bucket (urgent, high, normal, low) |
| priority_score | The numeric score behind queue priority, range 1 to 6 |
| Agent | A customer-care employee who receives a ticket |
| Skill | An agent capability, mapped to complaint categories |
| Human Review | A state where a ticket needs a person to check it before or instead of automatic routing |
| Confidence | The minimum of the four fields' predicted-class probabilities for a ticket |
| Eval set | Fixed, labeled examples used to measure AI quality before release |
| Validation | The 1,003-row split used to measure the model during development |
| Test | The 518-row split, touched once under a guard, for the final evaluation |
| Single-task | One model per field (four MARBERTv2 models, one for each field) |
| Multi-task | One shared encoder with four heads, trained jointly |
| Kendall | Kendall uncertainty weighting, the multi-task loss used in the prototype |
| MARBERTv2 | UBC-NLP/MARBERTv2, the validated classification model |
| Whisper | OpenAI Whisper large-v3, the transcription model |
| STT | Speech-to-text, converting a voice recording to text |
| Macro-F1 | Unweighted average of per-class F1 scores, used when class counts differ |
| p95 | The 95th percentile latency |
| MVP | Minimum viable product, the smallest release that proves the core value |
| RAG | Retrieval-augmented generation, answering from retrieved company content |
| Handoff | Transfer of a ticket from automatic routing to a human |
| RBAC | Role-based access control |

### 1.6 References

- Prototype PRD v1.7 (SVR-PRD-01), the record of the research and validation work.
- Fair re-run summary, 2026-11-19 (runs/fair-comparison-2026-11-19.md): MARBERTv2 wins every field.
- Validation report, runs/validation-report-2026-11-20.md.
- Research recommendations, research/recommendations.md.
- STT output format v1, 10 columns.
- Class weights, final/class_weights.json (train-only).

---

## 2. Problem, goals and success metrics

### 2.1 Problem statement

A customer-care team handles voicemail in arrival order. A time-sensitive service failure can wait behind a routine question. The agent who eventually calls back must listen to the whole message before understanding the issue, and the callback can start cold, with no summary, no customer request, and no routing rationale. The cost is delayed handling of urgent complaints, wasted agent time discovering the issue, and no structured record for routing or measurement. The evidence base is the SVR Voicemail Corpus: 6,522 voicemails, 12.63 hours of audio, with a clean set of 5,096 rows.

### 2.2 Why AI

Rules cannot read a free-text voicemail and decide what the complaint is about, how urgent it is, or what the customer wants. A fine-tuned text classifier (MARBERTv2) does this from the words, with measured accuracy: combined validation macro-F1 0.7708 on the winner run, 0.7907 on the independent fair re-run. The following stays deterministic: the priority formula, the routing rules, the skill mapping, and the human review triggers are fixed rules, not model outputs. The model predicts the four fields. The system decides priority and routing by rules.

### 2.3 Goals and non-goals

Goals:

1. Convert one valid voicemail into a structured ticket with an explainable result.
2. Classify the four fields with the validated accuracy (section 2.4).
3. Route each ticket to an eligible agent with a plain-language reason, or leave it unassigned with a reason.
4. Give the supervisor a prioritized queue with evidence for every decision.
5. Keep a human in the loop for low-confidence tickets, missing labels, and unassigned tickets.
6. Run locally by default. No raw audio goes to a third-party AI service.

Non-goals:

- Real telephony, SIP, CRM, SMTP, or production voicemail ingestion.
- Automatic callbacks or other customer-facing actions.
- A production-grade multi-tenant claim.
- A native mobile app.
- Audio emotion inference.
- The multi-task model as the production model.

### 2.4 Success metrics

| Metric | Type | Baseline (validated) | Target | Measured by |
|---|---|---|---|---|
| Category macro-F1 (validation) | AI quality | 0.7872 | At least 0.75 | Eval suite on the validation set |
| Urgency macro-F1 (validation) | AI quality | 0.7211 | At least 0.70 | Eval suite on the validation set |
| Customer state macro-F1 (validation) | AI quality | 0.7471 | At least 0.70 | Eval suite on the validation set |
| Churn macro-F1 (validation) | AI quality | 0.8277 | At least 0.80 | Eval suite on the validation set |
| Combined macro-F1 (validation) | AI quality | 0.7708 | At least 0.75 | Eval suite on the validation set |
| Combined macro-F1 (test) | AI quality | None, test not run yet | Reported once, guarded | Guarded final test evaluation |
| Routing agreement | AI quality | Not measured yet | At least 80% agreement with a human-reviewed ideal assignment | Ibthal validation report |
| p95 end-to-end latency | Product | Hypothesis, under 10 s | At most 10 s for a 60 s clip | Benchmark on the production server |
| Human review rate | Product | Not measured yet | At most 20% of tickets flagged | Audit log |
| Ticket processing success rate | Product | Not measured yet | At least 99% of valid uploads become tickets | Audit log |
| Agent time saved per callback | Business | Not measured yet | To be set after one month of operation (Q5) | Supervisor survey and audit log |

---

## 3. Users, workflows and user stories

### 3.1 Personas and roles

| Role | Main responsibility | Example permissions | Platform |
|---|---|---|---|
| Admin | Manage the organization and the system | Users, roles, agents, skills, script templates, thresholds, integrations, settings | Web |
| Supervisor (queue manager) | Manage the operation | Queue, tickets, human review queue, corrections, reassignments, reports, quality reviews | Web |
| Agent (callback agent) | Do the callback work | Assigned tickets, ticket detail, callback brief, status updates | Web |
| Customer (voicemail caller) | Receives the callback | None in the system; the caller does not log in | None |
| AI pipeline | Automated actor | Only the pipeline actions in AI4: transcribe, classify, compute priority, route, create tickets | System |

### 3.2 Workflows

#### WF1 Voicemail to ticket (core workflow)

Trigger: a voicemail file is uploaded or recorded. Outcome: the voicemail becomes a structured ticket, assigned to an agent or flagged for human review, with full evidence.

| # | Actor | Action | System / AI response | Exception path |
|---|---|---|---|---|
| 1 | Supervisor or Agent | Uploads a voicemail file (WAV, MP3, M4A) or records one in the browser | File validated (format, size at most 25 MB, duration at most 60 s); ticket created in status processing | Invalid file, the system returns a clear error and creates no ticket |
| 2 | AI pipeline | Transcribes the audio (Whisper large-v3) | Transcript, normalized text, and STT metadata stored (10-column format) | Transcription fails, the ticket goes to Human Review with the error recorded |
| 3 | AI pipeline | Classifies the four fields (MARBERTv2 single-task, one model per field) | Four labels with probabilities stored; each probability is a number from 0 to 1 and the four probabilities for a field sum to 1 | A label is missing or outside the taxonomy, the ticket goes to Human Review |
| 4 | System | Computes confidence (minimum of the four fields' predicted-class probabilities) | Confidence stored on the ticket | Confidence below the threshold (0.5, PROPOSED), the ticket goes to Human Review |
| 5 | System | Computes priority_score and queue priority by the approved formula | Priority and bucket stored, with the contributing signals and a readable reason | Any input is null, priority and queue stay null and the ticket goes to Human Review |
| 6 | System | Routes to an eligible agent (skill, availability, capacity; first eligible in seed order) | Ticket assigned, route reason stored | No eligible agent, the ticket stays UNASSIGNED and enters the Human Routing Queue |
| 7 | System | Creates the callback brief (summary, customer request, suggested script) | Brief stored on the ticket, grounded only in ticket facts | Brief cannot be built, the ticket shows the transcript instead and is flagged |
| 8 | System | Logs and measures | Audit log entry, per-stage latency, outcome recorded | Logging fails, the ticket is still created and the failure is logged to the error log |

Ticket status lifecycle:

| Status | Meaning | Entered when | Allowed next status |
|---|---|---|---|
| received | Voicemail accepted, ticket created | Upload or recording passes validation | processing |
| processing | Transcription and classification are running | Processing starts | ready, unassigned, failed |
| ready | Ticket is complete and assigned to an agent | Routing succeeds | in_progress, resolved |
| unassigned | Ticket needs a human (no eligible agent, low confidence, missing label, or processing error) | Routing cannot assign it or a review trigger fires | ready (after a supervisor assigns it), in_progress |
| in_progress | An agent has picked up the ticket | Agent opens it to work the callback | resolved |
| resolved | The callback is done | Agent marks it resolved | closed |
| closed | The ticket is finished and archived | Supervisor or agent closes it | None |
| failed | Processing failed and the ticket cannot be completed automatically | A stage fails and no fallback applies | unassigned (after a supervisor reviews it) |

#### WF2 Supervisor reviews and corrects a ticket

Trigger: a supervisor opens a ticket. Outcome: the supervisor sees the evidence, corrects a label if it is wrong, and the correction is logged.

1. Supervisor opens a ticket from the queue.
2. The system shows the transcript, the four fields with probabilities, the priority signals and reason, the route reason, the confidence, and the human review flag.
3. Supervisor corrects a label if needed; the system records the old value, the new value, who changed it, and when.
4. The system recomputes priority and routing from the corrected labels, and shows the new result before the supervisor confirms it.
5. The correction is stored in the audit log.

#### WF3 Human review queue

Trigger: a ticket is flagged for review. Outcome: a supervisor works through the queue and clears each ticket.

1. The system adds the ticket to the Human Review Queue with the reason (low confidence, missing label, no eligible agent, or processing error).
2. Supervisor opens the queue, filters by reason, and opens a ticket.
3. Supervisor corrects the labels, assigns an agent, or resolves the ticket.
4. The system records the action and removes the ticket from the queue.

#### WF4 Admin configures agents, skills, thresholds, and templates

1. Admin creates or edits an agent (name, skills, capacity, availability).
2. Admin maps complaint categories to agent skills.
3. Admin sets the confidence threshold (default 0.5, PROPOSED) and the routing rules.
4. Admin edits a suggested script template for a category.
5. The system validates the change, logs it, and applies it to new tickets only. Tickets already created keep the configuration they were created with.

#### WF5 Evaluation and model update

1. The team runs the eval suite on the validation set; the system reports per-field macro-F1 and the combined mean.
2. The team runs the guarded final test evaluation once; the system records a guard claim before reading the test labels, and reports the test scores.
3. The team reviews the production monitoring (classification distribution, confidence distribution, handoff rate, latency).
4. A model update is a new versioned artifact with its own eval run; the old version stays available until the new one passes the release gates in AI9.

### 3.3 User stories

| ID | As a | I want to | So that | Acceptance criteria | Priority | Links |
|---|---|---|---|---|---|---|
| US1 | Supervisor | Upload a voicemail so it becomes a ticket | I do not handle raw audio files by hand | Given a valid WAV file under 25 MB and under 60 s, when I upload it, then a ticket appears in the queue in status processing within 2 s | Must | WF1, FR1 |
| US2 | Agent | Understand the problem without replaying the whole message | I can start the callback prepared | Given a ready ticket, when I open it, then I see a summary, the customer request, the transcript, and the four fields | Must | WF1, FR12 |
| US3 | Supervisor | See why a ticket has its queue position | I trust the ordering | Given a ready ticket, when I open it, then I see the priority score, the bucket, the contributing signals, and a readable reason | Must | WF1, FR9 |
| US4 | Supervisor | See why a ticket went to an agent | I can check the routing | Given an assigned ticket, when I open it, then I see the route reason with skill, availability, and capacity | Must | WF1, FR10 |
| US5 | Agent | Receive a useful opening line | I start the callback politely and accurately | Given a ready ticket, when I open it, then I see a suggested script that refers only to facts in the ticket, and it is not sent to the customer automatically | Must | WF1, FR14 |
| US6 | Supervisor | Correct a wrong label | The ticket reflects the truth | Given a ticket, when I change a label, then the system records the old value, the new value, my name, and the time, and recomputes priority and routing | Must | WF2, FR13 |
| US7 | Supervisor | Work through the human review queue | Nothing flagged is lost | Given a ticket flagged for review, when I open the Human Review Queue, then I see it with its reason, and I can correct it, assign it, or resolve it | Must | WF3, FR13 |
| US8 | Admin | Configure agents and their skills | Routing matches the real team | Given the agents page, when I add an agent with skills and capacity, then new tickets can route to that agent | Must | WF4, FR19 |
| US9 | Admin | Set the confidence threshold | I control when the system asks a human | Given the settings page, when I change the threshold, then new tickets use the new threshold and the change is logged | Should | WF4, FR21 |
| US10 | Supervisor | Measure quality | I know whether the system is working | Given a date range, when I open the evaluation page, then I see per-field macro-F1 on validation, the routing agreement, the human review rate, and p95 latency | Must | WF5, AI9 |
| US11 | Agent | See only my assigned tickets | I focus on my work | Given I am logged in as an agent, when I open my tickets, then I see only tickets assigned to me | Must | FR22 |
| US12 | Supervisor | See that a ticket came from the model, not a human | I know what to trust | Given a ticket, when I open it, then the model outputs are labeled as model outputs and are separate from human corrections | Must | S4 |

---

## 4. Product overview and AI capabilities

### 4.1 Modules

| Module | Description | Release |
|---|---|---|
| Authentication and authorization | Login, sessions, RBAC (admin, supervisor, agent), single-tenant isolation | MVP |
| Voicemail intake | Upload and browser recording, validation, processing status | MVP |
| Transcription (STT) | Whisper large-v3, transcript, normalized text, STT metadata | MVP |
| Text classification | MARBERTv2 single-task, four fields, labels with probabilities | MVP |
| Priority and routing | Priority formula, queue buckets, agent routing, route reason | MVP |
| Tickets and human review | Ticket view, callback brief, corrections, Human Review Queue | MVP |
| Supervisor dashboard | Prioritized queue, filters, ticket detail, evidence, evaluation page | MVP |
| Agents and skills (admin) | Agent management, skill mapping, script templates, thresholds | MVP |
| Audit and monitoring | Audit log, per-stage latency, classification and confidence distributions, alerts | MVP |
| Evaluation | Eval suite (validation), guarded final test evaluation, release gates | MVP |
| Integrations (CRM, telephony) | External system connections | Phase 2 |
| Analytics | Trend reports, agent performance, quality over time | Phase 2 |

### 4.2 AI capability map

| Capability | Input | Output | Autonomy | Fallback when unsure |
|---|---|---|---|---|
| Speech-to-text | Audio file (WAV, MP3, M4A, up to 60 s) | Transcript, normalized text, STT metadata | Autonomous | Ticket goes to Human Review with the error recorded |
| Complaint category classification | Normalized transcript | Category label plus probabilities for 11 values | Autonomous | Ticket goes to Human Review |
| Complaint urgency classification | Normalized transcript | Urgency label plus probabilities for 3 values | Autonomous | Ticket goes to Human Review |
| Customer state classification | Normalized transcript | State label plus probabilities for 4 values | Autonomous | Ticket goes to Human Review |
| Churn risk classification | Normalized transcript | Churn label plus probabilities for 2 values | Autonomous | Ticket goes to Human Review |
| Priority computation | Four labels | priority_score (1 to 6) and queue bucket | Autonomous, by fixed rule | Priority and queue stay null, ticket goes to Human Review |
| Agent routing | Four labels, priority, agent skills, availability, capacity | Assigned agent plus route reason, or UNASSIGNED | Autonomous, by fixed rule | Ticket stays UNASSIGNED and enters the Human Routing Queue |
| Callback brief | Transcript, four labels, category | Summary, customer request, suggested script template | Autonomous, by fixed rule and template | Ticket shows the transcript instead and is flagged |
| Suggested script | Predicted category | Script template for that category | Autonomous, by template | No script shown; the ticket is flagged |

---

## 5. Competitive landscape and differentiation

### 5.1 Competitors

| Competitor | Type | Target customers | Pricing | Strengths | Weaknesses |
|---|---|---|---|---|---|
| Manual voicemail handling (status quo) | Status quo | Telecom customer-care teams | Staff time | Familiar, no switching cost, a human understands nuance | Slow, arrival-order queues hide urgent complaints, no structured record, no measurement |
| Generic voicemail-to-text service | Indirect | Any team with voicemail | Varies by provider | Transcribes audio to text | Transcription only; no classification, no priority, no routing, no callback brief |
| Generic AI chatbot or LLM tool | Indirect | Any team with customer messages | Varies by provider | Cheap, fast to set up, answers in natural language | Answers only; no structured ticket, no explainable priority, no agent routing, no audit trail for routing decisions |
| Traditional IVR and call-center software | Direct | Telecom and large contact centers | Varies, usually per seat | Routes by menu and IVR, integrates with telephony | Routes by menu choice, not by understanding a free voicemail; no text classification of the complaint, no explainable priority from the message content |

No direct named competitor with a published price for Egyptian Arabic voicemail classification and routing was identified in the project research. The comparison above is based on product categories, not on a named vendor benchmark.

### 5.2 Capability comparison

| Capability | SVR | Manual handling | Generic voicemail-to-text | Generic AI chatbot | Traditional IVR |
|---|---|---|---|---|---|
| Voicemail becomes a structured ticket | Yes | No | Partial (text only) | No | Partial (ticket, no content understanding) |
| Classifies complaint category, urgency, customer state, churn risk | Yes | By hand | No | Partial (free text, not a fixed taxonomy) | No |
| Explainable queue priority with a readable reason | Yes | No | No | No | Partial (priority by queue, not by content) |
| Routes to an agent by skill, availability, and capacity | Yes | By hand | No | No | Partial (by menu, not by content) |
| Human review queue for low-confidence and unassigned tickets | Yes | Not applicable | No | Partial | No |
| Egyptian Arabic with English telecom terms | Yes | Yes | Partial | Partial | Partial |
| Runs locally by default, no raw audio to a third-party AI | Yes | Yes | No | No | Varies |
| Audit log for every decision | Yes | No | No | Partial | Partial |

### 5.3 Key differentiators

| ID | Differentiator | Why customers care | Proof / evidence | How hard to copy | Delivered by |
|---|---|---|---|---|---|
| DF1 | A voicemail becomes a structured, explainable ticket: four classified fields, a priority with a readable reason, and an assigned agent | Urgent complaints are handled first, and the agent starts the callback prepared | Validated combined macro-F1 0.7708 (winner run) and 0.7907 (independent fair re-run); routing agreement target at least 80% | High: needs the validated model, the taxonomy, and the routing rules together | AI1, AI2, FR6, FR9, FR10 |
| DF2 | Explainable priority and routing, with a human review queue for everything unsure | Supervisors trust the ordering and nothing flagged is lost | Every ticket shows its signals and reason; the Human Review Queue holds every flagged ticket | Medium: needs the fixed rules and the review flow, not only a model | FR9, FR10, FR13, S1 |
| DF3 | Built for Egyptian Arabic voicemail with English telecom terms, and local-first by default | The product understands the actual messages and keeps voice data local | Validated on the SVR Voicemail Corpus (5,096 clean rows); no raw audio goes to a third-party AI by default | High: needs the corpus, the validated model, and the local deployment | AI1, AI8, NFR2 |
| DF4 | A test-once evaluation discipline: the test set is touched once, under a guard, so the reported score is honest | The reported quality is credible, not tuned on the test set | Guard claim logged before test labels are read; test evaluated once by Aya | Medium: needs the guard and the frozen split | AI9, AI10 |

### 5.4 Positioning statement

For a telecom customer-care operation that receives Egyptian Arabic voicemails, SVR is a voicemail routing system that turns each voicemail into a structured, explainable callback ticket with a priority and an assigned agent. Unlike manual handling or generic transcription, it understands the complaint, the urgency, the customer state, and the churn risk from the words, and it shows why every decision was made.

### 5.5 Defensibility (AI moat)

- Data and feedback loop: supervisor corrections on tickets feed a labeled correction set. Within the privacy rules, corrections improve the next model version. The audit of the labels is ongoing, and corrections are applied in the retrain step.
- Workflow depth: the taxonomy, the priority formula, the skill mapping, the script templates, and the human review flow live in the product. Replacing the product means rebuilding that configuration, not only swapping a model.
- Domain evaluation: the SVR Voicemail Corpus (5,096 clean rows, frozen split) and the validated per-field metrics are specific to Egyptian Arabic telecom voicemail. A generic model does not have this eval set.
- Switching costs: ticket history, audit log, agent skills, script templates, and routing rules live in the product.
- Distribution: the product is built for the operator that validated it, with the team that built the corpus and the model.

---

## 6. MVP and extended features

### 6.1 MVP goal

The MVP shall let a supervisor upload a voicemail and get a structured ticket with a transcript, four classified fields, an explainable priority, and an assigned agent (WF1), and shall prove that the production-served model reproduces the validated validation numbers within the AI9 tolerance, and that at least 80% of routing decisions agree with a human-reviewed ideal assignment.

### 6.2 MVP features

| Feature | Module | Description | AI autonomy in MVP | Linked requirements |
|---|---|---|---|---|
| Authentication, RBAC | Auth | Login, sessions, roles (admin, supervisor, agent), single-tenant isolation | None | FR22, FR23, FR24 |
| Voicemail intake | Intake | Upload (WAV, MP3, M4A, at most 25 MB, at most 60 s) and browser recording, validation, processing status | None | FR1, FR2, FR3 |
| Transcription | STT | Whisper large-v3, transcript, normalized text, STT metadata (10-column format) | Autonomous | FR4, FR5, AI1 |
| Text classification | Classification | MARBERTv2 single-task, four fields, labels with probabilities | Autonomous | FR6, FR7, FR8, AI1, AI2 |
| Priority and routing | Priority and routing | Priority formula, queue buckets, agent routing, route reason | Autonomous, by fixed rule | FR9, FR10, FR11, AI2 |
| Tickets and human review | Tickets | Ticket view, callback brief, corrections, Human Review Queue | Autonomous, by rule and template, with human override | FR12, FR13, FR14, FR15 |
| Supervisor dashboard | Dashboard | Prioritized queue, filters, ticket detail, evidence, evaluation page | None | FR16, FR17, FR18 |
| Agents and skills (admin) | Admin | Agent management, skill mapping, script templates, confidence threshold | None | FR19, FR20, FR21 |
| Audit and monitoring | Audit | Audit log, per-stage latency, classification and confidence distributions, alerts | None | FR18, AI10, NFR19, NFR20 |
| Evaluation | Evaluation | Eval suite on validation, guarded final test evaluation, release gates | None | AI9, AI10 |

### 6.3 MVP exit criteria

- All MVP workflows (WF1, WF2, WF3, WF4, WF5) pass end-to-end tests.
- The production-served model meets the AI9 quality thresholds on the validation set.
- The guarded final test evaluation has run once and its scores are reported.
- Performance targets met: p95 end-to-end latency at most 10 s for a 60 s clip on the production server; a valid upload appears in the queue in status processing within 2 s.
- Routing agreement is at least 80% on the validation set (Ibthal validation report).
- Security review passed; no open critical defects.
- The audit log records every decision, correction, and configuration change.

### 6.4 Extended features (post-MVP)

| Feature | Phase | Value to users | Depends on | Start when |
|---|---|---|---|---|
| CRM and telephony integration | Phase 2 | Tickets link to customer records; voicemails arrive automatically | MVP stable, operator approves the integration | Operator requests it and approves the data handling |
| Analytics (trends, agent performance, quality over time) | Phase 2 | Supervisors see patterns and quality drift | MVP production data | 1 month of production data |
| Multi-tenancy | Phase 2 | More than one organization on the same deployment | MVP stable, data model carries a tenant id (FR24) | Operator requests it |
| Multi-task model as an option | Phase 2 | One model instead of four, if it ever beats single-task | A multi-task run that beats the single-task validation numbers (it does not yet: 0.75536 vs 0.7708) | A multi-task run beats single-task on validation and passes AI9 |
| More languages or dialects | Phase 3 | The same routing for other Arabic dialects or languages | Labeled data and a validated model for the new language | Labeled data is available and validated |
| Higher AI autonomy (fewer human reviews) | Phase 2 | Less supervisor load | AI10 metrics stable and the human review rate below target for 1 month | Monitoring shows stable quality |

### 6.5 Not planned

- Automatic callbacks or customer-facing messages. The system prepares the callback; a human makes the call.
- Audio emotion inference. The audio model was tested and closed on 2026-11-17: audio carries no emotion signal for this data. Customer state comes from text only.
- The multi-task model as the production model. It underperforms the single-task model (0.75536 vs 0.7708 combined validation macro-F1), so the production model is single-task.
- Real-time voice calls or live multi-party call handling. The product handles recorded single-speaker voicemail only.
- A native mobile app. The MVP is a responsive web application.

---

## 7. Functional requirements

### 7.1 Voicemail intake and transcription

**FR1 Upload voicemail**

- Priority: Must. Release: MVP. AI involvement: None.
- SVR shall allow a supervisor or an agent to upload a voicemail file in WAV, MP3, or M4A format, up to 25 MB and up to 60 seconds.
- The system shall validate format, size, and duration before creating a ticket. On an invalid file, it shall return a clear error naming the problem (format, size, or duration) and shall create no ticket.
- The system shall recommend clips of 15 to 60 seconds but shall not reject a shorter valid clip.
- Acceptance criteria: Given a valid WAV file under 25 MB and under 60 s, when it is uploaded, then a ticket appears in the queue in status processing within 2 s. Given a file over 25 MB, when it is uploaded, then the system returns an error and creates no ticket.

**FR2 Browser recording**

- Priority: Should. Release: MVP. AI involvement: None.
- SVR shall allow a supervisor or an agent to record a voicemail in the browser and submit it as a ticket.
- The recording shall be validated the same way as an upload (format, size, duration).
- Acceptance criteria: Given a browser recording under 60 s, when it is submitted, then a ticket appears in the queue in status processing within 2 s.

**FR3 Processing status**

- Priority: Must. Release: MVP. AI involvement: None.
- SVR shall show the processing status of each ticket (received, processing, ready, unassigned, in_progress, resolved, closed, failed) and the per-stage status and timing.
- The system shall update the status in real time on the dashboard without a page reload.
- Acceptance criteria: Given a ticket in processing, when a stage completes, then the dashboard shows the new status within 2 s.

**FR4 Transcribe voicemail**

- Priority: Must. Release: MVP. AI involvement: Autonomous.
- SVR shall transcribe each voicemail with Whisper large-v3, for Egyptian Arabic with English telecom terms.
- The system shall store the transcript, the normalized text (text_norm), and the STT metadata in the 10-column format (file, model, text, text_norm, min_avg_logprob, max_no_speech_prob, needs_review, review_reasons, dup_text_size, error).
- Acceptance criteria: Given a valid voicemail, when transcription completes, then the ticket shows a transcript and the 10 STT fields are stored.

**FR5 Language-mix indication**

- Priority: Should. Release: MVP. AI involvement: Autonomous.
- SVR shall record a language-mix indication for each transcript (Arabic, English telecom terms present, or mixed).
- Acceptance criteria: Given a transcript with English telecom terms, when the ticket is viewed, then the language-mix indication is shown.

### 7.2 Authorization and multi-tenancy

**FR22 Authentication**

- Priority: Must. Release: MVP. AI involvement: None.
- SVR shall require login for every user. Sessions shall expire after 8 hours of inactivity, and tokens shall be invalidated on logout, account status change, or role change.
- Acceptance criteria: Given a logged-out user, when they open a protected page, then they are redirected to login. Given a session older than 8 hours without activity, when they make a request, then the system requires login again.

**FR23 Role-based access control**

- Priority: Must. Release: MVP. AI involvement: None.
- SVR shall support the roles in section 3.1 (admin, supervisor, agent), each with a defined permission set.
- The backend shall check role and permission on every protected endpoint. The UI shall hide what the user cannot use.
- Users shall not be able to grant themselves additional roles or permissions.
- Acceptance criteria: Given a logged-in agent, when they request an admin endpoint, then the system returns a 403 error. Given a logged-in agent, when they open the dashboard, then they see only their assigned tickets and not the admin pages.

**FR24 Tenant isolation**

- Priority: Must. Release: MVP. AI involvement: None.
- The MVP is single-tenant (one organization). Users shall only access data that belongs to their organization.
- The data model shall carry an organization id on every record, so multi-tenancy can be added later without a schema change.
- Acceptance criteria: Given a user in the organization, when they list tickets, then they see only tickets from that organization.

### 7.3 Classification, priority, routing, and tickets

**FR6 Classify the four fields**

- Priority: Must. Release: MVP. AI involvement: Autonomous.
- SVR shall classify each ticket on four fields with the MARBERTv2 single-task models (one model per field): complaint_category (11 values), complaint_urgency (3 values), customer_state (4 values scored), churn_risk (2 values).
- For each field, the system shall store the predicted label and the probabilities for every class in that field. The probabilities for a field shall sum to 1 within 0.001.
- Acceptance criteria: Given a transcribed ticket, when classification completes, then the ticket shows four labels and four probability sets, each summing to 1 within 0.001.

**FR7 Keep the four fields independent**

- Priority: Must. Release: MVP. AI involvement: None.
- SVR shall keep complaint category, complaint urgency, customer state, and churn risk independent through storage, the UI, and evaluation. No field shall be derived from another field.
- Acceptance criteria: Given a ticket, when its labels are read from storage, the UI, and the eval suite, then the four values are identical in all three places.

**FR8 Validate classification outputs**

- Priority: Must. Release: MVP. AI involvement: Autonomous.
- SVR shall validate every predicted label against the agreed taxonomy. A label outside the taxonomy shall be rejected.
- An ambiguous or unsupported result shall send the ticket to Human Review.
- Acceptance criteria: Given a model output with a label outside the taxonomy, when the ticket is processed, then the ticket goes to Human Review and the rejected label is recorded.

**FR9 Compute queue priority**

- Priority: Must. Release: MVP. AI involvement: Autonomous, by fixed rule.
- SVR shall compute priority_score as complaint_urgency (high 3, medium 2, low 1) plus churn_risk (at_risk 2, not_at_risk 0) plus customer_state (mad 1, frustrated 1, calm 0, satisfied 0, unclear 0). The range is 1 to 6.
- The system shall map the score to a bucket: 6 is urgent, 5 is high, 3 to 4 is normal, 1 to 2 is low.
- The system shall show the score, the bucket, the contributing signals, and a readable reason on the ticket.
- If any input is null, priority_score and queue priority shall stay null and the ticket shall go to Human Review.
- Acceptance criteria: Given a ticket with urgency high, churn at_risk, and state mad, when priority is computed, then priority_score is 6 and the bucket is urgent. Given a ticket with a null urgency, when priority is computed, then priority_score is null and the ticket goes to Human Review.

**FR10 Route to an agent**

- Priority: Must. Release: MVP. AI involvement: Autonomous, by fixed rule.
- SVR shall route each ticket to an eligible agent by approved skill and category, availability, and capacity. It shall pick the first eligible agent in seed order. There is no tier policy.
- The system shall store a plain-language route reason (skill, availability, capacity) on the ticket.
- If no eligible agent exists, the ticket shall stay UNASSIGNED and enter the Human Routing Queue, with the reason recorded.
- Acceptance criteria: Given a ticket in category offers_and_packages and an available Billing agent with capacity, when routing runs, then the ticket is assigned to that agent with a route reason naming the skill. Given a ticket and no eligible agent, when routing runs, then the ticket stays UNASSIGNED and appears in the Human Routing Queue.

**FR11 Route reason**

- Priority: Must. Release: MVP. AI involvement: None.
- SVR shall show a route reason on every ticket, whether assigned or unassigned.
- Acceptance criteria: Given any ticket, when it is viewed, then a route reason is shown.

**FR12 Ticket view and callback brief**

- Priority: Must. Release: MVP. AI involvement: Autonomous, by rule and template.
- SVR shall show on each ticket: the transcript, the four fields with probabilities, the priority score and bucket with signals and reason, the route reason, the confidence, the human review flag, the summary, the customer request, and the suggested script.
- Acceptance criteria: Given a ready ticket, when it is opened, then all of these items are present.

**FR13 Human review queue and corrections**

- Priority: Must. Release: MVP. AI involvement: None.
- SVR shall provide a Human Review Queue listing every flagged ticket with its reason (low confidence, missing label, no eligible agent, or processing error).
- A supervisor shall be able to correct a label, assign an agent, or resolve a ticket from the queue.
- A correction shall record the old value, the new value, who changed it, and when. The system shall recompute priority and routing from the corrected labels and show the new result before the supervisor confirms it.
- Acceptance criteria: Given a flagged ticket, when a supervisor corrects a label, then the audit log shows the old value, the new value, the supervisor, and the time, and the priority is recomputed.

**FR14 Suggested script**

- Priority: Must. Release: MVP. AI involvement: Autonomous, by template.
- SVR shall show a suggested opening line for each ticket, selected from a template per predicted category.
- The script shall refer only to facts in the ticket. It shall never be sent to the customer automatically.
- Acceptance criteria: Given a ready ticket, when it is opened, then a suggested script is shown and it contains no fact that is not in the ticket.

**FR15 Summary and customer request**

- Priority: Must. Release: MVP. AI involvement: Autonomous, by fixed rule.
- SVR shall build the summary as the transcript itself, truncated to 200 characters if it is longer.
- SVR shall build the customer request as a sentence from the predicted category.
- Acceptance criteria: Given a ticket with a transcript longer than 200 characters, when the summary is built, then it is at most 200 characters and is the start of the transcript.

### 7.4 Dashboard, agents, and settings

**FR16 Supervisor dashboard**

- Priority: Must. Release: MVP. AI involvement: None.
- SVR shall provide a supervisor dashboard with the prioritized queue, filters (by bucket, category, status, agent), ticket detail, and evidence for every decision.
- The dashboard shall update the queue in real time without a page reload.
- Acceptance criteria: Given 10 tickets in different buckets, when the supervisor opens the dashboard, then the tickets are ordered by priority (urgent first) and the filter by category returns only tickets in that category.

**FR17 Agent view**

- Priority: Must. Release: MVP. AI involvement: None.
- SVR shall provide an agent view showing only the tickets assigned to the logged-in agent, with the callback brief for each.
- Acceptance criteria: Given an agent with 3 assigned tickets, when they open their view, then they see exactly those 3 tickets.

**FR18 Audit log**

- Priority: Must. Release: MVP. AI involvement: None.
- SVR shall record an audit event for every login, ticket creation, classification, priority computation, routing decision, correction, reassignment, status change, configuration change, and export.
- Each audit event shall carry who did it (or that the system did it), what changed, the old and new values where applicable, and the time.
- Acceptance criteria: Given a ticket that was corrected, when the audit log is opened, then the correction event shows the old value, the new value, the supervisor, and the time.

**FR19 Manage agents**

- Priority: Must. Release: MVP. AI involvement: None.
- SVR shall allow an admin to create, edit, and deactivate agents, each with a name, skills, capacity (maximum concurrent tickets), and availability.
- Acceptance criteria: Given an admin, when they add an agent with skills and capacity 5, then new tickets can route to that agent.

**FR20 Manage skill mapping**

- Priority: Must. Release: MVP. AI involvement: None.
- SVR shall allow an admin to map complaint categories to agent skills. The 11 categories shall each map to at least one skill.
- The current mapping is: Network agent covers network_and_connectivity, no_reply_or_long_wait, sim_services. Billing agent covers billing_and_charges, balance_and_data, offers_and_packages. General agent covers app_and_account, branch_and_staff, cancellation_request, thanks_or_praise, other.
- Acceptance criteria: Given the mapping above, when a ticket in category sim_services is routed, then it can go to a Network agent and not to a Billing agent.

**FR21 Manage thresholds and templates**

- Priority: Must. Release: MVP. AI involvement: None.
- SVR shall allow an admin to set the confidence threshold (default 0.5, PROPOSED, see AI3) and to edit the suggested script template for each category.
- A change shall apply to new tickets only. Tickets already created shall keep the configuration they were created with. Every change shall be logged.
- Acceptance criteria: Given an admin, when they change the threshold from 0.5 to 0.6, then new tickets use 0.6, old tickets keep 0.5, and the change is in the audit log.

### 7.5 Requirements index

| ID | Requirement | Module | Priority | Release | Status |
|---|---|---|---|---|---|
| FR1 | Upload voicemail | Intake | Must | MVP | Draft |
| FR2 | Browser recording | Intake | Should | MVP | Draft |
| FR3 | Processing status | Intake | Must | MVP | Draft |
| FR4 | Transcribe voicemail | Transcription | Must | MVP | Draft |
| FR5 | Language-mix indication | Transcription | Should | MVP | Draft |
| FR6 | Classify the four fields | Classification | Must | MVP | Draft |
| FR7 | Keep the four fields independent | Classification | Must | MVP | Draft |
| FR8 | Validate classification outputs | Classification | Must | MVP | Draft |
| FR9 | Compute queue priority | Priority and routing | Must | MVP | Draft |
| FR10 | Route to an agent | Priority and routing | Must | MVP | Draft |
| FR11 | Route reason | Priority and routing | Must | MVP | Draft |
| FR12 | Ticket view and callback brief | Tickets | Must | MVP | Draft |
| FR13 | Human review queue and corrections | Tickets | Must | MVP | Draft |
| FR14 | Suggested script | Tickets | Must | MVP | Draft |
| FR15 | Summary and customer request | Tickets | Must | MVP | Draft |
| FR16 | Supervisor dashboard | Dashboard | Must | MVP | Draft |
| FR17 | Agent view | Dashboard | Must | MVP | Draft |
| FR18 | Audit log | Dashboard | Must | MVP | Draft |
| FR19 | Manage agents | Admin | Must | MVP | Draft |
| FR20 | Manage skill mapping | Admin | Must | MVP | Draft |
| FR21 | Manage thresholds and templates | Admin | Must | MVP | Draft |
| FR22 | Authentication | Authorization | Must | MVP | Draft |
| FR23 | Role-based access control | Authorization | Must | MVP | Draft |
| FR24 | Tenant isolation | Authorization | Must | MVP | Draft |

---

## 8. AI / ML requirements

### 8.1 Models and providers

**AI1 Model selection**

| Task | Model / provider | Fallback model | Why this model | Max cost per call |
|---|---|---|---|---|
| Speech-to-text | Whisper large-v3, self-hosted | None; on failure the ticket goes to Human Review | Validated on the corpus; Egyptian Arabic with English telecom terms | Compute only, no per-call provider fee |
| Complaint category | MARBERTv2 (UBC-NLP/MARBERTv2), single-task, self-hosted | None; on failure the ticket goes to Human Review | Winner of the fair comparison; combined validation macro-F1 0.7708 (winner run) and 0.7907 (independent fair re-run) | Compute only |
| Complaint urgency | MARBERTv2, single-task, self-hosted | None; on failure the ticket goes to Human Review | Same as above; urgency macro-F1 0.7211 (winner run) | Compute only |
| Customer state | MARBERTv2, single-task, self-hosted | None; on failure the ticket goes to Human Review | Same as above; state macro-F1 0.7471 (winner run) | Compute only |
| Churn risk | MARBERTv2, single-task, self-hosted | None; on failure the ticket goes to Human Review | Same as above; churn macro-F1 0.8277 (winner run) | Compute only |

- The system shall route each task to its configured model. There is no fallback ML model. If a model is unavailable, the ticket shall go to Human Review with the error recorded.
- Model versions shall be configurable without a code deploy. The model name, revision, and version shall be recorded on every ticket and every eval run.
- The production model is single-task MARBERTv2 (four separate models, one per field), lr 2e-5, batch 16, epochs 3, max seq len 128, dropout 0.1, class weights in the loss, 5 seeds (42, 1337, 2023, 7, 99). The multi-task model is not used in production: it underperforms single-task (mean validation macro-F1 0.75536 vs 0.7708).

### 8.2 AI agent behavior

**AI2 Pipeline behavior**

- The AI pipeline shall run the stages in order: transcribe, normalize, classify the four fields, compute confidence, compute priority, route, build the callback brief, as in WF1. It shall log every stage with its input, output, latency, and any error.
- The pipeline shall only perform the actions listed in AI4. It shall not send messages to customers, make calls, or change data outside a ticket.
- Acceptance criteria: Given a valid voicemail, when the pipeline runs, then the audit log shows one entry per stage with latency, and the ticket is complete.

**AI3 Confidence and human handoff**

- The system shall compute a confidence score per ticket as the minimum of the four fields' predicted-class probabilities.
- The system shall send a ticket to Human Review when confidence is below the threshold (0.5, PROPOSED, see Q3), when any label is missing, when no eligible agent exists, or when a supervisor requests review.
- The handoff shall include the transcript, the four fields with probabilities, the priority signals, the route reason, and the confidence.
- Acceptance criteria: Given a ticket with confidence 0.4 and a threshold of 0.5, when it is processed, then it goes to Human Review. Given a ticket with confidence 0.8, when it is processed, then it is routed normally.

**AI4 Tools and actions**

| Tool / action | What it does | Risk | Needs approval | Limits |
|---|---|---|---|---|
| transcribe_audio | Transcribes a voicemail with Whisper large-v3 | Low | No | One voicemail per call |
| classify_fields | Classifies the four fields with MARBERTv2 | Low | No | One ticket per call |
| compute_priority | Computes priority_score and bucket by the fixed formula | Low | No | Fixed formula, no model output |
| route_ticket | Assigns an agent by skill, availability, and capacity | Medium | No, but a supervisor can reassign it | One agent per ticket; capacity enforced |
| create_ticket | Creates the ticket record with all fields and evidence | Low | No | One ticket per voicemail |
| flag_for_review | Adds a ticket to the Human Review Queue | Low | No | Reason recorded |

- Before each action, the system shall validate permissions and preconditions.
- The system shall prevent duplicate execution (idempotency key per voicemail) and shall support retry or escalation on failure.

### 8.3 Knowledge and retrieval (RAG)

**AI5 Knowledge base**

- Not applicable: SVR does not use retrieval-augmented generation. The system classifies and routes voicemails; it does not answer questions from a knowledge base. The suggested script is a template selected by category (FR14), not a generated answer from retrieved content. There is no vector store and no retrieval step in the pipeline.

**AI6 Grounding**

- Every ticket shall show the evidence it is based on: the transcript, the four fields with probabilities, the priority signals and reason, and the route reason (FR12).
- The summary and the suggested script shall only use facts from the ticket (FR14, FR15). They shall never invent a fact.
- When the evidence is missing or the model is unsure, the ticket shall go to Human Review instead of showing a guessed answer (AI3, FR8).
- Acceptance criteria: Given a ready ticket, when it is opened, then the transcript, the four probabilities, and the priority signals are all shown, and the suggested script contains no fact that is not in the ticket.

### 8.4 Prompts and context

**AI7 Prompt and context management**

- Not applicable for LLM prompts: SVR uses no large language model for classification, summary, or routing. Classification is a fine-tuned MARBERTv2 model, not a prompted LLM. The summary and the customer request are built by fixed rules (FR15). The suggested script is a template per category (FR14).
- The rule-based text outputs and the script templates shall be versioned like code, reviewed before release, and tested against the eval set before release.
- The system shall never send a transcript, a ticket, or a recording to an external language model.

### 8.5 Data for training and evaluation

**AI8 Data requirements**

| Dataset | Source | Size | Labels | Owner | PII handling |
|---|---|---|---|---|---|
| SVR Voicemail Corpus (clean) | Recorded for data collection, simulated | 5,096 rows: train 3,575, validation 1,003, test 518 | Category, urgency, state, churn | SVR Team | Simulated data; no real customer data; audio kept local by default |
| Validation eval set | Clean set, validation split | 1,003 rows | Four fields | SVR Team | Same as above |
| Test eval set | Clean set, test split | 518 rows | Four fields | SVR Team | Same as above; touched once, guarded |
| Class weights | Computed from train only (sklearn balanced) | 4 fields | Not applicable | SVR Team | Not applicable |

- The split is FROZEN: train 3,575, validation 1,003, test 518. The 655 worst transcripts (Whisper logprob below -0.30) were excluded from the clean set.
- The labels come from a model and are being audited by the team. The labels are not human-verified until the audit approves them. The system shall label model outputs as model outputs in the UI and the audit log.
- The test set shall be evaluated once, under the guard in AI9. Members shall never produce test predictions on their own.
- Customer data shall not be used to train a third-party model.

### 8.6 Evaluation

**AI9 Quality thresholds (release gates)**

A capability does not ship until it meets its threshold on the eval set. The production-served model shall reproduce the validated validation numbers within the tolerance below.

| Capability | Metric | Threshold | Eval set | Method |
|---|---|---|---|---|
| Complaint category | Macro-F1 | At least 0.75 (validated 0.7872) | Validation, 1,003 rows | Automated eval suite |
| Complaint urgency | Macro-F1 | At least 0.70 (validated 0.7211) | Validation, 1,003 rows | Automated eval suite |
| Customer state | Macro-F1 | At least 0.70 (validated 0.7471) | Validation, 1,003 rows | Automated eval suite |
| Churn risk | Macro-F1 | At least 0.80 (validated 0.8277) | Validation, 1,003 rows | Automated eval suite |
| Combined | Mean of the four macro-F1 values | At least 0.75 (validated 0.7708) | Validation, 1,003 rows | Automated eval suite |
| Routing | Agreement with a human-reviewed ideal assignment | At least 80% | Validation, 1,003 rows | Ibthal validation report |
| Final test | Combined macro-F1 | Reported once, no threshold gate (the test is the truth, reported honestly) | Test, 518 rows, touched once | Guarded final test evaluation |

- The test evaluation shall run once per model and dataset version. A guard claim shall be logged before the test labels are read. The checkpoint hash shall be recorded for provenance.
- Churn rests on only 7 at-risk validation rows, so the churn macro-F1 is fragile: one row changes the score materially. The eval report shall show the per-seed churn values and the at-risk row count, not only the mean.

**AI10 Production monitoring**

- The system shall track the classification distribution per field, the confidence distribution, the human review rate, the routing agreement on a sampled set, and cost and latency per ticket.
- It shall alert the supervisor when the human review rate exceeds 20% for 24 hours, or when p95 latency exceeds 10 s for 24 hours.
- At least 5% of tickets shall be sampled for human review every week.
- The system shall record an eval run (dataset version, split, model version, config, per-field metrics, latency) for every evaluation.

### 8.7 AI cost and latency budget

| Item | Budget |
|---|---|
| Cost per AI ticket | Compute only; no per-call provider fee (models are self-hosted) |
| Monthly AI spend at target volume | Compute cost of the production server only; no third-party AI spend |
| Time to first AI response | Not applicable (the pipeline is asynchronous; the ticket appears in processing within 2 s, FR1) |
| Max tokens per request | Not applicable (no LLM is used) |
| p95 end-to-end latency | At most 10 s for a clip up to 60 s, on the production server |

---

## 9. Non-functional requirements

### 9.1 Security

- NFR1 Authentication and sessions: passwords shall be hashed with bcrypt (cost factor at least 10). Sessions shall use HTTP-only, Secure cookies with a 8-hour inactivity expiry. Tokens shall be invalidated on logout, account status change, or role change.
- NFR2 Encryption: ticket data and audio files shall be encrypted at rest. All traffic shall use TLS 1.2 or higher. API keys and model paths shall be kept in environment variables or a secret store, and never shown to unauthorized users. No secret or recording shall appear in code, logs, public notebooks, or prompts.
- NFR3 Access control: every protected operation shall check role, permission, and organization. The backend shall enforce this on every endpoint, including requests made by the AI pipeline.

### 9.2 Performance

- NFR4 API response: standard operations (list tickets, open a ticket, update a status) shall complete within 2 s at p95 under normal load, excluding model inference.
- NFR5 AI latency: the pipeline (transcription plus classification plus priority plus routing) shall complete within 10 s at p95 for a clip up to 60 s, on the production server.
- NFR6 Dashboard queries: a 30-day dashboard query shall complete within 3 s.

### 9.3 Scalability

- NFR7 Concurrency: the system shall support at least 20 concurrent users without noticeable slowdown.
- NFR8 Volume: the system shall support at least 100,000 tickets, using pagination, indexing, and archiving.
- NFR9 Horizontal scaling: the backend and the AI services shall scale out when load increases. The pipeline shall run as a worker that can be replicated.

### 9.4 Usability, localization and accessibility

- NFR10 Simplicity: core actions (upload, open a ticket, correct a label, assign an agent) shall take at most 3 steps. Every action shall give clear success, error, and loading feedback.
- NFR11 Languages and accessibility: the UI shall support English and Arabic, including right-to-left layout for Arabic transcript display. The system shall meet WCAG 2.2 AA.

### 9.5 Reliability

- NFR12 Availability: the system shall be available 99.5% of the time, excluding scheduled maintenance and third-party outages.
- NFR13 Data integrity: uploads and webhook events shall be deduplicated by an idempotency key, so the same voicemail cannot create two tickets.
- NFR14 Failure recovery: the pipeline shall retry a failed stage with backoff (3 attempts, then the ticket goes to Human Review with the error recorded). When a model is unavailable, the product shall degrade to Human Review for every affected ticket, not fail silently.
- NFR15 Backup: the database shall be backed up every 24 hours. RPO shall be at most 24 hours, RTO at most 4 hours. Restores shall be tested every quarter.

### 9.6 Maintainability and interoperability

- NFR16 Documentation: APIs shall be documented in OpenAPI. Major architecture decisions shall be recorded.
- NFR17 Modularity and extensibility: the intake, STT, classification, priority, routing, ticket, and dashboard services shall stay separate. New channels, integrations, and model versions shall be addable without changing existing ones.
- NFR18 Real-time updates: the dashboard queue and ticket status shall update in real time via WebSockets.

### 9.7 Auditability and monitoring

- NFR19 Audit log: the system shall log logins, permission changes, data edits, exports, AI actions, and integration calls, with who, what, when, and old and new values.
- NFR20 Monitoring: the system shall monitor app health, API performance, errors, AI services, and integrations, with alerts to the supervisor when a threshold is crossed (AI10).

### 9.8 Constraints

- NFR21 Technology stack: the product shall use the stack in section 11.1.
- NFR22 Deployment: the product shall run on a server the operator controls, with a GPU for inference (see A4). The exact provider and region are an open question (Q2).

---

## 10. Responsible AI, safety, privacy and compliance

### 10.1 Guardrails

- S1 Permitted actions: the AI pipeline shall only perform the actions listed in AI4. It shall not send messages to customers, make calls, or change data outside a ticket. Assigning an agent is reversible by a supervisor.
- S2 Prompt injection: the system uses no large language model, so there is no prompt to inject into. Input text (transcripts, labels, templates) is data, never instructions. The pipeline shall treat all input text as data and shall never execute it as a command.
- S3 Output checks: the system shall block a ticket that invents facts. The summary and the suggested script shall only use facts from the ticket (FR14, FR15). A ticket with an unsupported label shall go to Human Review (FR8).
- S4 AI disclosure: model outputs shall be labeled as model outputs in the UI and the audit log, and kept separate from human corrections. A supervisor shall be able to see, for every field, whether the value came from the model or from a human.

### 10.2 Privacy and data handling

| Data type | Sent to AI provider? | Retention | Redaction | Legal basis |
|---|---|---|---|---|
| Voicemail audio | No, processed locally by default | Configurable, default 90 days (Q1) | Not applicable (audio identifies the speaker) | Consent confirmed for this use (simulated data) |
| Transcript and normalized text | No, processed locally by default | Same as the ticket | Direct identifiers masked before any permitted external text call | Consent confirmed for this use |
| Ticket data (labels, priority, routing) | No | Same as the ticket | Not applicable | Consent confirmed for this use |
| Agent and supervisor data | No | While the account is active | Not applicable | Contract |

- The data is simulated: the voicemails were recorded by people for data collection, not by real customers, and the emotions in them are acted. No real customer data is used in the initial deployment.
- Raw voice shall not be sent to a third-party AI service by default. Any external audio processing requires an explicit project decision and a recorded approval, and shall be recorded as a limitation in the results.
- If an approved external text model is ever used, direct identifiers shall be masked locally first, the payload shall be minimized, and a durable pre-transfer approval tied to the exact payload, provider, and purpose shall be required. That approval shall not authorize raw-audio transfer.
- Data residency: the data shall stay on the server the operator controls, in the region the operator chooses (Q2).

### 10.3 Transparency and fairness

- AI-generated content, actions, and evaluations shall be labeled and kept separate from human ones, in the UI and in the audit log (S4).
- Users shall be able to see why the AI acted: the ticket shows the transcript, the four fields with probabilities, the priority signals and reason, and the route reason.
- Quality shall be checked per class (per-field precision, recall, F1, and confusion matrices). A class with a macro-F1 below the AI9 threshold shall block release.

### 10.4 Compliance

- Regulations: the Egyptian data protection law applies to the operator's data handling. The system is a limited-risk AI system: it assists routing and a human decides, with human oversight (section 10.5). The exact regulatory review is an open question for the operator's legal advisor (Q6).
- Required documents: a data protection impact assessment (DPIA) and a model card for the MARBERTv2 classification models, before the production launch.

### 10.5 Human oversight

- Only an admin can change AI permissions, thresholds, script templates, and skill mappings. Only a supervisor can correct labels and reassign tickets. Changes shall be logged and reviewable.
- Kill switch: an admin or a supervisor shall be able to turn off automatic routing, effective immediately. When it is off, every new ticket goes to the Human Review Queue instead of being routed automatically.

---

## 11. Architecture, integrations and data

### 11.1 Technology stack

| Layer | Technology | Notes |
|---|---|---|
| Web app | Next.js, React, TypeScript | Responsive, RTL support for Arabic |
| Backend API | Python, FastAPI | Same language as the ML services; the prototype already used FastAPI |
| AI services | Python, PyTorch, transformers (MARBERTv2, Whisper large-v3), self-hosted | The validated models; no third-party LLM provider |
| Database | PostgreSQL | Tickets, agents, assignments, audit log |
| File storage | Local disk or S3-compatible object storage | Audio files and model artifacts |
| Cache / queue | Redis (queue and cache) | Async pipeline jobs; idempotency keys |
| DevOps | Docker, GitHub Actions | Containers, CI/CD, tests on every push |
| Observability | Structured logs, Prometheus, Grafana | App health, API performance, AI latency, alerts |

### 11.2 High-level architecture

The system has four parts: a web app (Next.js), a backend API (FastAPI), AI services (Python workers), and data stores (PostgreSQL plus object storage). The flow of one voicemail (WF1) is:

```
[Browser / Upload] -> [API: validate, create ticket, enqueue job]
   -> [Queue: Redis]
   -> [STT worker: Whisper large-v3 -> transcript, text_norm, STT metadata]
   -> [Classification worker: MARBERTv2 x4 -> four labels + probabilities]
   -> [Rules engine: confidence, priority_score, bucket, routing]
   -> [Ticket service: callback brief, store ticket, audit log]
   -> [API: WebSocket push -> Dashboard shows the ticket]
```

The API never blocks on model inference. Upload returns within 2 s (FR1). The pipeline runs asynchronously in workers. The dashboard receives status updates over WebSockets (NFR18). The rules engine (priority, routing, human review triggers) is separate from the models, so a rule change does not need a model redeploy. The model artifacts are versioned, and the model name, revision, and version are recorded on every ticket (AI1).

### 11.3 Integrations

| System | Purpose | Direction | Auth | AI access |
|---|---|---|---|---|
| None in the MVP | Not applicable | Not applicable | Not applicable | Not applicable |
| CRM (Phase 2) | Link tickets to customer records | Read | To be decided | Read-only |
| Telephony / voicemail system (Phase 2) | Voicemails arrive automatically | Inbound | To be decided | None (ingestion only) |

- The MVP has no external integrations. It is self-contained.
- Admins shall configure credentials, endpoints, and field mappings for any future integration. Credentials shall be stored securely.
- Webhooks shall be deduplicated, retries shall be configurable, and every call shall be logged.

### 11.4 Data model

**Voicemail**

| Field | Type | Required | Description |
|---|---|---|---|
| id | UUID | Yes | Primary key |
| organization_id | UUID | Yes | Tenant isolation |
| file_name | string | Yes | Original file name |
| file_path | string | Yes | Object storage path |
| format | string | Yes | WAV, MP3, or M4A |
| size_bytes | integer | Yes | At most 25,000,000 |
| duration_seconds | number | Yes | At most 60 |
| status | string | Yes | received, processing, ready, unassigned, in_progress, resolved, closed, failed |
| created_at | timestamp | Yes | Creation time |
| created_by | UUID | Yes | The user who uploaded it |

**Ticket**

| Field | Type | Required | Description |
|---|---|---|---|
| id | UUID | Yes | Primary key |
| voicemail_id | UUID | Yes | The voicemail this ticket came from |
| organization_id | UUID | Yes | Tenant isolation |
| transcript | text | Yes | Whisper transcript |
| text_norm | text | Yes | Normalized transcript, the model input |
| complaint_category | string | Yes, unless null (then Human Review) | One of the 11 values |
| complaint_urgency | string | Yes, unless null | high, medium, or low |
| customer_state | string | Yes, unless null | calm, frustrated, mad, satisfied, or unclear |
| churn_risk | string | Yes, unless null | at_risk or not_at_risk |
| probabilities | JSON | Yes | Per-field class probabilities, each summing to 1 within 0.001 |
| confidence | number | Yes | Minimum of the four fields' predicted-class probabilities |
| priority_score | integer | Yes, unless null | 1 to 6, null when any input is null |
| queue_priority | string | Yes, unless null | urgent, high, normal, or low |
| route_reason | text | Yes | Plain-language reason |
| assigned_agent_id | UUID | No | Null when UNASSIGNED |
| summary | text | Yes | Transcript truncated to 200 characters |
| customer_request | text | Yes | Sentence from the predicted category |
| suggested_script | text | Yes | Template for the predicted category |
| needs_human_review | boolean | Yes | True when a review trigger fires |
| review_reason | string | No | The reason, when flagged |
| model_version | string | Yes | Model name, revision, and version |
| created_at | timestamp | Yes | Creation time |
| updated_at | timestamp | Yes | Last update time |

**Agent**

| Field | Type | Required | Description |
|---|---|---|---|
| id | UUID | Yes | Primary key |
| organization_id | UUID | Yes | Tenant isolation |
| name | string | Yes | Agent name |
| skills | string array | Yes | Skill names, mapped to categories |
| capacity | integer | Yes | Maximum concurrent tickets |
| current_load | integer | Yes | Tickets currently assigned |
| available | boolean | Yes | Whether the agent can take tickets |
| active | boolean | Yes | Whether the agent is in the team |

**Assignment**

| Field | Type | Required | Description |
|---|---|---|---|
| id | UUID | Yes | Primary key |
| ticket_id | UUID | Yes | The ticket |
| agent_id | UUID | Yes | The agent |
| assigned_at | timestamp | Yes | When it was assigned |
| assigned_by | string | Yes | system or a user id |
| route_reason | text | Yes | Plain-language reason |
| status | string | Yes | active, released, or completed |

**AuditEvent**

| Field | Type | Required | Description |
|---|---|---|---|
| id | UUID | Yes | Primary key |
| organization_id | UUID | Yes | Tenant isolation |
| entity_type | string | Yes | ticket, agent, user, setting |
| entity_id | UUID | Yes | The record |
| action | string | Yes | created, classified, routed, corrected, reassigned, status_changed, setting_changed |
| actor | string | Yes | system or a user id |
| old_value | JSON | No | Value before the change |
| new_value | JSON | No | Value after the change |
| created_at | timestamp | Yes | When it happened |

**AIInteractionLog**

| Field | Type | Required | Description |
|---|---|---|---|
| id | UUID | Yes | Primary key |
| ticket_id | UUID | Yes | The ticket |
| stage | string | Yes | transcribe, classify, priority, route, brief |
| model | string | Yes | Model name and version, or "rules" for rule stages |
| input_ref | string | Yes | Reference to the input (not the raw audio) |
| output | JSON | Yes | The stage output |
| latency_ms | integer | Yes | Stage latency in milliseconds |
| created_at | timestamp | Yes | When it ran |

**EvalRun**

| Field | Type | Required | Description |
|---|---|---|---|
| id | UUID | Yes | Primary key |
| dataset_version | string | Yes | Dataset version |
| split | string | Yes | validation or test |
| model_version | string | Yes | Model name, revision, and version |
| config | JSON | Yes | Hyperparameters and settings |
| metrics | JSON | Yes | Per-field macro-F1, combined mean, per-seed values |
| guard_claim_id | string | No | The guard claim id, for test runs |
| created_at | timestamp | Yes | When it ran |
| created_by | string | Yes | Who ran it |

---

## 12. UX requirements

### 12.1 Web pages

| Page | Purpose | Key content and actions | Roles |
|---|---|---|---|
| Login | Sign in | Email, password, error feedback | All |
| Dashboard (supervisor queue) | See what needs attention and why | Prioritized queue, filters (bucket, category, status, agent), ticket counts, real-time updates | Supervisor, Admin |
| Ticket detail | Work one ticket | Transcript, four fields with probabilities, priority signals and reason, route reason, confidence, human review flag, summary, customer request, suggested script, audio playback, correct label, reassign, resolve | Supervisor, Agent, Admin |
| My tickets (agent view) | Focus on assigned work | Only the tickets assigned to the logged-in agent, with the callback brief | Agent |
| Human Review Queue | Clear flagged tickets | Flagged tickets with reasons, filters by reason, correct, assign, resolve | Supervisor, Admin |
| Agents and skills (admin) | Manage the team | Agent list, add/edit/deactivate, skills, capacity, availability, skill mapping | Admin |
| Settings (admin) | Configure the system | Confidence threshold, script templates per category, routing rules | Admin |
| Evaluation | Measure quality | Per-field macro-F1 on validation, routing agreement, human review rate, p95 latency, eval run history | Supervisor, Admin |
| Audit log | See what happened | Filterable log of every decision, correction, and configuration change | Supervisor, Admin |

### 12.2 Mobile screens

- Not applicable: the MVP is a responsive web application. A native mobile app is not in scope. The web app shall be usable on mobile browsers: the queue, ticket detail, and human review queue shall work on a phone screen, and admin configuration may stay desktop-only.

### 12.3 AI UX patterns

- Model outputs shall be marked clearly as model outputs, and a user shall be able to open the evidence (transcript, probabilities, signals) behind them.
- A supervisor shall be able to accept, edit, or reject a model label. Every correction shall be captured with the old value, the new value, who changed it, and when.
- The system shall show that processing is running (a processing state with the current stage), and shall always offer a clear path to human review.
- On handoff to Human Review, the supervisor shall see a summary, the context, and what the pipeline already did.
- The system shall never fail silently: it shall show what it could not do and why (for example, "transcription failed" with the error recorded).

### 12.4 UI behavior and consistency

- Role-based navigation: users shall only see pages and actions they are allowed to use.
- The same terminology and components shall be used on every page. The taxonomy terms (category, urgency, state, churn) shall be shown the same way everywhere.
- Layouts shall be responsive. The queue, ticket detail, and human review queue shall work on desktop and on a phone screen.
- Loading, empty, success, validation, and error states shall exist on every page.
- Confirmation shall be required before sensitive or irreversible actions (deactivating an agent, changing the confidence threshold, deleting a ticket).

---

## 13. Limitations

### 13.1 AI limitations

| ID | Limitation | Impact on users | Mitigation / workaround |
|---|---|---|---|
| L1 | Model outputs are probabilistic and can be wrong for the same input across seeds | Occasional incorrect labels | Confidence threshold plus handoff (AI3), human review sampling (AI10) |
| L2 | Labels come from a model and are being audited; they are not human-verified until the audit approves them | A label may be wrong and the model may repeat the error | Supervisor corrections feed a correction set; the audit continues; model outputs are labeled as model outputs (S4) |
| L3 | Quality is validated only for single-speaker Egyptian Arabic voicemail (simulated data) with English telecom terms | Lower quality outside this data | Hand off unsupported input; expand the eval set before adding a language or dialect |
| L4 | Audio emotion is not used; customer state comes from text only | Tone is not a signal | The audio model was tested and closed on 2026-11-17: audio carries no emotion signal for this data (silhouette -0.10, 4-class about 37% below the about 40% calm baseline) |
| L5 | The multi-task model underperforms the single-task model (mean validation macro-F1 0.75536 vs 0.7708) | One model cannot replace the four single-task models yet | Production uses single-task (AI1); multi-task is a Phase 2 option only if it beats single-task |
| L6 | Churn risk rests on only 7 at-risk validation rows, so the churn macro-F1 is fragile | One row changes the churn score materially | The eval report shows per-seed churn values and the at-risk row count, not only the mean (AI9) |
| L7 | The test set is touched once, under a guard, so the test score is a single evaluation | The test score cannot be repeated to check variance | The validation mean and standard deviation across 5 seeds are reported alongside the test score |

### 13.2 Technical and platform limitations

| ID | Limitation | Impact on users | Mitigation / workaround |
|---|---|---|---|
| L8 | Inference needs a GPU for the latency budget; on CPU alone the pipeline is slower | p95 latency above 10 s on CPU-only deployment | Deploy with a GPU (A4); measure and report the actual latency per deployment |
| L9 | Requires the server; no offline mode | The product does not work without the server | Not applicable in the MVP; the server is the deployment target |
| L10 | Supported platforms: modern browsers (Chrome, Edge, Firefox, Safari, current versions) on desktop and mobile browsers | Old browsers may not work | Document the supported browsers; the UI degrades gracefully |
| L11 | No real telephony, SIP, or CRM integration in the MVP | Voicemails arrive by upload or browser recording, not automatically | Phase 2 integrations (section 11.3) |

### 13.3 Business and operational limitations

| ID | Limitation | Impact on users | Mitigation / workaround |
|---|---|---|---|
| L12 | The operator must configure agents, skills, script templates, and thresholds before the system routes well | Setup effort before value | Default templates and the validated skill mapping (FR20) ship with the MVP |
| L13 | Single-tenant in the MVP; one organization per deployment | A second organization needs a second deployment | The data model carries an organization id (FR24); multi-tenancy is a Phase 2 feature |
| L14 | The product is built for the operator that validated it; the first deployment is for that operation | The product is not yet proven on another operation's data | The eval suite and the release gates (AI9) are rerun for a new operation before launch |

---

## 14. Assumptions and dependencies

- A1 Validated ML core: the MARBERTv2 single-task models (Sira's 2e-5 run, 5 seeds), the SVR Voicemail Corpus (5,096 clean rows, frozen split), the taxonomy, the priority formula, and the routing rules are available and carried over from the prototype. The checkpoints are on Drive (verified handoff, 20 of 20 checkpoints, SHA-256 checked).
- A2 Deployment: a server with a GPU is available for inference (see NFR5 and L8). The exact provider and region are an open question (Q2).
- A3 Human oversight: the operator configures agents, skills, script templates, and thresholds for its own operation (WF4).
- A4 Evaluation data: the validation set (1,003 rows) and the test set (518 rows) are available. The test set is evaluated once, under the guard.
- A5 Input: voicemails are single-speaker Egyptian Arabic, up to 60 seconds, in WAV, MP3, or M4A format.
- A6 Data: the initial deployment uses the simulated corpus. No real customer data is used until the operator approves it and the privacy review is done.
- A7 Labels: the labels are model-generated and under audit. Corrections from supervisors feed a correction set for a future retrain.
- A8 Build: The production build follows this PRD. The SVR Team is the product owner and approves the build at each gate.

---

## 15. Build requirements and resources

### 15.1 Team and roles

| Role | Count | Key skills | Allocation | Needed from |
|---|---|---|---|---|
| Product owner | 1 | Requirements, decisions, acceptance | Part-time, at each gate | Start |
| Build team | 1 | Full-stack build from a PRD, Python, TypeScript, Docker | Full-time during the build | Start |
| AI / ML reviewer | 1 | Specification, verification, review of the build against this PRD | Part-time, at each gate | Start |
| Operator (supervisor and agents) | 1 supervisor, 2 or more agents | Customer-care operation, label correction, threshold decisions | Part-time, for acceptance testing | Month 3 |

### 15.2 Skills and knowledge

| Skill area | Needed for | Team has it? | Plan to close gap |
|---|---|---|---|
| Python, FastAPI, PyTorch, transformers | AI1, AI2, section 11.1 | Yes | None |
| MARBERTv2 and Whisper integration | AI1, AI2 | Yes, with this PRD as the spec | None |
| Arabic NLP (Egyptian dialect, text normalization) | AI1, AI2, AI8 | Yes (validated in the prototype; the corpus and the config are provided) | None |
| Next.js, React, TypeScript, RTL layouts | Section 11.1, NFR11 | Yes | None |
| PostgreSQL, Redis, Docker, CI/CD | Section 11.1 | Yes | None |
| AI evaluation (macro-F1, guard, release gates) | AI9, AI10 | Yes (validated in the prototype; Aya's guard and harness are the reference) | None |
| Security and single-tenant architecture | NFR1 to NFR3 | Yes | Review at the security gate |
| Telecom customer-care domain | FR9, FR10, FR20 | Partly (the prototype team defined the taxonomy and rules; the operator confirms them) | Operator review at the Month 3 acceptance test |

### 15.3 Development tools and software

| Category | Tool | Purpose | License / cost |
|---|---|---|---|
| Source control | GitHub | Code, reviews, issues | Existing account |
| Project management | GitHub issues and milestones | Backlog, gates, tracking | Existing account |
| IDEs | VS Code | Development | The SVR Team's arrangement |
| API testing | Postman or curl | API development and testing | Free |
| CI/CD | GitHub Actions | Build, test, deploy | Free for the repo size |
| Monitoring and logging | Prometheus, Grafana, structured logs | Errors, performance, alerts | Open source |
| Documentation | Markdown in the repo, OpenAPI | Specs, API docs, guides | Free |
| Testing | pytest, Playwright | Unit, integration, end-to-end tests | Open source |

### 15.4 Infrastructure and environments

| Environment | Purpose | Key resources | Est. monthly cost |
|---|---|---|---|
| Local | Day-to-day development | Docker, local database, model files | None |
| Development / test | Integration and QA | App server, database, object storage, queue | To be decided (Q2) |
| Staging | Pre-release, demos, UAT, load tests | Production-like setup at smaller scale | To be decided (Q2) |
| Production | Live operation | Scaled app and AI services, managed database, backups | To be decided (Q2) |
| GPU / model hosting | Inference (Whisper large-v3, MARBERTv2) | GPU server (see A2) | To be decided (Q2) |

- Cloud provider and region: to be decided (Q2). The data shall stay on a server the operator controls.
- Domains and certificates: to be decided (Q2). TLS is required (NFR2).

### 15.5 Third-party accounts, APIs and access

- Not applicable in the MVP: the system uses no third-party LLM provider, no messaging channel, no payment provider, and no CRM. The models are self-hosted.
- If a cloud provider is chosen for hosting, a billing account and access roles are needed (Q2). Lead time is days.
- No long-lead third-party account (business verification, app store review) is needed for the MVP.

### 15.6 Data needed for the build

| Data | Purpose | Source | Volume | Ready by |
|---|---|---|---|---|
| SVR Voicemail Corpus (clean) | Training data reference and eval sets | Repo, final/clean_training_train.csv, _val.csv, _test.csv | 5,096 rows | Available now |
| MARBERTv2 checkpoints (Sira's 2e-5 run, 5 seeds) | Production model artifacts | Drive handoff (verified, 20 of 20 checkpoints, SHA-256 checked, 36.48 GiB) | 20 checkpoints | Available now |
| Whisper large-v3 model | Transcription | Hugging Face (downloaded at build time) | 1 model | Available now |
| Taxonomy, priority formula, routing rules, skill mapping | Product configuration | This PRD (sections 7, 8, Appendix) | 11 categories, 4 fields, 1 formula | In this PRD |
| Class weights | Training reference (train-only) | final/class_weights.json | 4 fields | Available now |
| Synthetic demo data | Development, demos, load testing | Generated from the corpus (a subset, clearly marked as demo) | 100 tickets | Month 1 |

### 15.7 Hardware and devices

- Developer machines: 16 GB RAM or more for Docker workloads.
- Production server: a GPU server for inference (see A2 and L8). The exact GPU model is an open question (Q2).
- Test devices: a desktop browser (Chrome, Edge, Firefox, Safari, current versions) and a mobile browser for responsive checks. No telephony hardware in the MVP.

### 15.8 Readiness checklist (before development starts)

- This PRD is approved by the SVR Team.
- The MARBERTv2 checkpoints are available (Drive handoff, verified).
- The dataset is available (repo, frozen split).
- The deployment target (provider, region, GPU) is decided (Q2).
- The repository, CI/CD, and project tools are set up.
- The architecture and data model (section 11) are reviewed.
- The budget for infrastructure is approved (section 19).

---

## 16. Deliverables

| ID | Deliverable | Description |
|---|---|---|
| D1 | Web application | Next.js, React, TypeScript; dashboard, ticket detail, agent view, Human Review Queue, admin pages, evaluation page |
| D2 | Mobile application | Not applicable in the MVP (responsive web only, section 12.2) |
| D3 | Backend API | FastAPI; auth, RBAC, intake, tickets, agents, settings, audit log; OpenAPI docs |
| D4 | AI services | STT worker (Whisper large-v3), classification workers (MARBERTv2 single-task, four fields), rules engine (confidence, priority, routing), guardrails |
| D5 | Eval suite and results | Eval suite on validation, guarded final test evaluation, release gates (AI9), latest scores |
| D6 | Integrations and API layer | REST APIs, WebSockets for real-time updates, OpenAPI docs; no external integrations in the MVP |
| D7 | Database and data layer | PostgreSQL schema, indexing, migrations, backups, object storage for audio |
| D8 | Deployment and DevOps | Docker containers, CI/CD, monitoring, logging, backup and restore |
| D9 | Documentation | Architecture, data model, API, deployment, AI configuration, user and admin guides |
| D10 | Testing | Unit, integration, security, load, and AI behavior test results |
| D11 | Final demonstration | End-to-end run of workflows WF1 to WF5 |

---

## 17. Timeline

Duration: 4 months. MVP (section 6) by month 3. Production ready by month 4. The start date is to be decided when the SVR Team approves this PRD.

| Period | Backend and DevOps | Frontend and UX | AI and Data | Milestone |
|---|---|---|---|---|
| Month 1 | Architecture, schema, auth, RBAC, CI/CD, Docker | UX research, design system, wireframes, login and dashboard shell | Model serving (Whisper, MARBERTv2), eval suite on validation, guard | Foundation |
| Month 2 | Intake, queue, ticket API, WebSockets | Upload, recording, ticket detail, queue | STT plus classification pipeline, priority and routing rules, callback brief | Core pipeline working end to end |
| Month 3 | Agents and skills, settings, audit log, monitoring | Human Review Queue, agent view, admin pages, evaluation page | Guarded final test evaluation, release gates, monitoring dashboards | MVP complete |
| Month 4 | Hardening, load tests, backup and restore tests, security review | Accessibility, usability tests | Tuning, monitoring, final eval report | Production ready |

---

## 18. Key success indicators (KSIs)

| Period | Milestone | KSI | Success target |
|---|---|---|---|
| Month 1 | Foundation | Auth and schema complete | 100% of auth flows implemented and tested |
| Month 1 | AI foundation | Model serving | The production-served model reproduces the validated validation numbers within the AI9 tolerance |
| Month 2 | Core pipeline | End-to-end pipeline | WF1 works end to end: a voicemail becomes a ticket with four fields, a priority, and an assignment |
| Month 3 | MVP | AI accuracy | All four fields meet the AI9 thresholds on the validation set |
| Month 3 | MVP | Routing | Routing agreement is at least 80% on the validation set |
| Month 3 | MVP | Performance | p95 end-to-end latency is at most 10 s for a 60 s clip; a valid upload appears in processing within 2 s |
| Month 3 | MVP | Test evaluation | The guarded final test evaluation has run once and its scores are reported |
| Month 4 | Launch | End-to-end success | Workflows WF1 to WF5 work with no open critical defects; the security review passed |

---

## 19. Cost and pricing

### 19.1 Estimated cost

| Item | Assumption | Monthly cost | One-time cost |
|---|---|---|---|
| Team | Built by the SVR Team | To be decided (the SVR Team's arrangement) | To be decided |
| Cloud infrastructure (server with GPU, database, storage, backups) | Provider and region to be decided (Q2) | To be decided (Q2) | None |
| AI usage | No per-call provider fee; models are self-hosted, so the cost is the server compute only | Included in infrastructure | None |
| Third-party APIs and tools | None in the MVP | None | None |
| Total | | To be decided (Q2) | To be decided |

### 19.2 Product pricing

The MVP is built for the operator that validated the product. No pricing applies to the MVP build itself. The product pricing model (per seat, per ticket, or subscription) is an open question for the SVR Team (Q4), to be decided before a second deployment. The AI usage is a variable cost only through server compute, since there is no per-call provider fee.

---

## 20. Risks

| ID | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R1 | Production model quality below the AI9 threshold (the served model does not reproduce the validated numbers) | Medium | High | Validation parity check before release; the release gate blocks launch; Human Review catches low-confidence tickets | AI / ML lead |
| R2 | Test score lower than validation (the test set is harder than validation) | Medium | Medium | Report the test score honestly; do not tune on the test set; the test is the truth | AI / ML lead |
| R3 | GPU or server cost higher than expected | Medium | Medium | Measure the actual cost in staging; the latency budget is measured per deployment; a CPU fallback is documented with a relaxed latency target | Engineering lead |
| R4 | Labels are wrong (the audit finds label errors after launch) | Medium | High | Supervisor corrections feed a correction set; a retrain is planned as a model update (WF5); model outputs are labeled as model outputs | Product owner |
| R5 | Scope expands before the core is stable | Medium | Medium | Gate work by the MVP exit criteria (section 6.3); The build covers only what this PRD specifies | Product owner |
| R6 | Build does not match this PRD | Medium | High | Review gates at the end of each month (section 17); acceptance tests against the FR and AI requirements; The SVR Team verifies the build | Product owner |
| R7 | A supervisor or agent misuses the system (for example, bulk actions without review) | Low | Medium | RBAC (FR23), audit log (FR18), confirmation before sensitive actions (section 12.4) | Admin |
| R8 | The operator does not configure agents, skills, and thresholds | Medium | Medium | Default templates and the validated skill mapping ship with the MVP (FR20); the admin setup is part of the Month 3 acceptance test | Product owner |

---

## 21. Open questions

- Q1 Retention period: how long are voicemails and tickets kept? The default in this PRD is 90 days, configurable. Owner: SVR Team. Due: before the production launch.
- Q2 Deployment target: which provider, region, and GPU model hosts the production server? Owner: SVR Team. Due: before Month 1 starts.
- Q3 Confidence threshold: is 0.5 the right threshold? It is PROPOSED in this PRD (AI3). It shall be confirmed from the validation data before launch. Owner: SVR Team. Due: Month 3.
- Q4 Pricing model: per seat, per ticket, or subscription, for a second deployment? Owner: SVR Team. Due: before a second deployment.
- Q5 Agent time saved: what is the target for agent time saved per callback? To be set after one month of operation. Owner: SVR Team. Due: one month after launch.
- Q6 Regulatory review: which specific regulations apply to the operator's deployment, and is a DPIA required before launch? Owner: operator's legal advisor. Due: before the production launch.
- Q7 First deployment: is the first production deployment for the SVR Team, or for a telecom operator? Owner: SVR Team. Due: before Month 1 starts.
- Q8 The 3e-5 five-seed run: the sweep rule (run the best lr, 3e-5, on all 5 seeds) is incomplete (1 of 20 tasks done). Since the production model is 2e-5, this run is not needed for the production build. Confirm it is dropped. Owner: SVR Team. Due: before Month 1 starts.

---

## Appendix

### A. Validated results (the evidence base)

| Item | Value |
|---|---|
| Winner model | MARBERTv2 (UBC-NLP/MARBERTv2), single-task, lr 2e-5, batch 16, epochs 3, max seq len 128, dropout 0.1, class weights in the loss, 5 seeds (42, 1337, 2023, 7, 99) |
| Sira's own run, validation combined macro-F1 | 0.7708 (category 0.7872, urgency 0.7211, state 0.7471, churn 0.8277) |
| Fair re-run (independent, Colab T4), validation combined macro-F1 | 0.7907 (category 0.7895, urgency 0.7250, state 0.7442, churn 0.9041) vs EgyBERT 0.6718; MARBERTv2 wins every field |
| LR sweep, seed 42, combined macro-F1 | 1e-5: 0.6760; 2e-5: 0.7661; 3e-5: 0.7778 (best on seed 42, but the gain is one churn row; 2e-5 is better on the other three fields) |
| Multi-task (Kendall, lr 2e-5), mean validation macro-F1 | 0.75536 across 5 seeds, lower than single-task; production model is single-task |
| Test model for the final evaluation | 2e-5, Sira's own 5-seed run |
| Dataset | SVR Voicemail Corpus: 6,522 voicemails, 12.63 hours; clean set 5,096 rows (train 3,575, validation 1,003, test 518), split frozen; 655 worst transcripts excluded (Whisper logprob below -0.30) |
| Audio emotion model | Closed 2026-11-17: audio carries no emotion signal (silhouette -0.10, 4-class about 37% below the about 40% calm baseline); customer state comes from text only |

### B. Taxonomy

| Field | Values |
|---|---|
| complaint_category (11 values) | network_and_connectivity, billing_and_charges, balance_and_data, app_and_account, branch_and_staff, no_reply_or_long_wait, cancellation_request, thanks_or_praise, other, offers_and_packages, sim_services (greeting_only has 0 rows) |
| complaint_urgency (3 values) | high, medium, low (from the complaint only, never from tone) |
| customer_state (4 values scored) | calm, frustrated, mad, satisfied (unclear has 0 train rows, 1 validation row, excluded from the state metric) |
| churn_risk (2 values) | at_risk, not_at_risk (only on explicit departure language) |

### C. Priority formula

priority_score equals complaint_urgency (high 3, medium 2, low 1) plus churn_risk (at_risk 2, not_at_risk 0) plus customer_state (mad 1, frustrated 1, calm 0, satisfied 0, unclear 0). Range 1 to 6. Buckets: 6 is urgent, 5 is high, 3 to 4 is normal, 1 to 2 is low. If any input is null, priority_score and queue priority stay null and the ticket goes to Human Review. No eligible agent means the ticket stays UNASSIGNED and enters the Human Routing Queue. No tier policy. First eligible agent in seed order. Fusion is disabled. language_mix is disabled.

### D. STT output format v1 (10 columns)

file, model, text, text_norm, min_avg_logprob, max_no_speech_prob, needs_review, review_reasons, dup_text_size, error.

### E. Glossary

- **Complaint category:** what kind of issue the customer reports.
- **Complaint urgency:** how time-sensitive or impact-heavy resolving that issue is.
- **Customer state:** the customer's interaction state, assessed under agreed label definitions, from the words.
- **Speech-to-text (STT):** converting a voice recording to text.
- **Churn risk:** estimated risk the customer may leave the service, separate from complaint urgency.
- **WER:** word error rate, measured against a human-verified transcript.
- **Macro-F1:** unweighted average of per-class F1 scores, useful when class counts differ.
- **Kendall:** Kendall uncertainty weighting, the multi-task loss used in the prototype.
- **Single-task:** one model per field (four MARBERTv2 models, one for each field).
- **Multi-task:** one shared encoder with four heads, trained jointly.
- **Guard:** the test-once guard, which logs a claim before the test labels are read, so the test set is evaluated once per model and dataset version.
