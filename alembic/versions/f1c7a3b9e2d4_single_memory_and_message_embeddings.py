"""single per-user memory profile + message embeddings for cross-session recall

Revision ID: f1c7a3b9e2d4
Revises: e5b3a8f2c1d7
Create Date: 2026-09-16
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "f1c7a3b9e2d4"
down_revision = "e5b3a8f2c1d7"
branch_labels = None
depends_on = None

EMBEDDING_DIM = 768


def upgrade() -> None:
    # collapse any existing multiple rows-per-user down to the most recent one
    op.execute(
        """
        DELETE FROM episodic_summaries a
        USING episodic_summaries b
        WHERE a.user_id = b.user_id AND a.id < b.id
        """
    )
    op.create_unique_constraint("uq_episodic_summaries_user_id", "episodic_summaries", ["user_id"])

    op.add_column("messages", sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "embedding")
    op.drop_constraint("uq_episodic_summaries_user_id", "episodic_summaries", type_="unique")