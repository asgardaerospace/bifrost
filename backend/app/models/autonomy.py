from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AutonomyOperation(Base, TimestampMixin):
    """Records every autonomous agent operation: proposal, decision, execution.

    Per AUTONOMY_GOVERNANCE doctrine: every autonomous operation must remain
    visible, auditable, explainable, reversible. This is the ledger.
    """

    __tablename__ = "autonomy_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    operation_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mission_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("missions.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="proposed", index=True
    )
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reasoning: Mapped[Optional[str]] = mapped_column(Text)
    retrieval_citations: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)

    # Sprint 6 — provenance for the workflow run.
    trigger: Mapped[Optional[str]] = mapped_column(String(128))
    workflow_key: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)

    proposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    decided_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    actions: Mapped[list["ProposedAction"]] = relationship(
        back_populates="operation", cascade="all, delete-orphan"
    )


class ProposedAction(Base, TimestampMixin):
    __tablename__ = "proposed_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    autonomy_operation_id: Mapped[int] = mapped_column(
        ForeignKey("autonomy_operations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_entity_type: Mapped[Optional[str]] = mapped_column(String(64))
    target_entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    operation: Mapped["AutonomyOperation"] = relationship(back_populates="actions")
