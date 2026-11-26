#!/usr/bin/env bash
set -euo pipefail

# Smart Voicemail Router (SVR) - One-Command Production Server Bootstrap
# Target: Ubuntu/Debian/Oracle Linux host (e.g., Oracle Cloud Always Free Ampere ARM 4 OCPU / 24 GB RAM)

COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"

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
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PASS}|" .env 2>/dev/null || echo "POSTGRES_PASSWORD=${PG_PASS}" >> .env
  echo "POSTGRES_PASSWORD=${PG_PASS}" >> .env
  sed -i "s|^SVR_COOKIE_SECURE=.*|SVR_COOKIE_SECURE=true|" .env
  sed -i "s|^SVR_LOW_MEMORY_MODE=.*|SVR_LOW_MEMORY_MODE=0|" .env
  echo "Created .env. Please review SVR_DOMAIN, SVR_CORS_ORIGINS, and SVR_BOOTSTRAP_PASSWORD before exposing publicly."
fi

if [ ! -d "models/marbertv2-single-task/seed_99" ]; then
  echo "WARNING: models/marbertv2-single-task/seed_99 not found."
  echo "Copy your exported seed_99 ONNX INT8 checkpoints before starting:"
  echo "  scp -r models/marbertv2-single-task/seed_99 user@host:$(pwd)/models/marbertv2-single-task/"
  exit 1
fi

echo "Building and starting SVR production stack..."
docker compose ${COMPOSE_FILES} up -d --build --remove-orphans

echo "Pulling qwen2.5:3b into local Ollama container..."
docker compose ${COMPOSE_FILES} exec -T ollama ollama pull "${QWEN_MODEL_ID:-qwen2.5:3b}"

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
