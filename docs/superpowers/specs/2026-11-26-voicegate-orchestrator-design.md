# VoiceGate Orchestrator & LangGraph Agentic Transcript Gate Design

**Date:** 2026-11-26
**Status:** Implemented & Verified
**System Name:** VoiceGate Orchestrator

---

## 1. Purpose

Add a local-first agentic transcript verification gate (`AgenticTranscriptGate` built on **LangGraph** `StateGraph`, powered by `qwen2.5:3b` via local Ollama) orchestrated by **VoiceGate Orchestrator** (`VoiceGateOrchestrator`). The agent manages the full 6-stage local AI pipeline so raw Whisper `large-v3` Egyptian Arabic + telecom transcripts are inspected, iteratively audited and repaired in telecom context, validated against strict anti-hallucination and acoustic guardrails, normalized cleanly for `MARBERTv2`, and displayed transparently alongside raw Whisper evidence in the UI.

## 2. Core Principles & Security Boundaries

1. **100% Local-First Execution (PRD AI6, AI7, DPIA):**
   - No transcript, ticket, or audio ever leaves localhost/self-hosted infrastructure.
   - Configured Ollama endpoints are strictly validated to loopback hosts (`127.0.0.1`, `localhost`, `::1`) via `validate_loopback_url()`.
2. **Sequential Memory Safety (`SVR_LOW_MEMORY_MODE=1`):**
   - On CPU hosts (~7.73 GB total RAM), Whisper `large-v3`, `qwen2.5:3b` (1.9 GB), and 4x MARBERTv2 checkpoints never stay resident concurrently.
   - `VoiceGateOrchestrator` enforces explicit sequential ownership: `WhisperSTTService.unload()` after transcription, `AgenticTranscriptGate.unload()` / Ollama `keep_alive=0` after verification, followed by sequential MARBERTv2 classification.
3. **Grounded Evidence Preservation:**
   - `voicemail.stt_v1_json` remains untouched (exact locked 10-column Whisper v1 output).
   - `ticket.transcript` and `ticket.text_norm` store the verified (or safely preserved raw) transcript consumed by MARBERTv2, Brief generation, and Search.
   - `ticket.transcript_verification_json` stores `raw_transcript`, `corrected_transcript`, `correction_applied`, `rounds_run`, `confidence`, `status`, `model`, `backend_used`, `changes`, and structured `trace` rounds.
4. **Fail-Safe Human Review Escalation:**
   - If `qwen2.5:3b` cannot reach confidence (`>= 0.75`) within `max_iterations` (default `4`), hits anti-hallucination guardrails, detects severe acoustic degradation (`min_avg_logprob < -0.75`), or experiences a runtime/unavailability error, VoiceGate Orchestrator falls back to the safest grounded transcript and routes the ticket to Human Review (`needs_human_review = True`, `review_reason = "uncertain_transcript"` or upstream error blocker).

## 3. Architecture

### 3.1 `AgenticTranscriptGate` (`backend/svr_platform/services/agentic_gate.py`)

Responsible for stateful, bounded iterative transcript auditing and Egyptian telecom word repair using `langgraph.graph.StateGraph`:
- **Graph Topology:** `pre_repair -> audit -> confidence_check -> finalize -> END` (with conditional loop from `confidence_check` back to `audit` when confidence `< early_stop_confidence` (`0.90`) or a guardrail critique was injected, up to `max_iterations=4`).
- **Backends:**
  1. **Local Ollama HTTP (`http://127.0.0.1:11434/api/chat`)** with `qwen2.5:3b` (`timeout_s=60.0`, `keep_alive=0` unload on completion), reporting `backend_used="langgraph"`.
  2. **Legacy Fallback (`TranscriptVerificationGate`):** Preserved when `AGENTIC_GATE_ENABLED=false`.
  3. **Dependency-injected `reviewer_override`** callable for deterministic fast unit/E2E testing (`backend_used="langgraph-override"`).
- **STT Upstream Enhancements (`backend/svr_platform/services/stt.py`):**
  - `normalize_wav_16k_loudness()` boosts quiet browser mic recordings (`< -40 dBFS`) toward `-20 dBFS` without clipping.
  - `faster-whisper` (`large-v3`) runs with `beam_size=3` and **no `initial_prompt`** (prevents Whisper from echoing prompt text on quiet segments).
- **Deterministic Pre-Repair & Anti-Hallucination Guardrails (`backend/svr_platform/services/transcript_gate.py`):**
  - Removes Whisper consecutive duplicate-sequence stutters (`deduplicate_whisper_sequences`) and applies high-confidence Egyptian telecom ASR repairs (`EGYPTIAN_TELECOM_ASR_REPAIRS`, e.g. `طبق -> التطبيق`, `بوقتي -> باقتي`).
  - `validate_candidate_transcript()` rejects empty output, CJK characters, unexpected Latin injection on Arabic-only raw text (`unexpected_latin_injection`), truncated/expanded length ratios, fabricated digit sequences, and excessive semantic drift (`word_similarity < 0.58`).
- **Acoustic-Gated Escalation:**
  - When `min_avg_logprob < -0.75`, confidence is capped at `0.65`, `"severe_acoustic_degradation"` is added to `lexical_flags`, and the ticket is forced to `status="uncertain"`, `needs_human_review=True`, `convergence_reason="severe_low_acoustic_logprob"`.

### 3.2 `VoiceGateOrchestrator` (`backend/svr_platform/services/orchestrator.py`)

Coordinates the 6-stage pipeline while preserving `run_voicemail_pipeline(...)`:
1. **Plan & Config Snapshot:** Reads org `SystemSetting` (`confidence_threshold`, `auto_routing_enabled`, `weekly_sample_rate`) + runtime memory mode.
2. **Stage 1 (`transcribe`):** Decrypts voicemail -> applies loudness normalization + Whisper `large-v3` (`beam_size=3`) -> immediately unloads Whisper -> logs `AIInteractionLog(stage="transcribe")` + updates `stage_status`.
3. **Stage 2 (`verify_transcript`):** Runs `AgenticTranscriptGate` (LangGraph + `qwen2.5:3b`) -> validates candidate -> updates `ticket.transcript`, recomputes `text_norm` & `language_mix`, saves `ticket.transcript_verification_json` -> unloads Qwen (`keep_alive=0`) -> logs `AIInteractionLog(stage="verify_transcript")` + `AuditEvent(action="transcript_verified")` -> broadcasts `ticket_stage_update`.
4. **Stage 3 (`classify`):** Runs 4 independent MARBERTv2 single-task models on verified `text_norm` -> merges confidence and label validation signals with gate confidence.
5. **Stages 4-6 (`priority`, `route`, `brief`):** Computes explainable priority score (`1..6`), checks combined blockers (`processing_error`, `invalid_label`, `missing_label`, `low_confidence`, `uncertain_transcript`), executes deterministic telecom routing and grounded callback brief generation, emits `ticket_update`.

## 4. Database, API, and Frontend Integration

- **ORM & Migration (`models.py`, `database.py`):** `Ticket.transcript_verification_json` (`JSON`, nullable) with idempotent column auto-migration in `DatabaseManager.create_all()`.
- **API Schemas & Routes (`schemas.py`, `main.py`):**
  - `_PIPELINE_STAGES = ("transcribe", "verify_transcript", "classify", "priority", "route", "brief")`.
  - Exposes typed `transcript_verification: TranscriptVerificationResponse | None = None` on `TicketDetail`.
- **Frontend UI (`ticket-detail.tsx`, `taxonomy.ts`, `i18n.ts`, `types.ts`, `voicemail-intake-sheet.tsx`):**
  - Displays verified transcript with **VoiceGate Orchestrator** status pill (confidence %, rounds, verified/corrected/uncertain state).
  - Collapsible **"VoiceGate Orchestrator Reasoning & Raw Whisper Comparison"** panel showing original `stt_v1_json.text`, word-level edits (`from -> to`), and iteration trace.

## 5. Verification Summary

- `pytest backend/tests -q`: **67 passed, 0 failed** (including 5 VoiceGate LangGraph, loudness normalization, and acoustic-escalation tests).
- Live Ollama `qwen2.5:3b` verified on all 20 database tickets (`13 verified`, `7 corrected`, `0 uncertain`, `0 unsynced`).
- Frontend `npm run build` verified cleanly with zero TypeScript errors and zero em/en dashes.
