from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Communication(Base, TimestampMixin):
    __tablename__ = "communications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")

    subject: Mapped[Optional[str]] = mapped_column(String(512))
    body: Mapped[Optional[str]] = mapped_column(Text)

    from_address: Mapped[Optional[str]] = mapped_column(String(320))
    to_address: Mapped[Optional[str]] = mapped_column(String(320))

    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Source provenance for drafts originated outside Bifrost's native
    # investor tables (e.g. the investor_engine integration). These are
    # optional: native Bifrost drafts leave both fields null.
    source_system: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    source_external_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
