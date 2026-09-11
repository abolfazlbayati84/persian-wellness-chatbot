"""add kb_documents table for RAG (A6)

Revision ID: b7f3a1c9d2e4
Revises: 9ca533019cda
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = "b7f3a1c9d2e4"
down_revision = "9ca533019cda"
branch_labels = None
depends_on = None

EMBEDDING_DIM = 768


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "kb_documents",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("domain", sa.String(length=50), nullable=False),
        sa.Column("content_type", sa.String(length=30), nullable=False, server_default="psychoeducation"),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("source", sa.String(length=300), nullable=True),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("review_status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kb_documents_domain", "kb_documents", ["domain"])


def downgrade() -> None:
    op.drop_index("ix_kb_documents_domain", table_name="kb_documents")
    op.drop_table("kb_documents")
    # NOTE: intentionally not dropping the "vector" extension on downgrade —
    # other tables/environments may depend on it.