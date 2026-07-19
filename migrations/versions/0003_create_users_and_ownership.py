"""Create users and document ownership metadata.

Revision ID: 0003_create_users_and_ownership
Revises: 0002_create_durable_retrieval
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_create_users_and_ownership"
down_revision: str | None = "0002_create_durable_retrieval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    op.create_table(
        "users",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_users_user_id"), "users", ["user_id"], unique=False)

    op.add_column("documents", sa.Column("owner_user_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_documents_owner_user_id"),
        "documents",
        ["owner_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_documents_owner_user_id_users"),
        "documents",
        "users",
        ["owner_user_id"],
        ["user_id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "document_chunks",
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        op.f("ix_document_chunks_owner_user_id"),
        "document_chunks",
        ["owner_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_document_chunks_owner_user_id_users"),
        "document_chunks",
        "users",
        ["owner_user_id"],
        ["user_id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "retrieval_metadata",
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        op.f("ix_retrieval_metadata_owner_user_id"),
        "retrieval_metadata",
        ["owner_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_retrieval_metadata_owner_user_id_users"),
        "retrieval_metadata",
        "users",
        ["owner_user_id"],
        ["user_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Revert the migration."""
    op.drop_constraint(
        op.f("fk_retrieval_metadata_owner_user_id_users"),
        "retrieval_metadata",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_retrieval_metadata_owner_user_id"),
        table_name="retrieval_metadata",
    )
    op.drop_column("retrieval_metadata", "owner_user_id")

    op.drop_constraint(
        op.f("fk_document_chunks_owner_user_id_users"),
        "document_chunks",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_document_chunks_owner_user_id"),
        table_name="document_chunks",
    )
    op.drop_column("document_chunks", "owner_user_id")

    op.drop_constraint(
        op.f("fk_documents_owner_user_id_users"),
        "documents",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_documents_owner_user_id"), table_name="documents")
    op.drop_column("documents", "owner_user_id")

    op.drop_index(op.f("ix_users_user_id"), table_name="users")
    op.drop_table("users")
