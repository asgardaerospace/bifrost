from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PresenceSession(Base, TimestampMixin):
    """Operator presence session — driven by websocket heartbeats.

    Active = `disconnected_at IS NULL AND last_heartbeat > now - PRESENCE_TTL`.
    Mission focus is optional; bare connection rows still count toward "active
    operators on the platform".
    """

    __tablename__ = "presence_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    mission_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("missions.id", ondelete="SET NULL"), index=True
    )

    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_heartbeat: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    disconnected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
