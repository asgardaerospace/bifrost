"""supplier os foundation

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
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
        "suppliers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=128), nullable=True),
        sa.Column("region", sa.String(length=128), nullable=True),
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("website", sa.String(length=512), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "onboarding_status",
            sa.String(length=32),
            nullable=False,
            server_default="identified",
        ),
        sa.Column("preferred_partner_score", sa.Integer(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_ts_cols(),
    )
    op.create_index("ix_suppliers_name", "suppliers", ["name"])
    op.create_index("ix_suppliers_type", "suppliers", ["type"])
    op.create_index("ix_suppliers_region", "suppliers", ["region"])
    op.create_index("ix_suppliers_country", "suppliers", ["country"])
    op.create_index(
        "ix_suppliers_onboarding_status", "suppliers", ["onboarding_status"]
    )

    op.create_table(
        "supplier_capabilities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "supplier_id",
            sa.Integer(),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("capability_type", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_ts_cols(),
    )
    op.create_index(
        "ix_supplier_capabilities_supplier_id",
        "supplier_capabilities",
        ["supplier_id"],
    )
    op.create_index(
        "ix_supplier_capabilities_capability_type",
        "supplier_capabilities",
        ["capability_type"],
    )

    op.create_table(
        "supplier_certifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "supplier_id",
            sa.Integer(),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("certification", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        *_ts_cols(),
    )
    op.create_index(
        "ix_supplier_certifications_supplier_id",
        "supplier_certifications",
        ["supplier_id"],
    )
    op.create_index(
        "ix_supplier_certifications_certification",
        "supplier_certifications",
        ["certification"],
    )
    op.create_index(
        "ix_supplier_certifications_status",
        "supplier_certifications",
        ["status"],
    )

    op.create_table(
        "program_suppliers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "program_id",
            sa.Integer(),
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            sa.Integer(),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="proposed",
        ),
        *_ts_cols(),
        sa.UniqueConstraint(
            "program_id", "supplier_id", name="uq_program_suppliers_pair"
        ),
    )
    op.create_index(
        "ix_program_suppliers_program_id",
        "program_suppliers",
        ["program_id"],
    )
    op.create_index(
        "ix_program_suppliers_supplier_id",
        "program_suppliers",
        ["supplier_id"],
    )
    op.create_index(
        "ix_program_suppliers_role", "program_suppliers", ["role"]
    )
    op.create_index(
        "ix_program_suppliers_status", "program_suppliers", ["status"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_program_suppliers_status", table_name="program_suppliers"
    )
    op.drop_index(
        "ix_program_suppliers_role", table_name="program_suppliers"
    )
    op.drop_index(
        "ix_program_suppliers_supplier_id", table_name="program_suppliers"
    )
    op.drop_index(
        "ix_program_suppliers_program_id", table_name="program_suppliers"
    )
    op.drop_table("program_suppliers")

    op.drop_index(
        "ix_supplier_certifications_status",
        table_name="supplier_certifications",
    )
    op.drop_index(
        "ix_supplier_certifications_certification",
        table_name="supplier_certifications",
    )
    op.drop_index(
        "ix_supplier_certifications_supplier_id",
        table_name="supplier_certifications",
    )
    op.drop_table("supplier_certifications")

    op.drop_index(
        "ix_supplier_capabilities_capability_type",
        table_name="supplier_capabilities",
    )
    op.drop_index(
        "ix_supplier_capabilities_supplier_id",
        table_name="supplier_capabilities",
    )
    op.drop_table("supplier_capabilities")

    op.drop_index("ix_suppliers_onboarding_status", table_name="suppliers")
    op.drop_index("ix_suppliers_country", table_name="suppliers")
    op.drop_index("ix_suppliers_region", table_name="suppliers")
    op.drop_index("ix_suppliers_type", table_name="suppliers")
    op.drop_index("ix_suppliers_name", table_name="suppliers")
    op.drop_table("suppliers")
