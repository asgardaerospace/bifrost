"""sprint 6: agent workflow stages — per-stage trace for autonomy operations

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-08

Sprint 6 reuses the existing `autonomy_operations` table as the canonical
agent-run row (per Sprint 0 doctrine — every autonomous operation is
visible, auditable, explainable, reversible). This migration adds:

  * agent_workflow_stages — per-stage trace for one agent run. Each row
    captures stage_index, stage_name, status, input/output payloads, the
    retrieval trace, the confidence emitted by the stage, and any error.
    Operators can replay the full DAG to inspect why an agent proposed
    something.

Adds two columns to autonomy_operations for completeness:
  * trigger (text)            — what kicked off this run
  * workflow_key (string(64)) — stable identifier of the workflow definition

Both nullable, both additive.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ts_cols() -> list:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    json_type = sa.dialects.postgresql.JSONB() if is_postgres else sa.JSON()

    op.add_column(
        "autonomy_operations",
        sa.Column("trigger", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "autonomy_operations",
        sa.Column("workflow_key", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_autonomy_operations_workflow_key",
        "autonomy_operations",
        ["workflow_key"],
    )

    op.create_table(
        "agent_workflow_stages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "autonomy_operation_id",
            sa.Integer(),
            sa.ForeignKey("autonomy_operations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage_index", sa.Integer(), nullable=False),
        sa.Column("stage_name", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="running",
            comment="running | completed | failed | skipped | cancelled",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_payload", json_type, nullable=True),
        sa.Column("output_payload", json_type, nullable=True),
        sa.Column("retrieval_trace", json_type, nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        *_ts_cols(),
        sa.UniqueConstraint(
            "autonomy_operation_id",
            "stage_index",
            name="uq_agent_workflow_stages_run_idx",
        ),
    )
    op.create_index(
        "ix_agent_workflow_stages_op_id",
        "agent_workflow_stages",
        ["autonomy_operation_id"],
    )
    op.create_index(
        "ix_agent_workflow_stages_status",
        "agent_workflow_stages",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_workflow_stages_status", table_name="agent_workflow_stages"
    )
    op.drop_index(
        "ix_agent_workflow_stages_op_id", table_name="agent_workflow_stages"
    )
    op.drop_table("agent_workflow_stages")

    op.drop_index(
        "ix_autonomy_operations_workflow_key", table_name="autonomy_operations"
    )
    op.drop_column("autonomy_operations", "workflow_key")
    op.drop_column("autonomy_operations", "trigger")
