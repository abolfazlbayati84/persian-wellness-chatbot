"""add risk_events table + users.is_admin (durable clinical review queue)

Revision ID: c4d8e2f1a6b3
Revises: b7f3a1c9d2e4
Create Date: 2026-09-12
"""
from alembic import op
import sqlalchemy as sa

revision = "c4d8e2f1a6b3"
down_revision = "b7f3a1c9d2e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "risk_events",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("risk_tier", sa.String(length=20), nullable=False),
        sa.Column("domain_tag", sa.String(length=30), nullable=True),
        sa.Column("user_text_snapshot", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_risk_events_user_id", "risk_events", ["user_id"])
    op.create_index("ix_risk_events_session_id", "risk_events", ["session_id"])
    op.create_index("ix_risk_events_status", "risk_events", ["status"])


def downgrade() -> None:
    op.drop_index("ix_risk_events_status", table_name="risk_events")
    op.drop_index("ix_risk_events_session_id", table_name="risk_events")
    op.drop_index("ix_risk_events_user_id", table_name="risk_events")
    op.drop_table("risk_events")
    op.drop_column("users", "is_admin")