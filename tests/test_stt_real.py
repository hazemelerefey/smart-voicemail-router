"""Tests for Stage 2 real STT integration (Role 6, Arafa)."""

from __future__ import annotations

import io
import wave
import pytest

from svr.pipeline import run_pipeline
from svr.schemas import AudioFormat
from svr.stages import stt
from svr.stages.intake import AudioMeta, validate_and_measure


def _make_wav_bytes(duration_s: float = 1.0, sample_rate_hz: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate_hz)
        wav.writeframes(b"\x00\x00" * int(sample_rate_hz * duration_s))
    return buf.getvalue()


def test_transcribe_mock_preserved():
    meta = AudioMeta(
        voicemail_id="vm-stt-001",
        filename="test.wav",
        format="wav",
        size_bytes=1000,
        duration_s=1.0,
        duration_checked=True,
        sample_rate_hz=16000,
        channels=1,
    )
    evidence = stt.transcribe_mock(meta)
    assert evidence.voicemail_id == "vm-stt-001"
    assert evidence.stt_provider == "mock"
    assert evidence.stt_model_version == "mock-stt-0.1"
    assert evidence.stt_confidence is None
    assert evidence.language_mix is None


def test_transcribe_dataset_lookup():
    wav_bytes = _make_wav_bytes(2.5)
    meta = validate_and_measure(
        wav_bytes,
        "frustrated_0001.wav",
        "vm-stt-lookup-01",
        audio_path_local="../svr-data/dataset/val/frustrated_0001.wav",
    )
    evidence = stt.transcribe(meta)
    assert evidence.voicemail_id == "vm-stt-lookup-01"
    assert evidence.stt_provider == "whisper"
    assert evidence.stt_model_version == "openai/whisper-large-v3"
    assert evidence.stt_confidence is not None
    assert 0.0 <= evidence.stt_confidence <= 1.0
    assert "خدمة" in evidence.transcript or len(evidence.transcript) > 10
    assert evidence.language_mix is None


def test_transcribe_registered_model():
    def dummy_stt(meta: AudioMeta, source):
        return {
            "transcript": "عندي مشكلة في الفاتورة والنت فاصل بقاله يومين.",
            "stt_provider": "custom-whisper",
            "stt_model_version": "whisper-finetuned-egy",
            "stt_confidence": 0.94,
        }

    try:
        stt.register_model(dummy_stt)
        assert stt.has_active_model() is True

        meta = AudioMeta(
            voicemail_id="vm-stt-reg-01",
            filename="unknown.wav",
            format="wav",
            size_bytes=2000,
            duration_s=3.0,
            duration_checked=True,
            sample_rate_hz=16000,
            channels=1,
        )
        evidence = stt.transcribe(meta)
        assert evidence.stt_provider == "custom-whisper"
        assert evidence.stt_model_version == "whisper-finetuned-egy"
        assert evidence.stt_confidence == 0.94
        assert "الفاتورة" in evidence.transcript
    finally:
        stt.register_model(None)
        assert stt.has_active_model() is False


def test_transcribe_unknown_fallback():
    meta = AudioMeta(
        voicemail_id="vm-stt-fallback",
        filename="non_existent_audio_file.wav",
        format="wav",
        size_bytes=1000,
        duration_s=1.0,
        duration_checked=True,
    )
    evidence = stt.transcribe(meta)
    assert evidence.voicemail_id == "vm-stt-fallback"
    assert evidence.stt_provider == "mock"


def test_pipeline_with_real_stt():
    wav_bytes = _make_wav_bytes(2.0)
    meta = validate_and_measure(
        wav_bytes,
        "frustrated_0001.wav",
        "vm-pipe-stt-01",
        audio_path_local="../svr-data/dataset/val/frustrated_0001.wav",
    )
    res = run_pipeline(meta, "vm-pipe-stt-01", use_real_stt=True)
    assert res.audio is not None
    assert res.audio.stt_provider == "whisper"
    assert res.ticket is not None
    assert res.ticket.ticket_status.value in ("completed", "queued")
