"""Tests for Gradio demo integration (Role 6, Arafa)."""

from __future__ import annotations

import io
import json
import wave
import pytest

from svr.demo import run_demo


def _make_wav_bytes(duration_s: float = 1.0, sample_rate_hz: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate_hz)
        wav.writeframes(b"\x00\x00" * int(sample_rate_hz * duration_s))
    return buf.getvalue()


def test_demo_empty_input():
    summary, detail = run_demo(None)
    assert "Upload an audio file first" in summary
    assert detail == ""


def test_demo_real_file_run(tmp_path):
    wav_path = tmp_path / "sample.wav"
    wav_path.write_bytes(_make_wav_bytes(2.0))

    summary, detail = run_demo(str(wav_path))
    assert "## Ticket" in summary
    assert "Processing:" in summary or "Total processing" in summary

    data = json.loads(detail)
    assert data["id"].startswith("ticket-voicemail-")
    assert data["ticket_status"] in ("completed", "queued", "needs_review")
    assert data["processing_ms"] > 0
    assert "audio_evidence" in data
    assert "text_analysis" in data
    assert "triage_decision" in data


def test_demo_five_consecutive_runs(tmp_path):
    for i in range(5):
        wav_path = tmp_path / f"test_{i}.wav"
        wav_path.write_bytes(_make_wav_bytes(1.5))
        summary, detail = run_demo(str(wav_path))
        assert "## Ticket" in summary
        data = json.loads(detail)
        assert data["ticket_status"] in ("completed", "queued", "needs_review")
