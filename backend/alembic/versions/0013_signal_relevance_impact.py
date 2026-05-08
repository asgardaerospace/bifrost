"""sprint 4: signal relevance + signal impact tables

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-08

Adds:
  * signal_relevance — per-(signal, mission) relevance score with full
    component breakdown for explainability. Replaces ad-hoc per-call
    scoring with a persisted, decay-aware index.
  * signal_impact — propagation traces. Records how a signal's relevance
    contributed to derived state (mission pressure, executive escalation,
    queue urgency). Auditable + reversible.

intel_items / intel_entities / intel_tags / intel_actions are NOT modified
— signal_type is derived in code from `category` (see services/signals.py)
to avoid a destructive schema change to a populated table.

Additive only.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0013"
down_revision: Union[str, None] = "0012"
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

    op.create_table(
        "signal_relevance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "intel_item_id",
            sa.Integer(),
            sa.ForeignKey("intel_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mission_id",
            sa.Integer(),
            sa.ForeignKey("missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("decayed_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("components", json_type, nullable=False),
        sa.Column(
            "is_relevant",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="score >= RELEVANCE_THRESHOLD; persisted for fast filtering",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        *_ts_cols(),
        sa.UniqueConstraint(
            "intel_item_id", "mission_id", name="uq_signal_relevance_pair"
        ),
    )
    op.create_index(
        "ix_signal_relevance_intel_item_id",
        "signal_relevance",
        ["intel_item_id"],
    )
    op.create_index(
        "ix_signal_relevance_mission_id", "signal_relevance", ["mission_id"]
    )
    op.create_index(
        "ix_signal_relevance_decayed_score",
        "signal_relevance",
        ["decayed_score"],
    )
    op.create_index(
        "ix_signal_relevance_is_relevant", "signal_relevance", ["is_relevant"]
    )

    op.create_table(
        "signal_impact",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "intel_item_id",
            sa.Integer(),
            sa.ForeignKey("intel_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mission_id",
            sa.Integer(),
            sa.ForeignKey("missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "impact_type",
            sa.String(length=64),
            nullable=False,
            comment=(
                "raises_pressure | lowers_pressure | escalation | "
                "opportunity | informational"
            ),
        ),
        sa.Column(
            "contribution",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="signed pressure contribution (negative = relief)",
        ),
        sa.Column("components", json_type, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        *_ts_cols(),
    )
    op.create_index(
        "ix_signal_impact_intel_item_id", "signal_impact", ["intel_item_id"]
    )
    op.create_index(
        "ix_signal_impact_mission_id", "signal_impact", ["mission_id"]
    )
    op.create_index(
        "ix_signal_impact_impact_type", "signal_impact", ["impact_type"]
    )


def downgrade() -> None:
    op.drop_index("ix_signal_impact_impact_type", table_name="signal_impact")
    op.drop_index("ix_signal_impact_mission_id", table_name="signal_impact")
    op.drop_index("ix_signal_impact_intel_item_id", table_name="signal_impact")
    op.drop_table("signal_impact")

    op.drop_index(
        "ix_signal_relevance_is_relevant", table_name="signal_relevance"
    )
    op.drop_index(
        "ix_signal_relevance_decayed_score", table_name="signal_relevance"
    )
    op.drop_index(
        "ix_signal_relevance_mission_id", table_name="signal_relevance"
    )
    op.drop_index(
        "ix_signal_relevance_intel_item_id", table_name="signal_relevance"
    )
    op.drop_table("signal_relevance")
