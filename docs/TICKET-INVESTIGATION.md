# Ticket Review Forensic Investigation (Phase 1)

**Branch:** `antigravity/ticket-review-fix` (branched from `origin/master` at `a6e11cca4893e6ed8b4d9c1bfac23c3c95b3bb27`; runtime Python/TypeScript code identical to `9677e189ef5c4ccf1500786d228a91e2b7d1288b`, as `9677e18..a6e11cc` only updated `CHANGELOG.md` and `README.md`)
**Database Inspected:** `storage/svr.db` (35 tickets total)
**Scope:** Forensic investigation of `#d18eb2ea`, `#249ab615`, and `#d7830282` prior to any code changes.

---

## 1. Deployed Code vs Repository Reconciliation

### Running Deployment Check
- Active backend (`127.0.0.1:8085`, uvicorn `svr_platform.api.main:app`) and frontend Vite preview (`127.0.0.1:4175`) run directly out of this workspace (`origin/master` runtime commit `9677e18`, which matches `origin/master` HEAD `a6e11cc` across all Python and TypeScript files).
- `git diff --ignore-all-space` on the repository shows zero code divergence between the deployed processes and `origin/master` (only a local LF-to-CRLF line-ending normalization in `frontend/src/routeTree.gen.ts`).
- `origin/hazem/svr-production-build` sits at an earlier commit (`446595af38c3818eca5563980dabbc8a66d8657a`) prior to the Cohere Arabic ASR INT8, MARBERTv2 ONNX `seed_99`, Cognitive Memory, and `ClassificationAdjudicator` upgrade (`9677e18`).

### Origin of the Four UI / Log Strings
None of the four strings come from unpushed code or an external layer; all four live in `origin/master` (`9677e18` / `a6e11cc`):

| String | Exact Repo Location on `origin/master` | Present on `origin/hazem/svr-production-build` (`446595a`)? |
| :--- | :--- | :--- |
| `"Uncertain Transcript (Needs Review)"` | `frontend/src/lib/i18n.ts:110` (`REVIEW_REASON_LABELS.en.uncertain_transcript`), paired with `"uncertain_transcript"` in `backend/svr_platform/taxonomy.py:166` (`REVIEW_REASONS`, 9 values) | UI label present (`frontend/src/lib/i18n.ts:110`); `taxonomy.py` on `446595a` only listed 8 values without `"uncertain_transcript"` |
| `"VoiceGate Orchestrator"` | `backend/svr_platform/services/orchestrator.py:42` (`AGENT_NAME = "VoiceGate Orchestrator"`), plus `agentic_gate.py` and `transcript_gate.py` | Yes (`orchestrator.py:39`, `agentic_gate.py`, `transcript_gate.py`) |
| `"adjudicated"` | `backend/svr_platform/services/adjudicator.py:109,583` (`AdjudicationResult.mode`), appended into `route_reason` at `backend/svr_platform/services/orchestrator.py:660` | No (`adjudicator.py` does not exist on `446595a`) |
| `"fast_verified"` | `backend/svr_platform/services/adjudicator.py:109,403` (`AdjudicationResult.mode`), appended into `route_reason` at `backend/svr_platform/services/orchestrator.py:660` | No (`adjudicator.py` does not exist on `446595a`) |

Note on pipeline entrypoint: `backend/svr_platform/services/pipeline.py` (48 lines) now delegates directly to `VoiceGateOrchestrator.run()` in `backend/svr_platform/services/orchestrator.py`. That is why routing is gated by `VoiceGateOrchestrator` at `orchestrator.py:638-649` and `orchestrator.py:739-771`, where `gate_res.needs_human_review` explicitly acts as a routing blocker (`blocker = gate_res.review_reason or "uncertain_transcript"`).

---

## 2. Full Database Records (Verbatim Snapshot)

### Organization Settings & Routing Capacity (`storage/svr.db`)
- `system_settings`: `organization_id="407c4737-8b2c-45b2-8660-c1e3c654371d"`, `confidence_threshold=0.5`, `auto_routing_enabled=1`, `retention_days=90`, `weekly_sample_rate=0.05`, `updated_at="2026-11-27 17:24:02.986346"`.
- `agents`:
  - `Network Care Specialist` (`id="1cb48d9c-3bd0-4cd5-869f-418f7a1ee579"`, `skills=["Network"]`, `capacity=25`, `current_load=11`, `available=1`, `active=1`, `seed_order=1`)
  - `Billing & Bundles Specialist` (`id="afc84005-1ade-4db2-8433-a09f993a06fc"`, `skills=["Billing"]`, `capacity=25`, `current_load=11`, `available=1`, `active=1`, `seed_order=2`)
  - `Subscriber Care Specialist` (`id="90d88cfc-6ff5-41f4-a12b-06216e7c01f9"`, `skills=["General"]`, `capacity=25`, `current_load=12`, `available=1`, `active=1`, `seed_order=3`)

### 2.1 Ticket `#d18eb2ea` (`d18eb2ea-087b-4f91-ae89-e747a991ef6c`)
- **Ticket Row:**
  - `voicemail_id`: `f9dea701-ecc9-4964-b376-1fd8cbe1bc6e`
  - `status`: `"unassigned"`
  - `transcript`: `"المفروض لما بلغ عن فقدان شريحه يتم ايقافها فورا بس قعدت شغاله اكتر من 24 ساعه"`
  - `text_norm`: `"المفروض لما بلغ عن فقدان شريحه يتم ايقافها فورا بس قعدت شغاله اكتر من 24 ساعه"`
  - `language_mix`: `"arabic"`
  - `complaint_category`: `"sim_services"`, `complaint_urgency`: `"medium"`, `customer_state`: `"frustrated"`, `churn_risk`: `"not_at_risk"`
  - `label_sources`: `{"complaint_category": "model", "complaint_urgency": "model", "customer_state": "model", "churn_risk": "model"}`
  - `probabilities`: `complaint_category` top `sim_services=0.542008` (calibrated by adjudicator; raw MARBERT `sim_services` probability recorded in `verify_transcript_reaudit` trigger was `0.3688`), `other=0.184112`, `network_and_connectivity=0.084364`, `cancellation_request=0.052272`; `complaint_urgency` `medium=0.6841492082333163`; `customer_state` `frustrated=0.8343833005701171`; `churn_risk` `not_at_risk=0.999177390714116`
  - `confidence`: `0.542008` (`confidence_threshold_snapshot`: `0.5`)
  - `priority_score`: `3`, `queue_priority`: `"normal"`
  - `priority_reason`: `"Score 3/6 (normal): urgency medium (+2), churn not_at_risk (+0), customer state frustrated (+1)."`
  - `assigned_agent_id`: `null`
  - `route_reason`: `"UNASSIGNED: ticket flagged for Human Review (uncertain_transcript) before automatic agent routing."`
  - `needs_human_review`: `1`, `review_reason`: `"uncertain_transcript"`
  - `model_version`: `"UBC-NLP/MARBERTv2:single-task-lr2e5-sha3ec4889bda76+vg-adjudicator"`
  - `stage_status`: `{"intake": "ok", "transcribe": "ok", "verify_transcript": "flagged", "classify": "ok", "adjudicate": "ok", "priority": "ok", "route": "ok", "brief": "ok"}`
  - `stage_timing_ms`: `{"transcribe": 7139.08, "verify_transcript": 5.37, "verify_transcript_reaudit": 17279.67, "classify": 17366.68, "adjudicate": 13610.37, "priority": 0.02, "route": 1.17, "brief": 1.45}`
  - `processing_ms`: `38134.05`
  - `created_at`: `"2026-11-27 17:35:52.434363"`, `updated_at`: `"2026-11-27 17:36:30.576491"`
  - `SHA256(id)[:8] % 1000`: `170` (not in weekly sample `< 50`)
- **Voicemail Row:** `file_name="frustrated_0324.wav"`, `duration_seconds=6.757`, `status="unassigned"`, `stt_v1_json`: `model="NAMAA-Space/cohere-transcribe-arabic-07-2026-int8"`, `min_avg_logprob=-0.0721`, `max_no_speech_prob=0.2488`, `needs_review=false`, `review_reasons=""`, `dup_text_size=1`, `error=""`.
- **Assignments:** `[]` (empty).
- **`transcript_verification_json` Summary:**
  - `status="uncertain"`, `correction_applied=false`, `rounds_run=4`, `confidence=0.0`, `convergence_reason="max_iterations_exhausted"`, `needs_human_review=true`, `review_reason="uncertain_transcript"`, `latency_ms=17279.67`.
  - All 4 rounds in `trace` produced valid coherent Arabic repairs with `confidence=0.85`, `is_coherent=true`, EXCEPT `candidate_text` was wrapped in literal XML tags `<untrusted_transcript>...</untrusted_transcript>`, so every round was rejected (`accepted=false`) with `critique="unexpected_latin_injection: ['transcript', 'untrusted']"`.
  - `orchestrator_adjudication`: `mode="adjudicated"`, `trigger_reasons=["complaint_category:low_prob(0.37)", "transcript_gate:uncertain"]`, `calibrated_confidence=0.542008`, `memory_episodes_used=7`, `max_episode_similarity=0.9087`, `semantic_rules_used=5`, `procedural_rules_used=4`, `resolved_gate_uncertainty=false`, `escalate_to_human=false`.
- **AI Interaction Logs (`ai_interaction_logs`):**
  1. `transcribe` (`17:35:59.581945`, `7139 ms`): `min_avg_logprob=-0.0721`, `max_no_speech_prob=0.2488`, `needs_review=false`.
  2. `verify_transcript` (`17:35:59.589037`, `5 ms`): `status="verified"`, `rounds_run=0`, `confidence=0.92`, `convergence_reason="fast_path_clean_acoustic"`, `needs_human_review=false`, `review_reason=null`.
  3. `verify_transcript_reaudit` (`17:36:30.571488`, `17279 ms`): `trigger_category_confidence=0.3688`, `status="uncertain"`, `correction_applied=false`, `rounds_run=4`, `confidence=0.0`.
  4. `adjudicate` (`17:36:30.571488`, `13610 ms`): `mode="adjudicated"`, confirmed `sim_services`, `calibrated_confidence=0.542008`, `escalate_to_human=false`, `resolved_gate_uncertainty=false`.
  5. `classify` (`17:36:30.571488`, `17366 ms`): `confidence=0.542008`, `needs_human_review=false`, `review_reason=null`.
  6. `priority` (`17:36:30.571488`, `0 ms`): `priority_score=3`, `queue_priority="normal"`.
  7. `route` (`17:36:30.571488`, `1 ms`): `assigned_agent_id=null`, `required_skill="Network"`, `route_reason="UNASSIGNED: ticket flagged for Human Review (uncertain_transcript) before automatic agent routing."`.
  8. `brief` (`17:36:30.571488`, `1 ms`): `flagged=false`, `flag_reason=null`.
- **Audit Events (`audit_events`):** `created` (`17:35:52.434363`), `classified` (`gate_status="uncertain"`), `priority_computed`, `routed` (`assigned_agent_id=null`), `status_changed` (`status="unassigned"`, `needs_human_review=true`, `review_reason="uncertain_transcript"`, `completed_steps=["transcribe", "verify_transcript", "verify_transcript_reaudit", "classify", "adjudicate", "priority", "route", "brief", "consolidate_memory"]`).

### 2.2 Ticket `#249ab615` (`249ab615-99a2-4bd4-9623-ee97fa1ea031`)
- **Ticket Row:**
  - `voicemail_id`: `941e1c5e-913c-4d49-b08d-419287ae6153`
  - `status`: `"ready"`
  - `transcript`: `"لما بستخدم باقة اليومية ساعات بتشتغل وساعات لأ ... مش عارف ليه"`
  - `text_norm`: `"لما بستخدم باقه اليوميه ساعات بتشتغل وساعات لا مش عارف ليه"`
  - `complaint_category`: `"balance_and_data"` (`0.764941`), `complaint_urgency`: `"medium"` (`0.737549`), `customer_state`: `"calm"` (`0.764638`), `churn_risk`: `"not_at_risk"` (`0.999185`)
  - `confidence`: `0.737549` (`confidence_threshold_snapshot`: `0.5`)
  - `priority_score`: `2`, `queue_priority`: `"low"`
  - `assigned_agent_id`: `"afc84005-1ade-4db2-8433-a09f993a06fc"` (`Billing & Bundles Specialist`)
  - `route_reason`: `"Assigned to Billing & Bundles Specialist: matched skill 'Billing' for 'balance_and_data', available on shift, concurrent load 8/25 (first eligible in seed order). Verified by VoiceGate Orchestrator (adjudicated)."`
  - `needs_human_review`: `1`, `review_reason`: `"weekly_quality_sample"`
  - `stage_status`: `{"intake": "ok", "transcribe": "ok", "verify_transcript": "ok", "classify": "ok", "adjudicate": "ok", "priority": "ok", "route": "ok", "brief": "ok"}`
  - `stage_timing_ms`: `{"transcribe": 4287.45, "verify_transcript": 14723.92, "classify": 855.2, "adjudicate": 10750.29, "priority": 0.02, "route": 2.78, "brief": 0.67}`
  - `processing_ms`: `30630.1`
  - `SHA256(id)[:8] % 1000`: `7` (`7 < 50`, matches `weekly_sample_rate=0.05`)
- **Voicemail Row:** `file_name="frustrated_0014.wav"`, `duration_seconds=5.908`, `status="ready"`, `stt_v1_json`: `min_avg_logprob=-0.1391`, `max_no_speech_prob=0.3791`, `needs_review=false`, `review_reasons=""`.
- **Assignments:** `id="7a140da0-aa60-4318-a7ad-30d79758f4d8"`, `agent_id="afc84005-1ade-4db2-8433-a09f993a06fc"`, `assigned_by="VoiceGate Orchestrator"`, `status="active"`.
- **`transcript_verification_json` & `ai_logs` Summary:**
  - `verify_transcript` (`14723 ms`): skipped fast-path because `max_no_speech_prob=0.3791 > 0.25` (`agentic_gate.py:283-285`), ran 4 rounds, and hit the **exact same `<untrusted_transcript>` tag-echo rejection** across all 4 rounds (`critique="unexpected_latin_injection: ['transcript', 'untrusted']"`, `confidence=0.0`, `status="uncertain"`, `review_reason="uncertain_transcript"`).
  - `adjudicate` (`10750 ms`): triggered solely by `["transcript_gate:uncertain"]`, ran `ClassificationAdjudicator` (`mode="adjudicated"`), confirmed `balance_and_data` (`calibrated_confidence=0.737549 >= max(0.50, 0.55)`), and set `resolved_gate_uncertainty=true`, which allowed `orchestrator.py:511-518` to restore `verify_transcript` to `"ok"`, route to `Billing & Bundles Specialist`, and apply `weekly_quality_sample` (`bucket 7 < 50`).

### 2.3 Ticket `#d7830282` (`d7830282-d813-4df9-9218-7e47110da61d`)
- **Ticket Row:**
  - `voicemail_id`: `59f082a3-980f-41f8-9641-56442f915e1f`
  - `status`: `"ready"`
  - `transcript`: `"عايز أعرف لو في عروض أسرية تشمل أكتر من خط بنفس الحساب"`
  - `text_norm`: `"عايز اعرف لو في عروض اسريه تشمل اكتر من خط بنفس الحساب"`
  - `complaint_category`: `"offers_and_packages"` (`0.838116`), `complaint_urgency`: `"low"` (`0.979451`), `customer_state`: `"calm"` (`0.942980`), `churn_risk`: `"not_at_risk"` (`0.999177`)
  - `confidence`: `0.838116` (`confidence_threshold_snapshot`: `0.5`)
  - `priority_score`: `1`, `queue_priority`: `"low"`
  - `assigned_agent_id`: `"afc84005-1ade-4db2-8433-a09f993a06fc"` (`Billing & Bundles Specialist`)
  - `route_reason`: `"Assigned to Billing & Bundles Specialist: matched skill 'Billing' for 'offers_and_packages', available on shift, concurrent load 10/25 (first eligible in seed order). Verified by VoiceGate Orchestrator (fast_verified)."`
  - `needs_human_review`: `1`, `review_reason`: `"weekly_quality_sample"`
  - `stage_status`: `{"intake": "ok", "transcribe": "ok", "verify_transcript": "ok", "classify": "ok", "adjudicate": "ok", "priority": "ok", "route": "ok", "brief": "ok"}`
  - `stage_timing_ms`: `{"transcribe": 3950.58, "verify_transcript": 2.03, "classify": 38.26, "adjudicate": 2774.1, "priority": 0.01, "route": 1.26, "brief": 0.35}`
  - `processing_ms`: `6774.37`
  - `SHA256(id)[:8] % 1000`: `10` (`10 < 50`, matches `weekly_sample_rate=0.05`)
- **Voicemail Row:** `file_name="calm_0059.wav"`, `duration_seconds=4.152`, `status="ready"`, `stt_v1_json`: `min_avg_logprob=-0.039`, `max_no_speech_prob=0.1301`, `needs_review=false`, `review_reasons=""`.
- **Assignments:** `id="05a09d90-c6b3-4741-b9a5-b6d518350fd1"`, `agent_id="afc84005-1ade-4db2-8433-a09f993a06fc"`, `assigned_by="VoiceGate Orchestrator"`, `status="active"`.
- **Pipeline Behavior:** Clean acoustic fast-path (`2.03 ms`, `rounds_run=0`, `confidence=0.92`), MARBERTv2 high confidence (`0.838116`), `ClassificationAdjudicator` took fast-verify (`mode="fast_verified"`, `adjudicator.py:403`), routed normally (`Billing & Bundles Specialist`), then sampled deterministically at `orchestrator.py:761-764`.

---

## 3. Code Path Trace & Effective Quality Sample Rate

### Why `#d18eb2ea` Was Flagged `UNASSIGNED` Despite a Verified Clean Transcript
1. **Clean STT & Initial Gate:** Cohere Arabic INT8 produced an accurate transcript (`min_avg_logprob=-0.0721 >= -0.35`, `max_no_speech_prob=0.2488 <= 0.25`, `needs_review=False`). `AgenticTranscriptGate` took the clean-acoustic fast-path (`rounds_run=0`, `status="verified"`, `confidence=0.92`, `needs_human_review=False`).
2. **Adaptive Re-Audit Trigger (`orchestrator.py:434-448`):** Because `rounds_run == 0` and MARBERTv2's raw `complaint_category` probability for `sim_services` was `0.3688 < 0.45` (`SVR_ADAPTIVE_REAUDIT_CATEGORY_THRESHOLD`), the orchestrator invoked `self.transcript_gate.verify(stt_res.text, ..., force_audit=True)`.
3. **Tag-Echo Rejection Defect (`agentic_gate.py:349-350,403,786-787,819` & `transcript_gate.py:438,529,636-637`):** `agentic_gate.py` wrapped `raw_asr_text` and `current_candidate` inside `<untrusted_transcript>...</untrusted_transcript>`. `qwen2.5:3b` echoed those literal wrapper tags back inside JSON field `corrected_text` on all 4 rounds. Neither `agentic_gate.py` nor `transcript_gate.py` stripped `<untrusted_transcript>` tags before calling `validate_candidate_transcript()` (`transcript_gate.py:437-439`), so the Latin-token anti-hallucination guard rejected every single round with `unexpected_latin_injection: ['transcript', 'untrusted']`, exhausting max iterations with `best_valid_confidence=0.0`, `status="uncertain"`, and `review_reason="uncertain_transcript"`.
4. **Unconditional Re-Audit Downgrade Defect (`orchestrator.py:468-470`):** Even though initial `verify_transcript` had already verified the transcript cleanly and the re-audit produced zero accepted changes (`correction_applied=False`, `confidence=0.0`), `orchestrator.py:468` unconditionally executed `gate_res = reaudit_res`, overwriting the clean `verified` result with `uncertain_transcript`.
5. **Arbitrary `0.55` Uncertainty-Clearance Floor (`adjudicator.py:574`):** `ClassificationAdjudicator` retrieved 7 episodes (`max_episode_similarity=0.9087`), confirmed `sim_services` (`escalate_to_human=False`), and recalibrated confidence to `0.542008` (above the org `confidence_threshold=0.50`). However, `adjudicator.py:574` required `validated_cls.confidence >= max(confidence_threshold, 0.55)`, missing `0.55` by `0.008`, leaving `resolved_gate_uncertainty=False`.
6. **Routing Blocked (`orchestrator.py:645-656`):** `gate_res.needs_human_review` remained `True`, so `human_review_blocker="uncertain_transcript"` bypassed eligible `Network Care Specialist` (`current_load 11/25`) and left `#d18eb2ea` `unassigned`.

### Quality Sampling Across All 35 Database Tickets
Formula in `backend/svr_platform/services/orchestrator.py:56-61`:
```python
bucket = int(hashlib.sha256(ticket_id.encode("utf-8")).hexdigest()[:8], 16) % 1000
return bucket < int(round(sample_rate * 1000))  # sample_rate=0.05 -> bucket < 50
```
- **Total tickets in `storage/svr.db`:** `35`
- **Buckets `< 50`:** `2` (`249ab615-99a2-4bd4-9623-ee97fa1ea031` -> `bucket = 7`; `d7830282-d813-4df9-9218-7e47110da61d` -> `bucket = 10`). Note `#d18eb2ea-087b-4f91-ae89-e747a991ef6c` -> `bucket = 170 >= 50`.
- **Tickets flagged `weekly_quality_sample`:** `2` (`#249ab615`, `#d7830282`)
- **Effective sample rate:** `2 / 35 = 5.71%` (expected at `5.0%` on 35 tickets is `1.75` tickets). Exact match between hash buckets and DB flags.

### All Angles Checked
- **STT quality thresholds:** Passed cleanly on all 3 tickets (`needs_review=False`; logprobs `-0.0721`, `-0.1391`, `-0.039`; no-speech probs `0.2488`, `0.3791`, `0.1301`).
- **Classification confidence:** `min` of top head probabilities (`classification.py:185`): `0.542008`, `0.737549`, `0.838116` (all `>= 0.50`).
- **Priority & Brief:** All 4 heads populated on all 3 tickets; priority rules (`priority.py`) and callback briefs (`brief.py`) succeeded with `flagged=false`.
- **Routing eligibility & capacity:** `DEFAULT_SKILL_MAPPING` covers all 11 categories (`sim_services -> Network`, `balance_and_data` & `offers_and_packages -> Billing`); all 3 seed agents are active, available, and well under capacity (`11/25`, `11/25`, `12/25`).
- **Sampler & UI labels:** Sampler is deterministic and exact; `i18n.ts:110` and `taxonomy.py:166` match stored `review_reason` strings.

---

## 4. Root Cause Statements (One Sentence Per Ticket)

1. **Ticket `#d18eb2ea` (REAL DEFECT):** During the adaptive low-category-confidence VoiceGate re-audit (`orchestrator.py:434-470`), `qwen2.5:3b` echoed the prompt's `<untrusted_transcript>` XML wrapper tags in `corrected_text` across all four rounds, causing `validate_candidate_transcript` (`transcript_gate.py:438`) to reject every round with `unexpected_latin_injection`, `orchestrator.py:468` to overwrite the already-verified clean fast-path with `uncertain_transcript`, and `adjudicator.py:574` (`max(..., 0.55)` floor) to fail to clear the gate at `0.542008`, blocking routing.
2. **Ticket `#249ab615` (`weekly_quality_sample` = NO DEFECT; hidden secondary occurrence of the same tag-echo bug):** The `Weekly 5% Quality Sample` flag on `#249ab615` is correct behavior because its deterministic SHA-256 hash bucket is `7 < 50` (`orchestrator.py:60`), while `"adjudicated"` ran only because `max_no_speech_prob=0.3791 > 0.25` skipped fast-path (`agentic_gate.py:283-285`) and triggered the same `<untrusted_transcript>` tag-echo rejection across all four rounds before `adjudicator.py:574` (`0.737549 >= 0.55`) rescued routing.
3. **Ticket `#d7830282` (NO DEFECT):** Ticket `#d7830282` functioned completely as designed: it passed the clean acoustic fast-path (`2.03 ms`), passed all four MARBERTv2 heads at high confidence (`0.838116`, `adjudicator.py:403` `fast_verified`), routed to `Billing & Bundles Specialist`, and received `weekly_quality_sample` because its deterministic SHA-256 hash bucket is `10 < 50` (`orchestrator.py:60`).
