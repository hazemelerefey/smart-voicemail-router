"""Stage 1: intake and preprocessing (owner: Sira, mock in Phase 1).

Validates the upload per contracts section 5: WAV, MP3, M4A inputs,
25 MB limit, 60 second maximum. Audio is normalized to 16 kHz mono WAV
by the real pipeline in Phase 2; the mock records the declared format
and measures WAV duration with the stdlib ``wave`` module.
"""

from __future__ import annotations

import io
import wave
from dataclasses import dataclass

MAX_BYTES = 25 * 1024 * 1024  # 25 MB, contracts section 5
MAX_DURATION_S = 60.0  # 60 seconds, contracts section 5
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a"}
ALLOWED_FORMATS = {"wav", "mp3", "m4a"}


@dataclass
class AudioMeta:
    """Intake output: what is known about the audio before STT."""

    voicemail_id: str
    filename: str
    format: str
    size_bytes: int
    duration_s: float | None
    duration_checked: bool


def _extension(filename: str) -> str:
    name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    dot = name.rfind(".")
    return name[dot:].lower() if dot != -1 else ""


def _wav_duration_s(data: bytes) -> float:
    with wave.open(io.BytesIO(data), "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
        if rate <= 0:
            raise ValueError("WAV file has an invalid frame rate")
        return frames / rate


def validate_and_measure(file_bytes: bytes, filename: str, voicemail_id: str) -> AudioMeta:
    """Validate format, size and duration. Raises ValueError with the reason."""
    ext = _extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"unsupported format {ext or '(none)'}: only WAV, MP3, M4A are accepted"
        )
    if len(file_bytes) > MAX_BYTES:
        raise ValueError(
            f"file is {len(file_bytes)} bytes, over the 25 MB limit"
        )
    if len(file_bytes) == 0:
        raise ValueError("empty file")
    fmt = ext.lstrip(".")
    duration: float | None = None
    duration_checked = False
    if fmt == "wav":
        try:
            duration = _wav_duration_s(file_bytes)
        except (wave.Error, EOFError, ValueError) as exc:
            raise ValueError(f"unreadable WAV file: {exc}") from exc
        duration_checked = True
        if duration > MAX_DURATION_S:
            raise ValueError(
                f"duration {duration:.1f}s exceeds the 60 second maximum"
            )
    # MP3/M4A duration is not measurable with the stdlib alone. Phase 2
    # (Sira's audio pipeline) measures it at intake; until then the file
    # is accepted on format and size only and duration_checked stays False.
    return AudioMeta(
        voicemail_id=voicemail_id,
        filename=filename,
        format=fmt,
        size_bytes=len(file_bytes),
        duration_s=duration,
        duration_checked=duration_checked,
    )
