from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    age_range: Mapped[str | None] = mapped_column(String(30), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(30), nullable=True)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="fa-IR")

    primary_concerns: Mapped[str | None] = mapped_column(Text, nullable=True)
    goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    communication_preferences: Mapped[str | None] = mapped_column(Text, nullable=True)

    consent_privacy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_ai_support: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_emergency: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    onboarding_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="profile")

    def __repr__(self) -> str:
        return f"<Profile id={self.id} user_id={self.user_id}>"