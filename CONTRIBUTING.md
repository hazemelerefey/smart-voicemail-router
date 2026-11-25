# Contributing to Smart Voicemail Router

Thank you for contributing to **Smart Voicemail Router (SVR)**. This document defines the engineering, security, privacy, and verification standards required for all changes merged into `master`.

## Architecture & Domain Invariants

1. **Separated Triage Signals**: Keep `complaint_category` (11 classes), `complaint_urgency` (3 levels), `customer_state` (4 scored emotions + `unclear`), `churn_risk` (2 classes), and deterministic `priority_score` (`1..6`) explicitly separated across models, schemas, API responses, and UI views.
2. **Grounded Callback Briefs**: Suggested opening scripts and customer-request summaries must derive strictly from approved category templates and verified transcript metadata, with zero invented subscriber facts or unapproved commitments.
3. **Human-in-the-Loop Provenance**: Supervisor label overrides must preserve model-vs-human provenance (`label_sources`) and append an immutable before/after JSON diff to `audit_events`.

## Data Privacy & Security Rules

- **Zero Raw Audio or PII in Git**: Never commit `.wav`, `.mp3`, `.m4a`, raw subscriber recordings, transcript exports, `.csv` datasets, model checkpoints, or `.env` secrets. Never bypass `.gitignore` with `git add -f`.
- **Encryption at Rest**: All ingested voicemail audio must pass through the Fernet (`AES-128-CBC + HMAC-SHA256`) storage layer before touching disk.
- **Session & CSRF Protection**: Never store session tokens, JWTs, or CSRF tokens in `localStorage` or `sessionStorage`. All state-changing HTTP endpoints require double-submit `X-CSRF-Token` verification and strict role-based access checks.
- **Test-Split Integrity**: Never tune thresholds, prompts, or hyperparameters on the held-out test split. Production test evaluation is gated by `backend/svr_platform/evaluation/once_guard.py`.

## Required Pre-PR Verification Suite

Every pull request targeting `master` must pass the full CI verification suite locally before review:

```bash
# 1. Backend & evaluation harness tests (Python 3.11+)
PYTHONPATH=.:backend pytest backend/tests infra/tests -v

# 2. Dependency vulnerability scan (Python)
pip-audit -r backend/requirements.txt

# 3. Frontend typecheck, production build & security audit (Node.js 22+)
cd frontend
npm ci
npx tsc --noEmit
npm run build
npm audit --audit-level=high
```

## Pull Request Checklist

- Clear summary of architectural purpose and modified components.
- Exact test and build commands executed along with observed outputs.
- Confirmation of RBAC, encryption, audit-log, and data-retention compatibility.
