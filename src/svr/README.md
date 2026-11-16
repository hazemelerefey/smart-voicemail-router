# SVR Phase 1: pipeline skeleton, API and demo (Role 6, Arafa)

Owner: Ahmed Gamal Arfa ([@AhmdArFa](https://github.com/AhmdArFa)),
Systems Integration and Demo Engineer.
Branch: `team/arafa-systems-demo`.
The base branch includes pushed Phase 1 audit fixes for Hazem's issues #2-#9,
verified live 13 November 2026. This branch includes the Phase 1 demo routing
integration. Tests: 130 passed.
Last update: 16 November 2026.
Source of truth: **SVR Contracts v1.0** (`arafa-contracts-v1.md` in the
competition goal files), `schema_version: 1`,
`label_version: "taxonomy-2026-11-15"`. Role guide: SVR-TEAM-04 Role 6.

## Merge note, 2026-11-12

Two Phase 1 skeletons existed in parallel: this one under `src/svr/` and
a second one under `svr_pipeline/` in a separate worktree. This
implementation is the one kept, and the three behaviours worth keeping
from the second one were ported into it:

1. **Queued placeholder safety.** A processing ticket carries
   `needs_human_review: true` and no labels until its run finishes, so
   it can never be mistaken for an answer.
2. **WebSocket live updates.** Connected `/ws/queue` clients receive a
   `ticket_update` broadcast when a run completes, in addition to the
   snapshot on connect.
3. **Metadata-only background runs.** The endpoint validates the upload
   and measures it, then discards the bytes. The background task carries
   only the measured metadata (filename, size, duration); the pipeline
   runs on `AudioMeta`, never on audio bytes. Phase 1 persists no audio.

The `svr_pipeline/` worktree was retired into this implementation after
the merge was verified; its package layout, contracts separation, demo
and test layout were not ported. A push broadcaster refinement
(dedicated broadcaster task, reconnect handling) stays a Phase 3 item.

The two commits were re-attributed to
[@AhmdArFa](https://github.com/AhmdArFa) via the GitHub noreply email, so
they show under his account; the content is unchanged.

## How to run

Python 3.11 or newer (developed on 3.12.3). From the repo root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r src/svr/requirements.txt
```

API (FastAPI + uvicorn, http://127.0.0.1:8000, HTML demo at `/`):

```bash
bash src/svr/run_api.sh
# or: PYTHONPATH=src .venv/bin/python -m svr
```

Gradio demo (http://127.0.0.1:7860):

```bash
bash src/svr/run_demo.sh
```

The Gradio launcher unsets the proxy environment variables first. This
sandbox's `no_proxy` contains IPv6 entries (`[::1]`) that httpx, used by
Gradio at import time, cannot parse, so `import gradio` fails with
`httpx.InvalidURL: Invalid port: ':1]'` unless they are unset. The API and
the plain HTML demo at `GET /` do not need this workaround.

Tests:

```bash
.venv/bin/python -m pytest tests/ -q
```

## What this is

Pipeline stages as separate modules under `src/svr/stages/`, data flowing
first stage to last, with per-stage status and `stage_timing_ms` plus
`processing_ms` on every ticket:

| Stage | Module | Phase 1 behaviour |
|---|---|---|
| Intake | `stages/intake.py` | Validates WAV/MP3/M4A, 25 MB, 60 s max (WAV duration via stdlib `wave`) |
| STT | `stages/stt.py` | Mock: fixed fixture transcript |
| Text analysis | `stages/classification.py` | Mock: fixed fixture fields |
| Voice evidence | `stages/voice.py` | Skipped, no voice evidence yet |
| Triage | `stages/triage.py` | Ibthal Phase 1 integration: validates evidence, computes the approved score and bucket when inputs are complete, reserves an eligible demo agent, and explains the route |
| Ticket | `stages/ticket.py` | Assembles the contracts section 3.5 Ticket |

API (`src/svr/api.py`, contracts section 6):

- `POST /api/voicemails`: 202 + ticket id, ticket visible as
  processing within 2 seconds, analysis in the background. Invalid
  format, size or duration is rejected with a clear 400 error (duration
  enforced for WAV only; MP3/M4A duration is measured in Phase 2 by the
  Audio/Speech role).
- `GET /api/tickets/{id}`: ticket fields, evidence, timing, route reason,
  audit events.
- `GET /api/agents`: seeded demo agents only, no real people.
- `PATCH /api/tickets/{id}`: manual status / reassignment, audit event.
- `GET /api/latency`: p95 report with hardware recorded (section 7).
- `WS /ws/queue`: queue snapshot on connect, plus a live `ticket_update`
  broadcast when a run completes. A push broadcaster refinement stays
  Phase 3.
- `GET /`: plain HTML demo (upload, run, ticket display).
- `GET /health`: mode, schema and label versions.

## What is mock vs real

MOCK inference (fixed values, contracts section 9 fixture, no real audio, no real
transcript, no real customer data, no model loaded, no network call):

- STT transcript: `[fixture transcript]`
- Classification: `network_and_connectivity` / `medium` / `frustrated` /
  `not_at_risk`, confidence 0.9
- Triage: assignment to the first seeded demo agent with a matching skill,
  on shift, and with capacity; when there is no eligible match the ticket
  stays `unassigned` and requests human routing review (PRD US-5).
- Priority uses the approved urgency, churn-risk, and text-state points; if
  any scoring input is missing, both priority fields stay null and the ticket
  requires human review. `customer_state_final`: null; `cached`: false.

REAL (implemented and tested): schema validation with the approved enums,
null/review rules, input validation, per-stage timing, p95 helper,
in-memory ticket store with audit events, seeded agents, API, demo display.

## What Phase 2 swaps in

Same function signatures, mock inference components replaced one at a time,
each tested in isolation before moving on (Role 6 Phase 2):

- Sira: `stages/stt.py` → Whisper large-v3 transcription; `stages/intake.py`
  → 16 kHz mono WAV normalization, MP3/M4A duration measurement;
  `stages/voice.py` → wav2vec2 XLS-R 300M voice evidence.
- Lama: `stages/classification.py` → fine-tuned EgyBERT / MARBERTv2 text
  model (single-task first, then multi-task, four heads).
- Ibthal: evaluate the integrated `stages/triage.py` on real model outputs;
  any further priority changes require approval. Ticket assembly remains in
  `stages/ticket.py`.
- Aya: evaluation harness plugs into `latency.py` reporting.

## Open decisions and approved policies (contracts section 10)

- **Complaint category.** The approved PRD taxonomy has 11 values:
  `network_and_connectivity`, `billing_and_charges`, `balance_and_data`,
  `app_and_account`, `branch_and_staff`, `no_reply_or_long_wait`,
  `cancellation_request`, `thanks_or_praise`, `other`,
  `offers_and_packages`, and `sim_services`. The runtime schema follows
  this list and rejects `greeting_only`. Older annotation and dataset
  artifacts may still need alignment by their data owners before training
  or evaluation.
- **`language_mix` values undefined.** Producers send null. The mock does
  not force a review on a null mix alone, because the section 9 fixture is
  the approved Phase 1 mock output; once Hazem defines the values, the
  "null mix goes to review" rule is switched on.
- **Priority policy approved and implemented.** Score is urgency points
  (high 3, medium 2, low 1) plus churn points (at-risk 2, not-at-risk 0)
  plus one point for text state `mad` or `frustrated`. Buckets are 1-2
  `low`, 3-4 `normal`, 5 `high`, and 6 `urgent`. If any scoring input is
  missing, both priority fields stay null and human review is required;
  explicit `unclear` contributes 0.
- **Production skill-to-category mapping and tier policy undefined.** For
  this Phase 1 demo, `offers_and_packages` routes to `agent-demo-billing`
  and `sim_services` routes to `agent-demo-network`. Routing uses only the
  seeded agents' listed skills, shift, and capacity; an ineligible category
  stays `unassigned` and requests human routing review. No production tier
  or tie-breaking policy is inferred.
- **Retry policy undefined for Phase 1.** The mock pipeline has no provider
  call to retry; stage failures go to `needs_review`. Provider-specific or
  controlled retries require the applicable provider contract/approval.
- **Fusion rules undefined.** `customer_state_final` stays null; the Ticket
  model rejects any non-null value. Fusion is a third field when enabled,
  never a replacement for text/voice evidence.
- **Dataset rights, consent, retention, processing locations.** Hazem.
  No real audio is used anywhere in this skeleton.
- **Python baseline, storage choice.** Team. Phase 1 uses an in-memory
  store; SQLite is a candidate for the local demo.
- **Competition deadline, judging criteria, demo format.** Hazem.

## Open demo posture

This is an open local demo, not a production service: no authentication,
no rate limiting, and no request-size limit at the app layer beyond the
25 MB upload limit (enforced while the upload streams in). Any caller
can submit a voicemail, read any ticket, and PATCH any ticket's status
or assignment; audit actors are validated against a known set, but that
is not authentication. Run it on localhost only, never expose it
publicly, and never point it at real customer data. Authentication and
rate limiting are a Phase 3 decision, not a Phase 1 requirement.

## Known limitations

- MP3/M4A duration is not measured at intake: the stdlib cannot parse
  those containers, so duration is checked for WAV only
  (`duration_checked: false` on the evidence). Sira's audio pipeline
  measures it in Phase 2.
- The in-memory store is per-process: restarting the API clears tickets.
- `cached` is always false: cached output is allowed only for the exact
  preapproved demo file (contracts section 4.6) and no such file exists yet.
- Agent capacity is concurrent load: assigning a run consumes one unit,
  released when the run finishes or the ticket is reassigned/unassigned.
  Loads reset when the API restarts.
