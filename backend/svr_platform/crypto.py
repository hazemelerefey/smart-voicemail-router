"""Encryption-at-rest utilities for voicemail audio and sensitive payloads (NFR2)."""

from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet


class EncryptionService:
    """Fernet authenticated symmetric encryption wrapper (AES-128-CBC + HMAC-SHA256)."""

    def __init__(self, fernet_key: str) -> None:
        self._fernet = Fernet(fernet_key.encode("ascii") if isinstance(fernet_key, str) else fernet_key)

    def encrypt_bytes(self, plaintext: bytes) -> bytes:
        return self._fernet.encrypt(plaintext)

    def decrypt_bytes(self, ciphertext: bytes) -> bytes:
        return self._fernet.decrypt(ciphertext)

    def write_encrypted_file(self, path: Path, plaintext: bytes) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.encrypt_bytes(plaintext))
        return path

    def read_encrypted_file(self, path: Path) -> bytes:
        return self.decrypt_bytes(path.read_bytes())
