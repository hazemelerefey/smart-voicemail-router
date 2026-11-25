"""Shared test fixtures for SVR production backend tests."""

from __future__ import annotations

import io
import os
import wave
from pathlib import Path

import pytest

from svr_platform.config import Settings
from svr_platform.database import DatabaseManager
from svr_platform.seed import seed_initial_data


def make_wav_bytes(duration_s: float = 1.0, rate: int = 16000, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    n_frames = int(duration_s * rate)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * n_frames * channels)
    return buf.getvalue()


@pytest.fixture()
def test_settings(tmp_path: Path) -> Settings:
    storage_dir = tmp_path / "storage"
    models_dir = tmp_path / "models"
    db_path = storage_dir / "test_svr.db"
    return Settings(
        SVR_ENV="test",
        DATABASE_URL=f"sqlite:///{db_path.as_posix()}",
        SVR_STORAGE_DIR=storage_dir,
        SVR_MODELS_DIR=models_dir,
        SVR_BOOTSTRAP_PASSWORD="TestPassword123!",
        SVR_SECRET_KEY="test-secret-key-for-unit-tests-only",
    )


@pytest.fixture()
def db_manager(test_settings: Settings) -> DatabaseManager:
    mgr = DatabaseManager(test_settings.database_url)
    mgr.create_all()
    with mgr.session_factory() as db:
        seed_initial_data(db, test_settings)
    return mgr
