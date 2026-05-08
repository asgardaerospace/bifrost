"""WebSocket endpoint — topic-scoped subscriptions, presence, heartbeats.

Sprint 2: connects to the in-process PubSubManager. Redis fanout is layered
on at app startup if `REDIS_URL` is configured.

Auth: anonymous when `auth_enforcement_enabled=False` (default). When on, a
`?token=<jwt>` query param is required.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.user import User
from app.services import presence as presence_service
from app.services.pubsub import manager

logger = logging.getLogger(__name__)
router = APIRouter()


def _user_from_token(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    sub = payload.get("sub")
    try:
        return {"id": int(sub), "email": payload.get("email"), "role": payload.get("role")}
    except (TypeError, ValueError):
        return None


def _resolve_display_name(user_payload: Optional[dict]) -> Optional[str]:
    if not user_payload:
        return None
    db: Session = SessionLocal()
    try:
        u = db.scalars(select(User).where(User.id == user_payload["id"])).first()
        return u.name or u.email if u else user_payload.get("email")
    finally:
        db.close()


@router.websocket("/ws")
async def ws_endpoint(
    websocket: WebSocket,
    token: Optional[str] = None,
    client_id: Optional[str] = None,
) -> None:
    settings = get_settings()
    user_payload = _user_from_token(token)
    if settings.auth_enforcement_enabled and user_payload is None:
        await websocket.close(code=4401)
        return

    cid = client_id or str(uuid.uuid4())
    conn = await manager.connect(websocket, cid)

    # Best-effort presence registration on connect (no mission focus yet).
    user_id = user_payload["id"] if user_payload else None
    display_name = _resolve_display_name(user_payload) if user_payload else None
    db = SessionLocal()
    try:
        presence_service.register_or_refresh(
            db,
            client_id=cid,
            user_id=user_id,
            display_name=display_name,
            mission_id=None,
        )
    except Exception:
        logger.exception("presence registration failed")
    finally:
        db.close()

    try:
        while True:
            msg = await websocket.receive_json()
            await _handle(cid, msg, user_id=user_id, display_name=display_name)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("ws handler crashed for client %s", cid)
    finally:
        await manager.disconnect(cid)
        db = SessionLocal()
        try:
            presence_service.disconnect(db, client_id=cid)
        finally:
            db.close()


async def _handle(
    client_id: str,
    msg: dict,
    *,
    user_id: Optional[int],
    display_name: Optional[str],
) -> None:
    action = (msg or {}).get("action")
    topic = msg.get("topic")
    mission_id = msg.get("mission_id")
    if action == "subscribe" and topic:
        await manager.subscribe(client_id, topic, mission_id)
        return
    if action == "unsubscribe" and topic:
        await manager.unsubscribe(client_id, topic, mission_id)
        return
    if action == "presence":
        # Update mission focus + display name. Done in a thread to avoid
        # blocking the loop with sync DB work.
        mid = msg.get("mission_id")
        name = msg.get("display_name") or display_name
        await asyncio.to_thread(
            _refresh_presence_sync, client_id, user_id, name, mid
        )
        # Broadcast a presence change to the mission channel so other ops see it.
        if mid is not None:
            await manager.broadcast(
                "presence",
                mid,
                {
                    "type": "presence_changed",
                    "topic": "presence",
                    "mission_id": mid,
                    "client_id": client_id,
                },
            )
        return
    if action == "heartbeat":
        await asyncio.to_thread(_heartbeat_sync, client_id)
        # Echo a pong frame so the client can reconcile timing.
        try:
            from datetime import datetime, timezone

            conn = manager._connections.get(client_id)
            if conn is not None:
                await conn.ws.send_json(
                    {"type": "pong", "ts": datetime.now(timezone.utc).isoformat()}
                )
        except Exception:
            pass
        return
    # Unknown — quietly ignore (compatible with future client versions).


def _refresh_presence_sync(
    client_id: str,
    user_id: Optional[int],
    display_name: Optional[str],
    mission_id: Optional[int],
) -> None:
    db = SessionLocal()
    try:
        presence_service.register_or_refresh(
            db,
            client_id=client_id,
            user_id=user_id,
            display_name=display_name,
            mission_id=mission_id,
        )
    finally:
        db.close()


def _heartbeat_sync(client_id: str) -> None:
    db = SessionLocal()
    try:
        presence_service.heartbeat(db, client_id=client_id)
    finally:
        db.close()
