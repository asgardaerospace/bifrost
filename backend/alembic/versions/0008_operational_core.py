"""operational core: missions, queue, events, relationships, autonomy, users

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-07

Sprint 0 — additive only. Adds the canonical operational substrate per the
Bifrost doctrine (mission service, execution queue, operational events,
relationships graph, autonomy ledger, users). Adds nullable mission_id FKs to
existing CRM/domain tables. Creates a SQL VIEW `intelligence_signals` aliasing
`intel_items` for forward compatibility (no rename yet).

Nothing existing is altered destructively. All adds are nullable.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: Union[str, None] = "0007"
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


# Tables that get a nullable mission_id FK in this migration.
_MISSION_FK_TABLES = (
    "investor_opportunities",
    "market_opportunities",
    "programs",
    "tasks",
    "approvals",
    "communications",
    "intel_items",
)


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("primary_role", sa.String(length=64), nullable=False, server_default="operator"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_ts_cols(),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # user_roles
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=128), nullable=True),
        *_ts_cols(),
        sa.UniqueConstraint("user_id", "role", "scope", name="uq_user_roles_triple"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_role", "user_roles", ["role"])

    # missions
    op.create_table(
        "missions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codename", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("mission_type", sa.String(length=64), nullable=False, server_default="strategic"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="planning"),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="normal"),
        sa.Column("pressure_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("health_status", sa.String(length=32), nullable=False, server_default="nominal"),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "parent_mission_id",
            sa.Integer(),
            sa.ForeignKey("missions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("target_completion_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_ts_cols(),
        sa.UniqueConstraint("codename", name="uq_missions_codename"),
    )
    op.create_index("ix_missions_codename", "missions", ["codename"])
    op.create_index("ix_missions_status", "missions", ["status"])
    op.create_index("ix_missions_priority", "missions", ["priority"])
    op.create_index("ix_missions_mission_type", "missions", ["mission_type"])
    op.create_index("ix_missions_health_status", "missions", ["health_status"])
    op.create_index("ix_missions_owner_user_id", "missions", ["owner_user_id"])
    op.create_index("ix_missions_parent_mission_id", "missions", ["parent_mission_id"])

    # mission_entities
    op.create_table(
        "mission_entities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "mission_id",
            sa.Integer(),
            sa.ForeignKey("missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column(
            "relationship_type",
            sa.String(length=32),
            nullable=False,
            server_default="linked",
        ),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "mission_id",
            "entity_type",
            "entity_id",
            "relationship_type",
            name="uq_mission_entities_quad",
        ),
    )
    op.create_index("ix_mission_entities_mission_id", "mission_entities", ["mission_id"])
    op.create_index("ix_mission_entities_entity_type", "mission_entities", ["entity_type"])
    op.create_index("ix_mission_entities_entity_id", "mission_entities", ["entity_id"])

    # relationships
    op.create_table(
        "relationships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("relationship_type", sa.String(length=32), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("meta", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_ts_cols(),
        sa.UniqueConstraint(
            "source_type",
            "source_id",
            "target_type",
            "target_id",
            "relationship_type",
            name="uq_relationships_edge",
        ),
    )
    op.create_index(
        "ix_relationships_source", "relationships", ["source_type", "source_id"]
    )
    op.create_index(
        "ix_relationships_target", "relationships", ["target_type", "target_id"]
    )
    op.create_index(
        "ix_relationships_relationship_type", "relationships", ["relationship_type"]
    )

    # operational_events
    op.create_table(
        "operational_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("topic", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column(
            "mission_id",
            sa.Integer(),
            sa.ForeignKey("missions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("actor", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column(
            "severity",
            sa.String(length=16),
            nullable=False,
            server_default="info",
        ),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_operational_events_topic", "operational_events", ["topic"])
    op.create_index(
        "ix_operational_events_event_type", "operational_events", ["event_type"]
    )
    op.create_index(
        "ix_operational_events_mission_id", "operational_events", ["mission_id"]
    )
    op.create_index(
        "ix_operational_events_entity_type", "operational_events", ["entity_type"]
    )
    op.create_index(
        "ix_operational_events_created_at", "operational_events", ["created_at"]
    )

    # execution_queue_items
    op.create_table(
        "execution_queue_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_type", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column(
            "mission_id",
            sa.Integer(),
            sa.ForeignKey("missions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("priority_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pressure_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_ts_cols(),
    )
    op.create_index(
        "ix_execution_queue_items_item_type", "execution_queue_items", ["item_type"]
    )
    op.create_index(
        "ix_execution_queue_items_source_type", "execution_queue_items", ["source_type"]
    )
    op.create_index(
        "ix_execution_queue_items_mission_id", "execution_queue_items", ["mission_id"]
    )
    op.create_index(
        "ix_execution_queue_items_status", "execution_queue_items", ["status"]
    )
    op.create_index(
        "ix_execution_queue_items_priority_score",
        "execution_queue_items",
        ["priority_score"],
    )
    op.create_index(
        "ix_execution_queue_items_due_at", "execution_queue_items", ["due_at"]
    )

    # autonomy_operations
    op.create_table(
        "autonomy_operations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_name", sa.String(length=128), nullable=False),
        sa.Column("operation_type", sa.String(length=64), nullable=False),
        sa.Column(
            "mission_id",
            sa.Integer(),
            sa.ForeignKey("missions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="proposed",
        ),
        sa.Column("confidence_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column(
            "retrieval_citations", sa.dialects.postgresql.JSONB(), nullable=True
        ),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column(
            "proposed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "decided_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        *_ts_cols(),
    )
    op.create_index(
        "ix_autonomy_operations_agent_name", "autonomy_operations", ["agent_name"]
    )
    op.create_index(
        "ix_autonomy_operations_operation_type",
        "autonomy_operations",
        ["operation_type"],
    )
    op.create_index(
        "ix_autonomy_operations_mission_id", "autonomy_operations", ["mission_id"]
    )
    op.create_index(
        "ix_autonomy_operations_status", "autonomy_operations", ["status"]
    )

    # proposed_actions
    op.create_table(
        "proposed_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "autonomy_operation_id",
            sa.Integer(),
            sa.ForeignKey("autonomy_operations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("target_entity_type", sa.String(length=64), nullable=True),
        sa.Column("target_entity_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="pending"
        ),
        sa.Column(
            "requires_approval",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        *_ts_cols(),
    )
    op.create_index(
        "ix_proposed_actions_autonomy_operation_id",
        "proposed_actions",
        ["autonomy_operation_id"],
    )
    op.create_index(
        "ix_proposed_actions_action_type", "proposed_actions", ["action_type"]
    )
    op.create_index(
        "ix_proposed_actions_status", "proposed_actions", ["status"]
    )

    # Add nullable mission_id to existing CRM tables.
    for table in _MISSION_FK_TABLES:
        op.add_column(
            table,
            sa.Column("mission_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            f"fk_{table}_mission_id",
            table,
            "missions",
            ["mission_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(f"ix_{table}_mission_id", table, ["mission_id"])

    # Compatibility VIEW: intelligence_signals → intel_items
    # Allows new doctrine-aligned reads without renaming the underlying table.
    op.execute(
        "CREATE OR REPLACE VIEW intelligence_signals AS SELECT * FROM intel_items"
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS intelligence_signals")

    for table in _MISSION_FK_TABLES:
        op.drop_index(f"ix_{table}_mission_id", table_name=table)
        op.drop_constraint(f"fk_{table}_mission_id", table, type_="foreignkey")
        op.drop_column(table, "mission_id")

    op.drop_index("ix_proposed_actions_status", table_name="proposed_actions")
    op.drop_index("ix_proposed_actions_action_type", table_name="proposed_actions")
    op.drop_index(
        "ix_proposed_actions_autonomy_operation_id", table_name="proposed_actions"
    )
    op.drop_table("proposed_actions")

    op.drop_index("ix_autonomy_operations_status", table_name="autonomy_operations")
    op.drop_index(
        "ix_autonomy_operations_mission_id", table_name="autonomy_operations"
    )
    op.drop_index(
        "ix_autonomy_operations_operation_type", table_name="autonomy_operations"
    )
    op.drop_index(
        "ix_autonomy_operations_agent_name", table_name="autonomy_operations"
    )
    op.drop_table("autonomy_operations")

    op.drop_index(
        "ix_execution_queue_items_due_at", table_name="execution_queue_items"
    )
    op.drop_index(
        "ix_execution_queue_items_priority_score", table_name="execution_queue_items"
    )
    op.drop_index(
        "ix_execution_queue_items_status", table_name="execution_queue_items"
    )
    op.drop_index(
        "ix_execution_queue_items_mission_id", table_name="execution_queue_items"
    )
    op.drop_index(
        "ix_execution_queue_items_source_type", table_name="execution_queue_items"
    )
    op.drop_index(
        "ix_execution_queue_items_item_type", table_name="execution_queue_items"
    )
    op.drop_table("execution_queue_items")

    op.drop_index(
        "ix_operational_events_created_at", table_name="operational_events"
    )
    op.drop_index(
        "ix_operational_events_entity_type", table_name="operational_events"
    )
    op.drop_index(
        "ix_operational_events_mission_id", table_name="operational_events"
    )
    op.drop_index(
        "ix_operational_events_event_type", table_name="operational_events"
    )
    op.drop_index("ix_operational_events_topic", table_name="operational_events")
    op.drop_table("operational_events")

    op.drop_index(
        "ix_relationships_relationship_type", table_name="relationships"
    )
    op.drop_index("ix_relationships_target", table_name="relationships")
    op.drop_index("ix_relationships_source", table_name="relationships")
    op.drop_table("relationships")

    op.drop_index(
        "ix_mission_entities_entity_id", table_name="mission_entities"
    )
    op.drop_index(
        "ix_mission_entities_entity_type", table_name="mission_entities"
    )
    op.drop_index(
        "ix_mission_entities_mission_id", table_name="mission_entities"
    )
    op.drop_table("mission_entities")

    op.drop_index("ix_missions_parent_mission_id", table_name="missions")
    op.drop_index("ix_missions_owner_user_id", table_name="missions")
    op.drop_index("ix_missions_health_status", table_name="missions")
    op.drop_index("ix_missions_mission_type", table_name="missions")
    op.drop_index("ix_missions_priority", table_name="missions")
    op.drop_index("ix_missions_status", table_name="missions")
    op.drop_index("ix_missions_codename", table_name="missions")
    op.drop_table("missions")

    op.drop_index("ix_user_roles_role", table_name="user_roles")
    op.drop_index("ix_user_roles_user_id", table_name="user_roles")
    op.drop_table("user_roles")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
