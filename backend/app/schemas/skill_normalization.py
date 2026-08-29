"""Output contract for the skill normalization service (Phase 5, docs/ARCHITECTURE.md §7)."""
from enum import Enum

from pydantic import BaseModel


class MatchStage(str, Enum):
    EXACT = "exact"  # stage 1: alias/canonical-name lookup
    FUZZY = "fuzzy"  # stage 2: edit-distance/token-set near-miss
    UNMATCHED = "unmatched"  # stages 1-2 failed; `suggestions` may carry stage-3 candidates


class SkillSuggestion(BaseModel):
    """A stage-3 candidate — never auto-confirmed, always surfaced for
    manual confirmation (docs/ARCHITECTURE.md §7)."""

    canonical_name: str
    similarity: float


class NormalizationResult(BaseModel):
    raw_text: str
    matched: bool
    stage: MatchStage
    canonical_name: str | None = None
    confidence: float | None = None
    suggestions: list[SkillSuggestion] = []
