# Smart Voicemail Router (SVR) - AI Agent Governance & Dataset Guide

This guide documents the non-negotiable engineering, evaluation, and privacy rules for AI agents and developers working on SVR.

## 1. Frozen Dataset Split Governance
- **Split names:** `train`, `validation`, and `test` (never use `dev`).
- **Clean dataset (`v2`, seed `42`):** `5,096` rows (`train`: `3,575`, `validation`: `1,003`, `test`: `518`).
- **Held-out test protection:** Never inspect, tune on, or run setup/smoke benchmarks against `final/clean_training_test.csv` or `dataset/test/`. Production test evaluation is guarded by the SHA-256 test-once ledger (`backend/svr_platform/eval/once_guard.py` -> `runs/test_evaluations.json`).
- **Class imbalance handling:** Never resample datasets during preprocessing; apply train-only class weights in the loss (`final/class_weights.json`).

## 2. Local-First Sovereignty & Security Boundaries
- **Zero external LLM / STT egress:** `OLLAMA_URL` must target loopback (`127.0.0.1`, `localhost`, `::1`) or internal Docker `http://ollama:11434` when `SVR_ALLOW_DOCKER_OLLAMA=1`.
- **Offline runtime inference:** Pre-download model weights via `ops/download_models.py` and run with `local_files_only=True` in production.
- **No plaintext audio persistence:** All uploaded or recorded voicemails are Fernet-encrypted (`AES-128-CBC + HMAC-SHA256`) at rest.

## 3. Code Quality & CI Static Guards
- **Zero em dashes (`\u2014`) or en dashes (`\u2013`)** in source code, config, tests, or documentation. Use commas or plain ASCII hyphens (`-`).
- **Zero empty `except: pass` blocks** in Python.
- **No `dangerouslySetInnerHTML`** and no `localStorage`/`sessionStorage` token storage in frontend TypeScript/React code.
- **Keep `brief.py` deterministic (PRD FR15 / S3):** `summary` uses `transcript[:200]`, and callback scripts use approved templates without LLM hallucination risk.
