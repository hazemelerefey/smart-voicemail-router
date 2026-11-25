"""Arabic/English transcript normalization and FR5 language-mix display indication."""

from __future__ import annotations

import re
import unicodedata

_DIACRITICS_RE = re.compile(r"[\u064b-\u065f\u0670\u0640]")
_ALEF_RE = re.compile(r"[أإآٱ]")
_WS_RE = re.compile(r"\s+")
_ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
_LATIN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")

# Common telecom terms appearing in Egyptian Arabic voicemails (eda_audio_speech.md section 3)
TELECOM_ENGLISH_TERMS = frozenset(
    {
        "sim",
        "esim",
        "4g",
        "5g",
        "3g",
        "lte",
        "dsl",
        "adsl",
        "vdsl",
        "mb",
        "gb",
        "kb",
        "otp",
        "pin",
        "puk",
        "app",
        "application",
        "router",
        "wifi",
        "wi-fi",
        "vpn",
        "flex",
        "bundle",
        "roaming",
        "sms",
        "mms",
        "voicemail",
        "call",
        "back",
        "online",
        "logout",
        "login",
        "control",
        "internet",
        "net",
        "data",
        "megabyte",
        "gigabyte",
        "bill",
        "package",
        "offer",
        "stop",
        "g",
    }
)


def normalize_transcript(text: str) -> str:
    """Normalize Whisper transcript into SVR corpus text_norm (verified against clean_training_val.csv)."""
    if not text:
        return ""
    s = text.lower()
    s = _DIACRITICS_RE.sub("", s)
    s = _ALEF_RE.sub("ا", s)
    s = s.replace("ة", "ه").replace("ى", "ي")
    s = "".join(ch if unicodedata.category(ch)[0] in ("L", "N") else " " for ch in s)
    return _WS_RE.sub(" ", s).strip()


def detect_language_mix(text: str) -> str:
    """FR5 read-only transcript language-mix indication (never used for routing or priority).

    Returns one of: 'arabic', 'english_telecom_terms', 'mixed'.
    """
    if not text or not text.strip():
        return "arabic"
    has_arabic = bool(_ARABIC_RE.search(text))
    latin_tokens = [m.group(0).lower() for m in _LATIN_WORD_RE.finditer(text)]
    if not latin_tokens:
        return "arabic"
    if not has_arabic:
        return "mixed"
    if all(tok in TELECOM_ENGLISH_TERMS for tok in latin_tokens):
        return "english_telecom_terms"
    return "mixed"
