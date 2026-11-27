#!/usr/bin/env bash
set -euo pipefail

# Smart Voicemail Router (SVR) - One-Command Production Server Bootstrap
# Target: Linux CPU host (Oracle Cloud ARM 24 GB) or 6 GB GPU host (RTX 3050 6 GB + 16 GB RAM with --gpu-6gb)

GPU_6GB=0
for arg in "$@"; do
  case "$arg" in
    --gpu-6gb) GPU_6GB=1 ;;
    *) echo "Unknown option: $arg (supported: --gpu-6gb)"; exit 1 ;;
  esac
done

COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
LLM_MODEL="${QWEN_MODEL_ID:-qwen2.5:3b}"
if [ "$GPU_6GB" -eq 1 ]; then
  COMPOSE_FILES="${COMPOSE_FILES} -f docker-compose.gpu-6gb.yml"
  LLM_MODEL="${QWEN_MODEL_ID:-qwen2.5:3b}"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed. Install Docker Engine first:"
  echo "  curl -fsSL https://get.docker.com | sh"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose v2 plugin is not available."
  exit 1
fi

if [ ! -f ".env" ]; then
  echo "Creating .env from .env.example with generated production secrets..."
  cp .env.example .env
  SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  FERNET_KEY="$(python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
  PG_PASS="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"
  sed -i "s|^SVR_ENV=.*|SVR_ENV=production|" .env
  sed -i "s|^SVR_SECRET_KEY=.*|SVR_SECRET_KEY=${SECRET_KEY}|" .env
  sed -i "s|^SVR_ENCRYPTION_KEY=.*|SVR_ENCRYPTION_KEY=${FERNET_KEY}|" .env
  if grep -q '^POSTGRES_PASSWORD=' .env; then
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PASS}|" .env
  else
    echo "POSTGRES_PASSWORD=${PG_PASS}" >> .env
  fi
  sed -i "s|^SVR_COOKIE_SECURE=.*|SVR_COOKIE_SECURE=true|" .env
  sed -i "s|^SVR_LOW_MEMORY_MODE=.*|SVR_LOW_MEMORY_MODE=0|" .env
  echo "Created .env. Please review SVR_DOMAIN, SVR_CORS_ORIGINS, and SVR_BOOTSTRAP_PASSWORD before exposing publicly."
fi

if [ ! -d "models/marbertv2-single-task/seed_99" ]; then
  echo "WARNING: models/marbertv2-single-task/seed_99 not found."
  echo "Download seed_99 automatically from Google Drive (https://drive.google.com/drive/folders/1wZPNugbk9Mxkl-zG1pLnP_nac9QWY_tG):"
  echo "  pip install gdown && python3 ops/download_models.py"
  exit 1
fi

if [ "$GPU_6GB" -eq 1 ]; then
  echo "6 GB GPU profile selected: using Cohere Arabic INT8 (NAMAA-Space/cohere-transcribe-arabic-07-2026-int8) + ${LLM_MODEL}."
  echo "Ensure Cohere INT8 weights are cached first via: python3 ops/download_models.py --with-cohere-int8"
  echo "To roll back to Whisper if needed, set SVR_STT_BACKEND=faster_whisper."
fi

echo "Building and starting SVR production stack (${COMPOSE_FILES})..."
docker compose ${COMPOSE_FILES} up -d --build --remove-orphans

echo "Pulling ${LLM_MODEL} into local Ollama container..."
docker compose ${COMPOSE_FILES} exec -T ollama ollama pull "${LLM_MODEL}"

echo "Waiting for backend healthcheck..."
for i in $(seq 1 24); do
  if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    echo "SVR stack is LIVE:"
    curl -fsS http://127.0.0.1:8000/api/health
    echo ""
    exit 0
  fi
  sleep 5
done

echo "ERROR: Backend did not become healthy in 120s. Check: docker compose ${COMPOSE_FILES} logs backend"
exit 1
