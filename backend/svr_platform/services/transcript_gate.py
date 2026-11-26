"""Local Qwen Transcript Verification Gate (iterative word repair and anti-hallucination guardrails)."""

from __future__ import annotations

import difflib
import gc
import json
import logging
import os
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable
from urllib.parse import urlparse

import httpx

from .text_norm import detect_language_mix, normalize_transcript

logger = logging.getLogger("svr_platform.transcript_gate")

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]")
_DIGITS_RE = re.compile(r"\d+")
_LATIN_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")

# Domain phonetic/ASR confusion hints common in Egyptian Arabic telecom voicemails
TELECOM_LEXICAL_HINTS: dict[str, str] = {
    "فور جي": "4G",
    "فايف جي": "5G",
    "واي فاي": "Wi-Fi",
    "واي فاى": "Wi-Fi",
    "فودافون": "Vodafone",
    "اورانج": "Orange",
    "اتصالات": "Etisalat",
    "راوتر": "router",
    "شريحة": "SIM",
    "سيم": "SIM",
    "فويس ميل": "voicemail",
}

# High-precision Egyptian Arabic telecom ASR phonetic/orthographic repairs
EGYPTIAN_TELECOM_ASR_REPAIRS: dict[str, str] = {
    "الكلتون": "الكول تون",
    "كلتون": "كول تون",
    "يخسموا": "يخصموا",
    "تخسموا": "تخصموا",
    "بيخسموا": "بيخصموا",
    "بيتخسم": "بيتخصم",
    "اتخسم": "اتخصم",
    "السبكة": "الشبكة",
    "سبكة": "شبكة",
    "السريحة": "الشريحة",
    "سريحة": "شريحة",
    "الراوترز": "الراوتر",
    "الوطر": "الراوتر",
    "بوقتي": "باقتي",
    "باقيتي": "باقتي",
}


def deduplicate_whisper_sequences(text: str) -> tuple[str, list[WordChange]]:
    """Collapse consecutive 1-to-4-word Whisper stutter/loop sequences cleanly."""
    words = (text or "").strip().split()
    if len(words) < 2:
        return (text or "").strip(), []

    changes: list[WordChange] = []
    changed = True
    current = words
    while changed:
        changed = False
        for n in range(4, 0, -1):
            out: list[str] = []
            idx = 0
            while idx < len(current):
                if idx + 2 * n <= len(current):
                    left_norm = [normalize_transcript(w) for w in current[idx : idx + n]]
                    right_norm = [normalize_transcript(w) for w in current[idx + n : idx + 2 * n]]
                    if left_norm == right_norm and any(len(t) > 0 for t in left_norm):
                        seq_str = " ".join(current[idx : idx + n])
                        changes.append(
                            WordChange(
                                from_text=f"{seq_str} {seq_str}",
                                to_text=seq_str,
                                reason="duplicate_sequence_removed",
                            )
                        )
                        out.extend(current[idx : idx + n])
                        idx += 2 * n
                        # Collapse 3+ consecutive repeats of the same n-gram
                        while idx + n <= len(current) and [normalize_transcript(w) for w in current[idx : idx + n]] == left_norm:
                            idx += n
                        changed = True
                        continue
                out.append(current[idx])
                idx += 1
            current = out
            if changed:
                break

    return " ".join(current).strip(), changes


def pre_repair_whisper_text(raw_text: str) -> tuple[str, list[WordChange], list[str]]:
    """Apply deterministic Whisper stutter deduplication and Egyptian telecom ASR repairs."""
    dedup_text, dup_changes = deduplicate_whisper_sequences(raw_text)
    words = dedup_text.split()
    repaired_words: list[str] = []
    lexical_changes: list[WordChange] = []
    flags: list[str] = []

    if dup_changes:
        flags.append("duplicate_sequence_detected")

    for w in words:
        w_norm = normalize_transcript(w)
        replacement = EGYPTIAN_TELECOM_ASR_REPAIRS.get(w) or EGYPTIAN_TELECOM_ASR_REPAIRS.get(w_norm)
        if replacement and normalize_transcript(replacement) != w_norm:
            repaired_words.append(replacement)
            lexical_changes.append(
                WordChange(
                    from_text=w,
                    to_text=replacement,
                    reason="egyptian_telecom_asr_repair",
                )
            )
        else:
            repaired_words.append(w)

    if lexical_changes:
        flags.append("telecom_asr_word_repaired")

    final_pre = " ".join(repaired_words).strip()
    return final_pre, [*dup_changes, *lexical_changes], flags


def validate_loopback_url(url: str) -> str:
    """Enforce PRD AI6/AI7: local LLM endpoints must strictly target loopback addresses."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Ollama URL must use http or https, got: {url!r}")
    host = (parsed.hostname or "").lower()
    allowed_hosts = set(_LOOPBACK_HOSTS)
    if os.environ.get("SVR_ALLOW_DOCKER_OLLAMA", "").strip().lower() in ("1", "true", "yes"):
        allowed_hosts.add("ollama")
    if host not in allowed_hosts:
        raise ValueError(
            f"External LLM host {host!r} is forbidden by local-first privacy rules; "
            "only loopback hosts (127.0.0.1, localhost, ::1) are allowed."
        )
    return url.rstrip("/")


@dataclass(frozen=True)
class STTSignalSummary:
    acoustic_risk: str  # low | medium | high
    lexical_flags: list[str]
    suspect_hints: list[str]
    recommended_rounds: int


@dataclass
class WordChange:
    from_text: str
    to_text: str
    reason: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "from": self.from_text,
            "to": self.to_text,
            "reason": self.reason,
        }


@dataclass
class GateRoundTrace:
    round_number: int
    thinking: str
    input_text: str
    candidate_text: str
    confidence: float
    is_coherent: bool
    accepted: bool
    critique: str | None = None
    changes: list[WordChange] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "round": self.round_number,
            "thinking": self.thinking,
            "input_text": self.input_text,
            "candidate_text": self.candidate_text,
            "confidence": round(float(self.confidence), 4),
            "is_coherent": self.is_coherent,
            "accepted": self.accepted,
            "critique": self.critique,
            "changes": [c.to_dict() for c in self.changes],
        }


@dataclass
class GateResult:
    agent_name: str
    model: str
    backend_used: str
    status: str  # verified | corrected | uncertain | skipped_empty | fallback_error
    raw_text: str
    final_text: str
    final_text_norm: str
    language_mix: str
    correction_applied: bool
    rounds_run: int
    confidence: float
    convergence_reason: str
    needs_human_review: bool
    review_reason: str | None
    signal_summary: dict[str, Any]
    changes: list[WordChange] = field(default_factory=list)
    trace: list[GateRoundTrace] = field(default_factory=list)
    latency_ms: float = 0.0
    error: str = ""

    def to_report_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "model": self.model,
            "backend_used": self.backend_used,
            "status": self.status,
            "raw_text": self.raw_text,
            "corrected_text": self.final_text,
            "correction_applied": self.correction_applied,
            "rounds_run": self.rounds_run,
            "confidence": round(float(self.confidence), 4),
            "convergence_reason": self.convergence_reason,
            "needs_human_review": self.needs_human_review,
            "review_reason": self.review_reason,
            "signal_summary": self.signal_summary,
            "changes": [c.to_dict() for c in self.changes],
            "trace": [t.to_dict() for t in self.trace],
            "latency_ms": round(float(self.latency_ms), 2),
            "error": self.error,
        }


def analyze_stt_signals(
    raw_text: str,
    *,
    min_avg_logprob: float | None = None,
    max_no_speech_prob: float | None = None,
    stt_review_reasons: str = "",
) -> STTSignalSummary:
    """Assess Whisper output confidence and Egyptian Arabic lexical risk before running Qwen."""
    flags: list[str] = []
    hints: list[str] = []
    clean = (raw_text or "").strip()

    if min_avg_logprob is not None and min_avg_logprob < -0.50:
        flags.append("low_acoustic_logprob")
    if max_no_speech_prob is not None and max_no_speech_prob > 0.80:
        flags.append("high_no_speech_prob")
    if stt_review_reasons:
        flags.extend([r for r in stt_review_reasons.split(";") if r and r not in flags])

    tokens = clean.split()
    if len(tokens) < 4:
        flags.append("very_short_utterance")

    # Repeated adjacent words can indicate Whisper decoding stutter
    for idx in range(len(tokens) - 1):
        if normalize_transcript(tokens[idx]) == normalize_transcript(tokens[idx + 1]) and len(tokens[idx]) > 1:
            flags.append("repeated_adjacent_token")
            hints.append(tokens[idx])
            break

    # Transliterated telecom terms that Whisper occasionally renders phonetically
    lowered = clean.lower()
    for phrase, canonical in TELECOM_LEXICAL_HINTS.items():
        if phrase in lowered:
            hints.append(f"{phrase}->{canonical}")

    if any(f in flags for f in ("low_acoustic_logprob", "high_no_speech_prob", "repeated_adjacent_token")):
        acoustic_risk = "high"
        rec_rounds = 3
    elif flags or hints:
        acoustic_risk = "medium"
        rec_rounds = 2
    else:
        acoustic_risk = "low"
        rec_rounds = 2

    return STTSignalSummary(
        acoustic_risk=acoustic_risk,
        lexical_flags=flags,
        suspect_hints=hints[:8],
        recommended_rounds=rec_rounds,
    )


def validate_candidate_transcript(
    raw_text: str,
    candidate_text: str,
    *,
    anchor_text: str | None = None,
) -> tuple[bool, str | None]:
    """Deterministic anti-hallucination validator guarding Qwen 0.5B edits."""
    cand = (candidate_text or "").strip()
    raw = (anchor_text or raw_text or "").strip()
    if not cand:
        return False, "empty_candidate"

    if _CJK_RE.search(cand):
        return False, "forbidden_non_arabic_cjk_script"

    # Guard against ungrounded Latin-script word injection when raw Whisper text was Arabic-only
    raw_latin = {t.lower() for t in _LATIN_TOKEN_RE.findall(raw) if not t.isdigit()}
    cand_latin = {t.lower() for t in _LATIN_TOKEN_RE.findall(cand) if not t.isdigit()}
    allowed_telecom_latin = {"4g", "5g", "3g", "wifi", "wi", "fi", "sim", "lte", "dsl", "adsl", "vdsl", "gb", "mb"}
    if not raw_latin and (cand_latin - allowed_telecom_latin):
        return False, f"unexpected_latin_injection: {sorted(cand_latin - allowed_telecom_latin)}"

    # Guard against runaway generation or severe truncation
    if len(raw) >= 12:
        ratio = len(cand) / float(len(raw))
        if ratio < 0.50:
            return False, f"candidate_too_short (ratio={ratio:.2f})"
        if ratio > 1.75:
            return False, f"candidate_over_expanded (ratio={ratio:.2f})"
    elif len(cand) > max(48, len(raw) * 3):
        return False, "short_candidate_over_expanded"

    # Guard against invented numeric entities (phone numbers, currency amounts, IDs)
    raw_digits = set(_DIGITS_RE.findall(raw))
    cand_digits = set(_DIGITS_RE.findall(cand))
    invented_multi_digits = {d for d in (cand_digits - raw_digits) if len(d) >= 2}
    if invented_multi_digits:
        return False, f"invented_numeric_tokens: {sorted(invented_multi_digits)}"

    # Semantic anchor check: repaired transcript must stay anchored to raw Whisper text
    norm_raw = normalize_transcript(raw)
    norm_cand = normalize_transcript(cand)
    char_similarity = difflib.SequenceMatcher(None, norm_raw, norm_cand).ratio()
    if char_similarity < 0.65:
        return False, f"excessive_semantic_drift (similarity={char_similarity:.2f})"
    raw_words = norm_raw.split()
    cand_words = norm_cand.split()
    if len(raw_words) >= 4:
        word_similarity = difflib.SequenceMatcher(None, raw_words, cand_words).ratio()
        if word_similarity < 0.58:
            return False, f"word_order_or_deletion_drift (word_similarity={word_similarity:.2f})"

    return True, None


def compute_word_changes(before: str, after: str, explicit: list[WordChange] | None = None) -> list[WordChange]:
    """Build explicit word-level change entries between two sentences."""
    if normalize_transcript(before) == normalize_transcript(after) and before.strip() == after.strip():
        return []
    if explicit:
        cleaned = [c for c in explicit if c.from_text.strip() or c.to_text.strip()]
        if cleaned:
            return cleaned

    a_words = before.split()
    b_words = after.split()
    matcher = difflib.SequenceMatcher(None, a_words, b_words)
    derived: list[WordChange] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        derived.append(
            WordChange(
                from_text=" ".join(a_words[i1:i2]),
                to_text=" ".join(b_words[j1:j2]),
                reason=tag,
            )
        )
    return derived


def _extract_json_object(raw_output: str) -> dict[str, Any]:
    """Parse JSON object from LLM text output, tolerating code fences or surrounding prose."""
    text = (raw_output or "").strip()
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
        loaded = json.loads(text[start : end + 1])
        if isinstance(loaded, dict):
            return loaded
    raise ValueError("LLM response did not contain a valid JSON object.")


def _parse_gate_response(raw_output: str | dict[str, Any], fallback_text: str) -> tuple[str, str, float, bool, list[WordChange]]:
    if isinstance(raw_output, dict):
        data = raw_output
    else:
        data = _extract_json_object(str(raw_output))

    corrected = str(data.get("corrected_text") or fallback_text).strip()
    thinking = str(data.get("thinking") or "").strip()[:500]
    try:
        conf = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    is_coherent = bool(data.get("is_coherent", True))

    parsed_changes: list[WordChange] = []
    raw_changes = data.get("changes")
    if isinstance(raw_changes, list):
        for item in raw_changes:
            if isinstance(item, dict):
                f_txt = str(item.get("from", "")).strip()
                t_txt = str(item.get("to", "")).strip()
                reason = str(item.get("reason", "")).strip()
                if f_txt or t_txt:
                    parsed_changes.append(WordChange(from_text=f_txt, to_text=t_txt, reason=reason))

    return corrected, thinking, conf, is_coherent, parsed_changes


class TranscriptVerificationGate:
    """Iterative local LLM transcript correction and verification gate (Ollama or HuggingFace)."""

    def __init__(
        self,
        *,
        backend: str = "auto",
        ollama_url: str = "http://127.0.0.1:11434",
        ollama_model: str = "qwen2:0.5b",
        hf_model_id: str = "Qwen/Qwen2.5-0.5B-Instruct",
        max_rounds: int = 3,
        confidence_threshold: float = 0.75,
        early_stop_confidence: float = 0.88,
        timeout_s: float = 25.0,
        low_memory_mode: bool | None = None,
        reviewer_override: Callable[[dict[str, Any]], dict[str, Any] | str] | None = None,
    ) -> None:
        self.backend = (backend or "auto").strip().lower()
        self.ollama_url = validate_loopback_url(ollama_url)
        self.ollama_model = ollama_model
        self.hf_model_id = hf_model_id
        self.max_rounds = max(1, min(5, int(max_rounds)))
        self.confidence_threshold = float(confidence_threshold)
        self.early_stop_confidence = max(self.confidence_threshold, float(early_stop_confidence))
        self.timeout_s = float(timeout_s)
        if low_memory_mode is None:
            env_flag = os.environ.get("SVR_LOW_MEMORY_MODE", "").strip().lower()
            self.low_memory_mode = env_flag in ("1", "true", "yes") or env_flag == ""
        else:
            self.low_memory_mode = bool(low_memory_mode)
        self._reviewer_override = reviewer_override

        self._lock = threading.Lock()
        self._hf_model = None
        self._hf_tokenizer = None
        self._ollama_loaded = False

    @property
    def canonical_model_name(self) -> str:
        if self._reviewer_override is not None:
            return f"{self.ollama_model}:verified-override"
        if self.backend == "transformers":
            return self.hf_model_id
        return self.ollama_model

    def unload(self) -> None:
        """Unload local Qwen weights (HuggingFace or Ollama) to reclaim CPU memory."""
        with self._lock:
            if self._hf_model is not None or self._hf_tokenizer is not None:
                self._hf_model = None
                self._hf_tokenizer = None
                gc.collect()
                logger.info("Unloaded in-process Qwen model=%s to reclaim host memory.", self.hf_model_id)
            if self._ollama_loaded:
                self._ollama_loaded = False
                try:
                    with httpx.Client(timeout=3.0) as client:
                        client.post(
                            f"{self.ollama_url}/api/generate",
                            json={"model": self.ollama_model, "prompt": "", "keep_alive": 0},
                        )
                    logger.info("Unloaded Ollama Qwen model=%s via keep_alive=0.", self.ollama_model)
                except Exception as exc:
                    logger.debug("Optional Ollama unload cleanup skipped: %s", exc)

    def _build_messages(
        self,
        *,
        raw_text: str,
        current_text: str,
        round_number: int,
        signals: STTSignalSummary,
        critique: str | None,
    ) -> list[dict[str, str]]:
        system_prompt = (
            "You are VoiceGate Transcript Verification Gate for Egypt Telecom Care.\n"
            "Inspect an Egyptian Arabic / telecom voicemail transcript produced by Whisper ASR.\n"
            "Repair ONLY misheard Arabic letters/words or garbled telecom terms so the sentence is accurate.\n"
            "Example input: {\"raw_whisper_text\": \"السبكة في الفور جي ضعيفة جدا\"}\n"
            "Example output: {\"thinking\": \"السبكة is an ASR typo for الشبكة\", \"suspect_words\": [\"السبكة\"], "
            "\"corrected_text\": \"الشبكة في الفور جي ضعيفة جدا\", \"confidence\": 0.86, \"is_coherent\": true, "
            "\"changes\": [{\"from\": \"السبكة\", \"to\": \"الشبكة\", \"reason\": \"arabic_telecom_typo\"}]}\n"
            "Strict Rules:\n"
            "1. Output strictly a single compact JSON object (keep thinking <= 15 words) with keys: thinking, suspect_words, corrected_text, confidence, is_coherent, changes.\n"
            "2. Keep the exact sentence length and word order. Replace ONLY misspelled words; NEVER delete or reorder words.\n"
            "3. Preserve Egyptian Arabic dialect and telecom terms (4G, 5G, Wi-Fi, SIM, router, fiber).\n"
            "4. NEVER invent phone numbers, amounts, dates, or unrelated complaints.\n"
            "5. If no word is wrong, return exact current_candidate as corrected_text with confidence >= 0.85."
        )
        user_payload = {
            "round": round_number,
            "raw_whisper_text": raw_text,
            "current_candidate": current_text,
            "stt_signals": asdict(signals),
            "previous_critique": critique,
        }
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]

    def _ollama_has_model(self) -> bool:
        try:
            with httpx.Client(timeout=min(3.0, self.timeout_s)) as client:
                resp = client.get(f"{self.ollama_url}/api/tags")
                if resp.status_code != 200:
                    return False
                data = resp.json()
                models = [str(m.get("name", "")) for m in data.get("models", []) if isinstance(m, dict)]
                target_base = self.ollama_model.split(":")[0]
                return any(m == self.ollama_model or m.startswith(f"{target_base}:") for m in models)
        except Exception:
            return False

    def _call_ollama(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.ollama_model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "keep_alive": "2m",
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 380,
            },
        }
        self._ollama_loaded = True
        with httpx.Client(timeout=self.timeout_s) as client:
            resp = client.post(f"{self.ollama_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("message") or {}
            content = str(msg.get("content") or "").strip()
            if not content:
                raise RuntimeError("Ollama returned an empty response body.")
            return content

    def _ensure_hf_model(self) -> tuple[Any, Any]:
        if self._hf_model is not None and self._hf_tokenizer is not None:
            return self._hf_tokenizer, self._hf_model
        with self._lock:
            if self._hf_model is not None and self._hf_tokenizer is not None:
                return self._hf_tokenizer, self._hf_model
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            logger.info("Loading local HuggingFace Qwen model=%s", self.hf_model_id)
            tok = AutoTokenizer.from_pretrained(self.hf_model_id, local_files_only=True)
            model = AutoModelForCausalLM.from_pretrained(
                self.hf_model_id,
                torch_dtype=torch.float32,
                local_files_only=True,
            )
            model.eval()
            self._hf_tokenizer = tok
            self._hf_model = model
            return tok, model

    def _call_transformers(self, messages: list[dict[str, str]]) -> str:
        import torch

        tok, model = self._ensure_hf_model()
        prompt_text = tok.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = tok(prompt_text, return_tensors="pt")
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=280,
                do_sample=False,
                pad_token_id=tok.eos_token_id,
            )
        gen_ids = outputs[0][inputs["input_ids"].shape[1] :]
        return str(tok.decode(gen_ids, skip_special_tokens=True)).strip()

    def _invoke_backend(self, context: dict[str, Any], messages: list[dict[str, str]]) -> tuple[str | dict[str, Any], str, str]:
        if self._reviewer_override is not None:
            return self._reviewer_override(context), "override", self.canonical_model_name

        if self.backend in ("auto", "ollama"):
            if self._ollama_has_model():
                return self._call_ollama(messages), "ollama", self.ollama_model
            if self.backend == "ollama":
                raise RuntimeError(
                    f"Local Ollama model '{self.ollama_model}' is unavailable at {self.ollama_url}"
                )

        if self.backend in ("auto", "transformers"):
            return self._call_transformers(messages), "transformers", self.hf_model_id

        raise RuntimeError(f"Unsupported transcript gate backend: {self.backend!r}")

    def verify(
        self,
        raw_text: str,
        *,
        min_avg_logprob: float | None = None,
        max_no_speech_prob: float | None = None,
        stt_review_reasons: str = "",
    ) -> GateResult:
        """Run iterative Whisper-output inspection and word correction until confident or bounded."""
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

        pre_repaired_text, pre_changes, pre_flags = pre_repair_whisper_text(raw_clean)
        if pre_flags:
            signals = STTSignalSummary(
                acoustic_risk="high" if signals.acoustic_risk == "high" or pre_changes else signals.acoustic_risk,
                lexical_flags=list(dict.fromkeys([*signals.lexical_flags, *pre_flags])),
                suspect_hints=list(
                    dict.fromkeys([*signals.suspect_hints, *[f"{c.from_text}->{c.to_text}" for c in pre_changes]])
                )[:10],
                recommended_rounds=max(signals.recommended_rounds, 2),
            )

        current_text = pre_repaired_text or raw_clean
        best_valid_text = current_text
        best_valid_confidence = 0.86 if pre_changes else 0.0
        best_valid_coherent = bool(pre_changes)
        prev_accepted_norm: str | None = None
        critique: str | None = None
        trace: list[GateRoundTrace] = []
        if pre_changes:
            trace.append(
                GateRoundTrace(
                    round_number=0,
                    thinking=(
                        "Pre-gate detected Whisper duplicate sequence(s) and/or Egyptian telecom ASR typo(s) "
                        "before Qwen contextual verification."
                    ),
                    input_text=raw_clean,
                    candidate_text=current_text,
                    confidence=0.86,
                    is_coherent=True,
                    accepted=True,
                    critique=None,
                    changes=pre_changes,
                )
            )
        backend_used = "override" if self._reviewer_override is not None else self.backend
        model_used = self.canonical_model_name
        convergence_reason = "max_rounds_reached"
        has_accepted_candidate = bool(pre_changes)

        try:
            target_rounds = min(self.max_rounds, max(1, self.max_rounds))
            for round_idx in range(1, target_rounds + 1):
                messages = self._build_messages(
                    raw_text=raw_clean,
                    current_text=current_text,
                    round_number=round_idx,
                    signals=signals,
                    critique=critique,
                )
                ctx = {
                    "round": round_idx,
                    "raw_text": raw_clean,
                    "current_text": current_text,
                    "signals": asdict(signals),
                    "critique": critique,
                }
                try:
                    raw_reply, backend_used, model_used = self._invoke_backend(ctx, messages)
                    candidate_text, thinking, conf, is_coherent, explicit_changes = _parse_gate_response(
                        raw_reply, current_text
                    )
                except ValueError as parse_exc:
                    trace.append(
                        GateRoundTrace(
                            round_number=round_idx,
                            thinking="",
                            input_text=current_text,
                            candidate_text=current_text,
                            confidence=0.0,
                            is_coherent=False,
                            accepted=False,
                            critique=f"malformed_json_output: {parse_exc}",
                            changes=[],
                        )
                    )
                    critique = (
                        "Previous response was incomplete or invalid JSON. Return one short valid JSON object "
                        "with concise thinking under 15 words."
                    )
                    continue
                is_valid, invalid_reason = validate_candidate_transcript(
                    raw_clean,
                    candidate_text,
                    anchor_text=pre_repaired_text or raw_clean,
                )
                round_changes = compute_word_changes(current_text, candidate_text, explicit_changes)

                trace.append(
                    GateRoundTrace(
                        round_number=round_idx,
                        thinking=thinking,
                        input_text=current_text,
                        candidate_text=candidate_text,
                        confidence=conf,
                        is_coherent=is_coherent,
                        accepted=is_valid,
                        critique=invalid_reason,
                        changes=round_changes,
                    )
                )

                if not is_valid:
                    critique = (
                        f"Previous revision failed validation ({invalid_reason}). "
                        "Keep the exact Arabic complaint meaning, preserve all digits, and edit ONLY unclear words."
                    )
                    continue

                has_accepted_candidate = True
                cand_norm = normalize_transcript(candidate_text)
                made_edit = cand_norm != normalize_transcript(current_text)

                if conf >= best_valid_confidence or not best_valid_coherent:
                    best_valid_text = candidate_text
                    best_valid_confidence = conf
                    best_valid_coherent = is_coherent

                current_text = candidate_text
                critique = None

                # Stop early once confident and coherent on an unedited/clean confirmation
                if is_coherent and conf >= self.early_stop_confidence:
                    convergence_reason = "high_confidence_reached"
                    break

                # Converged when a verification pass produces the identical sentence with sufficient confidence
                if (
                    not made_edit
                    and prev_accepted_norm is not None
                    and cand_norm == prev_accepted_norm
                    and is_coherent
                    and conf >= self.confidence_threshold
                ):
                    convergence_reason = "converged_stable"
                    break

                # Trigger next self-check critique if sentence changed or confidence is still below threshold
                if conf < self.confidence_threshold or not is_coherent:
                    critique = (
                        f"Confidence {conf:.2f} is below target {self.confidence_threshold:.2f}. "
                        "Re-read the repaired sentence carefully and verify every telecom term and Arabic word."
                    )
                prev_accepted_norm = cand_norm

        except Exception as exc:
            logger.warning("TranscriptVerificationGate failed cleanly (%s); preserving raw transcript.", exc)
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
                rounds_run=len(trace),
                confidence=0.0,
                convergence_reason="runtime_fallback",
                needs_human_review=True,
                review_reason="uncertain_transcript",
                signal_summary=asdict(signals),
                changes=[],
                trace=trace,
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                error=str(exc),
            )
        finally:
            if self.low_memory_mode:
                self.unload()

        # Final confidence decision gate
        confident_enough = (
            has_accepted_candidate
            and best_valid_coherent
            and best_valid_confidence >= self.confidence_threshold
        )
        if not confident_enough:
            # Never pass an unverified or low-confidence mutation silently; keep safest grounded text & escalate
            safe_text = best_valid_text if has_accepted_candidate else raw_clean
            all_changes = compute_word_changes(raw_clean, safe_text)
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
                rounds_run=len(trace),
                confidence=best_valid_confidence,
                convergence_reason=convergence_reason,
                needs_human_review=True,
                review_reason="uncertain_transcript",
                signal_summary=asdict(signals),
                changes=all_changes,
                trace=trace,
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                error="",
            )

        final_changes = compute_word_changes(raw_clean, best_valid_text)
        if pre_changes and normalize_transcript(best_valid_text) == normalize_transcript(pre_repaired_text):
            final_changes = pre_changes
        correction_applied = (
            normalize_transcript(best_valid_text) != normalize_transcript(raw_clean)
            or best_valid_text.strip() != raw_clean
        )
        return GateResult(
            agent_name="VoiceGate Orchestrator",
            model=model_used,
            backend_used=backend_used,
            status="corrected" if correction_applied else "verified",
            raw_text=raw_clean,
            final_text=best_valid_text,
            final_text_norm=normalize_transcript(best_valid_text),
            language_mix=detect_language_mix(best_valid_text),
            correction_applied=correction_applied,
            rounds_run=len(trace),
            confidence=best_valid_confidence,
            convergence_reason=convergence_reason,
            needs_human_review=False,
            review_reason=None,
            signal_summary=asdict(signals),
            changes=final_changes,
            trace=trace,
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
            error="",
        )
