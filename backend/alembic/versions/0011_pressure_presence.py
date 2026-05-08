"""sprint 2: pressure snapshots + presence sessions

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-08

Adds:
  * mission_pressure_snapshots — historical pressure scoring with full
    component breakdown for explainability (PRESSURE_ENGINE doctrine).
  * presence_sessions — short-lived operator presence rows; pruned by
    heartbeat age. Carries mission_id so we can answer "who is viewing X".

Additive only.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011"
down_revision: Union[str, None] = "0010"
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
        "mission_pressure_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "mission_id",
            sa.Integer(),
            sa.ForeignKey("missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column(
            "health_status", sa.String(length=32), nullable=False, server_default="nominal"
        ),
        sa.Column("components", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("blockers_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overdue_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "pending_approvals_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "unresolved_dependencies_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "high_priority_intel_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "activity_volume", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "escalation_flags_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="trigger"),
        sa.Column("trigger_event_id", sa.Integer(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_mission_pressure_snapshots_mission_id",
        "mission_pressure_snapshots",
        ["mission_id"],
    )
    op.create_index(
        "ix_mission_pressure_snapshots_computed_at",
        "mission_pressure_snapshots",
        ["computed_at"],
    )
    op.create_index(
        "ix_mission_pressure_snapshots_mission_at",
        "mission_pressure_snapshots",
        ["mission_id", "computed_at"],
    )

    op.create_table(
        "presence_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column(
            "mission_id",
            sa.Integer(),
            sa.ForeignKey("missions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_heartbeat",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        *_ts_cols(),
    )
    op.create_index(
        "ix_presence_sessions_client_id", "presence_sessions", ["client_id"]
    )
    op.create_index(
        "ix_presence_sessions_user_id", "presence_sessions", ["user_id"]
    )
    op.create_index(
        "ix_presence_sessions_mission_id", "presence_sessions", ["mission_id"]
    )
    op.create_index(
        "ix_presence_sessions_last_heartbeat",
        "presence_sessions",
        ["last_heartbeat"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_presence_sessions_last_heartbeat", table_name="presence_sessions"
    )
    op.drop_index(
        "ix_presence_sessions_mission_id", table_name="presence_sessions"
    )
    op.drop_index(
        "ix_presence_sessions_user_id", table_name="presence_sessions"
    )
    op.drop_index(
        "ix_presence_sessions_client_id", table_name="presence_sessions"
    )
    op.drop_table("presence_sessions")

    op.drop_index(
        "ix_mission_pressure_snapshots_mission_at",
        table_name="mission_pressure_snapshots",
    )
    op.drop_index(
        "ix_mission_pressure_snapshots_computed_at",
        table_name="mission_pressure_snapshots",
    )
    op.drop_index(
        "ix_mission_pressure_snapshots_mission_id",
        table_name="mission_pressure_snapshots",
    )
    op.drop_table("mission_pressure_snapshots")
