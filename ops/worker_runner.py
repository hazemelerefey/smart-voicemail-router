"""Horizontally scalable SVR AI pipeline worker runner (PRD NFR9, Section 11.2).

Consumes queued ticket IDs from Redis (BLPOP on 'svr:pipeline:queue') and executes
the full WF1 pipeline (Whisper large-v3 STT -> MARBERTv2 x4 -> priority -> route -> brief).
Falls back to polling received tickets in the database if Redis is not configured.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time

from sqlalchemy import select

from svr_platform.config import get_settings
from svr_platform.crypto import EncryptionService
from svr_platform.database import DatabaseManager
from svr_platform.models import Ticket
from svr_platform.services.classification import MARBERTv2ClassifierService
from svr_platform.services.pipeline import run_voicemail_pipeline
from svr_platform.services.stt import WhisperSTTService
from svr_platform.taxonomy import TicketStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [svr-worker] %(message)s",
)
logger = logging.getLogger("svr.worker")

QUEUE_KEY = os.environ.get("SVR_REDIS_QUEUE_KEY", "svr:pipeline:queue")
POLL_INTERVAL_S = float(os.environ.get("SVR_WORKER_POLL_SECONDS", "2.0"))

_SHUTDOWN = False


def _handle_signal(signum: int, _frame: object) -> None:
    global _SHUTDOWN
    logger.info("Received signal %s; draining worker loop.", signum)
    _SHUTDOWN = True


def _connect_redis(redis_url: str):
    if not redis_url:
        return None
    try:
        import redis

        client = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=5.0)
        client.ping()
        logger.info("Connected to Redis queue at %s", QUEUE_KEY)
        return client
    except Exception as exc:
        logger.warning("Redis connection failed (%s); falling back to database polling.", exc)
        return None


def main() -> int:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    settings = get_settings()
    db_mgr = DatabaseManager(settings.database_url)
    db_mgr.create_all()

    crypto = EncryptionService(settings.svr_encryption_key)
    stt_service = WhisperSTTService(
        model_id=settings.whisper_model_id,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
        ffmpeg_bin=settings.ffmpeg_bin,
    )
    classifier_service = MARBERTv2ClassifierService(
        models_dir=settings.svr_models_dir,
        repo_root=settings.repo_root,
        base_model_id=settings.marbert_base_model,
        seed=settings.marbert_checkpoint_seed,
    )
    redis_client = _connect_redis(settings.redis_url)

    logger.info(
        "SVR AI worker started (whisper=%s/%s, local_checkpoints=%s).",
        settings.whisper_model_id,
        settings.whisper_device,
        classifier_service.has_local_checkpoints(),
    )

    while not _SHUTDOWN:
        ticket_id: str | None = None
        if redis_client is not None:
            try:
                item = redis_client.blpop(QUEUE_KEY, timeout=int(max(1, POLL_INTERVAL_S)))
                if item is not None:
                    ticket_id = str(item[1])
            except Exception as exc:
                logger.warning("Redis BLPOP failed (%s); retrying after backoff.", exc)
                time.sleep(POLL_INTERVAL_S)
                continue
        else:
            with db_mgr.session_factory() as db:
                pending = db.scalar(
                    select(Ticket)
                    .where(Ticket.status == TicketStatus.RECEIVED.value)
                    .order_by(Ticket.created_at.asc())
                    .limit(1)
                )
                if pending is not None:
                    ticket_id = pending.id
            if ticket_id is None:
                time.sleep(POLL_INTERVAL_S)
                continue

        if not ticket_id:
            continue

        with db_mgr.session_factory() as db:
            try:
                run_voicemail_pipeline(
                    db,
                    ticket_id=ticket_id,
                    crypto=crypto,
                    stt_service=stt_service,
                    classifier_service=classifier_service,
                )
                logger.info("Processed ticket %s", ticket_id)
            except Exception as exc:
                logger.exception("Worker failed processing ticket %s: %s", ticket_id, exc)

    logger.info("SVR AI worker stopped cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
