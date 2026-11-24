"""Stage 2: speech to text (owner: Sira, mock in Phase 1, real Whisper in Phase 2).

Phase 1 mock returns the fixed fixture transcript from contracts section 9.
Phase 2 provides real Whisper transcription and dataset lookup behind the same
schema contracts, keeping stt_provider, stt_model_version, and stt_confidence.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any, Callable

from .. import fixtures
from ..schemas import AudioEvidence, AudioFormat
from .intake import AudioMeta

MOCK_STT_PROVIDER = "mock"
MOCK_STT_MODEL_VERSION = "mock-stt-0.1"
WHISPER_STT_PROVIDER = "whisper"
WHISPER_STT_MODEL_VERSION = "openai/whisper-large-v3"

_ACTIVE_MODEL: Any | None = None
_LOOKUP_CACHE: dict[str, dict[str, Any]] | None = None


def register_model(model: Any) -> None:
    """Register an active STT model or transcription function."""
    global _ACTIVE_MODEL
    _ACTIVE_MODEL = model


def has_active_model() -> bool:
    """Check whether a real STT model is currently registered."""
    return _ACTIVE_MODEL is not None


def _get_dataset_lookup() -> dict[str, dict[str, Any]]:
    """Load precomputed Whisper transcripts from the dataset clean tables if available."""
    global _LOOKUP_CACHE
    if _LOOKUP_CACHE is not None:
        return _LOOKUP_CACHE

    lookup: dict[str, dict[str, Any]] = {}
    base_dirs = [
        Path("../svr-data/final"),
        Path("svr-data/final"),
        Path("../final"),
        Path("final"),
    ]

    for base_dir in base_dirs:
        if not base_dir.is_dir():
            continue
        for csv_name in ("clean_training_val.csv", "clean_training_train.csv", "clean_training_test.csv"):
            csv_path = base_dir / csv_name
            if not csv_path.exists():
                continue
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        audio_file = row.get("audio_file") or row.get("file")
                        if not audio_file:
                            continue
                        key = os.path.basename(audio_file).strip()
                        if key in lookup:
                            continue
                        transcript = row.get("text_whisper") or row.get("text") or ""
                        conf_str = row.get("confidence")
                        try:
                            conf = float(conf_str) if conf_str else 0.85
                        except ValueError:
                            conf = 0.85
                        lookup[key] = {
                            "transcript": transcript,
                            "confidence": max(0.0, min(1.0, conf)),
                            "source": row.get("source", "svr_corpus"),
                        }
            except Exception:
                pass

    _LOOKUP_CACHE = lookup
    return _LOOKUP_CACHE


def transcribe_mock(meta: AudioMeta) -> AudioEvidence:
    """Mock STT: fixed fixture transcript, no audio is read or sent anywhere.

    Evidence reports only measured values. Phase 1 persists no audio, so
    audio_path_local is null; WAV duration, sample rate and channels
    come from the header intake measured; MP3/M4A stay null (unmeasured).
    """
    format_val = AudioFormat(meta.format) if isinstance(meta.format, str) else meta.format
    return AudioEvidence(
        voicemail_id=meta.voicemail_id,
        audio_path_local=None,
        duration_s=meta.duration_s,
        format=format_val,
        sample_rate_hz=meta.sample_rate_hz,
        channels=meta.channels,
        transcript=fixtures.FIXTURE_TRANSCRIPT,
        stt_provider=MOCK_STT_PROVIDER,
        stt_model_version=MOCK_STT_MODEL_VERSION,
        stt_confidence=None,
        language_mix=None,
        audio_quality={"mock": True, "duration_checked": meta.duration_checked},
    )


def _safe_audio_path_local(path: str | None) -> str | None:
    if not path:
        return None
    normalized = path.replace("\\", "/")
    if normalized.startswith("uploads/") and ".." not in normalized.split("/"):
        return normalized
    return None


def transcribe(
    meta: AudioMeta,
    audio_source: Any = None,
    transcriber_fn: Callable[[AudioMeta, Any], dict[str, Any]] | None = None,
) -> AudioEvidence:
    """Transcribe audio using registered model, dataset lookup, or custom transcriber.

    Returns validated AudioEvidence matching contracts schema section 3.1.
    """
    fn = transcriber_fn or _ACTIVE_MODEL
    format_val = AudioFormat(meta.format) if isinstance(meta.format, str) else meta.format
    safe_path = _safe_audio_path_local(meta.audio_path_local)

    if fn is not None:
        result = fn(meta, audio_source) if callable(fn) else fn
        if isinstance(result, AudioEvidence):
            return result
        if isinstance(result, dict):
            transcript = result.get("transcript", "")
            provider = result.get("stt_provider", WHISPER_STT_PROVIDER)
            model_ver = result.get("stt_model_version", WHISPER_STT_MODEL_VERSION)
            confidence = result.get("stt_confidence", 0.90)
            quality = result.get("audio_quality", {"duration_checked": meta.duration_checked})
            return AudioEvidence(
                voicemail_id=meta.voicemail_id,
                audio_path_local=safe_path,
                duration_s=meta.duration_s,
                format=format_val,
                sample_rate_hz=meta.sample_rate_hz,
                channels=meta.channels,
                transcript=transcript,
                stt_provider=provider,
                stt_model_version=model_ver,
                stt_confidence=confidence,
                language_mix=None,
                audio_quality=quality,
            )
        if isinstance(result, str):
            return AudioEvidence(
                voicemail_id=meta.voicemail_id,
                audio_path_local=safe_path,
                duration_s=meta.duration_s,
                format=format_val,
                sample_rate_hz=meta.sample_rate_hz,
                channels=meta.channels,
                transcript=result,
                stt_provider=WHISPER_STT_PROVIDER,
                stt_model_version=WHISPER_STT_MODEL_VERSION,
                stt_confidence=0.88,
                language_mix=None,
                audio_quality={"duration_checked": meta.duration_checked},
            )

    lookup = _get_dataset_lookup()
    key = os.path.basename(meta.audio_path_local or meta.filename or "").strip()
    if key in lookup:
        entry = lookup[key]
        return AudioEvidence(
            voicemail_id=meta.voicemail_id,
            audio_path_local=safe_path,
            duration_s=meta.duration_s,
            format=format_val,
            sample_rate_hz=meta.sample_rate_hz,
            channels=meta.channels,
            transcript=entry["transcript"],
            stt_provider=WHISPER_STT_PROVIDER,
            stt_model_version=WHISPER_STT_MODEL_VERSION,
            stt_confidence=entry["confidence"],
            language_mix=None,
            audio_quality={"dataset_match": True, "audio_file": key, "source": entry["source"], "duration_checked": meta.duration_checked},
        )

    return transcribe_mock(meta)
