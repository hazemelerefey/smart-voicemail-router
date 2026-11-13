"""Stage 2: speech to text (owner: Sira, mock in Phase 1).

Phase 1 mock: returns the fixed fixture transcript from contracts
section 9. Phase 2 plugs in Whisper large-v3 here, behind the same
``transcribe_mock`` signature (renamed then to ``transcribe``), keeping
``stt_provider`` / ``stt_model_version`` / ``stt_confidence`` fields.
"""

from __future__ import annotations

from .. import fixtures
from ..schemas import AudioEvidence
from .intake import AudioMeta

MOCK_STT_PROVIDER = "mock"
MOCK_STT_MODEL_VERSION = "mock-stt-0.1"


def transcribe_mock(meta: AudioMeta) -> AudioEvidence:
    """Mock STT: fixed fixture transcript, no audio is read or sent anywhere.

    Evidence reports only measured values. Phase 1 persists no audio, so
    ``audio_path_local`` is null; WAV duration, sample rate and channels
    come from the header intake measured; MP3/M4A stay null (unmeasured).
    """
    return AudioEvidence(
        voicemail_id=meta.voicemail_id,
        audio_path_local=None,
        duration_s=meta.duration_s,
        format=meta.format,
        sample_rate_hz=meta.sample_rate_hz,
        channels=meta.channels,
        transcript=fixtures.FIXTURE_TRANSCRIPT,
        stt_provider=MOCK_STT_PROVIDER,
        stt_model_version=MOCK_STT_MODEL_VERSION,
        stt_confidence=None,  # unknown for a mock; null, not guessed
        language_mix=None,  # values OPEN, contracts section 2
        audio_quality={"mock": True, "duration_checked": meta.duration_checked},
    )
