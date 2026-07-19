"""Create durable retrieval tables.

Revision ID: 0002_create_durable_retrieval
Revises: 0001_create_document_metadata
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_create_durable_retrieval"
down_revision: str | None = "0001_create_document_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    op.create_table(
        "document_chunks",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("source_filename", sa.String(length=512), nullable=False),
        sa.Column("source_media_type", sa.String(length=255), nullable=False),
        sa.Column("source_size_bytes", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.document_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("chunk_id"),
    )
    op.create_index(
        op.f("ix_document_chunks_chunk_id"),
        "document_chunks",
        ["chunk_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_chunks_document_id"),
        "document_chunks",
        ["document_id"],
        unique=False,
    )

    op.create_table(
        "embeddings",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["document_chunks.chunk_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("chunk_id"),
    )
    op.create_index(
        op.f("ix_embeddings_chunk_id"),
        "embeddings",
        ["chunk_id"],
        unique=False,
    )

    op.create_table(
        "retrieval_metadata",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["document_chunks.chunk_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("chunk_id"),
    )
    op.create_index(
        op.f("ix_retrieval_metadata_chunk_id"),
        "retrieval_metadata",
        ["chunk_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_retrieval_metadata_document_id"),
        "retrieval_metadata",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_retrieval_metadata_filename"),
        "retrieval_metadata",
        ["filename"],
        unique=False,
    )


def downgrade() -> None:
    """Revert the migration."""
    op.drop_index(
        op.f("ix_retrieval_metadata_filename"),
        table_name="retrieval_metadata",
    )
    op.drop_index(
        op.f("ix_retrieval_metadata_document_id"),
        table_name="retrieval_metadata",
    )
    op.drop_index(
        op.f("ix_retrieval_metadata_chunk_id"),
        table_name="retrieval_metadata",
    )
    op.drop_table("retrieval_metadata")
    op.drop_index(op.f("ix_embeddings_chunk_id"), table_name="embeddings")
    op.drop_table("embeddings")
    op.drop_index(op.f("ix_document_chunks_document_id"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_chunk_id"), table_name="document_chunks")
    op.drop_table("document_chunks")
