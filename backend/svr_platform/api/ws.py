"""Authenticated organization-scoped WebSocket hub for real-time queue updates (FR3, NFR18)."""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("svr_platform.ws")


@dataclass(eq=False)
class QueueConnection:
    websocket: WebSocket
    organization_id: str
    user_id: str
    role: str
    linked_agent_id: str | None = None


class QueueHub:
    """Thread-safe org-scoped WebSocket broadcaster with dead-socket cleanup and agent scoping."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connections: dict[str, set[QueueConnection]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        with self._lock:
            self._loop = loop

    async def connect(
        self,
        websocket: WebSocket,
        *,
        organization_id: str,
        user_id: str,
        role: str,
        linked_agent_id: str | None,
        snapshot: dict[str, Any],
    ) -> QueueConnection:
        await websocket.accept()
        try:
            running_loop = asyncio.get_running_loop()
            self.set_loop(running_loop)
        except RuntimeError as exc:
            logger.debug("No running event loop captured on WS connect: %s", exc)

        conn = QueueConnection(
            websocket=websocket,
            organization_id=organization_id,
            user_id=user_id,
            role=role,
            linked_agent_id=linked_agent_id,
        )
        with self._lock:
            self._connections.setdefault(organization_id, set()).add(conn)

        try:
            await websocket.send_json({"type": "queue_snapshot", **snapshot})
        except Exception as exc:
            logger.warning("Failed sending initial queue_snapshot to user %s: %s", user_id, exc)
            self.disconnect(conn)
            raise
        return conn

    def disconnect(self, conn: QueueConnection) -> None:
        with self._lock:
            org_conns = self._connections.get(conn.organization_id)
            if org_conns is not None:
                org_conns.discard(conn)
                if not org_conns:
                    self._connections.pop(conn.organization_id, None)

    def active_count(self, organization_id: str | None = None) -> int:
        with self._lock:
            if organization_id is not None:
                return len(self._connections.get(organization_id, set()))
            return sum(len(conns) for conns in self._connections.values())

    @staticmethod
    def _is_visible_to(conn: QueueConnection, event: dict[str, Any]) -> bool:
        if conn.role != "agent":
            return True
        evt_type = event.get("type", "")
        if evt_type == "settings_updated":
            return True
        if not conn.linked_agent_id:
            return False
        assigned_id = event.get("assigned_agent_id")
        previous_id = event.get("previous_agent_id")
        return assigned_id == conn.linked_agent_id or previous_id == conn.linked_agent_id

    async def broadcast(self, organization_id: str, event: dict[str, Any]) -> int:
        with self._lock:
            targets = list(self._connections.get(organization_id, set()))

        if not targets:
            return 0

        dead: list[QueueConnection] = []
        sent = 0
        for conn in targets:
            if not self._is_visible_to(conn, event):
                continue
            try:
                await conn.websocket.send_json(event)
                sent += 1
            except Exception as exc:
                logger.info(
                    "Removing dead WebSocket connection for user=%s org=%s (%s)",
                    conn.user_id,
                    organization_id,
                    exc,
                )
                dead.append(conn)

        for conn in dead:
            self.disconnect(conn)
        return sent

    def broadcast_threadsafe(self, organization_id: str, event: dict[str, Any]) -> None:
        """Schedule an org-scoped broadcast from a synchronous background worker thread."""
        with self._lock:
            loop = self._loop
            has_targets = bool(self._connections.get(organization_id))

        if not has_targets or loop is None or loop.is_closed():
            return

        try:
            future = asyncio.run_coroutine_threadsafe(
                self.broadcast(organization_id, event),
                loop,
            )

            def _log_future_error(done_fut) -> None:
                try:
                    done_fut.result()
                except Exception as exc:
                    logger.warning("Async WebSocket broadcast failed: %s", exc)

            future.add_done_callback(_log_future_error)
        except Exception as exc:
            logger.warning("Failed to schedule WebSocket broadcast on event loop: %s", exc)
