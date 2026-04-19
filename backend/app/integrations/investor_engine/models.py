"""Storage models for the investor engine snapshot cache.

A dedicated table keeps engine-owned data isolated from Bifrost's own
investor tables. This is what makes the integration read-only and
non-destructive: Bifrost's core `investor_firms` / `investor_contacts`
/ `investor_opportunities` are never rewritten by sync.
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class InvestorEngineSnapshot(Base, TimestampMixin):
    __tablename__ = "investor_engine_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    firm_name: Mapped[str] = mapped_column(String(255), index=True)

    # Normalized execution surface — the subset Bifrost renders.
    stage: Mapped[Optional[str]] = mapped_column(String(64))
    follow_up_status: Mapped[Optional[str]] = mapped_column(String(64))
    last_touch_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_follow_up_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    next_step: Mapped[Optional[str]] = mapped_column(String(1024))
    owner: Mapped[Optional[str]] = mapped_column(String(255))

    # Full normalized record — kept as JSON so schema drift upstream
    # does not require a migration.
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Provenance
    engine_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
