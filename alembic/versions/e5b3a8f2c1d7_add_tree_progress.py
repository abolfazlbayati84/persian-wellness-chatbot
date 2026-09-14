"""add tree_progress table (decision-tree conversation engine)

Revision ID: e5b3a8f2c1d7
Revises: d9a2f7c1e8b5
Create Date: 2026-09-14
"""
from alembic import op
import sqlalchemy as sa

revision = "e5b3a8f2c1d7"
down_revision = "d9a2f7c1e8b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tree_progress",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("domain", sa.String(length=30), nullable=False),
        sa.Column("current_node_id", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("unclear_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("visited_nodes", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_tree_progress_session_id", "tree_progress", ["session_id"])
    op.create_index("ix_tree_progress_user_id", "tree_progress", ["user_id"])
    op.create_index("ix_tree_progress_status", "tree_progress", ["status"])


def downgrade() -> None:
    op.drop_index("ix_tree_progress_status", table_name="tree_progress")
    op.drop_index("ix_tree_progress_user_id", table_name="tree_progress")
    op.drop_index("ix_tree_progress_session_id", table_name="tree_progress")
    op.drop_table("tree_progress")