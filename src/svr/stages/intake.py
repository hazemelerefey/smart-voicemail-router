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
    """Intake output: what is known about the audio before STT.

    ``duration_s``, ``sample_rate_hz`` and ``channels`` are measured from
    the WAV header when the format is WAV; they stay null for MP3/M4A,
    whose duration the stdlib cannot measure (Phase 2, Sira).
    """

    voicemail_id: str
    filename: str
    format: str
    size_bytes: int
    duration_s: float | None
    duration_checked: bool
    sample_rate_hz: int | None = None
    channels: int | None = None


def _extension(filename: str) -> str:
    name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    dot = name.rfind(".")
    return name[dot:].lower() if dot != -1 else ""


def _wav_info(data: bytes) -> tuple[float, int, int]:
    """Measured WAV values from the file header: duration, sample rate,
    channel count. Raises ValueError on an invalid header."""
    with wave.open(io.BytesIO(data), "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
        if rate <= 0:
            raise ValueError("WAV file has an invalid frame rate")
        return frames / rate, rate, wav.getnchannels()


def _wav_duration_s(data: bytes) -> float:
    return _wav_info(data)[0]


def validate_metadata(
    filename: str,
    size_bytes: int,
    duration_s: float | None = None,
    duration_checked: bool = False,
    voicemail_id: str = "",
    sample_rate_hz: int | None = None,
    channels: int | None = None,
) -> AudioMeta:
    """Validate upload metadata only. No audio bytes are read here: the
    endpoint measures them first (validate_and_measure) and the pipeline
    runs on this metadata, so bytes never enter a background task."""
    ext = _extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"unsupported format {ext or '(none)'}: only WAV, MP3, M4A are accepted"
        )
    if size_bytes > MAX_BYTES:
        raise ValueError(f"file is {size_bytes} bytes, over the 25 MB limit")
    if size_bytes == 0:
        raise ValueError("empty file")
    if duration_checked and duration_s is not None and duration_s > MAX_DURATION_S:
        raise ValueError(
            f"duration {duration_s:.1f}s exceeds the 60 second maximum"
        )
    return AudioMeta(
        voicemail_id=voicemail_id,
        filename=filename,
        format=ext.lstrip("."),
        size_bytes=size_bytes,
        duration_s=duration_s,
        duration_checked=duration_checked,
        sample_rate_hz=sample_rate_hz,
        channels=channels,
    )


def validate_and_measure(file_bytes: bytes, filename: str, voicemail_id: str) -> AudioMeta:
    """Validate format, size and duration. Raises ValueError with the reason.

    The only place audio bytes are read: the endpoint calls this, then
    discards the bytes. Format, size and empty are checked first, so an
    oversize file reports the 25 MB limit instead of a parse error. WAV
    duration is measured here with the stdlib ``wave`` module; MP3/M4A
    duration stays unmeasured, see below.
    """
    # Format, size and empty first (duration not measured yet).
    validate_metadata(filename, len(file_bytes), None, False, voicemail_id)
    duration: float | None = None
    duration_checked = False
    sample_rate_hz: int | None = None
    channels: int | None = None
    if _extension(filename) == ".wav":
        try:
            duration, sample_rate_hz, channels = _wav_info(file_bytes)
        except (wave.Error, EOFError, ValueError) as exc:
            raise ValueError(f"unreadable WAV file: {exc}") from exc
        duration_checked = True
    # MP3/M4A duration is not measurable with the stdlib alone. Phase 2
    # (Sira's audio pipeline) measures it at intake; until then the file
    # is accepted on format and size only and duration_checked stays False.
    return validate_metadata(
        filename,
        len(file_bytes),
        duration,
        duration_checked,
        voicemail_id,
        sample_rate_hz,
        channels,
    )
