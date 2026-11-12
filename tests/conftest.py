"""Test setup.

Strips proxy environment variables before anything imports httpx: this
sandbox's no_proxy contains IPv6 entries (``[::1]``) that httpx cannot
parse, so ``httpx.Client()`` (used by Starlette's TestClient) raises
``httpx.InvalidURL: Invalid port: ':1]'`` unless they are unset.
Also puts ``src/`` on the path so tests can import the ``svr`` package.
"""

import os
import sys
from pathlib import Path

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
