"""market os foundation: accounts, campaigns, opportunities

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
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
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sector", sa.String(length=128), nullable=True),
        sa.Column("region", sa.String(length=128), nullable=True),
        sa.Column("type", sa.String(length=64), nullable=True),
        sa.Column("website", sa.String(length=512), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_ts_cols(),
    )
    op.create_index("ix_accounts_name", "accounts", ["name"])
    op.create_index("ix_accounts_sector", "accounts", ["sector"])
    op.create_index("ix_accounts_region", "accounts", ["region"])
    op.create_index("ix_accounts_type", "accounts", ["type"])

    op.create_table(
        "account_contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("linkedin", sa.String(length=512), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_ts_cols(),
    )
    op.create_index(
        "ix_account_contacts_account_id", "account_contacts", ["account_id"]
    )
    op.create_index("ix_account_contacts_email", "account_contacts", ["email"])

    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sector", sa.String(length=128), nullable=True),
        sa.Column("region", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_ts_cols(),
    )
    op.create_index("ix_campaigns_name", "campaigns", ["name"])
    op.create_index("ix_campaigns_sector", "campaigns", ["sector"])
    op.create_index("ix_campaigns_region", "campaigns", ["region"])
    op.create_index("ix_campaigns_status", "campaigns", ["status"])

    op.create_table(
        "account_campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            sa.Integer(),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="not_contacted",
        ),
        sa.Column(
            "last_contacted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "next_follow_up_at", sa.DateTime(timezone=True), nullable=True
        ),
        *_ts_cols(),
        sa.UniqueConstraint(
            "account_id", "campaign_id", name="uq_account_campaigns_pair"
        ),
    )
    op.create_index(
        "ix_account_campaigns_account_id", "account_campaigns", ["account_id"]
    )
    op.create_index(
        "ix_account_campaigns_campaign_id", "account_campaigns", ["campaign_id"]
    )
    op.create_index(
        "ix_account_campaigns_status", "account_campaigns", ["status"]
    )
    op.create_index(
        "ix_account_campaigns_next_follow_up_at",
        "account_campaigns",
        ["next_follow_up_at"],
    )

    op.create_table(
        "market_opportunities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "stage",
            sa.String(length=32),
            nullable=False,
            server_default="identified",
        ),
        sa.Column("estimated_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("next_step", sa.Text(), nullable=True),
        sa.Column("next_step_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_ts_cols(),
    )
    op.create_index(
        "ix_market_opportunities_account_id",
        "market_opportunities",
        ["account_id"],
    )
    op.create_index(
        "ix_market_opportunities_stage", "market_opportunities", ["stage"]
    )
    op.create_index(
        "ix_market_opportunities_next_step_due_at",
        "market_opportunities",
        ["next_step_due_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_opportunities_next_step_due_at",
        table_name="market_opportunities",
    )
    op.drop_index(
        "ix_market_opportunities_stage", table_name="market_opportunities"
    )
    op.drop_index(
        "ix_market_opportunities_account_id",
        table_name="market_opportunities",
    )
    op.drop_table("market_opportunities")

    op.drop_index(
        "ix_account_campaigns_next_follow_up_at",
        table_name="account_campaigns",
    )
    op.drop_index(
        "ix_account_campaigns_status", table_name="account_campaigns"
    )
    op.drop_index(
        "ix_account_campaigns_campaign_id", table_name="account_campaigns"
    )
    op.drop_index(
        "ix_account_campaigns_account_id", table_name="account_campaigns"
    )
    op.drop_table("account_campaigns")

    op.drop_index("ix_campaigns_status", table_name="campaigns")
    op.drop_index("ix_campaigns_region", table_name="campaigns")
    op.drop_index("ix_campaigns_sector", table_name="campaigns")
    op.drop_index("ix_campaigns_name", table_name="campaigns")
    op.drop_table("campaigns")

    op.drop_index("ix_account_contacts_email", table_name="account_contacts")
    op.drop_index(
        "ix_account_contacts_account_id", table_name="account_contacts"
    )
    op.drop_table("account_contacts")

    op.drop_index("ix_accounts_type", table_name="accounts")
    op.drop_index("ix_accounts_region", table_name="accounts")
    op.drop_index("ix_accounts_sector", table_name="accounts")
    op.drop_index("ix_accounts_name", table_name="accounts")
    op.drop_table("accounts")
