"""SQLAlchemy model for scoring_weights (Phase 7, docs/ARCHITECTURE.md §8:
"These weights live in a config table... not in code, specifically so the
roadmap's later step — replacing/augmenting them with a learned model —
is a data change, not a rewrite."). Not shown in Architecture §5's SQL
block (that section predates this table being named), so this schema is
this phase's own design, kept intentionally simple: named, versioned
weight sets, exactly one active at a time.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ScoringWeights(Base):
    __tablename__ = "scoring_weights"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    weights: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
