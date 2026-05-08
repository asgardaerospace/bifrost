"""auth + governance: password_hash, queue.requires_approval

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-08

Sprint 1 — additive only. Adds:
  * users.password_hash (nullable) — JWT login uses passlib bcrypt; nullable so
    existing dev users can be granted dev tokens without a password set.
  * execution_queue_items.requires_approval (boolean, default false) — gates
    direct status→completed transitions; the governance service creates an
    Approval row (entity_type='execution_queue_item') when this is true, and
    the queue PATCH route refuses completion until that approval is granted.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "execution_queue_items",
        sa.Column(
            "requires_approval",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index(
        "ix_execution_queue_items_requires_approval",
        "execution_queue_items",
        ["requires_approval"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_execution_queue_items_requires_approval",
        table_name="execution_queue_items",
    )
    op.drop_column("execution_queue_items", "requires_approval")
    op.drop_column("users", "password_hash")
