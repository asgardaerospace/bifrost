"""Realtime pub/sub manager — websocket connection registry + Redis fanout.

Sprint 2: in-memory by default (single-process dev / smoke tests). When the
`REDIS_URL` env var is set and the `redis` package is installed, publish goes
through Redis pub/sub so multi-worker / multi-instance deployments share the
event stream.

Topology:

    events.publish(db, ev)
       ↓ persist row
       ↓ pubsub.publish(topic, payload)
       ↓ if Redis configured: PUBLISH bifrost:<topic>
       ↓                      a per-process subscriber forwards to local sockets
       ↓ else:                fan to local sockets directly
       ↓
    WebSocket clients filter by (topic, mission_id?) and receive JSON frames

Wire format from server → client (subset):

    {"type":"event","topic":"missions","event_type":"mission.updated",
     "mission_id":1,"entity_type":"mission","entity_id":1,"payload":{...},
     "severity":"info","occurred_at":"...","actor":"..."}
    {"type":"presence","mission_id":1,"operators":[...]}
    {"type":"pong","ts":"..."}
    {"type":"hello","client_id":"..."}
    {"type":"subscribed","topic":"missions","mission_id":1}
    {"type":"error","detail":"..."}

Wire format from client → server:

    {"action":"subscribe","topic":"missions"}
    {"action":"subscribe","topic":"missions","mission_id":1}
    {"action":"unsubscribe","topic":"missions","mission_id":1}
    {"action":"presence","mission_id":1,"display_name":"Operator","client_id":"uuid"}
    {"action":"heartbeat"}
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Set, Tuple

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Subscription = (topic, mission_id_or_None). mission_id=None means "all
# missions for this topic" (or no mission scoping where N/A).
Subscription = Tuple[str, Optional[int]]


@dataclass
class WSConnection:
    ws: WebSocket
    client_id: str
    subscriptions: Set[Subscription] = field(default_factory=set)


class PubSubManager:
    """In-process pub/sub registry + websocket fanout.

    Thread/loop-affinity: all methods are async and assume they're called
    from the running event loop; the FastAPI websocket route is async, and
    `events.publish` is called from sync DB code via a small bridge
    (`broadcast_sync`) that schedules onto the loop.
    """

    def __init__(self) -> None:
        self._connections: dict[str, WSConnection] = {}
        self._lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # Redis hooks (optional). Populated by attach_redis() at app startup.
        self._redis = None
        self._redis_pubsub_task: Optional[asyncio.Task] = None

    # -- lifecycle ------------------------------------------------------

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Capture the running loop so sync callers can schedule broadcasts."""
        self._loop = loop

    async def connect(self, ws: WebSocket, client_id: str) -> WSConnection:
        await ws.accept()
        conn = WSConnection(ws=ws, client_id=client_id)
        async with self._lock:
            # Replace any prior connection for this client_id.
            existing = self._connections.get(client_id)
            if existing is not None:
                try:
                    await existing.ws.close()
                except Exception:
                    pass
            self._connections[client_id] = conn
        await self._send(conn, {"type": "hello", "client_id": client_id})
        return conn

    async def disconnect(self, client_id: str) -> None:
        async with self._lock:
            self._connections.pop(client_id, None)

    async def subscribe(
        self, client_id: str, topic: str, mission_id: Optional[int] = None
    ) -> None:
        async with self._lock:
            conn = self._connections.get(client_id)
            if conn is None:
                return
            conn.subscriptions.add((topic, mission_id))
        await self._send(
            self._connections[client_id],
            {"type": "subscribed", "topic": topic, "mission_id": mission_id},
        )

    async def unsubscribe(
        self, client_id: str, topic: str, mission_id: Optional[int] = None
    ) -> None:
        async with self._lock:
            conn = self._connections.get(client_id)
            if conn is None:
                return
            conn.subscriptions.discard((topic, mission_id))

    # -- broadcast ------------------------------------------------------

    async def broadcast(
        self, topic: str, mission_id: Optional[int], message: dict[str, Any]
    ) -> None:
        """Local fan-out. Redis fanout is layered above this in publish()."""
        async with self._lock:
            conns = list(self._connections.values())

        for conn in conns:
            if not _matches(conn.subscriptions, topic, mission_id):
                continue
            await self._send(conn, message)

    async def publish(
        self, topic: str, mission_id: Optional[int], message: dict[str, Any]
    ) -> None:
        """Topic-scoped publish. Goes to Redis if attached, else local fanout.

        When Redis is attached, the local subscriber will receive the message
        back and call broadcast(); we don't double-fan locally to avoid
        duplicate delivery.
        """
        if self._redis is not None:
            try:
                channel = f"bifrost:{topic}"
                await self._redis.publish(
                    channel,
                    json.dumps(
                        {"topic": topic, "mission_id": mission_id, "message": message}
                    ),
                )
                return
            except Exception:
                logger.exception("redis publish failed; falling back to local fanout")
        await self.broadcast(topic, mission_id, message)

    def publish_sync(
        self, topic: str, mission_id: Optional[int], message: dict[str, Any]
    ) -> None:
        """Bridge for sync callers (events.publish runs in sync DB code).

        Schedules the async publish onto the captured event loop. Silently
        no-ops if no loop is bound (e.g. during smoke tests with sync-only
        TestClient calls and no live websocket layer).
        """
        loop = self._loop
        if loop is None or not loop.is_running():
            return
        # Coroutine scheduling from a non-loop thread.
        try:
            asyncio.run_coroutine_threadsafe(
                self.publish(topic, mission_id, message), loop
            )
        except Exception:
            logger.exception("publish_sync scheduling failed")

    # -- redis (optional) ----------------------------------------------

    async def attach_redis(self, url: str) -> bool:
        try:
            import redis.asyncio as redis_async  # type: ignore[import-not-found]
        except Exception:
            logger.warning("REDIS_URL set but redis package not installed — staying in-memory")
            return False
        try:
            self._redis = redis_async.from_url(url, decode_responses=True)
            await self._redis.ping()
        except Exception:
            logger.exception("redis connection failed; staying in-memory")
            self._redis = None
            return False

        # Subscribe to every topic on the bifrost: prefix and forward to local.
        async def _subscriber():
            assert self._redis is not None
            try:
                ps = self._redis.pubsub()
                await ps.psubscribe("bifrost:*")
                async for msg in ps.listen():
                    if msg.get("type") != "pmessage":
                        continue
                    try:
                        data = json.loads(msg["data"])
                        await self.broadcast(
                            data["topic"], data.get("mission_id"), data["message"]
                        )
                    except Exception:
                        logger.exception("malformed redis message dropped")
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("redis subscriber crashed")

        self._redis_pubsub_task = asyncio.create_task(_subscriber())
        logger.info("pubsub: redis fanout attached at %s", url)
        return True

    async def detach_redis(self) -> None:
        if self._redis_pubsub_task is not None:
            self._redis_pubsub_task.cancel()
            try:
                await self._redis_pubsub_task
            except Exception:
                pass
            self._redis_pubsub_task = None
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None

    # -- inspection -----------------------------------------------------

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    def list_subscribers(self, topic: str, mission_id: Optional[int] = None) -> int:
        return sum(
            1
            for c in self._connections.values()
            if _matches(c.subscriptions, topic, mission_id)
        )

    # -- internals ------------------------------------------------------

    async def _send(self, conn: WSConnection, message: dict[str, Any]) -> None:
        # Bounded send timeout — a slow consumer must not block fanout.
        try:
            await asyncio.wait_for(conn.ws.send_json(message), timeout=5.0)
        except (asyncio.TimeoutError, Exception):
            # Drop the connection on send failure or timeout — caller will
            # re-establish on its own backoff.
            try:
                await conn.ws.close(code=1011)
            except Exception:
                pass
            await self.disconnect(conn.client_id)


def _matches(
    subs: Set[Subscription], topic: str, mission_id: Optional[int]
) -> bool:
    """A subscription matches if its topic equals the message topic AND its
    mission_id filter is either None (catch-all) or equals the message
    mission_id."""
    for t, m in subs:
        if t != topic:
            continue
        if m is None or m == mission_id:
            return True
    return False


# Module-level singleton — the pubsub registry is per-process.
manager = PubSubManager()


def get_redis_url() -> Optional[str]:
    return os.environ.get("REDIS_URL") or None
