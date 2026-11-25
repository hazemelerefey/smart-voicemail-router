"""Voicemail upload validation, probing, and 16 kHz mono WAV decoding (FR1, FR2, NFR13)."""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

logger = logging.getLogger("svr_platform.intake")

MAX_BYTES = 25 * 1024 * 1024  # 25 MB (FR1)
MAX_DURATION_S = 60.0  # 60 seconds (FR1)
RECOMMENDED_MIN_DURATION_S = 15.0  # FR1 recommendation only, never rejected
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a"}
_CHUNK_SIZE = 1024 * 1024  # 1 MiB streaming cap


class IntakeValidationError(ValueError):
    """Raised when an uploaded voicemail fails format, size, or duration validation."""

    def __init__(self, problem: str, detail: str) -> None:
        self.problem = problem  # format | size | duration
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class AudioProbeResult:
    file_name: str
    format: str  # wav | mp3 | m4a
    size_bytes: int
    duration_seconds: float
    sample_rate_hz: int | None
    channels: int | None
    content_sha256: str
    recommendation_note: str | None = None


def _safe_extension(filename: str) -> str:
    clean_name = os.path.basename(filename or "").strip()
    dot = clean_name.rfind(".")
    return clean_name[dot:].lower() if dot != -1 else ""


def _check_container_magic(data: bytes, ext: str) -> None:
    if ext == ".wav":
        if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
            raise IntakeValidationError("format", "Invalid WAV file: missing RIFF/WAVE header.")
    elif ext == ".mp3":
        has_id3 = data[:3] == b"ID3"
        has_sync = len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0
        if not (has_id3 or has_sync):
            raise IntakeValidationError("format", "Invalid MP3 file: missing ID3 tag or MPEG frame sync.")
    elif ext == ".m4a":
        if len(data) < 12 or data[4:8] != b"ftyp":
            raise IntakeValidationError("format", "Invalid M4A file: missing ISO BMFF ftyp box.")


def _probe_wav_stdlib(data: bytes) -> tuple[float, int, int]:
    try:
        with wave.open(io.BytesIO(data), "rb") as wf:
            rate = wf.getframerate()
            frames = wf.getnframes()
            channels = wf.getnchannels()
            if rate <= 0:
                raise IntakeValidationError("format", "Invalid WAV file: sample rate must be positive.")
            return frames / float(rate), rate, channels
    except IntakeValidationError:
        raise
    except (wave.Error, EOFError, ValueError) as exc:
        raise IntakeValidationError("format", f"Unreadable WAV audio file: {exc}") from exc


def _probe_with_ffprobe(data: bytes, ext: str, ffprobe_bin: str) -> tuple[float, int | None, int | None]:
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
            tf.write(data)
            tmp_path = Path(tf.name)
        proc = subprocess.run(
            [
                ffprobe_bin,
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=sample_rate,channels,duration:format=duration",
                "-of",
                "json",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if proc.returncode != 0:
            raise IntakeValidationError(
                "format", f"Unreadable {ext.lstrip('.').upper()} audio file."
            )
        payload = json.loads(proc.stdout or "{}")
        streams = payload.get("streams") or []
        fmt_info = payload.get("format") or {}
        if not streams:
            raise IntakeValidationError("format", "Uploaded file contains no audio stream.")
        stream = streams[0]
        raw_dur = stream.get("duration") or fmt_info.get("duration")
        if raw_dur is None:
            raise IntakeValidationError("duration", "Unable to determine audio duration.")
        duration = float(raw_dur)
        sr = int(stream["sample_rate"]) if stream.get("sample_rate") else None
        ch = int(stream["channels"]) if stream.get("channels") else None
        return duration, sr, ch
    except IntakeValidationError:
        raise
    except FileNotFoundError as exc:
        logger.error("ffprobe binary not found at %s: %s", ffprobe_bin, exc)
        raise IntakeValidationError(
            "format", "Audio probing tool unavailable on server; cannot validate MP3/M4A duration."
        ) from exc
    except Exception as exc:
        logger.warning("ffprobe failed for %s upload: %s", ext, exc)
        raise IntakeValidationError("format", f"Failed to inspect audio file: {exc}") from exc
    finally:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError as exc:
                logger.warning("Could not remove temp probe file %s: %s", tmp_path, exc)


async def read_upload_limited(file: UploadFile, limit_bytes: int = MAX_BYTES) -> bytes:
    """Read upload in 1 MiB chunks, rejecting oversize payloads before full allocation."""
    buf = bytearray()
    while True:
        chunk = await file.read(_CHUNK_SIZE)
        if not chunk:
            return bytes(buf)
        if len(buf) + len(chunk) > limit_bytes:
            raise IntakeValidationError(
                "size",
                f"File size exceeds the {limit_bytes // (1024 * 1024)} MB maximum limit.",
            )
        buf.extend(chunk)


def validate_and_probe_audio(
    data: bytes,
    filename: str,
    *,
    ffprobe_bin: str = "ffprobe",
) -> AudioProbeResult:
    """Validate format, size, container magic, and duration before ticket creation (FR1, FR2)."""
    clean_name = os.path.basename(filename or "").strip() or "voicemail.wav"
    ext = _safe_extension(clean_name)
    if ext not in ALLOWED_EXTENSIONS:
        raise IntakeValidationError(
            "format",
            f"Unsupported audio format '{ext or '(none)'}': only WAV, MP3, and M4A are accepted.",
        )

    size_bytes = len(data)
    if size_bytes == 0:
        raise IntakeValidationError("size", "Uploaded audio file is empty (0 bytes).")
    if size_bytes > MAX_BYTES:
        raise IntakeValidationError(
            "size",
            f"File size ({size_bytes} bytes) exceeds the 25 MB maximum limit.",
        )

    _check_container_magic(data, ext)

    if ext == ".wav":
        duration_s, sr, ch = _probe_wav_stdlib(data)
    else:
        duration_s, sr, ch = _probe_with_ffprobe(data, ext, ffprobe_bin)

    if duration_s <= 0.0:
        raise IntakeValidationError("duration", "Audio duration must be greater than 0 seconds.")
    if duration_s > MAX_DURATION_S:
        raise IntakeValidationError(
            "duration",
            f"Audio duration ({duration_s:.1f} s) exceeds the 60 second maximum limit.",
        )

    recommendation: str | None = None
    if duration_s < RECOMMENDED_MIN_DURATION_S:
        recommendation = (
            f"Clip is {duration_s:.1f} s; 15 to 60 seconds is recommended, accepted for processing."
        )

    return AudioProbeResult(
        file_name=clean_name,
        format=ext.lstrip("."),
        size_bytes=size_bytes,
        duration_seconds=round(duration_s, 3),
        sample_rate_hz=sr,
        channels=ch,
        content_sha256=hashlib.sha256(data).hexdigest(),
        recommendation_note=recommendation,
    )


def decode_to_wav_16k_mono(data: bytes, fmt: str, *, ffmpeg_bin: str = "ffmpeg") -> bytes:
    """Decode WAV/MP3/M4A bytes into 16 kHz mono 16-bit PCM WAV for Whisper large-v3."""
    if fmt == "wav":
        try:
            with wave.open(io.BytesIO(data), "rb") as wf:
                if wf.getframerate() == 16000 and wf.getnchannels() == 1 and wf.getsampwidth() == 2:
                    return data
        except wave.Error as exc:
            logger.warning("Direct WAV check failed, falling back to ffmpeg decode: %s", exc)

    in_path: Path | None = None
    out_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as tf_in:
            tf_in.write(data)
            in_path = Path(tf_in.name)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf_out:
            out_path = Path(tf_out.name)
        proc = subprocess.run(
            [
                ffmpeg_bin,
                "-y",
                "-v",
                "error",
                "-i",
                str(in_path),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-sample_fmt",
                "s16",
                str(out_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg decode failed: {proc.stderr.strip()}")
        return out_path.read_bytes()
    finally:
        for p in (in_path, out_path):
            if p is not None and p.exists():
                try:
                    p.unlink()
                except OSError as exc:
                    logger.warning("Could not remove temp audio file %s: %s", p, exc)
