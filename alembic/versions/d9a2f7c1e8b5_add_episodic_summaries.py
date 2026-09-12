"""add episodic_summaries table (persistent cross-session memory, doc 4.2)

Revision ID: d9a2f7c1e8b5
Revises: c4d8e2f1a6b3
Create Date: 2026-09-12
"""
from alembic import op
import sqlalchemy as sa

revision = "d9a2f7c1e8b5"
down_revision = "c4d8e2f1a6b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "episodic_summaries",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_episodic_summaries_user_id", "episodic_summaries", ["user_id"])
    op.create_index("ix_episodic_summaries_session_id", "episodic_summaries", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_episodic_summaries_session_id", table_name="episodic_summaries")
    op.drop_index("ix_episodic_summaries_user_id", table_name="episodic_summaries")
    op.drop_table("episodic_summaries")