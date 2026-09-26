"""add missing updated_at column to episodic_summaries

Revision ID: a3d8f6c2b9e1
Revises: f1c7a3b9e2d4
Create Date: 2026-09-16
"""
from alembic import op
import sqlalchemy as sa

revision = "a3d8f6c2b9e1"
down_revision = "f1c7a3b9e2d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "episodic_summaries",
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    # backfill existing rows so updated_at is never NULL going forward
    op.execute("UPDATE episodic_summaries SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column("episodic_summaries", "updated_at", nullable=False)


def downgrade() -> None:
    op.drop_column("episodic_summaries", "updated_at")