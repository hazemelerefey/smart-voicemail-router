#!/usr/bin/env bash
# Run the Gradio demo skeleton on http://127.0.0.1:7860
# Usage: from the repo root: bash src/svr/run_demo.sh
# The proxy variables must be unset first: this sandbox's no_proxy contains
# IPv6 entries that httpx (used by Gradio at import time) cannot parse,
# so `import gradio` fails with `httpx.InvalidURL: Invalid port: ':1]'`
# unless they are unset. The plain HTML demo at GET / in the API does not
# need this workaround.
set -euo pipefail
cd "$(dirname "$0")/../.."
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy NO_PROXY no_proxy
PYTHONPATH=src .venv/bin/python -m svr.demo
