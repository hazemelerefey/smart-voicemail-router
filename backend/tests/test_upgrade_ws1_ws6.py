"""Comprehensive unit and integration tests for WS1-WS6 upgrades and VG-01..VG-12 fixes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from conftest import make_wav_bytes
from svr_platform.api.main import create_app
from svr_platform.config import Settings
from svr_platform.eval.cli import run_evaluation
from svr_platform.services.agentic_gate import AgenticTranscriptGate, TELECOM_FEW_SHOT_REPAIRS
from svr_platform.services.classification import CLASSIFICATION_FIELDS, MARBERTv2ClassifierService
from svr_platform.services.factories import build_stt_service, build_transcript_gate
from svr_platform.services.orchestrator import VoiceGateOrchestrator
from svr_platform.services.stt import (
    STT_V1_COLUMNS,
    CohereArabicSTTService,
    WhisperSTTService,
    aggregate_chunk_signals,
    chunk_pcm_by_vad,
    detect_repetition_breakdown,
    join_chunk_transcripts,
)
from svr_platform.services.text_norm import normalize_transcript
from svr_platform.services.transcript_gate import (
    TranscriptVerificationGate,
    analyze_stt_signals,
    parse_strict_bool,
    pre_repair_whisper_text,
    validate_candidate_transcript,
)
from svr_platform.taxonomy import REVIEW_REASONS, TRAINED_CLASSES_BY_FIELD


def _dist(classes: list[str], winner: str, p_win: float = 0.88) -> dict[str, float]:
    rest = (1.0 - p_win) / (len(classes) - 1)
    probs = {c: round(rest, 6) for c in classes if c != winner}
    probs[winner] = round(1.0 - sum(probs.values()), 6)
    return probs


def _pred(category: str = "network_and_connectivity", cat_prob: float = 0.90) -> dict[str, dict[str, Any]]:
    return {
        "complaint_category": {
            "label": category,
            "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["complaint_category"], category, cat_prob),
        },
        "complaint_urgency": {
            "label": "high",
            "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["complaint_urgency"], "high", 0.90),
        },
        "customer_state": {
            "label": "frustrated",
            "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["customer_state"], "frustrated", 0.90),
        },
        "churn_risk": {
            "label": "not_at_risk",
            "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["churn_risk"], "not_at_risk", 0.92),
        },
    }


def test_ws3_cohere_stt_service_and_factory_dispatch(tmp_path: Path):
    cfg_cohere = Settings(
        SVR_ENV="test",
        DATABASE_URL=f"sqlite:///{(tmp_path / 'c.db').as_posix()}",
        SVR_STORAGE_DIR=tmp_path / "storage",
        SVR_STT_BACKEND="cohere_gpu_int8",
    )
    svc = build_stt_service(cfg_cohere)
    assert isinstance(svc, CohereArabicSTTService)
    assert svc.canonical_model_name == "NAMAA-Space/cohere-transcribe-arabic-07-2026-int8"

    cfg_whisper = Settings(
        SVR_ENV="test",
        DATABASE_URL=f"sqlite:///{(tmp_path / 'w.db').as_posix()}",
        SVR_STORAGE_DIR=tmp_path / "storage",
        SVR_STT_BACKEND="faster_whisper",
    )
    wsvc = build_stt_service(cfg_whisper)
    assert isinstance(wsvc, WhisperSTTService)

    override_svc = CohereArabicSTTService(
        backend_mode="cohere_gpu_int8",
        transcriber_override=lambda _b, _f: {
            "text": "الشبكة فصلت والراوتر Wi-Fi مش شغال",
            "min_avg_logprob": -0.22,
            "max_no_speech_prob": 0.04,
        },
    )
    res = override_svc.transcribe(make_wav_bytes(1.0), "wav", file_label="val_01.wav")
    v1 = res.to_v1_dict()
    assert tuple(v1.keys()) == STT_V1_COLUMNS
    assert res.needs_review is False
    assert res.language_mix == "english_telecom_terms"

    loop_svc = CohereArabicSTTService(
        transcriber_override=lambda _b, _f: {
            "text": "الشبكة الشبكة الشبكة الشبكة ضعيفة",
            "min_avg_logprob": -0.20,
            "max_no_speech_prob": 0.05,
        }
    )
    loop_res = loop_svc.transcribe(make_wav_bytes(1.0), "wav", file_label="loop.wav")
    assert loop_res.needs_review is True
    assert "repetition_loop" in loop_res.review_reasons


def test_ws3_vad_chunking_signal_aggregation_and_overlap_join():
    assert detect_repetition_breakdown("مش شغال مش شغال مش شغال مش شغال") is True
    assert detect_repetition_breakdown("الشبكة ضعيفة جدا في المنطقة") is False

    sr = 16000
    pcm = np.zeros(50 * sr, dtype=np.float32)
    segments = [(1 * sr, 20 * sr), (22 * sr, 48 * sr)]
    chunks = chunk_pcm_by_vad(pcm, segments, sr=sr, target_max_s=30.0, hard_max_s=35.0)
    assert len(chunks) >= 2
    assert all(len(c) <= int(35.0 * sr) for c in chunks)

    min_lp, max_nsp = aggregate_chunk_signals([-0.15, -0.62, None], [0.05, 0.30])
    assert min_lp == -0.62
    assert max_nsp == 0.30

    joined = join_chunk_transcripts(["النت عندي بيفصل كل شوية", "كل شوية في الراوتر"])
    assert joined == "النت عندي بيفصل كل شوية في الراوتر"


def test_vg01_worker_runner_atomic_redis_reaper_and_api_enqueue(test_settings, db_manager, monkeypatch):
    import ops.worker_runner as wr

    class FakeRedis:
        def __init__(self):
            self.lists: dict[str, list[str]] = {
                "svr:pipeline:queue": ["t2"],
                "svr:pipeline:inflight": ["t1"],
            }
            self.published: list[tuple[str, str]] = []

        def rpoplpush(self, src: str, dst: str):
            if not self.lists[src]:
                return None
            item = self.lists[src].pop()
            self.lists[dst].insert(0, item)
            return item

        def blmove(
            self,
            first_list: str,
            second_list: str,
            timeout: int = 1,
            src: str = "LEFT",
            dest: str = "RIGHT",
        ):
            if not self.lists[first_list]:
                return None
            item = self.lists[first_list].pop(0) if src == "LEFT" else self.lists[first_list].pop()
            if dest == "RIGHT":
                self.lists[second_list].append(item)
            else:
                self.lists[second_list].insert(0, item)
            return item

        def lrem(self, key: str, _count: int, value: str):
            self.lists[key] = [x for x in self.lists[key] if x != value]
            return 1

        def publish(self, channel: str, payload: str):
            self.published.append((channel, payload))

        def rpush(self, key: str, value: str):
            self.lists.setdefault(key, []).append(value)

    fake = FakeRedis()
    reaped = wr.reap_inflight_queue(fake, "svr:pipeline:queue", "svr:pipeline:inflight")
    assert reaped == 1
    assert fake.lists["svr:pipeline:inflight"] == []
    nxt = wr.pop_next_ticket_id(fake, "svr:pipeline:queue", "svr:pipeline:inflight", 1)
    assert nxt == "t1"
    assert fake.lists["svr:pipeline:inflight"] == ["t1"]
    wr.ack_inflight_ticket(fake, "svr:pipeline:inflight", "t1")
    assert fake.lists["svr:pipeline:inflight"] == []
    wr.publish_ticket_event(fake, "svr:pipeline:events", {"ticket_id": "t1", "status": "ready"})
    assert len(fake.published) == 1

    gate = build_transcript_gate(test_settings)
    assert isinstance(gate, AgenticTranscriptGate)

    # API enqueue falls back cleanly to BackgroundTasks if Redis is unreachable
    monkeypatch.setattr(test_settings, "redis_url", "redis://127.0.0.1:6399/0")
    app = create_app(
        settings=test_settings,
        db_manager=db_manager,
        stt_service=WhisperSTTService(
            transcriber_override=lambda _b, _f: {
                "text": "النت عندي بيفصل كل شوية",
                "min_avg_logprob": -0.20,
                "max_no_speech_prob": 0.05,
            }
        ),
        transcript_gate=AgenticTranscriptGate(fast_path_enabled=True),
        classifier_service=MARBERTv2ClassifierService(
            models_dir=test_settings.svr_models_dir,
            repo_root=test_settings.repo_root,
            allow_validated_artifact_fallback=False,
            predictor_override=lambda _tn: _pred(),
        ),
    )
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": "supervisor@telecom.local", "password": test_settings.svr_bootstrap_password},
        )
        headers = {"X-CSRF-Token": client.cookies["svr_csrf"]}
        up = client.post(
            "/api/voicemails",
            files={"file": ("vg01.wav", make_wav_bytes(1.2), "audio/wav")},
            headers={**headers, "Idempotency-Key": "vg01-fallback-key"},
        )
        assert up.status_code == 202
        health = client.get("/api/health").json()
        assert "stt_backend" in health and "stt_model" in health


def test_vg02_vg03_vg04_signal_separation_latin_guard_and_punctuation_pre_repair():
    # VG-02: benign telecom words do NOT block fast-path; confusion triggers DO block fast-path
    benign_sig = analyze_stt_signals(
        "انا مشترك فودافون والراوتر شغال تمام",
        min_avg_logprob=-0.20,
        max_no_speech_prob=0.05,
    )
    assert benign_sig.acoustic_risk == "low"
    assert benign_sig.suspect_hints == []

    confusion_sig = analyze_stt_signals(
        "الشيخة في فودافون مش شغالة",
        min_avg_logprob=-0.20,
        max_no_speech_prob=0.05,
    )
    assert confusion_sig.acoustic_risk == "medium"
    assert "الشيخة" in confusion_sig.suspect_hints

    # VG-02 vad_only fast-path check
    calls: list[dict[str, Any]] = []
    vad_gate = AgenticTranscriptGate(
        fast_path_enabled=True,
        reviewer_override=lambda ctx: calls.append(ctx) or {"corrected_text": ctx["current_text"], "confidence": 0.9, "is_coherent": True},
    )
    vad_res = vad_gate.verify(
        "انا مشترك فودافون والراوتر فصل خالص",
        min_avg_logprob=None,
        max_no_speech_prob=0.10,
        stt_confidence_source="vad_only",
    )
    assert len(calls) == 0
    assert vad_res.status == "verified"
    assert vad_res.convergence_reason == "fast_path_clean_acoustic"

    # VG-03: mixed AR/EN telecom terms accepted, ungrounded Latin rejected even when raw has Latin
    raw_mixed = "عندي مشكلة في 4G على Vodafone و Wi-Fi"
    ok_mixed, _ = validate_candidate_transcript(raw_mixed, "عندي مشكلة في 4G على Vodafone و Wi-Fi")
    assert ok_mixed is True
    ok_injected, reason = validate_candidate_transcript(raw_mixed, "عندي مشكلة في 4G على Vodafone و Wi-Fi hackedxyz")
    assert ok_injected is False
    assert "unexpected_latin_injection" in (reason or "")

    # VG-04: taa marbuta + punctuation pre-repair preserves punctuation
    repaired, changes, _flags = pre_repair_whisper_text("السبكة، في السريحة.")
    assert repaired == "الشبكة، في الشريحة."
    assert len(changes) == 2


def test_vg05_vg06_vg07_vg08_agentic_gate_semantics_and_httpx_mock():
    assert "uncertain_transcript" in REVIEW_REASONS
    assert all(r["wrong"] not in ("تطبيق", "روتر", "بالتطبيق") for r in TELECOM_FEW_SHOT_REPAIRS)
    assert parse_strict_bool("false") is False
    assert parse_strict_bool("0") is False
    assert parse_strict_bool("true") is True

    # VG-06 & VG-07: "false" string is False, pre_changes + all-error LLM rounds escalate to uncertain
    err_gate = AgenticTranscriptGate(
        max_iterations=2,
        reviewer_override=lambda _ctx: (_ for _ in ()).throw(RuntimeError("ollama down")),
    )
    err_res = err_gate.verify("السبكة ضعيفة جدا عندي")
    assert err_res.status == "uncertain"
    assert err_res.needs_human_review is True
    assert err_res.final_text == "الشبكة ضعيفة جدا عندي"

    # VG-06: direct_loop matches LangGraph semantics (no hardcoded False, iteration 0 present)
    direct_gate = AgenticTranscriptGate(
        max_iterations=2,
        confidence_threshold=0.75,
        reviewer_override=lambda ctx: {
            "thinking": "Coherent string false test",
            "corrected_text": ctx["current_text"],
            "confidence": 0.72,
            "is_coherent": "false",
        },
    )
    direct_gate._graph = None
    d_res = direct_gate.verify("السبكة عندي ضعيفة جدا")
    assert d_res.status == "uncertain"
    assert d_res.needs_human_review is True
    assert d_res.trace[0].round_number == 0

    # VG-07 + VG-08: real httpx.MockTransport Ollama JSON parsing + _ollama_loaded unload guard
    unload_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal unload_calls
        if request.url.path == "/api/chat":
            return httpx.Response(
                200,
                json={
                    "message": {
                        "content": json.dumps(
                            {
                                "thinking": "Fixed acoustic typo",
                                "suspect_words": ["الشيخة"],
                                "corrected_text": "الشبكة عندي ضعيفة جدا",
                                "confidence": 0.93,
                                "is_coherent": True,
                                "changes": [{"from": "الشيخة", "to": "الشبكة", "reason": "typo"}],
                            },
                            ensure_ascii=False,
                        )
                    }
                },
            )
        if request.url.path == "/api/generate":
            unload_calls += 1
            return httpx.Response(200, json={"done": True})
        return httpx.Response(404)

    orig_client = httpx.Client
    transport = httpx.MockTransport(handler)

    def patched_client(*args, **kwargs):
        kwargs["transport"] = transport
        return orig_client(*args, **kwargs)

    # Fast-path does NOT call unload
    mp = pytest.MonkeyPatch()
    mp.setattr(httpx, "Client", patched_client)
    try:
        http_gate = AgenticTranscriptGate(low_memory_mode=True, fast_path_enabled=True)
        fp_res = http_gate.verify("النت عندي بيفصل كل شوية", min_avg_logprob=-0.20, max_no_speech_prob=0.05)
        assert fp_res.status == "verified"
        assert unload_calls == 0

        # Non-fast-path calls chat AND unloads once
        rep_res = http_gate.verify("الشيخة عندي ضعيفة جدا", min_avg_logprob=-0.20, max_no_speech_prob=0.05)
        assert rep_res.status == "corrected"
        assert rep_res.final_text == "الشبكة عندي ضعيفة جدا"
        assert unload_calls == 1
    finally:
        mp.undo()


def test_vg09_and_vg10_skipped_empty_and_adaptive_reaudit(test_settings, db_manager):
    # VG-09: empty transcript skips classifier and keeps review_reason == 'uncertain_transcript'
    clf_calls: list[str] = []
    app_empty = create_app(
        settings=test_settings,
        db_manager=db_manager,
        stt_service=WhisperSTTService(
            transcriber_override=lambda _b, _f: {"text": "", "min_avg_logprob": -1.0, "max_no_speech_prob": 0.99}
        ),
        transcript_gate=AgenticTranscriptGate(fast_path_enabled=True),
        classifier_service=MARBERTv2ClassifierService(
            models_dir=test_settings.svr_models_dir,
            repo_root=test_settings.repo_root,
            allow_validated_artifact_fallback=False,
            predictor_override=lambda tn: clf_calls.append(tn) or _pred(),
        ),
    )
    with TestClient(app_empty) as client:
        client.post(
            "/api/auth/login",
            json={"email": "supervisor@telecom.local", "password": test_settings.svr_bootstrap_password},
        )
        headers = {"X-CSRF-Token": client.cookies["svr_csrf"]}
        up = client.post(
            "/api/voicemails",
            files={"file": ("silent.wav", make_wav_bytes(1.0), "audio/wav")},
            headers={**headers, "Idempotency-Key": "vg09-empty"},
        )
        tid = up.json()["ticket_id"]
        detail = client.get(f"/api/tickets/{tid}").json()
        assert detail["status"] == "unassigned"
        assert detail["review_reason"] == "uncertain_transcript"
        assert detail["stage_status"]["classify"] == "skipped"
        assert clf_calls == []

    # VG-10: max-1 adaptive re-audit fires ONLY when rounds_run == 0 and category prob < 0.60
    gate_calls: list[dict[str, Any]] = []

    def _reaudit_reviewer(ctx: dict[str, Any]) -> dict[str, Any]:
        gate_calls.append(ctx)
        return {
            "thinking": "Repaired subtle dialect phrase on adaptive re-audit",
            "corrected_text": "النت في البيت بيفصل كتير",
            "confidence": 0.94,
            "is_coherent": True,
            "changes": [{"from": "الميت", "to": "البيت", "reason": "phonetic_reaudit"}],
        }

    def _adaptive_pred(tn: str) -> dict[str, dict[str, Any]]:
        if "الميت" in tn:
            return _pred("other", cat_prob=0.42)
        return _pred("network_and_connectivity", cat_prob=0.92)

    app_reaudit = create_app(
        settings=test_settings,
        db_manager=db_manager,
        stt_service=WhisperSTTService(
            transcriber_override=lambda _b, _f: {
                "text": "النت في الميت بيفصل كتير",
                "min_avg_logprob": -0.20,
                "max_no_speech_prob": 0.05,
            }
        ),
        transcript_gate=AgenticTranscriptGate(fast_path_enabled=True, reviewer_override=_reaudit_reviewer),
        classifier_service=MARBERTv2ClassifierService(
            models_dir=test_settings.svr_models_dir,
            repo_root=test_settings.repo_root,
            allow_validated_artifact_fallback=False,
            predictor_override=_adaptive_pred,
        ),
    )
    with TestClient(app_reaudit) as client:
        client.post(
            "/api/auth/login",
            json={"email": "supervisor@telecom.local", "password": test_settings.svr_bootstrap_password},
        )
        headers = {"X-CSRF-Token": client.cookies["svr_csrf"]}
        up = client.post(
            "/api/voicemails",
            files={"file": ("reaudit.wav", make_wav_bytes(1.2), "audio/wav")},
            headers={**headers, "Idempotency-Key": "vg10-reaudit"},
        )
        tid = up.json()["ticket_id"]
        detail = client.get(f"/api/tickets/{tid}").json()
        assert len(gate_calls) >= 1
        assert detail["complaint_category"] == "network_and_connectivity"
        assert detail["transcript"] == "النت في البيت بيفصل كتير"
        reaudit_logs = [log for log in detail["ai_logs"] if log["stage"] == "verify_transcript_reaudit"]
        assert len(reaudit_logs) == 1


def test_ws5_bounded_onnx_lru_cache_and_eval_cli_voicegate(tmp_path: Path, monkeypatch):
    # Bounded LRU cache respects max_resident_onnx_heads and unloads cleanly
    svc = MARBERTv2ClassifierService(
        models_dir=tmp_path,
        repo_root=tmp_path,
        allow_validated_artifact_fallback=False,
        max_resident_onnx_heads=2,
    )
    ckpt_dirs = {}
    for f in CLASSIFICATION_FIELDS:
        d = tmp_path / "seed_99" / f
        d.mkdir(parents=True)
        (d / "config.json").write_text('{"id2label": {"0": "a"}}', encoding="utf-8")
        (d / "model_int8.onnx").write_bytes(b"dummy")
        ckpt_dirs[f] = d

    import onnxruntime as ort

    monkeypatch.setattr(ort, "InferenceSession", lambda path, **kw: {"path": path, "opts": kw.get("sess_options")})
    for f in CLASSIFICATION_FIELDS:
        sess, _ = svc._get_or_load_onnx_session(ckpt_dirs, f)
        assert sess["opts"].enable_cpu_mem_arena is False
        assert len(svc._onnx_sessions) <= 2
    assert list(svc._onnx_sessions.keys()) == ["customer_state", "churn_risk"]
    svc.unload()
    assert len(svc._onnx_sessions) == 0

    # eval/cli.py supports --with-voicegate ablation
    from test_eval_cli import _make_synthetic_dataset

    rows = _make_synthetic_dataset(tmp_path, "val")
    rows_by_text = {r["text_norm"]: r for r in rows}
    settings = Settings(
        SVR_ENV="test",
        DATABASE_URL=f"sqlite:///{(tmp_path / 'eval_vg.db').as_posix()}",
        SVR_STORAGE_DIR=tmp_path / "storage",
        SVR_MODELS_DIR=tmp_path / "models",
        SVR_BOOTSTRAP_PASSWORD="TestPassword123!",
        SVR_SECRET_KEY="test-secret-eval-vg",
    )
    report = run_evaluation(
        split="validation",
        stt_sample_size=2,
        seed=99,
        batch_size=4,
        repo_root=tmp_path,
        models_dir=tmp_path / "models",
        output_dir=tmp_path / "runs" / "eval_vg",
        database_url=settings.database_url,
        ledger_path=tmp_path / "runs" / "test_evaluations.json",
        with_voicegate=True,
        stt_service=WhisperSTTService(
            transcriber_override=lambda _b, _f: {
                "text": "السبكة ضعيفة جدا",
                "min_avg_logprob": -0.45,
                "max_no_speech_prob": 0.05,
            }
        ),
        transcript_gate=AgenticTranscriptGate(
            reviewer_override=lambda _ctx: {
                "thinking": "Verified",
                "corrected_text": "الشبكة ضعيفة جدا",
                "confidence": 0.92,
                "is_coherent": True,
            }
        ),
        classifier_service=MARBERTv2ClassifierService(
            models_dir=tmp_path / "models",
            repo_root=tmp_path,
            allow_validated_artifact_fallback=False,
            predictor_override=lambda tn: _pred(
                rows_by_text[tn]["complaint_category"] if tn in rows_by_text else "other"
            ),
        ),
        settings_override=settings,
    )
    assert report["stt_sample"]["voicegate_enabled"] is True
    assert report["stt_sample"]["voicegate_repaired_count"] == 2
    assert "verify_transcript" in report["latency_ms"]
