"""Create durable document and indexing metadata tables.

Revision ID: 0001_create_document_metadata
Revises:
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_create_document_metadata"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    op.create_table(
        "documents",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("document_id"),
    )
    op.create_index(
        op.f("ix_documents_document_id"),
        "documents",
        ["document_id"],
        unique=False,
    )
    op.create_table(
        "indexing_states",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("state_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.document_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("state_id"),
    )
    op.create_index(
        op.f("ix_indexing_states_document_id"),
        "indexing_states",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_indexing_states_state_id"),
        "indexing_states",
        ["state_id"],
        unique=False,
    )


def downgrade() -> None:
    """Revert the migration."""
    op.drop_index(op.f("ix_indexing_states_state_id"), table_name="indexing_states")
    op.drop_index(op.f("ix_indexing_states_document_id"), table_name="indexing_states")
    op.drop_table("indexing_states")
    op.drop_index(op.f("ix_documents_document_id"), table_name="documents")
    op.drop_table("documents")
