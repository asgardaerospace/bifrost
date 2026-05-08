"""sprint 3: memory_records + semantic_chunks (vector memory layer)

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-08

Adds the canonical organizational-memory tables required by the doctrine:
  * memory_records — one row per memorable operational artifact (mission,
    operational event, approval, communication, intel item, note, queue
    item, document). Carries source_type/source_id pointers, source_hash
    for change detection, mission_id + entity_type/entity_id linkage,
    created_by attribution, and version/refresh metadata.
  * semantic_chunks — chunked text + embeddings derived from memory_records.
    chunk_index preserves ordering; source_hash enables idempotent refresh.
    Embedding column uses pgvector on Postgres (extension auto-created) and
    JSON on SQLite (variant fallback used by the smoke harness).

Additive only.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Embedding dimension. text-embedding-3-small returns 1536-dim vectors and is
# the recommended default per Sprint 3 doctrine. The local fallback provider
# uses the same dim so prod + dev stay column-compatible.
EMBEDDING_DIM = 1536


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

    # Sprint 3 stores embeddings as JSON list-of-floats (works on Postgres
    # as JSONB and SQLite as JSON). Sprint 4 candidate: swap to pgvector
    # `vector(N)` for in-DB similarity. That migration would also create
    # the `vector` extension — `postgres:16-alpine` does not ship it, so
    # operators must move to `pgvector/pgvector:pg16` before that swap.
    # We deliberately do NOT create the extension here so this migration
    # is portable across both Postgres images.
    embedding_col_type = (
        sa.dialects.postgresql.JSONB() if is_postgres else sa.JSON()
    )

    op.create_table(
        "memory_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column(
            "source_hash",
            sa.String(length=64),
            nullable=False,
            comment="sha256 of (source_type, source_id, content) for change detection",
        ),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "mission_id",
            sa.Integer(),
            sa.ForeignKey("missions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column(
            "source_occurred_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="when the underlying source event/record happened",
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "embedding_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("meta", sa.dialects.postgresql.JSONB() if is_postgres else sa.JSON(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_ts_cols(),
        sa.UniqueConstraint(
            "source_type", "source_id", name="uq_memory_records_source"
        ),
    )
    op.create_index("ix_memory_records_source_type", "memory_records", ["source_type"])
    op.create_index("ix_memory_records_source_id", "memory_records", ["source_id"])
    op.create_index("ix_memory_records_mission_id", "memory_records", ["mission_id"])
    op.create_index("ix_memory_records_entity_type", "memory_records", ["entity_type"])
    op.create_index("ix_memory_records_entity_id", "memory_records", ["entity_id"])
    op.create_index(
        "ix_memory_records_embedding_status",
        "memory_records",
        ["embedding_status"],
    )
    op.create_index(
        "ix_memory_records_source_occurred_at",
        "memory_records",
        ["source_occurred_at"],
    )

    op.create_table(
        "semantic_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "memory_record_id",
            sa.Integer(),
            sa.ForeignKey("memory_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding", embedding_col_type, nullable=True),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.Column("embedding_dim", sa.Integer(), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "memory_record_id",
            "chunk_index",
            name="uq_semantic_chunks_record_idx",
        ),
    )
    op.create_index(
        "ix_semantic_chunks_memory_record_id",
        "semantic_chunks",
        ["memory_record_id"],
    )
    op.create_index(
        "ix_semantic_chunks_source_hash", "semantic_chunks", ["source_hash"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_semantic_chunks_source_hash", table_name="semantic_chunks"
    )
    op.drop_index(
        "ix_semantic_chunks_memory_record_id", table_name="semantic_chunks"
    )
    op.drop_table("semantic_chunks")

    for ix in (
        "ix_memory_records_source_occurred_at",
        "ix_memory_records_embedding_status",
        "ix_memory_records_entity_id",
        "ix_memory_records_entity_type",
        "ix_memory_records_mission_id",
        "ix_memory_records_source_id",
        "ix_memory_records_source_type",
    ):
        op.drop_index(ix, table_name="memory_records")
    op.drop_table("memory_records")
