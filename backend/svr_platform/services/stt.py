"""Self-hosted Whisper large-v3 STT service producing locked 10-column format v1 (FR4, FR5, AI1, NFR14)."""

from __future__ import annotations

import logging
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .intake import decode_to_wav_16k_mono
from .text_norm import detect_language_mix, normalize_transcript

logger = logging.getLogger("svr_platform.stt")

STT_V1_COLUMNS = (
    "file",
    "model",
    "text",
    "text_norm",
    "min_avg_logprob",
    "max_no_speech_prob",
    "needs_review",
    "review_reasons",
    "dup_text_size",
    "error",
)

LOW_LOGPROB_THRESHOLD = -0.50
HIGH_NO_SPEECH_THRESHOLD = 0.80


@dataclass
class STTResult:
    """Exact 10-column STT output format v1 (PRD Appendix D, FR4)."""

    file: str
    model: str
    text: str
    text_norm: str
    min_avg_logprob: float | None
    max_no_speech_prob: float | None
    needs_review: bool
    review_reasons: str
    dup_text_size: int
    error: str

    def to_v1_dict(self) -> dict:
        data = asdict(self)
        return {col: data[col] for col in STT_V1_COLUMNS}

    @property
    def language_mix(self) -> str:
        return detect_language_mix(self.text)


class WhisperSTTService:
    """Local self-hosted Whisper large-v3 service via faster-whisper (zero external API calls)."""

    def __init__(
        self,
        *,
        model_id: str = "large-v3",
        device: str = "cpu",
        compute_type: str = "int8",
        download_root: str | None = None,
        ffmpeg_bin: str = "ffmpeg",
        max_retries: int = 3,
        retry_backoff_s: float = 0.5,
        transcriber_override: Callable[[bytes, str], dict] | None = None,
    ) -> None:
        self.model_id = model_id
        self.canonical_model_name = (
            "openai/whisper-large-v3" if model_id == "large-v3" else model_id
        )
        self.device = device
        self.compute_type = compute_type
        self.download_root = download_root
        self.ffmpeg_bin = ffmpeg_bin
        self.max_retries = max_retries
        self.retry_backoff_s = retry_backoff_s
        self._transcriber_override = transcriber_override
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            from faster_whisper import WhisperModel

            logger.info(
                "Loading local Whisper model=%s device=%s compute_type=%s",
                self.model_id,
                self.device,
                self.compute_type,
            )
            self._model = WhisperModel(
                self.model_id,
                device=self.device,
                compute_type=self.compute_type,
                download_root=self.download_root,
            )
            return self._model

    def _run_once(self, audio_bytes: bytes, fmt: str) -> tuple[str, float | None, float | None]:
        if self._transcriber_override is not None:
            res = self._transcriber_override(audio_bytes, fmt)
            return (
                str(res.get("text", "")),
                res.get("min_avg_logprob"),
                res.get("max_no_speech_prob"),
            )

        wav_16k = decode_to_wav_16k_mono(audio_bytes, fmt, ffmpeg_bin=self.ffmpeg_bin)
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                tf.write(wav_16k)
                tmp_path = Path(tf.name)
            model = self._get_model()
            segments_iter, _info = model.transcribe(
                str(tmp_path),
                language="ar",
                beam_size=1,
                vad_filter=True,
            )
            segments = list(segments_iter)
            text = " ".join(seg.text.strip() for seg in segments if seg.text.strip()).strip()
            if segments:
                min_logprob = round(min(float(seg.avg_logprob) for seg in segments), 4)
                max_no_speech = round(max(float(seg.no_speech_prob) for seg in segments), 4)
            else:
                min_logprob = -1.0
                max_no_speech = 1.0
            return text, min_logprob, max_no_speech
        finally:
            if tmp_path is not None and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError as exc:
                    logger.warning("Failed to remove temp STT wav %s: %s", tmp_path, exc)

    def transcribe(
        self,
        audio_bytes: bytes,
        fmt: str,
        *,
        file_label: str,
        dup_count_fn: Callable[[str], int] | None = None,
    ) -> STTResult:
        """Transcribe audio with up to 3 retry attempts; degrade safely to Human Review on error."""
        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                text, min_logprob, max_no_speech = self._run_once(audio_bytes, fmt)
                text_norm = normalize_transcript(text)
                reasons: list[str] = []
                if not text_norm:
                    reasons.append("empty_transcript")
                elif len(text_norm.split()) < 2:
                    reasons.append("too_short")
                if min_logprob is not None and min_logprob < LOW_LOGPROB_THRESHOLD:
                    reasons.append("low_confidence")
                if max_no_speech is not None and max_no_speech > HIGH_NO_SPEECH_THRESHOLD:
                    reasons.append("high_no_speech")

                dup_size = 1
                if text_norm and dup_count_fn is not None:
                    try:
                        dup_size = max(1, int(dup_count_fn(text_norm)))
                    except Exception as exc:
                        logger.warning("dup_text_size lookup failed: %s", exc)
                        dup_size = 1

                return STTResult(
                    file=file_label,
                    model=self.canonical_model_name,
                    text=text,
                    text_norm=text_norm,
                    min_avg_logprob=min_logprob,
                    max_no_speech_prob=max_no_speech,
                    needs_review=bool(reasons),
                    review_reasons=";".join(reasons),
                    dup_text_size=dup_size,
                    error="",
                )
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "STT attempt %d/%d failed for %s: %s",
                    attempt,
                    self.max_retries,
                    file_label,
                    last_error,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_s * attempt)

        return STTResult(
            file=file_label,
            model=self.canonical_model_name,
            text="",
            text_norm="",
            min_avg_logprob=None,
            max_no_speech_prob=None,
            needs_review=True,
            review_reasons="stt_error",
            dup_text_size=0,
            error=f"Transcription failed after {self.max_retries} attempts: {last_error}",
        )
