"""Horizontally scalable SVR AI pipeline worker runner (PRD NFR9, Section 11.2).

Consumes queued ticket IDs atomically from Redis (BLMOVE 'svr:pipeline:queue' -> 'svr:pipeline:inflight')
and executes the full WF1 pipeline (STT -> VoiceGate -> MARBERTv2 x4 -> priority -> route -> brief).
Publishes real-time stage updates over Redis Pub/Sub for WebSocket QueueHub fan-out, and falls back
to polling received/processing tickets in the database if Redis is not configured.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from typing import Any

from sqlalchemy import select

from svr_platform.config import get_settings
from svr_platform.crypto import EncryptionService
from svr_platform.database import DatabaseManager
from svr_platform.models import Ticket
from svr_platform.services.classification import MARBERTv2ClassifierService
from svr_platform.services.factories import (
    build_adjudicator,
    build_memory_service,
    build_stt_service,
    build_transcript_gate,
)
from svr_platform.services.pipeline import run_voicemail_pipeline
from svr_platform.taxonomy import TicketStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [svr-worker] %(message)s",
)
logger = logging.getLogger("svr.worker")

QUEUE_KEY = os.environ.get("SVR_REDIS_QUEUE_KEY", "svr:pipeline:queue")
INFLIGHT_KEY = os.environ.get("SVR_REDIS_INFLIGHT_KEY", "svr:pipeline:inflight")
EVENTS_CHANNEL = os.environ.get("SVR_REDIS_EVENTS_CHANNEL", "svr:pipeline:events")
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

        client = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=10.0)
        client.ping()
        logger.info("Connected to Redis queue at %s", QUEUE_KEY)
        return client
    except Exception as exc:
        logger.warning("Redis connection failed (%s); falling back to database polling.", exc)
        return None


def reap_inflight_queue(redis_client: Any, queue_key: str, inflight_key: str) -> int:
    """Re-queue any orphaned tickets left in inflight_key from an unexpected worker crash."""
    requeued = 0
    if redis_client is None:
        return 0
    while True:
        item = redis_client.rpoplpush(inflight_key, queue_key)
        if not item:
            break
        requeued += 1
    if requeued:
        logger.warning("Reaped %d orphaned ticket(s) from %s back to %s.", requeued, inflight_key, queue_key)
    return requeued


def pop_next_ticket_id(
    redis_client: Any,
    queue_key: str,
    inflight_key: str,
    timeout_s: int,
) -> str | None:
    """Atomically move next ticket ID from queue_key into inflight_key."""
    item = redis_client.blmove(queue_key, inflight_key, timeout=max(1, int(timeout_s)), src="LEFT", dest="RIGHT")
    return str(item) if item else None


def ack_inflight_ticket(redis_client: Any, inflight_key: str, ticket_id: str) -> None:
    """Remove completed ticket ID from inflight_key."""
    if redis_client is None or not ticket_id:
        return
    try:
        redis_client.lrem(inflight_key, 1, ticket_id)
    except Exception as exc:
        logger.warning("Failed to ack inflight ticket %s: %s", ticket_id, exc)


def publish_ticket_event(redis_client: Any, channel: str, payload: dict[str, Any]) -> None:
    """Publish pipeline stage or completion events to Redis Pub/Sub for WebSocket fan-out."""
    if redis_client is None:
        return
    try:
        redis_client.publish(channel, json.dumps(payload, ensure_ascii=False))
    except Exception as exc:
        logger.warning("Failed publishing ticket event to %s: %s", channel, exc)


def main() -> int:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    settings = get_settings()
    queue_key = settings.redis_queue_key or QUEUE_KEY
    inflight_key = settings.redis_inflight_key or INFLIGHT_KEY
    events_channel = settings.redis_events_channel or EVENTS_CHANNEL

    db_mgr = DatabaseManager(settings.database_url)
    db_mgr.create_all()

    crypto = EncryptionService(settings.svr_encryption_key)
    stt_service = build_stt_service(settings)
    transcript_gate = build_transcript_gate(settings)
    memory_service = build_memory_service(settings)
    adjudicator = build_adjudicator(settings, memory_service)
    classifier_service = MARBERTv2ClassifierService(
        models_dir=settings.svr_models_dir,
        repo_root=settings.repo_root,
        base_model_id=settings.marbert_base_model,
        seed=settings.marbert_checkpoint_seed,
        max_resident_onnx_heads=settings.onnx_max_resident_heads,
    )
    redis_client = _connect_redis(settings.redis_url)
    if redis_client is not None:
        reap_inflight_queue(redis_client, queue_key, inflight_key)

    logger.info(
        "SVR AI worker started (stt=%s/%s, gate=%s, local_checkpoints=%s).",
        stt_service.canonical_model_name,
        stt_service.device,
        transcript_gate.canonical_model_name,
        classifier_service.has_local_checkpoints(),
    )

    while not _SHUTDOWN:
        ticket_id: str | None = None
        if redis_client is not None:
            try:
                ticket_id = pop_next_ticket_id(
                    redis_client,
                    queue_key,
                    inflight_key,
                    int(max(1, POLL_INTERVAL_S)),
                )
            except Exception as exc:
                logger.warning("Redis BLMOVE failed (%s); retrying after backoff.", exc)
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
                    transcript_gate=transcript_gate,
                    classifier_service=classifier_service,
                    adjudicator=adjudicator,
                    memory_service=memory_service,
                    on_update=lambda evt: publish_ticket_event(redis_client, events_channel, evt),
                    adaptive_reaudit_enabled=settings.adaptive_reaudit_enabled,
                    adaptive_reaudit_category_threshold=settings.adaptive_reaudit_category_threshold,
                    allow_transcript_edits=settings.transcript_edit_enabled,
                )
                logger.info("Processed ticket %s", ticket_id)
            except Exception as exc:
                logger.exception("Worker failed processing ticket %s: %s", ticket_id, exc)
            finally:
                if redis_client is not None:
                    ack_inflight_ticket(redis_client, inflight_key, ticket_id)

    classifier_service.unload()
    logger.info("SVR AI worker stopped cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
