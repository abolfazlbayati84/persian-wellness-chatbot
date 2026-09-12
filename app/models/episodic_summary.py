from datetime import datetime
from sqlalchemy import Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class EpisodicSummary(Base):
    """Persistent, cross-session memory (design doc section 4.2, tier 2).
    One row per ended session, holding an LLM-generated summary -- lets the
    bot recall past sessions even after the current session's short-term
    working memory has no visibility into them."""

    __tablename__ = "episodic_summaries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)

    summary_text: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)