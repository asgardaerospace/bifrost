"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
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
        "investor_firms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("website", sa.String(length=512)),
        sa.Column("stage_focus", sa.String(length=128)),
        sa.Column("location", sa.String(length=255)),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="active"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_ts_cols(),
    )
    op.create_index("ix_investor_firms_name", "investor_firms", ["name"])

    op.create_table(
        "investor_contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("firm_id", sa.Integer(), sa.ForeignKey("investor_firms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255)),
        sa.Column("email", sa.String(length=320)),
        sa.Column("phone", sa.String(length=64)),
        sa.Column("linkedin_url", sa.String(length=512)),
        sa.Column("notes", sa.Text()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_ts_cols(),
    )
    op.create_index("ix_investor_contacts_firm_id", "investor_contacts", ["firm_id"])
    op.create_index("ix_investor_contacts_email", "investor_contacts", ["email"])

    op.create_table(
        "investor_opportunities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("firm_id", sa.Integer(), sa.ForeignKey("investor_firms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("primary_contact_id", sa.Integer(), sa.ForeignKey("investor_contacts.id", ondelete="SET NULL")),
        sa.Column("stage", sa.String(length=64), nullable=False, server_default="prospect"),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="open"),
        sa.Column("amount", sa.Numeric(18, 2)),
        sa.Column("target_close_date", sa.Date()),
        sa.Column("summary", sa.Text()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_ts_cols(),
    )
    op.create_index("ix_investor_opportunities_firm_id", "investor_opportunities", ["firm_id"])

    op.create_table(
        "communications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("subject", sa.String(length=512)),
        sa.Column("body", sa.Text()),
        sa.Column("from_address", sa.String(length=320)),
        sa.Column("to_address", sa.String(length=320)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_ts_cols(),
    )
    op.create_index("ix_communications_entity", "communications", ["entity_type", "entity_id"])

    op.create_table(
        "meetings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("location", sa.String(length=512)),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("raw_notes", sa.Text()),
        sa.Column("outcome", sa.Text()),
        sa.Column("next_step", sa.Text()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_ts_cols(),
    )
    op.create_index("ix_meetings_entity", "meetings", ["entity_type", "entity_id"])

    op.create_table(
        "notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("author", sa.String(length=255)),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_ts_cols(),
    )
    op.create_index("ix_notes_entity", "notes", ["entity_type", "entity_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=64)),
        sa.Column("entity_id", sa.Integer()),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(length=16)),
        sa.Column("assignee", sa.String(length=255)),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_ts_cols(),
    )
    op.create_index("ix_tasks_entity", "tasks", ["entity_type", "entity_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_key", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=64)),
        sa.Column("entity_id", sa.Integer()),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("triggered_by", sa.String(length=255)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("error_message", sa.Text()),
        *_ts_cols(),
    )
    op.create_index("ix_workflow_runs_workflow_key", "workflow_runs", ["workflow_key"])
    op.create_index("ix_workflow_runs_entity", "workflow_runs", ["entity_type", "entity_id"])

    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("workflow_run_id", sa.Integer(), sa.ForeignKey("workflow_runs.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.String(length=255)),
        sa.Column("reviewer", sa.String(length=255)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("decision_note", sa.Text()),
        *_ts_cols(),
    )
    op.create_index("ix_approvals_entity", "approvals", ["entity_type", "entity_id"])
    op.create_index("ix_approvals_status", "approvals", ["status"])

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=64)),
        sa.Column("entity_id", sa.Integer()),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=128)),
        sa.Column("size_bytes", sa.BigInteger()),
        sa.Column("summary", sa.Text()),
        sa.Column("uploaded_by", sa.String(length=255)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_ts_cols(),
    )
    op.create_index("ix_documents_entity", "documents", ["entity_type", "entity_id"])

    op.create_table(
        "activity_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("actor", sa.String(length=255)),
        sa.Column("source", sa.String(length=64)),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_activity_events_entity", "activity_events", ["entity_type", "entity_id"])
    op.create_index("ix_activity_events_event_type", "activity_events", ["event_type"])
    op.create_index("ix_activity_events_created_at", "activity_events", ["created_at"])

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("color", sa.String(length=32)),
        *_ts_cols(),
    )

    op.create_table(
        "entity_tags",
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("tag_id", "entity_type", "entity_id", name="pk_entity_tags"),
    )


def downgrade() -> None:
    op.drop_table("entity_tags")
    op.drop_table("tags")
    op.drop_index("ix_activity_events_created_at", table_name="activity_events")
    op.drop_index("ix_activity_events_event_type", table_name="activity_events")
    op.drop_index("ix_activity_events_entity", table_name="activity_events")
    op.drop_table("activity_events")
    op.drop_index("ix_documents_entity", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_approvals_status", table_name="approvals")
    op.drop_index("ix_approvals_entity", table_name="approvals")
    op.drop_table("approvals")
    op.drop_index("ix_workflow_runs_entity", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_workflow_key", table_name="workflow_runs")
    op.drop_table("workflow_runs")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_index("ix_tasks_entity", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_notes_entity", table_name="notes")
    op.drop_table("notes")
    op.drop_index("ix_meetings_entity", table_name="meetings")
    op.drop_table("meetings")
    op.drop_index("ix_communications_entity", table_name="communications")
    op.drop_table("communications")
    op.drop_index("ix_investor_opportunities_firm_id", table_name="investor_opportunities")
    op.drop_table("investor_opportunities")
    op.drop_index("ix_investor_contacts_email", table_name="investor_contacts")
    op.drop_index("ix_investor_contacts_firm_id", table_name="investor_contacts")
    op.drop_table("investor_contacts")
    op.drop_index("ix_investor_firms_name", table_name="investor_firms")
    op.drop_table("investor_firms")
