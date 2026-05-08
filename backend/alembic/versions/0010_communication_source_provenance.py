"""patch: communications.source_system + source_external_id

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-08

Schema-drift fix flagged in the Sprint 0 audit: the ORM model
Communication has `source_system` and `source_external_id` columns (used by
the investor_engine integration) but no historical migration created them.
The queue projection introduced in Sprint 0 reads Communication rows for
draft items, which surfaced the missing-column error in Postgres.

Additive only — both columns are nullable.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "communications",
        sa.Column("source_system", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "communications",
        sa.Column("source_external_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_communications_source_system",
        "communications",
        ["source_system"],
    )
    op.create_index(
        "ix_communications_source_external_id",
        "communications",
        ["source_external_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_communications_source_external_id", table_name="communications"
    )
    op.drop_index(
        "ix_communications_source_system", table_name="communications"
    )
    op.drop_column("communications", "source_external_id")
    op.drop_column("communications", "source_system")
