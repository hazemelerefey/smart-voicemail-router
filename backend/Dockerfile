# SVR Production Backend & AI Worker Image (PRD D8, NFR21, NFR22)
# Build context: repository root (.)
FROM python:3.11-slim

ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ARG INSTALL_GPU_EXTRAS=0
ARG APP_UID=10001
ARG APP_GID=10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/app/backend \
    SVR_STORAGE_DIR=/data/storage \
    SVR_MODELS_DIR=/data/models/marbertv2-single-task \
    HF_HOME=/data/cache/huggingface \
    TORCH_HOME=/data/cache/torch \
    FFMPEG_BIN=ffmpeg \
    FFPROBE_BIN=ffprobe

# Install ffmpeg/ffprobe for audio validation/decoding and postgresql-client for backups
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libpq5 \
        postgresql-client \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged runtime user and writable data directories
RUN groupadd --gid "${APP_GID}" svr \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --create-home --shell /bin/bash svr \
    && mkdir -p /app /data/storage/voicemails /data/models /data/cache/huggingface /data/cache/torch /data/backups \
    && chown -R svr:svr /app /data

WORKDIR /app

# Install Python dependencies first for layer caching
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip \
    && pip install --index-url "${TORCH_INDEX_URL}" torch \
    && pip install -r /app/backend/requirements.txt \
    && if [ "${INSTALL_GPU_EXTRAS}" = "1" ]; then pip install "bitsandbytes>=0.45.0" "accelerate>=1.0.0"; fi

# Copy backend application, evaluation harness, and operational utilities
COPY backend /app/backend
COPY infra /app/infra
COPY ops/backup_restore.py /app/ops/backup_restore.py
COPY ops/worker_runner.py /app/ops/worker_runner.py

RUN pip install --no-deps --editable /app/backend \
    && chown -R svr:svr /app /data

USER svr

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["uvicorn", "svr_platform.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
