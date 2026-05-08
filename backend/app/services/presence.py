"""Presence service — operator-focus tracking driven by ws heartbeats."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.presence import PresenceSession


# After this many seconds without a heartbeat, a session is treated as stale.
PRESENCE_TTL_SECONDS = 45


def _now() -> datetime:
    return datetime.now(timezone.utc)


def register_or_refresh(
    db: Session,
    *,
    client_id: str,
    user_id: Optional[int] = None,
    display_name: Optional[str] = None,
    mission_id: Optional[int] = None,
) -> PresenceSession:
    """Idempotent — a re-connect with the same client_id refreshes the row."""
    session = db.scalars(
        select(PresenceSession).where(PresenceSession.client_id == client_id)
    ).first()
    now = _now()
    if session is None:
        session = PresenceSession(
            client_id=client_id,
            user_id=user_id,
            display_name=display_name,
            mission_id=mission_id,
            connected_at=now,
            last_heartbeat=now,
            disconnected_at=None,
        )
        db.add(session)
    else:
        session.last_heartbeat = now
        session.disconnected_at = None
        if mission_id is not None:
            session.mission_id = mission_id
        if display_name is not None:
            session.display_name = display_name
        if user_id is not None:
            session.user_id = user_id
    db.commit()
    db.refresh(session)
    return session


def heartbeat(db: Session, *, client_id: str) -> Optional[PresenceSession]:
    session = db.scalars(
        select(PresenceSession).where(PresenceSession.client_id == client_id)
    ).first()
    if session is None:
        return None
    session.last_heartbeat = _now()
    session.disconnected_at = None
    db.commit()
    db.refresh(session)
    return session


def disconnect(db: Session, *, client_id: str) -> None:
    session = db.scalars(
        select(PresenceSession).where(PresenceSession.client_id == client_id)
    ).first()
    if session is None:
        return
    session.disconnected_at = _now()
    db.commit()


def list_active(
    db: Session, *, mission_id: Optional[int] = None
) -> list[PresenceSession]:
    cutoff = _now() - timedelta(seconds=PRESENCE_TTL_SECONDS)
    stmt = (
        select(PresenceSession)
        .where(PresenceSession.disconnected_at.is_(None))
        .where(PresenceSession.last_heartbeat >= cutoff)
    )
    if mission_id is not None:
        stmt = stmt.where(PresenceSession.mission_id == mission_id)
    stmt = stmt.order_by(PresenceSession.last_heartbeat.desc())
    return list(db.scalars(stmt).all())


def prune_stale(db: Session) -> int:
    """Mark sessions stale (older than PRESENCE_TTL) as disconnected.

    Returns the number of sessions marked. Called periodically; safe to call
    on every presence query (idempotent, cheap).
    """
    cutoff = _now() - timedelta(seconds=PRESENCE_TTL_SECONDS)
    stale = db.scalars(
        select(PresenceSession)
        .where(PresenceSession.disconnected_at.is_(None))
        .where(PresenceSession.last_heartbeat < cutoff)
    ).all()
    for s in stale:
        s.disconnected_at = _now()
    if stale:
        db.commit()
    return len(stale)
