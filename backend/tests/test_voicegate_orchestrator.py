"""Unit, security, and integration tests for VoiceGate Orchestrator and TranscriptVerificationGate."""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from svr_platform.api.main import create_app
from svr_platform.config import Settings
from svr_platform.services.agentic_gate import AgenticTranscriptGate
from svr_platform.services.classification import MARBERTv2ClassifierService
from svr_platform.services.stt import WhisperSTTService, normalize_wav_16k_loudness
from svr_platform.services.text_norm import normalize_transcript
from svr_platform.services.transcript_gate import (
    TranscriptVerificationGate,
    analyze_stt_signals,
    deduplicate_whisper_sequences,
    validate_candidate_transcript,
    validate_loopback_url,
)
from svr_platform.taxonomy import TRAINED_CLASSES_BY_FIELD
from tests.conftest import make_wav_bytes


def _make_probs(field: str, winner: str, top_prob: float) -> dict[str, float]:
    classes = TRAINED_CLASSES_BY_FIELD[field]
    others = [c for c in classes if c != winner]
    rem = (1.0 - top_prob) / len(others)
    probs = {c: round(rem, 6) for c in others}
    probs[winner] = round(1.0 - sum(probs.values()), 6)
    return probs


def _sample_prediction(category: str = "network_and_connectivity") -> dict[str, dict[str, Any]]:
    return {
        "complaint_category": {
            "label": category,
            "probabilities": _make_probs("complaint_category", category, 0.92),
        },
        "complaint_urgency": {
            "label": "high",
            "probabilities": _make_probs("complaint_urgency", "high", 0.89),
        },
        "customer_state": {
            "label": "frustrated",
            "probabilities": _make_probs("customer_state", "frustrated", 0.90),
        },
        "churn_risk": {
            "label": "not_at_risk",
            "probabilities": _make_probs("churn_risk", "not_at_risk", 0.94),
        },
    }


def test_loopback_url_guard_blocks_external_llm(tmp_path):
    assert validate_loopback_url("http://127.0.0.1:11434/") == "http://127.0.0.1:11434"
    assert validate_loopback_url("http://localhost:11434") == "http://localhost:11434"
    with pytest.raises(ValueError):
        validate_loopback_url("https://api.openai.com/v1")
    with pytest.raises(ValueError):
        Settings(
            SVR_ENV="test",
            DATABASE_URL=f"sqlite:///{(tmp_path / 'x.db').as_posix()}",
            SVR_STORAGE_DIR=tmp_path / "storage",
            OLLAMA_URL="https://external-llm.example.com",
        )


def test_signal_analysis_and_anti_hallucination_guardrails():
    signals = analyze_stt_signals(
        "النت في الفور جي ضعيف جدا جدا ومفيش اشاره",
        min_avg_logprob=-0.65,
        max_no_speech_prob=0.1,
    )
    assert signals.acoustic_risk == "high"
    assert "low_acoustic_logprob" in signals.lexical_flags
    assert "repeated_adjacent_token" in signals.lexical_flags

    raw = "الشيخة عندي في ال 4G ضعيفة جدا ومش عارف اتصل"
    ok, reason = validate_candidate_transcript(raw, "الشبكة عندي في ال 4G ضعيفة جدا ومش عارف اتصل")
    assert ok is True
    assert reason is None

    # Rejects CJK leakage, invented numbers, severe truncation, and semantic drift
    assert validate_candidate_transcript(raw, "الشبكة ضعيفة 中文")[0] is False
    assert validate_candidate_transcript(raw, "الشبكة عندي في ال 4G ضعيفة جدا رقم 01099887766")[0] is False
    assert validate_candidate_transcript(raw, "ضعيفة")[0] is False
    assert validate_candidate_transcript(raw, "تم سداد فاتورة الكهرباء امس بنجاح كامل")[0] is False


def test_whisper_duplicate_sequence_and_egyptian_telecom_asr_repair():
    raw = "كنت عايز ألغي خدمة الكلتون وكل مرة يخسموا يخسموا مني والرسالة تقول لم يتم تنفيذ الطلب"
    deduped, dup_changes = deduplicate_whisper_sequences(raw)
    assert "يخسموا يخسموا" not in deduped
    assert len(dup_changes) == 1
    assert dup_changes[0].reason == "duplicate_sequence_removed"

    gate = TranscriptVerificationGate(
        reviewer_override=lambda ctx: {
            "thinking": "Verified repaired Egyptian Arabic call-tone complaint.",
            "corrected_text": ctx["current_text"],
            "confidence": 0.91,
            "is_coherent": True,
            "changes": [],
        }
    )
    res = gate.verify(raw)
    assert res.status == "corrected"
    assert res.correction_applied is True
    assert res.final_text == "كنت عايز ألغي خدمة الكول تون وكل مرة يخصموا مني والرسالة تقول لم يتم تنفيذ الطلب"
    assert res.trace[0].round_number == 0
    assert any(c.to_text == "الكول تون" for c in res.changes)
    assert any(c.to_text == "يخصموا" for c in res.changes)


def test_gate_iterative_self_correction_after_guardrail_rejection():
    raw = "الشيخة عندي في ال 4G ضعيفة جدا"
    calls: list[dict[str, Any]] = []

    def reviewer(ctx: dict[str, Any]) -> dict[str, Any]:
        calls.append(ctx)
        if ctx["round"] == 1:
            # First round triggers guardrail (CJK drift)
            return {
                "thinking": "Bad output test",
                "corrected_text": "الشبكة عندي في ال 4G ضعيفة جدا 测试",
                "confidence": 0.91,
                "is_coherent": True,
            }
        # Second round receives critique and fixes misrecognized word cleanly
        return {
            "thinking": "Fixed acoustic confusion between الشيخة and الشبكة using telecom 4G context.",
            "suspect_words": ["الشيخة"],
            "corrected_text": "الشبكة عندي في ال 4G ضعيفة جدا",
            "confidence": 0.90,
            "is_coherent": True,
            "changes": [{"from": "الشيخة", "to": "الشبكة", "reason": "telecom_network_context"}],
        }

    gate = TranscriptVerificationGate(max_rounds=3, reviewer_override=reviewer)
    res = gate.verify(raw, min_avg_logprob=-0.62)

    assert res.status == "corrected"
    assert res.correction_applied is True
    assert res.final_text == "الشبكة عندي في ال 4G ضعيفة جدا"
    assert res.needs_human_review is False
    assert res.rounds_run == 2
    assert len(calls) == 2
    assert calls[1]["critique"] is not None
    assert res.trace[0].accepted is False
    assert res.trace[1].accepted is True
    assert res.changes[0].from_text == "الشيخة"
    assert res.changes[0].to_text == "الشبكة"


def test_gate_low_confidence_and_error_escalate_to_human_review():
    raw = "الكلام مش واضح في الباقة والرصيد"
    uncertain_gate = TranscriptVerificationGate(
        max_rounds=2,
        confidence_threshold=0.75,
        reviewer_override=lambda ctx: {
            "thinking": "Still ambiguous after verification pass",
            "corrected_text": ctx["current_text"],
            "confidence": 0.42,
            "is_coherent": False,
        },
    )
    uncertain = uncertain_gate.verify(raw)
    assert uncertain.status == "uncertain"
    assert uncertain.needs_human_review is True
    assert uncertain.review_reason == "uncertain_transcript"
    assert uncertain.final_text == raw

    def broken_reviewer(_ctx: dict[str, Any]) -> dict[str, Any]:
        raise ConnectionError("Ollama local daemon unreachable")

    broken_gate = TranscriptVerificationGate(reviewer_override=broken_reviewer)
    fallback = broken_gate.verify(raw)
    assert fallback.status == "fallback_error"
    assert fallback.needs_human_review is True
    assert fallback.review_reason == "uncertain_transcript"
    assert fallback.final_text == raw
    assert "Ollama local daemon unreachable" in fallback.error


def test_voicegate_orchestrator_end_to_end_repaired_and_uncertain(test_settings, db_manager):
    seen_classifier_inputs: list[str] = []
    mode = {"uncertain": False}

    stt = WhisperSTTService(
        transcriber_override=lambda _audio, _fmt: {
            "text": "الشيخة عندي في ال 4G ضعيفة جدا ومش عارف اتصل",
            "min_avg_logprob": -0.58,
            "max_no_speech_prob": 0.08,
        }
    )

    def _gate_reviewer(ctx: dict[str, Any]) -> dict[str, Any]:
        if mode["uncertain"]:
            return {
                "thinking": "Sentence remains ambiguous even after context check.",
                "corrected_text": ctx["current_text"],
                "confidence": 0.45,
                "is_coherent": False,
            }
        return {
            "thinking": "Replaced الشيخة with الشبكة based on 4G connectivity context.",
            "suspect_words": ["الشيخة"],
            "corrected_text": "الشبكة عندي في ال 4G ضعيفة جدا ومش عارف اتصل",
            "confidence": 0.92,
            "is_coherent": True,
            "changes": [{"from": "الشيخة", "to": "الشبكة", "reason": "acoustic_telecom_repair"}],
        }

    gate = TranscriptVerificationGate(reviewer_override=_gate_reviewer)
    clf = MARBERTv2ClassifierService(
        models_dir=test_settings.svr_models_dir,
        repo_root=test_settings.repo_root,
        allow_validated_artifact_fallback=False,
        predictor_override=lambda tn: (
            seen_classifier_inputs.append(tn) or _sample_prediction()
        ),
    )

    app = create_app(
        settings=test_settings,
        db_manager=db_manager,
        stt_service=stt,
        transcript_gate=gate,
        classifier_service=clf,
    )

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": "supervisor@telecom.local", "password": test_settings.svr_bootstrap_password},
        )
        assert login.status_code == 200
        headers = {"X-CSRF-Token": client.cookies["svr_csrf"]}

        up1 = client.post(
            "/api/voicemails",
            files={"file": ("voice_repaired.wav", make_wav_bytes(1.5), "audio/wav")},
            headers={**headers, "Idempotency-Key": "vg-repaired-01"},
        )
        assert up1.status_code == 202
        t1_id = up1.json()["ticket_id"]

        for _ in range(30):
            d1 = client.get(f"/api/tickets/{t1_id}").json()
            if d1["status"] in ("ready", "unassigned"):
                break
            time.sleep(0.02)

        assert d1["status"] == "ready"
        assert d1["transcript"] == "الشبكة عندي في ال 4G ضعيفة جدا ومش عارف اتصل"
        assert d1["stt_v1_json"]["text"] == "الشيخة عندي في ال 4G ضعيفة جدا ومش عارف اتصل"
        assert seen_classifier_inputs[0] == normalize_transcript("الشبكة عندي في ال 4G ضعيفة جدا ومش عارف اتصل")
        assert d1["transcript_verification"]["status"] == "corrected"
        assert d1["transcript_verification"]["correction_applied"] is True
        assert d1["transcript_verification"]["changes"][0]["from"] == "الشيخة"
        assert d1["transcript_verification"]["changes"][0]["to"] == "الشبكة"
        assert any(ev["action"] == "transcript_verified" and ev["actor"] == "VoiceGate Orchestrator" for ev in d1["audit_events"])

        # Uncertain transcript escalates to UNASSIGNED + Human Review
        mode["uncertain"] = True
        up2 = client.post(
            "/api/voicemails",
            files={"file": ("voice_uncertain.wav", make_wav_bytes(1.6), "audio/wav")},
            headers={**headers, "Idempotency-Key": "vg-uncertain-02"},
        )
        assert up2.status_code == 202
        t2_id = up2.json()["ticket_id"]
        for _ in range(30):
            d2 = client.get(f"/api/tickets/{t2_id}").json()
            if d2["status"] in ("ready", "unassigned"):
                break
            time.sleep(0.02)

        assert d2["status"] == "unassigned"
        assert d2["needs_human_review"] is True
        assert d2["review_reason"] == "uncertain_transcript"
        assert d2["transcript_verification"]["status"] == "uncertain"


def test_agentic_gate_langgraph_multi_step_convergence():
    raw = "طبق مش بيظهر بوقتي الحالية ولا استهلاكها بقالوا يومين كده"
    target = "التطبيق مش بيظهر باقتي الحالية ولا استهلاكها بقاله يومين كده"
    calls: list[dict[str, Any]] = []

    def reviewer(ctx: dict[str, Any]) -> dict[str, Any]:
        calls.append(ctx)
        if ctx["iteration"] == 1:
            return {
                "thinking": "Fixed app word, still checking quota and pronoun.",
                "corrected_text": "التطبيق مش بيظهر بوقتي الحالية ولا استهلاكها بقالوا يومين كده",
                "confidence": 0.72,
                "is_coherent": True,
                "changes": [{"from": "طبق", "to": "التطبيق", "reason": "phonetic_prefix_drop"}],
            }
        return {
            "thinking": "Repaired quota and pronoun to match Egyptian telecom app complaint.",
            "corrected_text": target,
            "confidence": 0.93,
            "is_coherent": True,
            "changes": [
                {"from": "بوقتي", "to": "باقتي", "reason": "vowel_confusion_waw_alef"},
                {"from": "بقالوا", "to": "بقاله", "reason": "pronoun_gender_mismatch"},
            ],
        }

    gate = AgenticTranscriptGate(
        max_iterations=4,
        confidence_threshold=0.75,
        early_stop_confidence=0.90,
        reviewer_override=reviewer,
    )
    res = gate.verify(raw)

    assert res.backend_used == "langgraph-override"
    assert res.status == "corrected"
    assert res.correction_applied is True
    assert res.final_text == target
    assert res.rounds_run == 2
    assert res.convergence_reason == "high_confidence_reached"
    assert res.needs_human_review is False
    assert len(calls) == 2
    assert any(c.from_text == "طبق" and c.to_text == "التطبيق" for c in res.changes)
    assert any(c.from_text == "بوقتي" and c.to_text == "باقتي" for c in res.changes)


def test_agentic_gate_langgraph_max_iterations_fallback():
    raw = "كلام مش واضح خالص في المكالمة"

    gate = AgenticTranscriptGate(
        max_iterations=2,
        confidence_threshold=0.75,
        reviewer_override=lambda ctx: {
            "thinking": "Too ambiguous to repair safely.",
            "corrected_text": ctx["current_text"],
            "confidence": 0.45,
            "is_coherent": False,
            "changes": [],
        },
    )
    res = gate.verify(raw)

    assert res.backend_used == "langgraph-override"
    assert res.status == "uncertain"
    assert res.needs_human_review is True
    assert res.review_reason == "uncertain_transcript"
    assert res.convergence_reason == "max_iterations_exhausted"
    assert res.rounds_run == 2
    assert res.final_text == raw


def test_agentic_gate_orchestrator_downstream_brief_uses_repaired_text(test_settings, db_manager):
    raw = "طبق مش بيظهر بوقتي الحالية ولا استهلاكها بقالوا يومين كده"
    target = "التطبيق مش بيظهر باقتي الحالية ولا استهلاكها بقاله يومين كده"
    seen_classifier_inputs: list[str] = []

    stt = WhisperSTTService(
        transcriber_override=lambda _audio, _fmt: {
            "text": raw,
            "min_avg_logprob": -0.45,
            "max_no_speech_prob": 0.05,
        }
    )
    gate = AgenticTranscriptGate(
        max_iterations=3,
        reviewer_override=lambda _ctx: {
            "thinking": "Repaired Egyptian telecom app complaint.",
            "corrected_text": target,
            "confidence": 0.94,
            "is_coherent": True,
            "changes": [
                {"from": "طبق", "to": "التطبيق", "reason": "phonetic_prefix_drop"},
                {"from": "بوقتي", "to": "باقتي", "reason": "vowel_confusion_waw_alef"},
                {"from": "بقالوا", "to": "بقاله", "reason": "pronoun_gender_mismatch"},
            ],
        },
    )
    clf = MARBERTv2ClassifierService(
        models_dir=test_settings.svr_models_dir,
        repo_root=test_settings.repo_root,
        allow_validated_artifact_fallback=False,
        predictor_override=lambda tn: (
            seen_classifier_inputs.append(tn) or _sample_prediction("network_and_connectivity")
        ),
    )

    app = create_app(
        settings=test_settings,
        db_manager=db_manager,
        stt_service=stt,
        transcript_gate=gate,
        classifier_service=clf,
    )

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": "supervisor@telecom.local", "password": test_settings.svr_bootstrap_password},
        )
        assert login.status_code == 200
        headers = {"X-CSRF-Token": client.cookies["svr_csrf"]}

        up = client.post(
            "/api/voicemails",
            files={"file": ("app_issue.wav", make_wav_bytes(1.5), "audio/wav")},
            headers={**headers, "Idempotency-Key": "ag-brief-sync-01"},
        )
        assert up.status_code == 202
        t_id = up.json()["ticket_id"]

        for _ in range(30):
            detail = client.get(f"/api/tickets/{t_id}").json()
            if detail["status"] in ("ready", "unassigned"):
                break
            time.sleep(0.02)

        assert detail["status"] == "ready"
        assert detail["transcript"] == target
        assert detail["summary"] == target[:200]
        assert detail["stt_v1_json"]["text"] == raw
        assert detail["transcript_verification"]["backend_used"] == "langgraph-override"
        assert seen_classifier_inputs[0] == normalize_transcript(target)


def test_stt_loudness_normalization_boosts_quiet_audio_without_clipping():
    import io
    import wave
    import numpy as np

    sr = 16000
    t = np.linspace(0, 0.5, sr // 2, endpoint=False)
    quiet_pcm = (np.sin(2 * np.pi * 440.0 * t) * 0.01 * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(quiet_pcm.tobytes())

    boosted_wav = normalize_wav_16k_loudness(buf.getvalue())
    with wave.open(io.BytesIO(boosted_wav), "rb") as w_out:
        out_pcm = np.frombuffer(w_out.readframes(w_out.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    out_rms = float(np.sqrt(np.mean(out_pcm ** 2)))
    out_peak = float(np.max(np.abs(out_pcm)))
    assert out_rms > 0.05
    assert out_peak <= 0.90


def test_agentic_gate_escalates_on_severe_acoustic_logprob():
    gate = AgenticTranscriptGate(
        max_iterations=2,
        reviewer_override=lambda ctx: {
            "thinking": "Overconfident LLM on garbled acoustic input.",
            "corrected_text": ctx["current_text"],
            "confidence": 0.90,
            "is_coherent": True,
            "changes": [],
        },
    )
    res = gate.verify(
        "أنت عندي داية تقود المجيء",
        min_avg_logprob=-0.99,
        max_no_speech_prob=0.50,
    )
    assert res.status == "uncertain"
    assert res.needs_human_review is True
    assert res.review_reason == "uncertain_transcript"
    assert res.confidence <= 0.65
    assert "severe_acoustic_degradation" in res.signal_summary["lexical_flags"]


def test_validate_loopback_url_docker_ollama_flag(monkeypatch):
    from svr_platform.services.transcript_gate import validate_loopback_url

    monkeypatch.delenv("SVR_ALLOW_DOCKER_OLLAMA", raising=False)
    assert validate_loopback_url("http://127.0.0.1:11434") == "http://127.0.0.1:11434"
    with pytest.raises(ValueError):
        validate_loopback_url("http://ollama:11434")
    with pytest.raises(ValueError):
        validate_loopback_url("https://api.openai.com")

    monkeypatch.setenv("SVR_ALLOW_DOCKER_OLLAMA", "1")
    assert validate_loopback_url("http://ollama:11434") == "http://ollama:11434"
    with pytest.raises(ValueError):
        validate_loopback_url("https://api.openai.com")
