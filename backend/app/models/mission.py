from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Mission(Base, TimestampMixin):
    __tablename__ = "missions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codename: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    mission_type: Mapped[str] = mapped_column(String(64), nullable=False, default="strategic", index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planning", index=True)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal", index=True)
    pressure_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    health_status: Mapped[str] = mapped_column(String(32), nullable=False, default="nominal", index=True)

    owner_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    parent_mission_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("missions.id", ondelete="SET NULL"), index=True
    )

    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    target_completion_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    entities: Mapped[List["MissionEntity"]] = relationship(
        back_populates="mission", cascade="all, delete-orphan"
    )


class MissionEntity(Base):
    __tablename__ = "mission_entities"
    __table_args__ = (
        UniqueConstraint(
            "mission_id",
            "entity_type",
            "entity_id",
            "relationship_type",
            name="uq_mission_entities_quad",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mission_id: Mapped[int] = mapped_column(
        ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False, default="linked")
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    mission: Mapped["Mission"] = relationship(back_populates="entities")
