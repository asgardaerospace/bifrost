"""program os foundation: programs + links

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
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
    op.create_table(
        "programs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "stage",
            sa.String(length=32),
            nullable=False,
            server_default="identified",
        ),
        sa.Column("estimated_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("probability_score", sa.Integer(), nullable=True),
        sa.Column("strategic_value_score", sa.Integer(), nullable=True),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("next_step", sa.Text(), nullable=True),
        sa.Column(
            "next_step_due_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_ts_cols(),
    )
    op.create_index("ix_programs_name", "programs", ["name"])
    op.create_index("ix_programs_account_id", "programs", ["account_id"])
    op.create_index("ix_programs_stage", "programs", ["stage"])
    op.create_index("ix_programs_owner", "programs", ["owner"])
    op.create_index(
        "ix_programs_next_step_due_at", "programs", ["next_step_due_at"]
    )

    op.create_table(
        "program_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "program_id",
            sa.Integer(),
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=32), nullable=False),
        *_ts_cols(),
        sa.UniqueConstraint(
            "program_id", "account_id", name="uq_program_accounts_pair"
        ),
    )
    op.create_index(
        "ix_program_accounts_program_id", "program_accounts", ["program_id"]
    )
    op.create_index(
        "ix_program_accounts_account_id", "program_accounts", ["account_id"]
    )
    op.create_index(
        "ix_program_accounts_role", "program_accounts", ["role"]
    )

    op.create_table(
        "program_investors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "program_id",
            sa.Integer(),
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "investor_id",
            sa.Integer(),
            sa.ForeignKey("investor_firms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relevance_type", sa.String(length=32), nullable=False),
        *_ts_cols(),
        sa.UniqueConstraint(
            "program_id", "investor_id", name="uq_program_investors_pair"
        ),
    )
    op.create_index(
        "ix_program_investors_program_id",
        "program_investors",
        ["program_id"],
    )
    op.create_index(
        "ix_program_investors_investor_id",
        "program_investors",
        ["investor_id"],
    )
    op.create_index(
        "ix_program_investors_relevance_type",
        "program_investors",
        ["relevance_type"],
    )

    op.create_table(
        "program_activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "program_id",
            sa.Integer(),
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("activity_type", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_ts_cols(),
    )
    op.create_index(
        "ix_program_activities_program_id",
        "program_activities",
        ["program_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_program_activities_program_id", table_name="program_activities"
    )
    op.drop_table("program_activities")

    op.drop_index(
        "ix_program_investors_relevance_type",
        table_name="program_investors",
    )
    op.drop_index(
        "ix_program_investors_investor_id", table_name="program_investors"
    )
    op.drop_index(
        "ix_program_investors_program_id", table_name="program_investors"
    )
    op.drop_table("program_investors")

    op.drop_index(
        "ix_program_accounts_role", table_name="program_accounts"
    )
    op.drop_index(
        "ix_program_accounts_account_id", table_name="program_accounts"
    )
    op.drop_index(
        "ix_program_accounts_program_id", table_name="program_accounts"
    )
    op.drop_table("program_accounts")

    op.drop_index("ix_programs_next_step_due_at", table_name="programs")
    op.drop_index("ix_programs_owner", table_name="programs")
    op.drop_index("ix_programs_stage", table_name="programs")
    op.drop_index("ix_programs_account_id", table_name="programs")
    op.drop_index("ix_programs_name", table_name="programs")
    op.drop_table("programs")
