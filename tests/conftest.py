"""Test setup.

Strips proxy environment variables before anything imports httpx: this
sandbox's no_proxy contains IPv6 entries (``[::1]``) that httpx cannot
parse, so ``httpx.Client()`` (used by Starlette's TestClient) raises
``httpx.InvalidURL: Invalid port: ':1]'`` unless they are unset.
Also puts ``src/`` on the path so tests can import the ``svr`` package.
"""

import io
import os
import sys
import wave
from pathlib import Path

import pytest

for _var in (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "http_proxy",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
    "NO_PROXY",
    "no_proxy",
):
    os.environ.pop(_var, None)

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


def make_wav_bytes(duration_s: float = 1.0, rate: int = 16000, channels: int = 1) -> bytes:
    """Build a valid WAV in memory. Shared test helper (issues #9): the
    API and pipeline tests used to define this twice."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * channels * int(rate * duration_s))
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _reset_demo_state():
    """Isolate tests: clear the store and restore the seeded agent loads
    before and after each test, so state never leaks across tests and
    results never depend on run order (issues #6, #9)."""
    from svr import agents as agents_module
    from svr.store import STORE

    agents_module.reset_loads()
    STORE.clear()
    yield
    agents_module.reset_loads()
    STORE.clear()
