"""Tests for Module 2: intake validation, text_norm, language_mix, and 10-column STT v1."""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

import pytest

from conftest import make_wav_bytes
from svr_platform.config import get_settings
from svr_platform.services.intake import (
    MAX_BYTES,
    IntakeValidationError,
    decode_to_wav_16k_mono,
    validate_and_probe_audio,
)
from svr_platform.services.stt import STT_V1_COLUMNS, WhisperSTTService
from svr_platform.services.text_norm import detect_language_mix, normalize_transcript


def test_intake_accepts_valid_wav_and_recommends_15_to_60s():
    wav_bytes = make_wav_bytes(duration_s=2.0, rate=16000, channels=1)
    probe = validate_and_probe_audio(wav_bytes, "caller_01.wav")
    assert probe.format == "wav"
    assert probe.duration_seconds == 2.0
    assert probe.sample_rate_hz == 16000
    assert probe.channels == 1
    assert probe.recommendation_note is not None
    assert "15 to 60" in probe.recommendation_note

    wav_20s = make_wav_bytes(duration_s=20.0, rate=16000, channels=1)
    probe20 = validate_and_probe_audio(wav_20s, "caller_20s.wav")
    assert probe20.recommendation_note is None


def test_intake_rejects_invalid_format_size_duration_and_fake_headers():
    with pytest.raises(IntakeValidationError) as exc_fmt:
        validate_and_probe_audio(b"plain text", "notes.txt")
    assert exc_fmt.value.problem == "format"

    with pytest.raises(IntakeValidationError) as exc_mp3:
        validate_and_probe_audio(b"not really an mp3 file", "spoofed.mp3")
    assert exc_mp3.value.problem == "format"

    with pytest.raises(IntakeValidationError) as exc_m4a:
        validate_and_probe_audio(b"not really an m4a file", "spoofed.m4a")
    assert exc_m4a.value.problem == "format"

    with pytest.raises(IntakeValidationError) as exc_empty:
        validate_and_probe_audio(b"", "empty.wav")
    assert exc_empty.value.problem == "size"

    with pytest.raises(IntakeValidationError) as exc_big:
        validate_and_probe_audio(b"\x00" * (MAX_BYTES + 1), "huge.wav")
    assert exc_big.value.problem == "size"

    overlong = make_wav_bytes(duration_s=61.0, rate=8000, channels=1)
    with pytest.raises(IntakeValidationError) as exc_dur:
        validate_and_probe_audio(overlong, "too_long.wav")
    assert exc_dur.value.problem == "duration"


def test_intake_probes_real_mp3_and_m4a_via_ffmpeg(tmp_path: Path):
    settings = get_settings()
    wav_bytes = make_wav_bytes(duration_s=1.5, rate=44100, channels=2)
    wav_file = tmp_path / "src.wav"
    wav_file.write_bytes(wav_bytes)

    mp3_file = tmp_path / "sample.mp3"
    m4a_file = tmp_path / "sample.m4a"
    subprocess.run(
        [settings.ffmpeg_bin, "-y", "-v", "error", "-i", str(wav_file), str(mp3_file)],
        check=True,
    )
    subprocess.run(
        [settings.ffmpeg_bin, "-y", "-v", "error", "-i", str(wav_file), str(m4a_file)],
        check=True,
    )

    p_mp3 = validate_and_probe_audio(mp3_file.read_bytes(), "sample.mp3", ffprobe_bin=settings.ffprobe_bin)
    assert p_mp3.format == "mp3"
    assert 1.3 <= p_mp3.duration_seconds <= 1.8

    p_m4a = validate_and_probe_audio(m4a_file.read_bytes(), "sample.m4a", ffprobe_bin=settings.ffprobe_bin)
    assert p_m4a.format == "m4a"
    assert 1.3 <= p_m4a.duration_seconds <= 1.8

    decoded = decode_to_wav_16k_mono(m4a_file.read_bytes(), "m4a", ffmpeg_bin=settings.ffmpeg_bin)
    decoded_probe = validate_and_probe_audio(decoded, "decoded.wav")
    assert decoded_probe.sample_rate_hz == 16000
    assert decoded_probe.channels == 1


def test_text_norm_matches_corpus_validation_set():
    assert normalize_transcript("الشبكة   ضعيفة جداً في 4G!!") == normalize_transcript("الشبكة ضعيفة جدا في 4G!!")
    val_csv = Path(__file__).resolve().parents[2] / "final" / "clean_training_val.csv"
    if not val_csv.is_file():
        return
    with val_csv.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    matches = sum(1 for r in rows if normalize_transcript(r["text"]) == r["text_norm"])
    # 1002/1003 exact match (1 row edited post-norm in bulk transcript fix commit 501aa8b)
    assert matches >= 1002


def test_language_mix_indication_fr5():
    assert detect_language_mix("الشبكة ضعيفة جدا في المنطقة") == "arabic"
    assert detect_language_mix("عندي مشكلة في شريحة eSIM والباقة 4G") == "english_telecom_terms"
    assert detect_language_mix("Please check my home address in Cairo") == "mixed"


def test_stt_produces_locked_10_columns_and_retries_on_failure():
    svc = WhisperSTTService(
        transcriber_override=lambda _b, _f: {
            "text": "الشبكة فصلت ومحتاج تفعيل eSIM فورا.",
            "min_avg_logprob": -0.18,
            "max_no_speech_prob": 0.02,
        }
    )
    res = svc.transcribe(
        make_wav_bytes(),
        "wav",
        file_label="calm_0001.wav",
        dup_count_fn=lambda _tn: 2,
    )
    v1 = res.to_v1_dict()
    assert tuple(v1.keys()) == STT_V1_COLUMNS
    assert v1["model"] == "openai/whisper-large-v3"
    assert v1["text_norm"] == "الشبكه فصلت ومحتاج تفعيل esim فورا"
    assert v1["dup_text_size"] == 2
    assert v1["needs_review"] is False
    assert v1["error"] == ""
    assert res.language_mix == "english_telecom_terms"

    # Retry 3 times then degrade cleanly to Human Review (NFR14)
    attempts = {"count": 0}

    def _failing(_b, _f):
        attempts["count"] += 1
        raise RuntimeError("whisper backend offline")

    fail_svc = WhisperSTTService(max_retries=3, retry_backoff_s=0.01, transcriber_override=_failing)
    fail_res = fail_svc.transcribe(make_wav_bytes(), "wav", file_label="broken.wav")
    assert attempts["count"] == 3
    assert fail_res.needs_review is True
    assert fail_res.review_reasons == "stt_error"
    assert "whisper backend offline" in fail_res.error
