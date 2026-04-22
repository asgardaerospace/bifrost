"""intelligence os foundation

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
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
        "intel_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("region", sa.String(length=64), nullable=True),
        sa.Column(
            "category",
            sa.String(length=64),
            nullable=False,
            server_default="uncategorized",
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "strategic_relevance_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "urgency_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "confidence_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        *_ts_cols(),
        sa.UniqueConstraint("source", "url", name="uq_intel_items_source_url"),
    )
    op.create_index("ix_intel_items_source", "intel_items", ["source"])
    op.create_index(
        "ix_intel_items_published_at", "intel_items", ["published_at"]
    )
    op.create_index("ix_intel_items_region", "intel_items", ["region"])
    op.create_index("ix_intel_items_category", "intel_items", ["category"])
    op.create_index(
        "ix_intel_items_strategic_relevance_score",
        "intel_items",
        ["strategic_relevance_score"],
    )

    op.create_table(
        "intel_entities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "intel_item_id",
            sa.Integer(),
            sa.ForeignKey("intel_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_name", sa.String(length=255), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_intel_entities_intel_item_id", "intel_entities", ["intel_item_id"]
    )
    op.create_index(
        "ix_intel_entities_entity_type", "intel_entities", ["entity_type"]
    )
    op.create_index(
        "ix_intel_entities_entity_name", "intel_entities", ["entity_name"]
    )

    op.create_table(
        "intel_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "intel_item_id",
            sa.Integer(),
            sa.ForeignKey("intel_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tag", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("intel_item_id", "tag", name="uq_intel_tags_pair"),
    )
    op.create_index("ix_intel_tags_intel_item_id", "intel_tags", ["intel_item_id"])
    op.create_index("ix_intel_tags_tag", "intel_tags", ["tag"])

    op.create_table(
        "intel_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "intel_item_id",
            sa.Integer(),
            sa.ForeignKey("intel_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        *_ts_cols(),
    )
    op.create_index(
        "ix_intel_actions_intel_item_id", "intel_actions", ["intel_item_id"]
    )
    op.create_index(
        "ix_intel_actions_action_type", "intel_actions", ["action_type"]
    )
    op.create_index("ix_intel_actions_status", "intel_actions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_intel_actions_status", table_name="intel_actions")
    op.drop_index("ix_intel_actions_action_type", table_name="intel_actions")
    op.drop_index("ix_intel_actions_intel_item_id", table_name="intel_actions")
    op.drop_table("intel_actions")

    op.drop_index("ix_intel_tags_tag", table_name="intel_tags")
    op.drop_index("ix_intel_tags_intel_item_id", table_name="intel_tags")
    op.drop_table("intel_tags")

    op.drop_index("ix_intel_entities_entity_name", table_name="intel_entities")
    op.drop_index("ix_intel_entities_entity_type", table_name="intel_entities")
    op.drop_index(
        "ix_intel_entities_intel_item_id", table_name="intel_entities"
    )
    op.drop_table("intel_entities")

    op.drop_index(
        "ix_intel_items_strategic_relevance_score", table_name="intel_items"
    )
    op.drop_index("ix_intel_items_category", table_name="intel_items")
    op.drop_index("ix_intel_items_region", table_name="intel_items")
    op.drop_index("ix_intel_items_published_at", table_name="intel_items")
    op.drop_index("ix_intel_items_source", table_name="intel_items")
    op.drop_table("intel_items")
