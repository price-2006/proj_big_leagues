import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.match_features import FeatureVector


class MatchCreateRequest(BaseModel):
    resume_id: uuid.UUID
    job_id: uuid.UUID


class MatchResponse(BaseModel):
    id: uuid.UUID
    resume_id: uuid.UUID
    job_id: uuid.UUID
    feature_vector: FeatureVector
    rule_based_score: float  # 0-100 scale, e.g. 82.50
    ml_score: float | None  # null until Phase 11
    scoring_model_version: str
    created_at: datetime

    model_config = {"from_attributes": True}
