"""The 10-feature vector (Phase 7, docs/ARCHITECTURE.md §8) computed per
(resume, job) pair, entirely from CandidateProfile + JobProfile +
skill taxonomy + embeddings — before any LLM involvement. Stored as
`matches.feature_vector` once Phase 8 wires up the matches table; also
exactly the feature set Phase 11's ML ranking model trains on.

Only 6 of these 10 feed the rule-based scorer v1 (app/ml/rule_based_scorer.py) —
domain_similarity, responsibility_similarity, and skill_importance_weighted_score
are computed and stored here for Phase 11, but the human-designed formula
doesn't use them (docs/ARCHITECTURE.md §8's own weight-rationale text only
justifies 6 terms).
"""
from pydantic import BaseModel, Field


class FeatureVector(BaseModel):
    required_skill_coverage: float = Field(ge=0.0)
    preferred_skill_coverage: float = Field(ge=0.0)
    semantic_experience_similarity: float
    project_relevance_similarity: float
    education_match: float = Field(ge=0.0, le=1.0)
    years_experience_match: float = Field(ge=0.0)  # can exceed 1.0, capped at 1.5 per §8
    domain_similarity: float
    responsibility_similarity: float
    seniority_match: float = Field(ge=0.0, le=1.0)
    skill_importance_weighted_score: float = Field(ge=0.0)


class MatchResult(BaseModel):
    features: FeatureVector
    rule_based_score: float
    scoring_weights_version: str
