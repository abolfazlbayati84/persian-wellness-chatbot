from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class RiskEvent(Base):
    """A durable, DB-persisted record of every moderate/severe-risk message,
    for the human clinical-review queue (design doc section 9.3 / 15).
    Unlike trace_store.py (in-memory, wiped on restart), this table is the
    real audit trail and must never silently disappear."""

    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"), nullable=True)

    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False)  # moderate | severe
    domain_tag: Mapped[str | None] = mapped_column(String(30), nullable=True)
    user_text_snapshot: Mapped[str] = mapped_column(Text, nullable=False)

    # pending | reviewed | dismissed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)