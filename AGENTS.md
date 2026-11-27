# AGENTS.md - Autonomous Setup & Deployment Playbook

This file is for any AI coding agent opening the **Smart Voicemail Router (SVR)** repository on a new machine right after `git clone`. Follow these steps in order without guessing.

- **Active Production Branch:** `hazem/svr-production-build`
- **Architecture & Deployment Spec:** [docs/ARCHITECTURE-AND-DEPLOYMENT.md](docs/ARCHITECTURE-AND-DEPLOYMENT.md)
- **Dataset & Governance Rules:** [docs/AI_AGENT_GUIDE.md](docs/AI_AGENT_GUIDE.md)

---

## Step 1: Detect Hardware & Prerequisites

Run these checks first to choose the right profile:

```bash
nvidia-smi || echo "NO_GPU"
free -h || wmic OS get FreePhysicalMemory,TotalVisibleMemorySize
docker --version && docker compose version || echo "NO_DOCKER"
ffmpeg -version | head -n 1
```

---

## Step 2: Download & Prepare Model Artifacts (Not Tracked in Git)

1. **MARBERTv2 (`seed_99` only, required for all deployments):**
   - Verified Google Drive sources:
     - **Production `seed_99` (direct folder):** `https://drive.google.com/drive/folders/1wZPNugbk9Mxkl-zG1pLnP_nac9QWY_tG`
     - **All 5 seeds + `MANIFEST.json`:** `https://drive.google.com/drive/folders/1HarYxoqG-YWW-IR5n-PkEWBV-gV4I6Rv`
     - **Handoff & `SHA256_MANIFEST.csv`:** `https://drive.google.com/drive/folders/1UbB6vuA4u1IEiWQFwb3ySynAE0kEwEWw`
   - Run the automated downloader + ONNX INT8 exporter (`~105 ms` CPU triage, `0 GB` VRAM):
     ```bash
     pip install gdown onnx onnxscript onnxruntime
     python ops/download_models.py
     ```
2. **Cohere Arabic ASR (`cohere_gpu_int8`, recommended for 6 GB NVIDIA GPUs like RTX 3050):**
   - Uses pre-quantized `NAMAA-Space/cohere-transcribe-arabic-07-2026-int8` (`~2.7-3.2 GB` VRAM, Apache 2.0 base `CohereLabs/cohere-transcribe-arabic-07-2026`) with bundled offline `silero-vad` and `<=30s` VAD chunking. Optional `Whisper` Egyptian CT2 builder (`--with-egyptian-whisper`) remains supported for fallback.
     ```bash
     pip install gdown onnx onnxscript onnxruntime torch transformers accelerate bitsandbytes silero-vad
     python ops/download_models.py --with-cohere-int8
     ```

---

## Step 3: Launch by Hardware Profile

### Profile A: RTX 3050 (6 GB VRAM) + 16 GB RAM (Docker + NVIDIA Container Toolkit)

Uses `docker-compose.yml` + `docker-compose.prod.yml` + `docker-compose.gpu-6gb.yml`:
- **STT:** Cohere Arabic INT8 (`NAMAA-Space/cohere-transcribe-arabic-07-2026-int8`, `~2.7-3.2 GB` VRAM) -> unloads after transcription (`SVR_STT_BACKEND=faster_whisper` fallback)
- **VoiceGate:** Ollama `qwen2.5:3b` (`Q4_K_M`, `~2.1 GB` VRAM, `num_ctx=1536`) -> unloads via `keep_alive=0` (`aya-expanse:8b` opt-in on >=8 GB VRAM)
- **Classification:** 4x MARBERTv2 ONNX INT8 on CPU (`SVR_MARBERT_BACKEND=onnx`, `SVR_ONNX_MAX_RESIDENT_HEADS=2`, `0 GB` VRAM, `~0.85 GB` RSS)

```bash
bash ops/deploy_server.sh --gpu-6gb
```

### Profile B: CPU-Only Server (16-24 GB RAM, e.g. Oracle Cloud Always Free Ampere ARM)

Uses `docker-compose.yml` + `docker-compose.prod.yml` with `SVR_LOW_MEMORY_MODE=0`, Ollama `qwen2.5:3b`, `Whisper large-v3` (`int8`), and 4x MARBERTv2 ONNX INT8:

```bash
bash ops/deploy_server.sh
```

### Profile C: Local Standalone Development (No Docker)

```bash
# 1. Python backend environment
python -m venv .venv
# Linux/macOS: source .venv/bin/activate | Windows: .\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
pip install --no-deps -e backend
cp .env.example .env

# 2. Local Ollama (loopback-only)
ollama serve &
ollama pull qwen2.5:3b   # or aya-expanse:8b on 6 GB GPU

# 3. Start API (set WHISPER_DEVICE=cuda WHISPER_COMPUTE_TYPE=int8_float16 SVR_MARBERT_BACKEND=onnx on 6 GB GPU)
PYTHONPATH=.:backend uvicorn svr_platform.api.main:app --host 127.0.0.1 --port 8000

# 4. Start Frontend (in another terminal)
cd frontend && npm ci && npm run dev
```

---

## Step 4: Post-Deploy Verification

Run these checks after startup:

```bash
# 1. Health endpoint
curl -fsS http://127.0.0.1:8000/api/health

# 2. Automated test suite
PYTHONPATH=.:backend pytest backend/tests infra/tests -q

# 3. Frontend build check
cd frontend && npm run build
```

For an end-to-end voicemail smoke test, sign in at `http://localhost:3000` (`supervisor@telecom.local` / password from `SVR_BOOTSTRAP_PASSWORD` in `.env`) and upload `dataset/val/calm_0011.wav`.

---

## Non-Negotiable Guardrails

1. **Zero em dashes (`\u2014`) or en dashes (`\u2013`)** in source, config, or docs, and **zero empty `except: pass` blocks** in Python (enforced by `.github/workflows/ci.yml`).
2. **Never touch `final/clean_training_test.csv` or `dataset/test/`** during setup, benchmarking, or smoke tests.
3. **Never switch Whisper to `distil-large-v3`** (English-only) and **never re-add `initial_prompt`** to `WhisperSTTService` (causes prompt echoing on quiet audio); always pass `language="ar"` and use offline `silero-vad` with `CohereArabicSTTService`.
4. **Keep `SVR_MARBERT_BACKEND=onnx`, `SVR_ONNX_MAX_RESIDENT_HEADS=2`, and `SVR_LOW_MEMORY_MODE=1` on 6 GB GPUs / 16 GB RAM** so STT + VoiceGate + ONNX never collide in VRAM or host RAM.
5. **Local-first LLM boundary:** Never configure external/cloud LLM endpoints; `OLLAMA_URL` must stay loopback (`127.0.0.1`) or internal Docker (`http://ollama:11434` with `SVR_ALLOW_DOCKER_OLLAMA=1`).
