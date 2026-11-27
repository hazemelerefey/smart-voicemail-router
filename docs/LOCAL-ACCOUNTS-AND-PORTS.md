# Local Accounts, Passwords & Non-Default Port Guide

This document lists the seeded operator accounts, default bootstrap credentials, and non-default localhost ports for running **Smart Voicemail Router (SVR)** alongside other projects that occupy ports `3000`/`8000` or `3001`/`8001`.

---

## 1. Seeded Platform Accounts

All 5 accounts are created idempotently by `seed_initial_data` in [backend/svr_platform/seed.py](../backend/svr_platform/seed.py) for the default `Egypt Telecom Care` organization.

| Email | Role | Display Name | Linked Specialist / Scope | Capabilities |
| --- | --- | --- | --- | --- |
| `admin@telecom.local` | `admin` | Telecom Operations Admin | Organization-wide | Full access: system settings, kill-switch, agent & skill routing management, audit export, ticket corrections, monitoring, agent memory stats & training export |
| `supervisor@telecom.local` | `supervisor` | Queue Care Supervisor | Organization-wide | Operations Overview KPIs, Human Routing Queue, label corrections (feeds VoiceGate Reflexion memory), ticket reassignment, monitoring, memory stats & training export |
| `network.agent@telecom.local` | `agent` | Network Care Specialist | Skill `Network` (`network_and_connectivity`, `no_reply_or_long_wait`, `sim_services`) | Scoped `/my-tickets` callback queue, voicemail audio playback, status transitions (`in_progress` / `resolved`) for own assigned tickets |
| `billing.agent@telecom.local` | `agent` | Billing & Bundles Specialist | Skill `Billing` (`billing_and_charges`, `balance_and_data`, `offers_and_packages`) | Scoped `/my-tickets` callback queue, voicemail audio playback, status transitions (`in_progress` / `resolved`) for own assigned tickets |
| `general.agent@telecom.local` | `agent` | Subscriber Care Specialist | Skill `General` (`app_and_account`, `branch_and_staff`, `cancellation_request`, `thanks_or_praise`, `other`) | Scoped `/my-tickets` callback queue, voicemail audio playback, status transitions (`in_progress` / `resolved`) for own assigned tickets |

### Bootstrap Password

- **Local Development Password (all 5 accounts):** `SvrTelecom2026!`
- **Configuration Variable:** `SVR_BOOTSTRAP_PASSWORD` in `.env` (default in `.env.example` and `Settings`).
- **Security Note:** Change `SVR_BOOTSTRAP_PASSWORD` immediately before any staging or production deployment (`backend/svr_platform/config.py` blocks default bootstrap passwords when `SVR_ENV=production`).

---

## 2. Non-Default Localhost Ports (Avoids 3000 / 8000 Collisions)

When another project uses `3000` / `8000` (or `3001` / `8001`), run SVR on:

- **Frontend Web App (Vite Preview / Dev):** `http://127.0.0.1:4175` (also reachable at `http://localhost:4175`)
- **Backend FastAPI API:** `http://127.0.0.1:8085`
- **Swagger / OpenAPI Docs:** `http://127.0.0.1:8085/docs`
- **Health Check:** `http://127.0.0.1:8085/api/health` (and proxied via frontend at `http://127.0.0.1:4175/api/health`)
- **VoiceGate Memory & Self-Training Stats (Supervisor/Admin):** `http://127.0.0.1:8085/api/agent/memory/stats`
- **Self-Training Dataset Export (JSONL / CSV):** `http://127.0.0.1:8085/api/agent/memory/training-export?format=jsonl`

Make sure `.env` includes `:4175` in `SVR_CORS_ORIGINS`:

```ini
SVR_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:4175,http://127.0.0.1:4175
```

---

## 3. Startup Commands on Alternate Ports (`8085` & `4175`)

### Terminal 1: Backend API (`127.0.0.1:8085`)

**Windows PowerShell:**

```powershell
$env:PYTHONPATH = ".;backend"
$env:HF_HOME = (Join-Path $PWD ".cache\huggingface")
$env:TORCH_HOME = (Join-Path $PWD ".cache\torch")
$env:PYTHONUNBUFFERED = "1"
.venv\Scripts\python.exe -m uvicorn svr_platform.api.main:app --host 127.0.0.1 --port 8085
```

**Linux / macOS:**

```bash
PYTHONPATH=.:backend HF_HOME=./.cache/huggingface TORCH_HOME=./.cache/torch \
  uvicorn svr_platform.api.main:app --host 127.0.0.1 --port 8085
```

### Terminal 2: Frontend App (`127.0.0.1:4175`)

Note: Build once (`npm run build`) and serve with `vite preview` so the strict `script-src 'self'` CSP in `frontend/vite.config.ts` works without dev inline HMR scripts.

**Windows PowerShell:**

```powershell
Set-Location frontend
$env:SVR_API_UPSTREAM = "http://127.0.0.1:8085"
npm.cmd run build
npm.cmd run preview -- --host 127.0.0.1 --port 4175 --strictPort
```

**Linux / macOS:**

```bash
cd frontend
SVR_API_UPSTREAM=http://127.0.0.1:8085 npm run build
SVR_API_UPSTREAM=http://127.0.0.1:8085 npm run preview -- --host 127.0.0.1 --port 4175 --strictPort
```
