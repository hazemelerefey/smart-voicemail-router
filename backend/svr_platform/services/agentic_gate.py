"""VoiceGate Orchestrator - Agentic Transcript Gate using LangGraph.

A stateful, iterative audit-and-repair agent that coordinates Whisper output
through a LangGraph StateGraph to produce accurate Egyptian Arabic telecom
complaint transcripts. Runs 100% locally via Ollama (loopback-only).

Agent pipeline per voicemail:
  pre_repair --> audit --> (fix --> audit)* --> confidence_check --> finalize

The agent loops audit-and-fix until it reaches strong confidence that the
transcript is a valid, coherent Egyptian Arabic telecom complaint, or until
max_iterations is exhausted (escalates to human review).
"""

from __future__ import annotations

import difflib
import json
import logging
import re
import time
from dataclasses import asdict
from typing import Any, Callable, Literal

import httpx

from .text_norm import detect_language_mix, normalize_transcript
from .transcript_gate import (
    GateResult,
    GateRoundTrace,
    STTSignalSummary,
    WordChange,
    analyze_stt_signals,
    compute_word_changes,
    deduplicate_whisper_sequences,
    pre_repair_whisper_text,
    validate_candidate_transcript,
    validate_loopback_url,
)

logger = logging.getLogger("svr_platform.agentic_gate")

# ---------------------------------------------------------------------------
# Egyptian Arabic telecom ASR confusion map (expanded, phoneme-level)
# ---------------------------------------------------------------------------
# Maps common Whisper mis-recognitions in Egyptian dialect telecom complaints
# to their correct forms. Covers: letter confusion, dialectal pronunciation,
# phonetic borrowings, and common garbling patterns.
TELECOM_FEW_SHOT_REPAIRS: list[dict[str, str]] = [
    # App / application misheard
    {"wrong": "طبق", "correct": "التطبيق", "reason": "phonetic_prefix_drop"},
    {"wrong": "الطبق", "correct": "التطبيق", "reason": "syllable_contraction"},
    {"wrong": "تطبيق", "correct": "التطبيق", "reason": "missing_article"},
    {"wrong": "بالتطبيق", "correct": "بالتطبيق", "reason": "correct_no_change"},
    # Data balance / quota
    {"wrong": "بوقتي", "correct": "باقتي", "reason": "vowel_confusion_waw_alef"},
    {"wrong": "باقيتي", "correct": "باقتي", "reason": "yaa_drop"},
    # Time duration pronoun
    {"wrong": "بقالوا", "correct": "بقاله", "reason": "pronoun_gender_mismatch"},
    {"wrong": "بقالها", "correct": "بقاله", "reason": "pronoun_gender_mismatch"},
    # Network
    {"wrong": "السبكة", "correct": "الشبكة", "reason": "seen_shin_confusion"},
    {"wrong": "سبكة", "correct": "شبكة", "reason": "seen_shin_confusion"},
    # Charge / deduct
    {"wrong": "يخسموا", "correct": "يخصموا", "reason": "seen_sad_confusion"},
    {"wrong": "بيخسموا", "correct": "بيخصموا", "reason": "seen_sad_confusion"},
    {"wrong": "يتخسم", "correct": "يتخصم", "reason": "seen_sad_confusion"},
    {"wrong": "اتخسم", "correct": "اتخصم", "reason": "seen_sad_confusion"},
    # Call tone / ring tone
    {"wrong": "الكلتون", "correct": "الكول تون", "reason": "phonetic_merge"},
    {"wrong": "كلتون", "correct": "كول تون", "reason": "phonetic_merge"},
    # SIM card
    {"wrong": "السريحة", "correct": "الشريحة", "reason": "seen_shin_confusion"},
    {"wrong": "سريحة", "correct": "شريحة", "reason": "seen_shin_confusion"},
    # Subscription
    {"wrong": "الاشتراخ", "correct": "الاشتراك", "reason": "kha_kaf_confusion"},
    {"wrong": "اشتراخ", "correct": "اشتراك", "reason": "kha_kaf_confusion"},
    # Invoice / bill
    {"wrong": "الفاتورا", "correct": "الفاتورة", "reason": "taa_marbuta_drop"},
    {"wrong": "فاتورا", "correct": "فاتورة", "reason": "taa_marbuta_drop"},
    # Router
    {"wrong": "الوطر", "correct": "الراوتر", "reason": "phonetic_reversal"},
    {"wrong": "روتر", "correct": "راوتر", "reason": "vowel_contraction"},
]

_FEW_SHOT_STR = "\n".join(
    f"  WRONG: {r['wrong']} -> CORRECT: {r['correct']} ({r['reason']})"
    for r in TELECOM_FEW_SHOT_REPAIRS
)

# ---------------------------------------------------------------------------
# System prompt engineering (the brain of the agent)
# ---------------------------------------------------------------------------
VOICEGATE_SYSTEM_PROMPT = f"""You are VoiceGate, an expert Egyptian Arabic ASR correction specialist for telecom customer care.

Your sole job: audit one Whisper ASR transcript of an Egyptian Arabic voicemail complaint, then fix only the misheard words.

CONTEXT: These are Egyptian Arabic voicemail complaints to a mobile telecom company (Vodafone/Orange/Etisalat/WE Egypt). Complaints cover:
- Mobile data issues (quota, speed, 4G/5G coverage)
- Billing disputes (wrong charges, deductions, invoices)
- App problems (My Vodafone, Orange app, etc.)
- Call services (call tone, IVR, dropped calls)
- SIM issues (activation, replacement)
- Network problems (no signal, slow connection)
- Subscription management (packages, renewals)

KNOWN ASR CONFUSION PATTERNS (Egyptian dialect):
{_FEW_SHOT_STR}

AUDIT RULES (follow strictly):
1. Read each Arabic word and decide: is it a misheard word OR a valid Egyptian dialect word?
2. Only fix words you are confident are ASR errors (phonetic confusion, letter substitution, syllable drop).
3. NEVER change word order. NEVER delete words. NEVER add new words.
4. NEVER invent phone numbers, amounts, dates, or ticket IDs.
5. NEVER switch to formal Arabic (MSA) - keep the Egyptian dialect as-is.
6. If the sentence is already correct and meaningful as a telecom complaint, return it unchanged.
7. Focus on making the sentence a coherent, specific telecom complaint.
8. Check EVERY word from the first word to the last: e.g. 'طبق مش بيظهر' -> 'التطبيق مش بيظهر' (the telecom app not showing quota).
9. If the Arabic sentence is severely garbled or nonsensical, set is_coherent=false and confidence <= 0.55.

CONFIDENCE GUIDE:
- 0.90+: Sentence is definitely a correct, coherent telecom complaint - all words verified.
- 0.80-0.89: Mostly correct, minor uncertainty about one word.
- 0.70-0.79: Some words unclear, applied best-guess repairs.
- below 0.70: Too uncertain - flag for human review.

RESPONSE FORMAT (compact JSON only, no extra text):
{{
  "thinking": "brief audit reasoning under 20 words",
  "suspect_words": ["word1", "word2"],
  "corrected_text": "the repaired Arabic sentence",
  "confidence": 0.85,
  "is_coherent": true,
  "telecom_category": "data|billing|app|network|sim|call|subscription|other",
  "changes": [{{"from": "wrong_word", "to": "correct_word", "reason": "asr_error_type"}}]
}}"""


# ---------------------------------------------------------------------------
# LangGraph state schema
# ---------------------------------------------------------------------------
try:
    from typing import TypedDict

    class TranscriptAuditState(TypedDict):
        """State flowing through all LangGraph nodes."""
        raw_text: str
        pre_repaired_text: str
        current_text: str
        iteration: int
        max_iterations: int
        confidence: float
        confidence_threshold: float
        early_stop_confidence: float
        audit_history: list[dict]
        pre_changes: list[dict]
        signal_summary: dict
        is_coherent: bool
        needs_human_review: bool
        convergence_reason: str
        final_text: str
        all_changes: list[dict]
        backend_used: str
        model_used: str
        error: str
        critique: str
        # Agent internal routing control
        _next: str

except ImportError:
    TranscriptAuditState = dict  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Utility: LLM interaction (Ollama HTTP)
# ---------------------------------------------------------------------------

def _call_ollama_chat(
    *,
    ollama_url: str,
    model: str,
    system_prompt: str,
    user_message: str,
    timeout_s: float = 45.0,
) -> str:
    """Call Ollama /api/chat and return the raw content string."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
        "format": "json",
        "keep_alive": "3m",
        "options": {
            "temperature": 0.05,
            "top_p": 0.9,
            "num_predict": 500,
            "repeat_penalty": 1.1,
        },
    }
    with httpx.Client(timeout=timeout_s) as client:
        resp = client.post(f"{ollama_url}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        msg = data.get("message") or {}
        content = str(msg.get("content") or "").strip()
        if not content:
            raise RuntimeError("Ollama returned empty response")
        return content


def _extract_json_object(raw: str) -> dict[str, Any]:
    """Extract JSON dict from LLM output tolerating code fences and prose."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        loaded = json.loads(text)
        if isinstance(loaded, dict):
            return loaded
    except ValueError as exc:
        logger.debug("Direct JSON parse failed, trying substring extraction: %s", exc)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            loaded = json.loads(text[start : end + 1])
            if isinstance(loaded, dict):
                return loaded
        except ValueError as exc:
            logger.debug("Substring JSON parse failed: %s", exc)
    raise ValueError(f"No valid JSON object in LLM output: {text[:200]!r}")


# ---------------------------------------------------------------------------
# LangGraph nodes
# ---------------------------------------------------------------------------

def build_langgraph_agent(
    *,
    ollama_url: str,
    model: str,
    max_iterations: int = 4,
    confidence_threshold: float = 0.75,
    early_stop_confidence: float = 0.90,
    timeout_s: float = 45.0,
    fast_path_enabled: bool = True,
    reviewer_override: Callable[[dict[str, Any]], dict[str, Any] | str] | None = None,
):
    """Build and return a compiled LangGraph StateGraph for transcript auditing.

    Returns the compiled graph or None if LangGraph is not installed.
    """
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        logger.warning("langgraph not installed; AgenticTranscriptGate will use direct loop fallback.")
        return None

    def node_pre_repair(state: TranscriptAuditState) -> dict:
        """Deterministic stutter deduplication + Egyptian telecom ASR fixes."""
        raw = state["raw_text"]
        pre_text, pre_changes, _ = pre_repair_whisper_text(raw)
        changes_dicts = [{"from": c.from_text, "to": c.to_text, "reason": c.reason} for c in pre_changes]
        sig = state.get("signal_summary") or {}
        min_lp = sig.get("min_avg_logprob")
        max_nsp = sig.get("max_no_speech_prob")
        clean_candidate = pre_text or raw
        is_fast_path = (
            fast_path_enabled
            and sig.get("acoustic_risk") == "low"
            and not sig.get("lexical_flags")
            and not sig.get("suspect_hints")
            and not pre_changes
            and len(clean_candidate.split()) >= 3
            and (min_lp is not None and float(min_lp) >= -0.35)
            and (max_nsp is None or float(max_nsp) <= 0.25)
        )
        logger.debug("pre_repair: %s -> %s (%d changes, fast_path=%s)", raw[:40], pre_text[:40], len(pre_changes), is_fast_path)
        if is_fast_path:
            return {
                "pre_repaired_text": clean_candidate,
                "current_text": clean_candidate,
                "pre_changes": changes_dicts,
                "iteration": 0,
                "confidence": 0.92,
                "is_coherent": True,
                "needs_human_review": False,
                "convergence_reason": "fast_path_clean_acoustic",
                "_next": "finalize",
            }
        return {
            "pre_repaired_text": clean_candidate,
            "current_text": clean_candidate,
            "pre_changes": changes_dicts,
            "iteration": 0,
            "_next": "audit",
        }

    def node_audit(state: TranscriptAuditState) -> dict:
        """Call Ollama (or reviewer_override) to audit the current transcript and propose repairs."""
        it = state["iteration"] + 1
        current = state["current_text"]
        raw = state["raw_text"]
        critique = state.get("critique", "")

        user_payload: dict[str, Any] = {
            "iteration": it,
            "raw_whisper_text": raw,
            "current_candidate": current,
            "stt_signals": state.get("signal_summary", {}),
        }
        if critique:
            user_payload["critique_from_previous_round"] = critique

        logger.debug("audit node iteration=%d text=%s", it, current[:50])
        try:
            if reviewer_override is not None:
                ctx = {
                    "round": it,
                    "iteration": it,
                    "raw_text": raw,
                    "current_text": current,
                    "signals": state.get("signal_summary", {}),
                    "critique": critique or None,
                }
                override_res = reviewer_override(ctx)
                if isinstance(override_res, str):
                    data = _extract_json_object(override_res)
                elif isinstance(override_res, dict):
                    data = override_res
                else:
                    data = {}
            else:
                raw_reply = _call_ollama_chat(
                    ollama_url=ollama_url,
                    model=model,
                    system_prompt=VOICEGATE_SYSTEM_PROMPT,
                    user_message=json.dumps(user_payload, ensure_ascii=False),
                    timeout_s=timeout_s,
                )
                data = _extract_json_object(raw_reply)
        except (ValueError, RuntimeError, httpx.HTTPError) as exc:
            logger.warning("audit node LLM call failed iteration=%d: %s", it, exc)
            history = list(state.get("audit_history", []))
            history.append({
                "iteration": it,
                "status": "error",
                "error": str(exc),
                "input_text": current,
                "candidate_text": current,
                "confidence": 0.0,
            })
            return {
                "iteration": it,
                "audit_history": history,
                "critique": f"Previous call failed: {exc}. Try again with strict JSON output.",
                "_next": "confidence_check",
            }

        candidate = str(data.get("corrected_text") or current).strip()
        thinking = str(data.get("thinking") or "").strip()[:300]
        try:
            conf = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        conf = max(0.0, min(1.0, conf))
        is_coherent = bool(data.get("is_coherent", True))
        telecom_cat = str(data.get("telecom_category") or "other").strip()

        raw_changes = data.get("changes") or []
        explicit_changes: list[dict] = []
        if isinstance(raw_changes, list):
            for c in raw_changes:
                if isinstance(c, dict) and (c.get("from") or c.get("to")):
                    explicit_changes.append({
                        "from": str(c.get("from", "")),
                        "to": str(c.get("to", "")),
                        "reason": str(c.get("reason", "llm_repair")),
                    })

        # Validate the candidate against anti-hallucination guardrails
        is_valid, invalid_reason = validate_candidate_transcript(
            raw,
            candidate,
            anchor_text=state.get("pre_repaired_text") or raw,
        )

        history = list(state.get("audit_history", []))
        history.append({
            "iteration": it,
            "status": "accepted" if is_valid else "rejected",
            "thinking": thinking,
            "input_text": current,
            "candidate_text": candidate,
            "confidence": round(conf, 4),
            "is_coherent": is_coherent,
            "telecom_category": telecom_cat,
            "changes": explicit_changes,
            "rejection_reason": invalid_reason if not is_valid else None,
        })

        if not is_valid:
            new_critique = (
                f"Revision rejected ({invalid_reason}). "
                "Keep exact word order and sentence length. Only fix clearly misheard Arabic words. "
                "Return the sentence unchanged if unsure."
            )
            logger.debug("audit rejected candidate (reason=%s) iteration=%d", invalid_reason, it)
            return {
                "iteration": it,
                "audit_history": history,
                "critique": new_critique,
                "_next": "confidence_check",
            }

        # Candidate is valid - accumulate changes and update current_text
        accumulated_changes = list(state.get("all_changes") or [])
        for c in explicit_changes:
            if not any(x.get("from") == c.get("from") and x.get("to") == c.get("to") for x in accumulated_changes):
                accumulated_changes.append(c)

        logger.debug(
            "audit accepted candidate conf=%.2f coherent=%s iteration=%d", conf, is_coherent, it
        )
        return {
            "iteration": it,
            "current_text": candidate,
            "confidence": conf,
            "is_coherent": is_coherent,
            "audit_history": history,
            "all_changes": accumulated_changes,
            "critique": "",
            "_next": "confidence_check",
        }

    def node_confidence_check(state: TranscriptAuditState) -> dict:
        """Decide: converged, need another round, or escalate to human review."""
        it = state["iteration"]
        max_it = state["max_iterations"]
        conf = state.get("confidence", 0.0)
        is_coherent = state.get("is_coherent", False)
        c_thresh = state["confidence_threshold"]
        early_thresh = state["early_stop_confidence"]
        history = state.get("audit_history", [])
        accepted = [h for h in history if h.get("status") == "accepted"]

        last_entry = accepted[-1] if accepted else None
        made_edit_last = bool(
            last_entry
            and normalize_transcript(last_entry.get("candidate_text", ""))
            != normalize_transcript(last_entry.get("input_text", ""))
        )

        # Check if any known Egyptian telecom ASR suspect token remains in current_text
        current_tokens = set(normalize_transcript(state.get("current_text", "")).split())
        suspect_remaining = [
            f"'{r['wrong']}' (often misheard for '{r['correct']}')"
            for r in TELECOM_FEW_SHOT_REPAIRS
            if r["wrong"] != r["correct"] and normalize_transcript(r["wrong"]) in current_tokens
        ]

        # Two consecutive accepted rounds agreed on the exact same sentence with sufficient confidence
        if is_coherent and conf >= c_thresh and len(accepted) >= 2 and not suspect_remaining:
            last_norm = normalize_transcript(accepted[-1].get("candidate_text", ""))
            prev_norm = normalize_transcript(accepted[-2].get("candidate_text", ""))
            if last_norm == prev_norm:
                return {"_next": "finalize", "convergence_reason": "converged_stable"}

        # High confidence without needing further edits (either clean pass or already verified)
        if is_coherent and conf >= early_thresh and (not made_edit_last or len(accepted) >= 2) and not suspect_remaining:
            return {"_next": "finalize", "convergence_reason": "high_confidence_reached"}

        # Max iterations exhausted
        if it >= max_it:
            if is_coherent and conf >= c_thresh:
                return {"_next": "finalize", "convergence_reason": "threshold_met"}
            return {
                "_next": "finalize",
                "convergence_reason": "max_iterations_exhausted",
                "needs_human_review": True,
            }

        # Need another audit-and-fix round
        critique = state.get("critique", "")
        if not critique:
            if suspect_remaining:
                hint_str = "; ".join(suspect_remaining[:3])
                critique = (
                    f"Potential ASR error(s) still present: {hint_str}. "
                    "Audit these words carefully in Egyptian telecom context and fix if misheard."
                )
            elif made_edit_last:
                critique = (
                    "Edits were applied. Now re-audit EVERY word from the very first word to the last "
                    "against Egyptian telecom complaint context. Fix any remaining ASR error (e.g. truncated "
                    "nouns like طبق -> التطبيق), or confirm unchanged with confidence >= 0.92 if 100% clean."
                )
            else:
                critique = (
                    f"Confidence {conf:.2f} is below target {early_thresh:.2f}. "
                    "Re-read each Arabic word carefully. Fix only clearly misheard words."
                )
        return {"_next": "audit", "critique": critique}

    def node_finalize(state: TranscriptAuditState) -> dict:
        """Produce the final transcript, compute all word-level changes."""
        final = state.get("current_text") or state.get("pre_repaired_text") or state["raw_text"]
        raw = state["raw_text"]

        all_changes_dicts: list[dict] = []
        # Start with pre-repairs
        for c in state.get("pre_changes") or []:
            all_changes_dicts.append(c)
        # Add LLM-found changes (deduplicated)
        for c in state.get("all_changes") or []:
            exists = any(
                x.get("from") == c.get("from") and x.get("to") == c.get("to")
                for x in all_changes_dicts
            )
            if not exists:
                all_changes_dicts.append(c)

        # If no explicit changes but text differs, compute them via diff
        if not all_changes_dicts and normalize_transcript(final) != normalize_transcript(raw):
            wc = compute_word_changes(raw, final)
            all_changes_dicts = [{"from": c.from_text, "to": c.to_text, "reason": c.reason} for c in wc]

        return {
            "final_text": final,
            "all_changes": all_changes_dicts,
            "_next": "END",
        }

    def route_after_confidence(state: TranscriptAuditState) -> Literal["audit", "finalize"]:
        return state.get("_next", "finalize")  # type: ignore[return-value]

    # Build the graph
    graph = StateGraph(TranscriptAuditState)
    graph.add_node("pre_repair", node_pre_repair)
    graph.add_node("audit", node_audit)
    graph.add_node("confidence_check", node_confidence_check)
    graph.add_node("finalize", node_finalize)

    graph.set_entry_point("pre_repair")
    graph.add_conditional_edges(
        "pre_repair",
        route_after_confidence,
        {"audit": "audit", "finalize": "finalize"},
    )
    graph.add_edge("audit", "confidence_check")
    graph.add_conditional_edges(
        "confidence_check",
        route_after_confidence,
        {"audit": "audit", "finalize": "finalize"},
    )
    graph.add_edge("finalize", END)

    compiled = graph.compile()
    logger.info("VoiceGate LangGraph agent compiled successfully (model=%s, max_iter=%d)", model, max_iterations)
    return compiled


# ---------------------------------------------------------------------------
# AgenticTranscriptGate: drop-in upgrade for TranscriptVerificationGate
# ---------------------------------------------------------------------------

class AgenticTranscriptGate:
    """LangGraph-powered transcript audit-and-repair agent (VoiceGate Orchestrator).

    Uses a StateGraph with iterative audit-and-fix loop anchored in Egyptian
    telecom complaint context. Falls back to a direct-loop implementation if
    LangGraph is not installed.

    Drop-in replacement for TranscriptVerificationGate - exposes the same
    .verify() method and returns the same GateResult type.
    """

    def __init__(
        self,
        *,
        ollama_url: str = "http://127.0.0.1:11434",
        ollama_model: str = "qwen2.5:3b",
        max_iterations: int = 4,
        confidence_threshold: float = 0.75,
        early_stop_confidence: float = 0.90,
        timeout_s: float = 60.0,
        low_memory_mode: bool = True,
        fast_path_enabled: bool = True,
        reviewer_override: Callable[[dict[str, Any]], dict[str, Any] | str] | None = None,
    ) -> None:
        self.ollama_url = validate_loopback_url(ollama_url)
        self.ollama_model = ollama_model
        self.max_iterations = max(1, min(6, int(max_iterations)))
        self.confidence_threshold = float(confidence_threshold)
        self.early_stop_confidence = max(self.confidence_threshold, float(early_stop_confidence))
        self.timeout_s = float(timeout_s)
        self.low_memory_mode = bool(low_memory_mode)
        self.fast_path_enabled = bool(fast_path_enabled)
        self._reviewer_override = reviewer_override

        # Try to build the LangGraph compiled graph
        self._graph = build_langgraph_agent(
            ollama_url=self.ollama_url,
            model=self.ollama_model,
            max_iterations=self.max_iterations,
            confidence_threshold=self.confidence_threshold,
            early_stop_confidence=self.early_stop_confidence,
            timeout_s=self.timeout_s,
            fast_path_enabled=self.fast_path_enabled,
            reviewer_override=self._reviewer_override,
        )
        backend_label = "langgraph" if self._graph is not None else "direct_loop"
        logger.info(
            "AgenticTranscriptGate initialized backend=%s model=%s max_iter=%d",
            backend_label, self.ollama_model, self.max_iterations,
        )

    @property
    def canonical_model_name(self) -> str:
        if self._reviewer_override is not None:
            return f"{self.ollama_model}:test-override"
        return self.ollama_model

    def unload(self) -> None:
        """Signal Ollama to unload the model from RAM (keep_alive=0)."""
        try:
            with httpx.Client(timeout=3.0) as client:
                client.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": self.ollama_model, "prompt": "", "keep_alive": 0},
                )
            logger.info("Unloaded Ollama model=%s via keep_alive=0.", self.ollama_model)
        except Exception as exc:
            logger.debug("Optional Ollama unload skipped: %s", exc)

    def _override_call(self, context: dict[str, Any]) -> dict[str, Any]:
        """Call the reviewer_override function and normalize its response."""
        raw = self._reviewer_override(context)  # type: ignore[misc]
        if isinstance(raw, str):
            try:
                return _extract_json_object(raw)
            except ValueError:
                return {"corrected_text": raw, "confidence": 0.85, "is_coherent": True, "changes": []}
        return raw if isinstance(raw, dict) else {}

    def _run_direct_loop(
        self,
        raw_text: str,
        signals: STTSignalSummary,
    ) -> tuple[str, float, bool, str, list[dict], list[dict]]:
        """Fallback direct audit-and-fix loop when LangGraph is unavailable or for override mode."""
        pre_text, pre_changes_obj, _ = pre_repair_whisper_text(raw_text)
        pre_changes = [{"from": c.from_text, "to": c.to_text, "reason": c.reason} for c in pre_changes_obj]
        current = pre_text or raw_text
        best_text = current
        best_conf = 0.86 if pre_changes else 0.0
        best_coherent = bool(pre_changes)
        audit_history: list[dict] = []
        all_changes: list[dict] = list(pre_changes)
        convergence_reason = "max_iterations_exhausted"
        critique = ""

        for it in range(1, self.max_iterations + 1):
            context = {
                "iteration": it,
                "raw_text": raw_text,
                "current_text": current,
                "signals": asdict(signals),
                "critique": critique,
            }
            user_payload = {
                "iteration": it,
                "raw_whisper_text": raw_text,
                "current_candidate": current,
                "stt_signals": asdict(signals),
            }
            if critique:
                user_payload["critique_from_previous_round"] = critique

            try:
                if self._reviewer_override is not None:
                    data = self._override_call(context)
                else:
                    raw_reply = _call_ollama_chat(
                        ollama_url=self.ollama_url,
                        model=self.ollama_model,
                        system_prompt=VOICEGATE_SYSTEM_PROMPT,
                        user_message=json.dumps(user_payload, ensure_ascii=False),
                        timeout_s=self.timeout_s,
                    )
                    data = _extract_json_object(raw_reply)
            except Exception as exc:
                audit_history.append({"iteration": it, "status": "error", "error": str(exc)})
                critique = f"Error: {exc}. Return strict JSON."
                continue

            candidate = str(data.get("corrected_text") or current).strip()
            thinking = str(data.get("thinking") or "").strip()[:200]
            try:
                conf = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
            except (TypeError, ValueError):
                conf = 0.0
            is_coherent = bool(data.get("is_coherent", True))
            explicit = data.get("changes") or []
            explicit_changes = [
                {"from": str(c.get("from", "")), "to": str(c.get("to", "")), "reason": str(c.get("reason", "llm_repair"))}
                for c in (explicit if isinstance(explicit, list) else [])
                if isinstance(c, dict)
            ]

            is_valid, invalid_reason = validate_candidate_transcript(
                raw_text, candidate, anchor_text=pre_text or raw_text
            )
            audit_history.append({
                "iteration": it,
                "status": "accepted" if is_valid else "rejected",
                "thinking": thinking,
                "input_text": current,
                "candidate_text": candidate,
                "confidence": round(conf, 4),
                "is_coherent": is_coherent,
                "changes": explicit_changes,
                "rejection_reason": invalid_reason if not is_valid else None,
            })

            if not is_valid:
                critique = (
                    f"Rejected ({invalid_reason}). Keep exact word order. "
                    "Only fix clearly misheard words. Return unchanged if unsure."
                )
                continue

            current = candidate
            if conf > best_conf or not best_coherent:
                best_text = candidate
                best_conf = conf
                best_coherent = is_coherent
            for c in explicit_changes:
                if not any(x.get("from") == c.get("from") and x.get("to") == c.get("to") for x in all_changes):
                    all_changes.append(c)
            critique = ""

            if is_coherent and conf >= self.early_stop_confidence:
                convergence_reason = "high_confidence_reached"
                break
            if is_coherent and conf >= self.confidence_threshold:
                convergence_reason = "threshold_met"
                break
            if conf < self.confidence_threshold:
                critique = (
                    f"Confidence {conf:.2f} below {self.confidence_threshold:.2f}. "
                    "Find and fix any remaining misheard telecom words."
                )

        return best_text, best_conf, best_coherent, convergence_reason, audit_history, all_changes

    def verify(
        self,
        raw_text: str,
        *,
        min_avg_logprob: float | None = None,
        max_no_speech_prob: float | None = None,
        stt_review_reasons: str = "",
    ) -> GateResult:
        """Run the agentic audit-and-repair loop on a Whisper transcript.

        Returns a GateResult compatible with TranscriptVerificationGate.
        """
        t0 = time.perf_counter()
        raw_clean = (raw_text or "").strip()
        signals = analyze_stt_signals(
            raw_clean,
            min_avg_logprob=min_avg_logprob,
            max_no_speech_prob=max_no_speech_prob,
            stt_review_reasons=stt_review_reasons,
        )

        if not raw_clean:
            return GateResult(
                agent_name="VoiceGate Orchestrator",
                model=self.canonical_model_name,
                backend_used="none",
                status="skipped_empty",
                raw_text="",
                final_text="",
                final_text_norm="",
                language_mix="arabic_only",
                correction_applied=False,
                rounds_run=0,
                confidence=0.0,
                convergence_reason="empty_raw_transcript",
                needs_human_review=True,
                review_reason="uncertain_transcript",
                signal_summary=asdict(signals),
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                error="Raw Whisper transcript was empty.",
            )

        backend_used = (
            "langgraph-override"
            if (self._graph is not None and self._reviewer_override is not None)
            else ("langgraph" if self._graph is not None else "direct_loop")
        )
        model_used = self.canonical_model_name

        try:
            if self._graph is not None:
                # LangGraph path
                sig_dict = asdict(signals)
                sig_dict["min_avg_logprob"] = min_avg_logprob
                sig_dict["max_no_speech_prob"] = max_no_speech_prob
                initial_state: TranscriptAuditState = {
                    "raw_text": raw_clean,
                    "pre_repaired_text": "",
                    "current_text": raw_clean,
                    "iteration": 0,
                    "max_iterations": self.max_iterations,
                    "confidence": 0.0,
                    "confidence_threshold": self.confidence_threshold,
                    "early_stop_confidence": self.early_stop_confidence,
                    "audit_history": [],
                    "pre_changes": [],
                    "signal_summary": sig_dict,
                    "is_coherent": False,
                    "needs_human_review": False,
                    "convergence_reason": "max_iterations_exhausted",
                    "final_text": raw_clean,
                    "all_changes": [],
                    "backend_used": "langgraph",
                    "model_used": self.ollama_model,
                    "error": "",
                    "critique": "",
                    "_next": "pre_repair",
                }
                final_state = self._graph.invoke(initial_state)
                final_text = final_state.get("final_text") or raw_clean
                confidence = final_state.get("confidence", 0.0)
                is_coherent = final_state.get("is_coherent", False)
                convergence_reason = final_state.get("convergence_reason", "max_iterations_exhausted")
                needs_human_review = final_state.get("needs_human_review", False)
                audit_history = final_state.get("audit_history", [])
                all_changes_dicts = final_state.get("all_changes", [])
                pre_changes_dicts = final_state.get("pre_changes", [])
                rounds_run = final_state.get("iteration", 0)
            else:
                # Direct loop path (fallback or override)
                final_text, confidence, is_coherent, convergence_reason, audit_history, all_changes_dicts = (
                    self._run_direct_loop(raw_clean, signals)
                )
                pre_changes_dicts = []
                for entry in audit_history:
                    if entry.get("iteration") == 0:
                        pre_changes_dicts = entry.get("changes", [])
                        break
                rounds_run = len([h for h in audit_history if h.get("status") != "error"])
                needs_human_review = False

        except Exception as exc:
            logger.warning("AgenticTranscriptGate failed (%s); preserving raw transcript.", exc)
            return GateResult(
                agent_name="VoiceGate Orchestrator",
                model=model_used,
                backend_used=backend_used,
                status="fallback_error",
                raw_text=raw_clean,
                final_text=raw_clean,
                final_text_norm=normalize_transcript(raw_clean),
                language_mix=detect_language_mix(raw_clean),
                correction_applied=False,
                rounds_run=0,
                confidence=0.0,
                convergence_reason="runtime_fallback",
                needs_human_review=True,
                review_reason="uncertain_transcript",
                signal_summary=asdict(signals),
                changes=[],
                trace=[],
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                error=str(exc),
            )
        finally:
            if self.low_memory_mode:
                self.unload()

        # Acoustic safety cap: if Whisper reported severe acoustic degradation, never auto-pass
        severe_acoustic_loss = min_avg_logprob is not None and float(min_avg_logprob) < -0.75
        if severe_acoustic_loss:
            confidence = min(float(confidence), 0.65)
            needs_human_review = True
            convergence_reason = "severe_low_acoustic_logprob"
            if "severe_acoustic_degradation" not in signals.lexical_flags:
                signals.lexical_flags.append("severe_acoustic_degradation")

        # Determine final confidence decision
        confident_enough = (
            not severe_acoustic_loss
            and (
                (is_coherent and confidence >= self.confidence_threshold)
                or convergence_reason in ("high_confidence_reached", "converged_stable", "threshold_met")
            )
        )

        # Also consider: if we have no human_review flag AND made a valid correction, treat as confident
        if not needs_human_review and not confident_enough:
            # Check if at least one round was accepted
            accepted_rounds = [h for h in audit_history if h.get("status") == "accepted"]
            if accepted_rounds and confidence >= 0.70:
                confident_enough = True

        # Build trace from audit history
        trace: list[GateRoundTrace] = []
        for entry in audit_history:
            changes_wc = [
                WordChange(from_text=c.get("from", ""), to_text=c.get("to", ""), reason=c.get("reason", ""))
                for c in entry.get("changes", [])
            ]
            trace.append(GateRoundTrace(
                round_number=entry.get("iteration", 0),
                thinking=entry.get("thinking", ""),
                input_text=entry.get("input_text", ""),
                candidate_text=entry.get("candidate_text", ""),
                confidence=entry.get("confidence", 0.0),
                is_coherent=entry.get("is_coherent", False),
                accepted=entry.get("status") == "accepted",
                critique=entry.get("rejection_reason"),
                changes=changes_wc,
            ))

        # Build clean, accurate word-level changes from raw_clean -> final_text
        reason_map: dict[tuple[str, str], str] = {}
        for c in all_changes_dicts:
            f_t = str(c.get("from", "")).strip()
            t_t = str(c.get("to", "")).strip()
            if f_t and t_t and f_t != t_t:
                reason_map[(normalize_transcript(f_t), normalize_transcript(t_t))] = str(c.get("reason", "asr_repair"))

        final_changes = compute_word_changes(raw_clean, final_text)
        for wc in final_changes:
            mapped = reason_map.get((normalize_transcript(wc.from_text), normalize_transcript(wc.to_text)))
            if mapped:
                wc.reason = mapped

        correction_applied = normalize_transcript(final_text) != normalize_transcript(raw_clean)

        if not confident_enough or needs_human_review:
            safe_text = final_text if correction_applied else raw_clean
            return GateResult(
                agent_name="VoiceGate Orchestrator",
                model=model_used,
                backend_used=backend_used,
                status="uncertain",
                raw_text=raw_clean,
                final_text=safe_text,
                final_text_norm=normalize_transcript(safe_text),
                language_mix=detect_language_mix(safe_text),
                correction_applied=normalize_transcript(safe_text) != normalize_transcript(raw_clean),
                rounds_run=rounds_run,
                confidence=confidence,
                convergence_reason=convergence_reason,
                needs_human_review=True,
                review_reason="uncertain_transcript",
                signal_summary=asdict(signals),
                changes=compute_word_changes(raw_clean, safe_text),
                trace=trace,
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                error="",
            )

        return GateResult(
            agent_name="VoiceGate Orchestrator",
            model=model_used,
            backend_used=backend_used,
            status="corrected" if correction_applied else "verified",
            raw_text=raw_clean,
            final_text=final_text,
            final_text_norm=normalize_transcript(final_text),
            language_mix=detect_language_mix(final_text),
            correction_applied=correction_applied,
            rounds_run=rounds_run,
            confidence=confidence,
            convergence_reason=convergence_reason,
            needs_human_review=False,
            review_reason=None,
            signal_summary=asdict(signals),
            changes=final_changes,
            trace=trace,
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
            error="",
        )
