"""SQLAlchemy model for text_embeddings (Phase 6, docs/ARCHITECTURE.md §5).

`entity_id` deliberately has no foreign key — it's polymorphic (a
resume.id or a job.id depending on entity_type), and both of those tables
don't exist until Phase 8. Architecture's own raw SQL schema doesn't
constrain it either, for the same reason.
"""
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

ENTITY_TYPES = ("resume_experience", "resume_project", "job_responsibility")


class TextEmbedding(Base):
    __tablename__ = "text_embeddings"
    __table_args__ = (CheckConstraint(f"entity_type IN {ENTITY_TYPES}", name="ck_text_embeddings_entity_type"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
