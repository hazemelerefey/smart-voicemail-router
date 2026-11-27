# Ticket Review & Permanent Fix Report (Phases 1-4)

**Branch:** `antigravity/ticket-review-fix` (branched from `origin/master` at `a6e11cca4893e6ed8b4d9c1bfac23c3c95b3bb27`; runtime code identical to `9677e189ef5c4ccf1500786d228a91e2b7d1288b`)
**Forensic Pre-Fix Doc:** [docs/TICKET-INVESTIGATION.md](TICKET-INVESTIGATION.md) (committed prior to any code changes at `68920b9`)
**Rollback Snapshot:** `C:\Users\PC\.gemini\antigravity\brain\a42fa106-35c1-4452-9024-389af09d3ff7\scratch\ticket_3_snapshot.json`

---

## 1. One-Sentence Root Cause Per Ticket

1. **Ticket `#d18eb2ea` (`d18eb2ea-087b-4f91-ae89-e747a991ef6c`, `frustrated_0324.wav`) - REAL DEFECT:** During adaptive low-category-confidence VoiceGate re-audit (`backend/svr_platform/services/orchestrator.py:434-470`), `qwen2.5:3b` echoed the prompt's `<untrusted_transcript>` wrapper tags in `corrected_text` across all four rounds, causing `validate_candidate_transcript` (`backend/svr_platform/services/transcript_gate.py:438`) to reject every round with `unexpected_latin_injection`, `orchestrator.py:468` to overwrite the clean acoustic fast-path with `uncertain_transcript`, and `adjudicator.py:574` (`max(..., 0.55)` floor) to fail to clear the gate at `0.542008`, blocking routing.
2. **Ticket `#249ab615` (`249ab615-99a2-4bd4-9623-ee97fa1ea031`, `frustrated_0014.wav`) - `weekly_quality_sample` = NO DEFECT (plus hidden secondary occurrence of the same tag-echo bug):** Its `Weekly 5% Quality Sample` flag is correct deterministic behavior because `SHA256("249ab615-99a2-4bd4-9623-ee97fa1ea031")[:8] % 1000 = 7 < 50` (`backend/svr_platform/services/orchestrator.py:60`), while `"adjudicated"` originally fired because `max_no_speech_prob=0.3791 > 0.25` skipped fast-path (`backend/svr_platform/services/agentic_gate.py:283-285`) and hit the same `<untrusted_transcript>` tag-echo rejection before `adjudicator.py` cleared it (`0.737549 >= 0.55`).
3. **Ticket `#d7830282` (`d7830282-d813-4df9-9218-7e47110da61d`, `calm_0059.wav`) - NO DEFECT:** Ticket `#d7830282` functioned completely as designed: it passed the clean acoustic fast-path (`2.03 ms` before, `1.90 ms` after), passed all four MARBERTv2 heads at high confidence (`0.838116`, `adjudicator.py:403` `fast_verified`), routed to `Billing & Bundles Specialist`, and received `weekly_quality_sample` because its deterministic SHA-256 hash bucket is `10 < 50` (`orchestrator.py:60`).

---

## 2. Origin of the UI / Route Strings & Repo Reconciliation

Live backend (`127.0.0.1:8085`) and frontend (`127.0.0.1:4175`) run exact `origin/master` code (`9677e18` / `a6e11cc`), not unpushed local code and not an external service.

| Label / Token | Source in `origin/master` | Present in `origin/hazem/svr-production-build` (`446595a`)? |
| :--- | :--- | :--- |
| `"Uncertain Transcript (Needs Review)"` | `frontend/src/lib/i18n.ts:110` mapping `"uncertain_transcript"` in `backend/svr_platform/taxonomy.py:166` | UI key exists (`i18n.ts:110`); `taxonomy.py` on `446595a` only listed 8 `REVIEW_REASONS` without `"uncertain_transcript"` |
| `"VoiceGate Orchestrator"` | `backend/svr_platform/services/orchestrator.py:42` (`AGENT_NAME`), `agentic_gate.py`, `transcript_gate.py` | Yes (`orchestrator.py:39`, `agentic_gate.py`, `transcript_gate.py`) |
| `"adjudicated"` | `backend/svr_platform/services/adjudicator.py:109,583`, appended in `orchestrator.py:660` | No (`adjudicator.py` was added in `9677e18` on `origin/master`) |
| `"fast_verified"` | `backend/svr_platform/services/adjudicator.py:109,403`, appended in `orchestrator.py:660` | No (`adjudicator.py` was added in `9677e18` on `origin/master`) |

---

## 3. Code Changes & Unchanged Configuration

### Changes Made (Branch `antigravity/ticket-review-fix`)
1. **Strip echoed `<untrusted_transcript>` wrapper tags & forbid tag echoing in prompts:**
   - `backend/svr_platform/services/transcript_gate.py`: Added `strip_untrusted_transcript_tags(text)` using `_UNTRUSTED_TAG_RE`, applied it inside `_parse_gate_response` before returning `corrected_text`, and added rule 6 in `TranscriptVerificationGate._build_messages` instructing the model never to include `<untrusted_transcript>` wrapper tags.
   - `backend/svr_platform/services/agentic_gate.py`: Imported `strip_untrusted_transcript_tags`, added rule 10 to `VOICEGATE_SYSTEM_PROMPT`, and applied `strip_untrusted_transcript_tags` in both `node_audit` and `_run_direct_loop` prior to `validate_candidate_transcript`.
2. **Prevent failed zero-acceptance re-audits from downgrading clean fast-path results:**
   - `backend/svr_platform/services/orchestrator.py:468-485`: When initial `verify_transcript` passed cleanly (`status == "verified"` and `not needs_human_review`) and `verify_transcript_reaudit` rejected all rounds with zero edits (`not correction_applied and needs_human_review and confidence <= 0.0`), the orchestrator keeps `verify_transcript_reaudit` logged in `ai_interaction_logs` for auditability but preserves the clean acoustic `gate_res` rather than downgrading it to `uncertain_transcript`.
3. **Align adjudicator gate-clearance threshold to organization `confidence_threshold`:**
   - `backend/svr_platform/services/adjudicator.py:574`: Replaced hardcoded `max(confidence_threshold, 0.55)` with `confidence_threshold` (`0.50`) so `resolved_gate_uncertainty` honors the configured organization threshold cleanly.
4. **Admin explicit-ID ticket reprocessing CLI with pre-run snapshot & rollback:**
   - `ops/reprocess_tickets.py`: Requires `--ticket-ids <id1> ...` (or `--restore-snapshot`), rejects empty args or wildcards (`*`, `all`, `%`, `?`), snapshots target tables + all non-target ticket fingerprints before mutating, safely releases active assignments, re-runs only explicit IDs, and asserts `0` diffs across all untouched tickets.
5. **Regression unit tests:**
   - `backend/tests/test_ticket_review_fixes.py`: Covers tag-echo stripping in both gates on `#d18eb2ea`'s transcript, orchestrator re-audit non-downgrade preserving `Network Care Specialist` routing, adjudicator gate clearance at `0.50 <= conf < 0.55`, exact SHA-256 hash buckets (`170`, `7`, `10`), and CLI refusal on missing/wildcard IDs.

### Explicitly Unchanged Thresholds & Tables
- Complaint taxonomy (`11` categories), skill mapping (`DEFAULT_SKILL_MAPPING`), and seed agents (`3` teams) were NOT altered.
- Organization `confidence_threshold` (`0.50`), `weekly_sample_rate` (`0.05`), STT acoustic review thresholds, and priority formula were NOT altered.

---

## 4. Before & After Reprocessing Results (`ops/reprocess_tickets.py`)

| Ticket | Field | Before Fix (`9677e18`) | After Fix & Re-run (`d0315db`) |
| :--- | :--- | :--- | :--- |
| `#d18eb2ea` (`frustrated_0324.wav`) | `status` | `unassigned` | `ready` |
| | `assigned_agent` | `None` | `Network Care Specialist` (`12/25`) |
| | `complaint_category` | `sim_services` | `sim_services` |
| | `confidence` | `0.542008` | `0.527055` |
| | `verify_status` | `uncertain` (`4` rejected rounds) | `corrected` (`2` accepted rounds, `conf=0.85`) |
| | `needs_human_review` / `review_reason` | `True` / `uncertain_transcript` | `False` / `None` |
| `#249ab615` (`frustrated_0014.wav`) | `status` | `ready` | `ready` |
| | `assigned_agent` | `Billing & Bundles Specialist` (`8/25`) | `Billing & Bundles Specialist` (`11/25`) |
| | `complaint_category` | `balance_and_data` | `balance_and_data` |
| | `confidence` | `0.737549` | `0.772004` |
| | `verify_status` | `uncertain` -> cleared by adjudicator (`resolved_gate_uncertainty=True`) | `corrected` (`2` accepted rounds, `conf=0.85`) |
| | `needs_human_review` / `review_reason` | `True` / `weekly_quality_sample` | `True` / `weekly_quality_sample` |
| `#d7830282` (`calm_0059.wav`) | `status` | `ready` | `ready` |
| | `assigned_agent` | `Billing & Bundles Specialist` (`10/25`) | `Billing & Bundles Specialist` (`11/25`) |
| | `complaint_category` | `offers_and_packages` | `offers_and_packages` |
| | `confidence` | `0.838116` | `0.838116` |
| | `verify_status` / `adjudicator_mode` | `verified` / `fast_verified` | `verified` / `fast_verified` |
| | `needs_human_review` / `review_reason` | `True` / `weekly_quality_sample` | `True` / `weekly_quality_sample` |

---

## 5. Effective Weekly Sample Rate & Untouched Ticket Proof

- **Effective Quality Sample Rate (`storage/svr.db`):** Out of `35` tickets total, exactly `2` have `SHA256(id)[:8] % 1000 < 50` (`#249ab615` bucket `7`, `#d7830282` bucket `10`), and exactly those `2` are flagged `weekly_quality_sample` (`2 / 35 = 5.71%`, vs `5.0%` configured rate). Database totals after re-run: `35` tickets, `35 ready`, `0 unassigned`, `2 weekly_quality_sample`.
- **Non-Target Isolation Proof:** Before resetting the `3` target IDs, `ops/reprocess_tickets.py` captured `(id, status, assigned_agent_id, updated_at, needs_human_review, review_reason)` for all `32` other tickets into `ticket_3_snapshot.json`. Post-run verification reported `untouched_tickets_verified: 32` and `untouched_diffs: 0`.
- **Verification Executed:**
  - Full test suite (`pytest backend/tests infra/tests -q`): `268 passed, 1 warning in 26.97s` (`0` failures).
  - Live services restarted on `127.0.0.1:8085` (backend) and `127.0.0.1:4175` (Vite preview); both `/api/health` endpoints returned `200 OK` (`status="ok"`, `marbert_checkpoints_ready=true`).
  - CI static guards: `0` em dashes (`\u2014`), `0` en dashes (`\u2013`), and `0` empty `except: pass` blocks in all modified/added files.

## 6. Out of Scope / Not Modified
- `origin/hazem/svr-production-build` (`446595a`) and `origin/master` (`a6e11cc`) were left untouched; all commits live on `origin/antigravity/ticket-review-fix`.
- Frozen evaluation splits (`final/clean_training_test.csv`, `dataset/test/`) and pre-existing untracked local workspace directories (`MARBERTv2_LR2e5_COMPLETE/`, `MARBERTv2_LR2e5_METADATA/`, `MEMBER.md`, `docs/project/`, `notebooks/`, `requirements/`) were left untouched.
