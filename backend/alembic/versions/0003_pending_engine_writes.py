"""pending_engine_writes outbox for investor engine mutations

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pending_engine_writes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "attempt_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "idempotency_key", sa.String(length=128), nullable=False
        ),
        sa.Column(
            "engine_updated_at_snapshot",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("approval_id", sa.Integer(), nullable=True),
        sa.Column("requested_by", sa.String(length=255), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("idempotency_key", name="uq_pending_engine_writes_idem"),
    )
    op.create_index(
        "ix_pending_engine_writes_external_id",
        "pending_engine_writes",
        ["external_id"],
    )
    op.create_index(
        "ix_pending_engine_writes_action_type",
        "pending_engine_writes",
        ["action_type"],
    )
    op.create_index(
        "ix_pending_engine_writes_status",
        "pending_engine_writes",
        ["status"],
    )
    op.create_index(
        "ix_pending_engine_writes_approval_id",
        "pending_engine_writes",
        ["approval_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pending_engine_writes_approval_id", table_name="pending_engine_writes"
    )
    op.drop_index(
        "ix_pending_engine_writes_status", table_name="pending_engine_writes"
    )
    op.drop_index(
        "ix_pending_engine_writes_action_type", table_name="pending_engine_writes"
    )
    op.drop_index(
        "ix_pending_engine_writes_external_id", table_name="pending_engine_writes"
    )
    op.drop_table("pending_engine_writes")
