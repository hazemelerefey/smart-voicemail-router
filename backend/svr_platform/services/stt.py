"""Self-hosted Arabic STT services (Cohere Arabic ASR & Whisper large-v3) producing locked 10-column format v1 (FR4, FR5, AI1, NFR14)."""

from __future__ import annotations

import gc
import io
import logging
import math
import os
import re
import subprocess
import tempfile
import threading
import time
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

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


def normalize_wav_16k_loudness(
    wav_bytes: bytes,
    *,
    min_rms_trigger: float = 0.05,
    target_rms: float = 0.10,
    max_peak: float = 0.89,
    max_gain: float = 20.0,
) -> bytes:
    """Remove DC offset / <80 Hz rumble and boost quiet 16-bit PCM WAV recordings safely."""
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as w_in:
            sr = w_in.getframerate()
            ch = w_in.getnchannels()
            sw = w_in.getsampwidth()
            n_frames = w_in.getnframes()
            if sw != 2 or n_frames == 0:
                return wav_bytes
            raw_pcm = w_in.readframes(n_frames)
    except Exception:
        return wav_bytes

    pcm = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32) / 32768.0
    if pcm.size == 0:
        return wav_bytes

    # Remove DC offset and sub-80 Hz telephony rumble without distorting speech bands
    pcm = pcm - float(np.mean(pcm))
    if sr > 160 and pcm.size >= 8:
        win = max(3, int(round(float(sr) / 80.0)))
        if win < pcm.size:
            kernel = np.ones(win, dtype=np.float32) / float(win)
            low_band = np.convolve(pcm, kernel, mode="same")
            pcm = pcm - low_band

    rms = float(np.sqrt(np.mean(pcm * pcm)))
    peak = float(np.max(np.abs(pcm)))
    if rms < 1e-4 or peak <= 0.0:
        return wav_bytes

    gain = 1.0
    if rms < min_rms_trigger:
        candidate_gain = min(target_rms / rms, max_peak / peak, max_gain)
        if candidate_gain > 1.05:
            gain = candidate_gain

    boosted = np.clip(pcm * gain, -1.0, 1.0)
    out_pcm = (boosted * 32767.0).astype(np.int16).tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w_out:
        w_out.setnchannels(ch)
        w_out.setsampwidth(2)
        w_out.setframerate(sr)
        w_out.writeframes(out_pcm)
    return buf.getvalue()


def _wav_bytes_to_float32(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    """Decode 16-bit PCM WAV bytes into mono float32 array in [-1.0, 1.0] and sample rate."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as w_in:
        sr = w_in.getframerate()
        ch = w_in.getnchannels()
        n_frames = w_in.getnframes()
        raw_pcm = w_in.readframes(n_frames)
    pcm = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1 and pcm.size > 0:
        pcm = pcm.reshape(-1, ch).mean(axis=1)
    return pcm, sr


def _float32_to_wav_bytes(pcm_f32: np.ndarray, sr: int = 16000) -> bytes:
    """Encode mono float32 array into 16-bit PCM WAV bytes."""
    clipped = np.clip(pcm_f32, -1.0, 1.0)
    out_pcm = (clipped * 32767.0).astype(np.int16).tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w_out:
        w_out.setnchannels(1)
        w_out.setsampwidth(2)
        w_out.setframerate(sr)
        w_out.writeframes(out_pcm)
    return buf.getvalue()


def detect_repetition_breakdown(text: str, *, min_repeats: int = 4) -> bool:
    """Detect degenerate AED decoding repetition loops (>=4 consecutive 1..4-word repeats)."""
    norm_tokens = normalize_transcript(text).split()
    if len(norm_tokens) < min_repeats:
        return False
    for n in range(1, 5):
        limit = len(norm_tokens) - n * min_repeats + 1
        for idx in range(max(0, limit)):
            gram = norm_tokens[idx : idx + n]
            if not any(gram):
                continue
            ok = True
            for k in range(1, min_repeats):
                if norm_tokens[idx + k * n : idx + (k + 1) * n] != gram:
                    ok = False
                    break
            if ok:
                return True
    return False


_SILERO_VAD_LOCK = threading.Lock()
_SILERO_VAD_MODEL: Any = None


def _get_offline_silero_vad():
    """Load offline PyPI silero-vad model once (never calls torch.hub.load)."""
    global _SILERO_VAD_MODEL
    if _SILERO_VAD_MODEL is not None:
        return _SILERO_VAD_MODEL
    with _SILERO_VAD_LOCK:
        if _SILERO_VAD_MODEL is not None:
            return _SILERO_VAD_MODEL
        from silero_vad import load_silero_vad

        _SILERO_VAD_MODEL = load_silero_vad()
        return _SILERO_VAD_MODEL


def run_offline_silero_vad(
    pcm_f32: np.ndarray,
    sr: int = 16000,
) -> tuple[float, list[tuple[int, int]]]:
    """Compute speech ratio and speech sample intervals using offline silero-vad (with energy fallback)."""
    total = int(pcm_f32.size)
    if total == 0:
        return 0.0, []

    try:
        import torch
        from silero_vad import get_speech_timestamps

        model = _get_offline_silero_vad()
        wav_tensor = torch.from_numpy(np.ascontiguousarray(pcm_f32, dtype=np.float32))
        timestamps = get_speech_timestamps(
            wav_tensor,
            model,
            sampling_rate=sr,
            return_seconds=False,
        )
        segments = [
            (max(0, int(ts["start"])), min(total, int(ts["end"])))
            for ts in timestamps
            if int(ts["end"]) > int(ts["start"])
        ]
        speech_samples = sum(end - start for start, end in segments)
        return round(min(1.0, speech_samples / float(total)), 4), segments
    except Exception as exc:
        logger.debug("Offline silero-vad unavailable (%s); using frame-energy VAD fallback.", exc)
        frame_len = max(1, int(sr * 0.03))  # 30 ms frames
        segments: list[tuple[int, int]] = []
        active_start: int | None = None
        for pos in range(0, total, frame_len):
            frame = pcm_f32[pos : pos + frame_len]
            rms = float(np.sqrt(np.mean(frame * frame))) if frame.size else 0.0
            if rms >= 0.015:
                if active_start is None:
                    active_start = pos
            elif active_start is not None:
                segments.append((active_start, pos))
                active_start = None
        if active_start is not None:
            segments.append((active_start, total))
        speech_samples = sum(end - start for start, end in segments)
        return round(min(1.0, speech_samples / float(total)), 4), segments


def chunk_pcm_by_vad(
    pcm_f32: np.ndarray,
    segments: list[tuple[int, int]],
    *,
    sr: int = 16000,
    target_max_s: float = 30.0,
    hard_max_s: float = 35.0,
) -> list[np.ndarray]:
    """Split audio > target_max_s along VAD quiet boundaries, respecting hard_max_s cap."""
    total = int(pcm_f32.size)
    if total == 0:
        return []

    target_samples = int(target_max_s * sr)
    hard_samples = int(hard_max_s * sr)
    if total <= target_samples:
        return [pcm_f32]

    pad = int(0.15 * sr)
    if not segments:
        segments = [(0, total)]

    # Merge tiny pauses into speech blocks with slight padding
    blocks: list[tuple[int, int]] = []
    for s, e in segments:
        ps = max(0, s - pad)
        pe = min(total, e + pad)
        if not blocks or ps > blocks[-1][1] + int(0.35 * sr):
            blocks.append((ps, pe))
        else:
            blocks[-1] = (blocks[-1][0], max(blocks[-1][1], pe))

    chunks: list[np.ndarray] = []
    cur_start: int | None = None
    cur_end: int = 0
    overlap = int(0.5 * sr)

    def _emit_range(start_idx: int, end_idx: int) -> None:
        pos = start_idx
        while pos < end_idx:
            sub_end = min(end_idx, pos + hard_samples)
            if sub_end > pos:
                chunks.append(pcm_f32[pos:sub_end])
            if sub_end >= end_idx:
                break
            pos = max(pos + 1, sub_end - overlap)

    for bs, be in blocks:
        if cur_start is None:
            if (be - bs) > target_samples:
                _emit_range(bs, be)
            else:
                cur_start, cur_end = bs, be
            continue

        if (be - cur_start) <= target_samples:
            cur_end = be
        else:
            _emit_range(cur_start, cur_end)
            if (be - bs) > target_samples:
                _emit_range(bs, be)
                cur_start = None
            else:
                cur_start, cur_end = bs, be

    if cur_start is not None:
        _emit_range(cur_start, cur_end)

    return chunks if chunks else [pcm_f32[:hard_samples]]


def aggregate_chunk_signals(
    chunk_logprobs: list[float | None],
    chunk_no_speech: list[float | None],
) -> tuple[float | None, float | None]:
    """Conservatively aggregate chunk confidence proxies across multi-chunk clips."""
    valid_lp = [float(x) for x in chunk_logprobs if x is not None and math.isfinite(float(x))]
    valid_nsp = [float(x) for x in chunk_no_speech if x is not None and math.isfinite(float(x))]
    min_lp = round(min(valid_lp), 4) if valid_lp else None
    max_nsp = round(max(valid_nsp), 4) if valid_nsp else None
    return min_lp, max_nsp


def join_chunk_transcripts(parts: list[str]) -> str:
    """Join sequential chunk transcripts while deduplicating 1..3-word overlap repetitions."""
    merged_words: list[str] = []
    for part in parts:
        words = (part or "").strip().split()
        if not words:
            continue
        if not merged_words:
            merged_words.extend(words)
            continue
        overlap_len = 0
        max_k = min(3, len(merged_words), len(words))
        for k in range(max_k, 0, -1):
            tail_norm = [normalize_transcript(w) for w in merged_words[-k:]]
            head_norm = [normalize_transcript(w) for w in words[:k]]
            if tail_norm == head_norm and any(tail_norm):
                overlap_len = k
                break
        merged_words.extend(words[overlap_len:])
    return " ".join(merged_words).strip()


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
    stt_confidence_source: str = "logprob"

    def to_v1_dict(self) -> dict:
        data = asdict(self)
        return {col: data[col] for col in STT_V1_COLUMNS}

    @property
    def language_mix(self) -> str:
        return detect_language_mix(self.text)


class BaseSTTService:
    """Shared local STT contract producing locked 10-column STT v1 records with retry & unload."""

    def __init__(
        self,
        *,
        model_id: str,
        canonical_model_name: str,
        device: str = "cpu",
        compute_type: str = "int8",
        ffmpeg_bin: str = "ffmpeg",
        max_retries: int = 3,
        retry_backoff_s: float = 0.5,
        low_memory_mode: bool | None = None,
        transcriber_override: Callable[[bytes, str], dict] | None = None,
        stt_confidence_source: str = "logprob",
    ) -> None:
        self.model_id = model_id
        self.canonical_model_name = canonical_model_name
        self.device = device
        self.compute_type = compute_type
        self.ffmpeg_bin = ffmpeg_bin
        self.max_retries = max_retries
        self.retry_backoff_s = retry_backoff_s
        if low_memory_mode is None:
            env_flag = os.environ.get("SVR_LOW_MEMORY_MODE", "").strip().lower()
            if env_flag in ("1", "true", "yes"):
                self.low_memory_mode = True
            elif env_flag in ("0", "false", "no"):
                self.low_memory_mode = False
            else:
                self.low_memory_mode = self.device == "cpu"
        else:
            self.low_memory_mode = bool(low_memory_mode)
        self._transcriber_override = transcriber_override
        self.stt_confidence_source = stt_confidence_source
        self._model = None
        self._lock = threading.Lock()

    def unload(self) -> None:
        """Release the resident STT model to reclaim host RAM / GPU VRAM."""
        with self._lock:
            if self._model is not None:
                self._model = None
                gc.collect()
                logger.info("Unloaded local STT model=%s to reclaim memory.", self.model_id)

    def _get_model(self):
        raise NotImplementedError

    def _run_once(self, audio_bytes: bytes, fmt: str) -> tuple[str, float | None, float | None]:
        raise NotImplementedError

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
                if text and detect_repetition_breakdown(text):
                    reasons.append("repetition_loop")

                dup_size = 1
                if text_norm and dup_count_fn is not None:
                    try:
                        dup_size = max(1, int(dup_count_fn(text_norm)))
                    except Exception as exc:
                        logger.warning("dup_text_size lookup failed: %s", exc)
                        dup_size = 1

                conf_source = "vad_only" if min_logprob is None and self.stt_confidence_source != "logprob" else self.stt_confidence_source
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
                    stt_confidence_source=conf_source,
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
            stt_confidence_source=self.stt_confidence_source,
        )


class WhisperSTTService(BaseSTTService):
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
        low_memory_mode: bool | None = None,
        transcriber_override: Callable[[bytes, str], dict] | None = None,
    ) -> None:
        canonical = "openai/whisper-large-v3" if model_id == "large-v3" else model_id
        super().__init__(
            model_id=model_id,
            canonical_model_name=canonical,
            device=device,
            compute_type=compute_type,
            ffmpeg_bin=ffmpeg_bin,
            max_retries=max_retries,
            retry_backoff_s=retry_backoff_s,
            low_memory_mode=low_memory_mode,
            transcriber_override=transcriber_override,
            stt_confidence_source="logprob",
        )
        self.download_root = download_root

    def _get_model(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            if self.low_memory_mode and self.device == "cpu":
                os.environ.setdefault("CT2_USE_MKL", "0")
                os.environ.setdefault("OMP_NUM_THREADS", "1")
                os.environ.setdefault("MKL_NUM_THREADS", "1")
            from faster_whisper import WhisperModel

            logger.info(
                "Loading local Whisper model=%s device=%s compute_type=%s low_memory=%s",
                self.model_id,
                self.device,
                self.compute_type,
                self.low_memory_mode,
            )
            kwargs: dict[str, object] = {
                "device": self.device,
                "compute_type": self.compute_type,
                "download_root": self.download_root,
            }
            if self.low_memory_mode and self.device == "cpu":
                kwargs["cpu_threads"] = 1
                kwargs["num_workers"] = 1
            self._model = WhisperModel(
                self.model_id,
                **kwargs,
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
        wav_16k = normalize_wav_16k_loudness(wav_16k)
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                tf.write(wav_16k)
                tmp_path = Path(tf.name)
            model = self._get_model()
            segments_iter, _info = model.transcribe(
                str(tmp_path),
                language="ar",
                beam_size=3,
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


class CohereArabicSTTService(BaseSTTService):
    """Local CohereLabs/cohere-transcribe-arabic-07-2026 STT service (INT8 GPU, BF16, or GGUF)."""

    def __init__(
        self,
        *,
        backend_mode: str = "cohere_gpu_int8",
        model_id: str | None = None,
        device: str = "cuda",
        compute_type: str = "int8",
        local_files_only: bool = True,
        gguf_bin: str = "",
        gguf_model_path: str = "",
        ffmpeg_bin: str = "ffmpeg",
        max_retries: int = 3,
        retry_backoff_s: float = 0.5,
        low_memory_mode: bool | None = None,
        transcriber_override: Callable[[bytes, str], dict] | None = None,
    ) -> None:
        self.backend_mode = backend_mode
        default_id = (
            "CohereLabs/cohere-transcribe-arabic-07-2026"
            if backend_mode == "cohere_bf16"
            else "NAMAA-Space/cohere-transcribe-arabic-07-2026-int8"
        )
        resolved_id = model_id or default_id
        conf_src = "vad_only" if backend_mode == "cohere_gguf" else "logprob"
        super().__init__(
            model_id=resolved_id,
            canonical_model_name=resolved_id,
            device=device,
            compute_type=compute_type,
            ffmpeg_bin=ffmpeg_bin,
            max_retries=max_retries,
            retry_backoff_s=retry_backoff_s,
            low_memory_mode=low_memory_mode,
            transcriber_override=transcriber_override,
            stt_confidence_source=conf_src,
        )
        self.local_files_only = bool(local_files_only)
        self.gguf_bin = gguf_bin
        self.gguf_model_path = gguf_model_path
        self._processor: Any = None

    def unload(self) -> None:
        with self._lock:
            released = self._model is not None or self._processor is not None
            self._model = None
            self._processor = None
            if released:
                gc.collect()
                try:
                    import torch

                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception as exc:
                    logger.debug("Optional CUDA cache empty skipped: %s", exc)
                logger.info("Unloaded local Cohere Arabic ASR model=%s.", self.model_id)

    def _get_model(self):
        if self.backend_mode == "cohere_gguf":
            if not self.gguf_bin or not Path(self.gguf_bin).is_file():
                raise RuntimeError(f"Cohere GGUF binary not found at SVR_COHERE_GGUF_BIN={self.gguf_bin!r}")
            if not self.gguf_model_path or not Path(self.gguf_model_path).is_file():
                raise RuntimeError(
                    f"Cohere GGUF model file not found at SVR_COHERE_GGUF_MODEL_PATH={self.gguf_model_path!r}"
                )
            return self.gguf_bin

        if self._model is not None and self._processor is not None:
            return self._model, self._processor

        with self._lock:
            if self._model is not None and self._processor is not None:
                return self._model, self._processor

            import torch
            import transformers
            from transformers import AutoProcessor

            model_cls = getattr(transformers, "CohereAsrForConditionalGeneration", None)
            if model_cls is None:
                from transformers import AutoModelForSpeechSeq2Seq

                model_cls = AutoModelForSpeechSeq2Seq

            logger.info(
                "Loading local Cohere Arabic ASR model=%s mode=%s device=%s local_only=%s",
                self.model_id,
                self.backend_mode,
                self.device,
                self.local_files_only,
            )
            try:
                processor = AutoProcessor.from_pretrained(
                    self.model_id,
                    local_files_only=self.local_files_only,
                )
            except Exception:
                processor = AutoProcessor.from_pretrained(
                    self.model_id,
                    local_files_only=self.local_files_only,
                    trust_remote_code=True,
                )

            load_kwargs: dict[str, Any] = {
                "local_files_only": self.local_files_only,
                "low_cpu_mem_usage": True,
            }
            if self.backend_mode == "cohere_bf16":
                load_kwargs["torch_dtype"] = torch.bfloat16
                if self.device == "cuda" and torch.cuda.is_available():
                    load_kwargs["device_map"] = "auto"
            elif self.device == "cuda" and torch.cuda.is_available():
                load_kwargs["device_map"] = "auto"

            try:
                model = model_cls.from_pretrained(self.model_id, **load_kwargs)
            except Exception:
                load_kwargs["trust_remote_code"] = True
                model = model_cls.from_pretrained(self.model_id, **load_kwargs)

            model.eval()
            self._processor = processor
            self._model = model
            return self._model, self._processor

    def _transcribe_hf_chunk(self, pcm_chunk: np.ndarray, sr: int) -> tuple[str, float | None]:
        import torch

        model, processor = self._get_model()
        try:
            inputs = processor(
                pcm_chunk,
                sampling_rate=sr,
                return_tensors="pt",
                language="ar",
            )
        except TypeError:
            inputs = processor(
                pcm_chunk,
                sampling_rate=sr,
                return_tensors="pt",
            )

        target_device = getattr(model, "device", None) or (
            torch.device("cuda") if self.device == "cuda" and torch.cuda.is_available() else torch.device("cpu")
        )
        encoder = model.get_encoder() if hasattr(model, "get_encoder") else model
        float_dtype = next(
            (p.dtype for p in encoder.parameters() if p.is_floating_point()),
            getattr(model, "dtype", torch.float32),
        )
        moved_inputs: dict[str, Any] = {}
        for k, v in inputs.items():
            if hasattr(v, "to"):
                if hasattr(v, "is_floating_point") and v.is_floating_point() and float_dtype is not None:
                    moved_inputs[k] = v.to(device=target_device, dtype=float_dtype)
                else:
                    moved_inputs[k] = v.to(target_device)
            else:
                moved_inputs[k] = v

        with torch.no_grad():
            gen_kwargs: dict[str, Any] = {
                "max_new_tokens": 448,
                "return_dict_in_generate": True,
                "output_scores": True,
            }
            if "language" in getattr(model.generation_config, "to_dict", lambda: {})():
                gen_kwargs["language"] = "ar"
            out = model.generate(**moved_inputs, **gen_kwargs)

        sequences = out.sequences if hasattr(out, "sequences") else out
        try:
            decoded = processor.decode(sequences[0], skip_special_tokens=True, language="ar")
        except TypeError:
            decoded = processor.batch_decode(sequences, skip_special_tokens=True)[0]

        avg_logprob: float | None = None
        if hasattr(out, "scores") and out.scores and hasattr(model, "compute_transition_scores"):
            try:
                transition = model.compute_transition_scores(
                    sequences,
                    out.scores,
                    normalize_logits=True,
                )
                finite = transition[torch.isfinite(transition)]
                if finite.numel() > 0:
                    avg_logprob = round(float(finite.mean().item()), 4)
            except Exception as exc:
                logger.debug("Could not extract Cohere sequence logprobs: %s", exc)
        cleaned_text = re.sub(r"\s*<[a-zA-Z_]+>\s*", " ", str(decoded))
        cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()
        return cleaned_text, avg_logprob

    def _transcribe_gguf_chunk(self, pcm_chunk: np.ndarray, sr: int) -> tuple[str, float | None]:
        gguf_bin = self._get_model()
        wav_chunk = _float32_to_wav_bytes(pcm_chunk, sr=sr)
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                tf.write(wav_chunk)
                tmp_path = Path(tf.name)
            proc = subprocess.run(
                [str(gguf_bin), "-m", str(self.gguf_model_path), "-f", str(tmp_path), "-l", "ar"],
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
            return proc.stdout.strip(), None
        finally:
            if tmp_path is not None and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError as exc:
                    logger.warning("Failed to remove temp GGUF wav %s: %s", tmp_path, exc)

    def _run_once(self, audio_bytes: bytes, fmt: str) -> tuple[str, float | None, float | None]:
        if self._transcriber_override is not None:
            res = self._transcriber_override(audio_bytes, fmt)
            return (
                str(res.get("text", "")),
                res.get("min_avg_logprob"),
                res.get("max_no_speech_prob"),
            )

        wav_16k = decode_to_wav_16k_mono(audio_bytes, fmt, ffmpeg_bin=self.ffmpeg_bin)
        wav_16k = normalize_wav_16k_loudness(wav_16k)
        pcm_f32, sr = _wav_bytes_to_float32(wav_16k)
        speech_ratio, segments = run_offline_silero_vad(pcm_f32, sr=sr)
        if speech_ratio < 0.05:
            return "", None, 1.0

        chunks = chunk_pcm_by_vad(pcm_f32, segments, sr=sr, target_max_s=30.0, hard_max_s=35.0)
        parts: list[str] = []
        chunk_logprobs: list[float | None] = []
        chunk_no_speech: list[float | None] = []

        for chunk in chunks:
            c_ratio, _ = run_offline_silero_vad(chunk, sr=sr)
            if c_ratio < 0.02:
                chunk_no_speech.append(round(1.0 - c_ratio, 4))
                continue
            if self.backend_mode == "cohere_gguf":
                c_text, c_lp = self._transcribe_gguf_chunk(chunk, sr)
            else:
                c_text, c_lp = self._transcribe_hf_chunk(chunk, sr)
            if c_text:
                parts.append(c_text)
            chunk_logprobs.append(c_lp)
            chunk_no_speech.append(round(max(0.0, min(1.0, 1.0 - c_ratio)), 4))

        final_text = join_chunk_transcripts(parts)
        min_lp, max_nsp = aggregate_chunk_signals(chunk_logprobs, chunk_no_speech)
        if not final_text and max_nsp is None:
            max_nsp = 1.0
        return final_text, min_lp, max_nsp
