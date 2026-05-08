"""sprint 5: recommendations table

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-08

Adds the canonical recommendations table — grounded operational
recommendations with rationale, citations (in components JSONB), confidence,
and explicit decision lifecycle (pending → accepted | dismissed | expired).

Doctrine: AI may recommend. AI may not execute. Every recommendation row is
auditable — rationale, sources, confidence, affected mission, target entity,
and the operator's decision are all persisted and visible.

Additive only.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0014"
down_revision: Union[str, None] = "0013"
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
        "recommendations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recommendation_type",
            sa.String(length=64),
            nullable=False,
            comment=(
                "queue_reprioritize | escalate | mitigate_supplier_risk | "
                "coordinate_mission | route_approval | executive_attention | "
                "operational_followup | escalate_intelligence"
            ),
        ),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "mission_id",
            sa.Integer(),
            sa.ForeignKey("missions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("target_entity_type", sa.String(length=64), nullable=True),
        sa.Column("target_entity_id", sa.Integer(), nullable=True),
        sa.Column(
            "projected_impact",
            sa.String(length=64),
            nullable=True,
            comment="raises_pressure | lowers_pressure | unblocks | informational",
        ),
        sa.Column("projected_delta", sa.Integer(), nullable=True),
        sa.Column("components", json_type, nullable=False),
        sa.Column("citations", json_type, nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="engine"),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("decided_by", sa.String(length=255), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *_ts_cols(),
    )
    op.create_index(
        "ix_recommendations_recommendation_type",
        "recommendations",
        ["recommendation_type"],
    )
    op.create_index("ix_recommendations_mission_id", "recommendations", ["mission_id"])
    op.create_index("ix_recommendations_status", "recommendations", ["status"])
    op.create_index(
        "ix_recommendations_target",
        "recommendations",
        ["target_entity_type", "target_entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_recommendations_target", table_name="recommendations")
    op.drop_index("ix_recommendations_status", table_name="recommendations")
    op.drop_index("ix_recommendations_mission_id", table_name="recommendations")
    op.drop_index(
        "ix_recommendations_recommendation_type", table_name="recommendations"
    )
    op.drop_table("recommendations")
