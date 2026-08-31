"""SQLAlchemy model for match_explanations (Phase 12, docs/ARCHITECTURE.md
§5). One row per (match, generation) — regenerating overwrites via upsert
in explanation_service.py, it doesn't accumulate history; `matches` itself
is what's versioned (scoring_model_version), not explanations.

`matching_skills`/`missing_skills`/`partial_skills` predate this table's
implementation (§5's schema) but this codebase's actual skill-matching
signal only ever computes 4 buckets (SkillBreakdown: matched/missing ×
required/preferred — app/ml/feature_engineering.py), never a distinct
"partial" tier — inventing a new NLP signal isn't this phase's job.
explanation_service.py maps: matching = matched_required ∪ matched_preferred,
missing = missing_required (the real gaps), partial = missing_preferred
(present-but-optional gaps — "partial" in the sense that lacking them
isn't disqualifying).
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MatchExplanation(Base):
    __tablename__ = "match_explanations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, unique=True)
    matching_skills: Mapped[list] = mapped_column(JSONB, nullable=False)
    missing_skills: Mapped[list] = mapped_column(JSONB, nullable=False)
    partial_skills: Mapped[list] = mapped_column(JSONB, nullable=False)
    strengths: Mapped[list] = mapped_column(JSONB, nullable=False)
    weaknesses: Mapped[list] = mapped_column(JSONB, nullable=False)
    recommendations: Mapped[list] = mapped_column(JSONB, nullable=False)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_check_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
