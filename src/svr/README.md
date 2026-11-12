# SVR Phase 1: pipeline skeleton, API and demo (Role 6, Arafa)

Branch: `team/arafa-systems-demo`.
Source of truth: **SVR Contracts v1.0** (`arafa-contracts-v1.md` in the
competition goal files), `schema_version: 1`,
`label_version: "taxonomy-2026-11-11"`. Role guide: SVR-TEAM-04 Role 6.

## Merge note, 2026-11-12

Two Phase 1 skeletons existed in parallel: this one under `src/svr/` and
a second one under `svr_pipeline/` in a separate worktree. This
implementation is the one kept, and the three behaviours worth keeping
from the second one were ported into it:

1. **Queued placeholder safety.** A queued/processing ticket carries
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
| Triage | `stages/triage.py` | Mock: fixture route reason, seeded-agent assignment |
| Ticket | `stages/ticket.py` | Assembles the contracts section 3.5 Ticket |

API (`src/svr/api.py`, contracts section 6):

- `POST /api/voicemails`: 202 + ticket id, ticket visible as
  queued/processing within 2 seconds, analysis in the background. Invalid
  format, size or duration is rejected with a clear 400 error.
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

MOCK (fixed values, contracts section 9 fixture, no real audio, no real
transcript, no real customer data, no model loaded, no network call):

- STT transcript: `[fixture transcript]`
- Classification: `network_and_connectivity` / `medium` / `frustrated` /
  `not_at_risk`, confidence 0.9
- Triage: fixed route reason, assignment to the first seeded demo agent
  with a matching skill, on shift, with capacity
- `priority_score`: null, `customer_state_final`: null, `cached`: false

REAL (implemented and tested): schema validation with the approved enums,
null/review rules, input validation, per-stage timing, p95 helper,
in-memory ticket store with audit events, seeded agents, API, demo display.

## What Phase 2 swaps in

Same function signatures, mocks replaced one at a time, each tested in
isolation before moving on (Role 6 Phase 2):

- Sira: `stages/stt.py` → Whisper large-v3 transcription; `stages/intake.py`
  → 16 kHz mono WAV normalization, MP3/M4A duration measurement;
  `stages/voice.py` → wav2vec2 XLS-R 300M voice evidence.
- Lama: `stages/classification.py` → fine-tuned EgyBERT / MARBERTv2 text
  model (single-task first, then multi-task, four heads).
- Ibthal: `stages/triage.py` → real triage rules and ticket generator,
  priority formula once agreed.
- Aya: evaluation harness plugs into `latency.py` reporting.

## Open conflicts, do not guess (contracts section 10)

- **Complaint category 9 vs 10 classes.** Model selection report says 9,
  approved taxonomy lists 10. This build uses the 10 approved values.
  Hazem to confirm whether the report excludes `greeting_only` or `other`.
- **New, observed 2026-11-12 in the audit app:** the audit app's Category
  list has **11 options**, and `Offers and packages` appears there (seen on
  voicemail 3) but is not among the 10 approved values. So the count is now
  9 (report) vs 10 (taxonomy) vs 11 (audit app). Flagged for Hazem, not
  resolved here; this build still uses the 10 approved values and rejects
  anything else.
- **`language_mix` values undefined.** Producers send null. The mock does
  not force a review on a null mix alone, because the section 9 fixture is
  the approved Phase 1 mock output; once Hazem defines the values, the
  "null mix goes to review" rule is switched on.
- **Priority formula, ranges, thresholds, weights undefined.** Owner
  Ibthal, Hazem approves. `priority_score` and `queue_priority` stay null.
- **Skill-to-category mapping and tier policy undefined.** Routing uses
  only the seeded agents' listed skills and says so in `route_reason`.
- **Fusion rules undefined.** `customer_state_final` stays null; the Ticket
  model rejects any non-null value. Fusion is a third field when enabled,
  never a replacement for text/voice evidence.
- **Dataset rights, consent, retention, processing locations.** Hazem.
  No real audio is used anywhere in this skeleton.
- **Python baseline, storage choice.** Team. Phase 1 uses an in-memory
  store; SQLite is a candidate for the local demo.
- **Competition deadline, judging criteria, demo format.** Hazem.

## Known limitations

- MP3/M4A duration is not measured at intake: the stdlib cannot parse
  those containers, so duration is checked for WAV only
  (`duration_checked: false` on the evidence). Sira's audio pipeline
  measures it in Phase 2.
- The in-memory store is per-process: restarting the API clears tickets.
- `cached` is always false: cached output is allowed only for the exact
  preapproved demo file (contracts section 4.6) and no such file exists yet.
- PATCH named-agent reassignment still needs a contracts decision: the
  Ticket object carries no agent id field, the agent id lives on the
  TriageDecision. PATCH covers ticket status, assignment status and a
  validated `assigned_agent_id` for the audit trail only.
