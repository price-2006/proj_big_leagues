import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.match_features import FeatureVector, SkillBreakdown


class MatchCreateRequest(BaseModel):
    resume_id: uuid.UUID
    job_id: uuid.UUID


class MatchResponse(BaseModel):
    id: uuid.UUID
    resume_id: uuid.UUID
    job_id: uuid.UUID
    feature_vector: FeatureVector
    skill_breakdown: SkillBreakdown  # computed fresh, not stored — see match_pipeline.get_skill_breakdown_for_match
    rule_based_score: float  # 0-100 scale, e.g. 82.50
    ml_score: float | None  # null until Phase 11
    scoring_model_version: str
    created_at: datetime


def build_match_response(match, skill_breakdown: SkillBreakdown) -> MatchResponse:
    """Explicit field mapping from the Match ORM row + a separately
    computed SkillBreakdown — not `model_validate(match, from_attributes=True)`,
    since skill_breakdown isn't an ORM column."""
    return MatchResponse(
        id=match.id,
        resume_id=match.resume_id,
        job_id=match.job_id,
        feature_vector=match.feature_vector,
        skill_breakdown=skill_breakdown,
        rule_based_score=float(match.rule_based_score),
        ml_score=float(match.ml_score) if match.ml_score is not None else None,
        scoring_model_version=match.scoring_model_version,
        created_at=match.created_at,
    )
