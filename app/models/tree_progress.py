from datetime import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class TreeProgress(Base):
    """Persistent state of a user's position inside a domain's decision
    tree (see app/decision_trees/*.json)."""

    __tablename__ = "tree_progress"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    domain: Mapped[str] = mapped_column(String(30), nullable=False)
    current_node_id: Mapped[str] = mapped_column(String(50), nullable=False)

    # active | completed | abandoned
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    unclear_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # history of {node, branch} steps taken, for later clinician review
    visited_nodes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)