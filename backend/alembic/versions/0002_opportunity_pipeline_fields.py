"""add pipeline-oriented fields to investor_opportunities

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("investor_opportunities", sa.Column("owner", sa.String(length=255)))
    op.add_column("investor_opportunities", sa.Column("next_step", sa.Text()))
    op.add_column(
        "investor_opportunities",
        sa.Column("next_step_due_at", sa.DateTime(timezone=True)),
    )
    op.add_column("investor_opportunities", sa.Column("fit_score", sa.Integer()))
    op.add_column("investor_opportunities", sa.Column("probability_score", sa.Integer()))
    op.add_column(
        "investor_opportunities", sa.Column("strategic_value_score", sa.Integer())
    )
    op.create_index(
        "ix_investor_opportunities_next_step_due_at",
        "investor_opportunities",
        ["next_step_due_at"],
    )
    op.create_index(
        "ix_investor_opportunities_stage", "investor_opportunities", ["stage"]
    )
    op.create_index(
        "ix_investor_opportunities_status", "investor_opportunities", ["status"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_investor_opportunities_status", table_name="investor_opportunities"
    )
    op.drop_index(
        "ix_investor_opportunities_stage", table_name="investor_opportunities"
    )
    op.drop_index(
        "ix_investor_opportunities_next_step_due_at",
        table_name="investor_opportunities",
    )
    op.drop_column("investor_opportunities", "strategic_value_score")
    op.drop_column("investor_opportunities", "probability_score")
    op.drop_column("investor_opportunities", "fit_score")
    op.drop_column("investor_opportunities", "next_step_due_at")
    op.drop_column("investor_opportunities", "next_step")
    op.drop_column("investor_opportunities", "owner")
