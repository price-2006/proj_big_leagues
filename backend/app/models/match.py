"""SQLAlchemy model for matches (Phase 8, docs/ARCHITECTURE.md §5).

Keyed on (resume_id, job_id, scoring_model_version) so re-scoring after a
weights/model change doesn't destroy history. `match_explanations` isn't
created yet — nothing writes to it until Phase 12's LLM layer exists;
same reasoning as `training_labels`/`experiments` staying deferred to the
phases that actually populate them (Phases 10/11).
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("resume_id", "job_id", "scoring_model_version", name="uq_match_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    feature_vector: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rule_based_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    ml_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)  # null until Phase 11
    scoring_model_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
