from datetime import datetime
from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.models.base import Base

# Must match the output dimension of the embedding model used in
# app/services/embeddings.py (intfloat/multilingual-e5-base -> 768).
EMBEDDING_DIM = 768


class KBDocument(Base):
    __tablename__ = "kb_documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # one of: stress_anxiety, depression_motivation, relationships_social,
    # time_management_study, self_esteem, general
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # psychoeducation | exercise | script
    content_type: Mapped[str] = mapped_column(String(30), nullable=False, default="psychoeducation")

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str | None] = mapped_column(String(300), nullable=True)

    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)

    # draft | clinician_approved  -- only clinician_approved rows should ever
    # be retrievable in production; see A6 step 2.
    review_status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )