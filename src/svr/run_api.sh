#!/usr/bin/env bash
# Run the SVR Phase 1 API (mock pipeline) on http://127.0.0.1:8000
# Usage: from the repo root: bash src/svr/run_api.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
PYTHONPATH=src .venv/bin/python -m svr
