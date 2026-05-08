"""Agent workflow stage trace.

Doctrine: every autonomous operation is visible, auditable, explainable,
reversible. The Sprint 0 `autonomy_operations` table records the run; this
table records the per-stage DAG trace so an operator can replay every
retrieval, every synthesis, every proposed action.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AgentWorkflowStage(Base, TimestampMixin):
    __tablename__ = "agent_workflow_stages"
    __table_args__ = (
        UniqueConstraint(
            "autonomy_operation_id",
            "stage_index",
            name="uq_agent_workflow_stages_run_idx",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    autonomy_operation_id: Mapped[int] = mapped_column(
        ForeignKey("autonomy_operations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage_index: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="running", index=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    input_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    output_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    retrieval_trace: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    confidence: Mapped[Optional[int]] = mapped_column(Integer)
    error: Mapped[Optional[str]] = mapped_column(Text)
