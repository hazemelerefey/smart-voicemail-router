"""Stage 4: voice evidence (owner: Sira, mock in Phase 1).

Phase 1: SKIPPED. The audio model (wav2vec2 XLS-R 300M) lands with Sira
in Phase 2. Until then there is no ``voice_state_candidate`` and no voice
confidence, and the pipeline records the stage as ``skipped`` with 0 ms.
Voice evidence is optional until validated and must never overwrite
``customer_state_text`` or decide complaint urgency (contracts section 2).
"""

from __future__ import annotations

from ..schemas import AudioEvidence, VoiceEvidence


def voice_evidence_mock(audio: AudioEvidence) -> VoiceEvidence | None:
    """Phase 1 mock: no voice evidence yet. Returns None (stage skipped)."""
    return None
