import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.match_explanation import MatchExplanation as MatchExplanationRow
from app.schemas.match_explanation import EvidencedClaim, Recommendation


class MatchExplanationResponse(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID
    matching_skills: list[str]
    missing_skills: list[str]
    partial_skills: list[str]
    strengths: list[EvidencedClaim]
    weaknesses: list[EvidencedClaim]
    recommendations: list[Recommendation]
    narrative: str | None
    llm_model: str | None
    evidence_check_passed: bool
    generated_at: datetime


def build_match_explanation_response(row: MatchExplanationRow) -> MatchExplanationResponse:
    return MatchExplanationResponse(
        id=row.id,
        match_id=row.match_id,
        matching_skills=row.matching_skills,
        missing_skills=row.missing_skills,
        partial_skills=row.partial_skills,
        strengths=[EvidencedClaim.model_validate(c) for c in row.strengths],
        weaknesses=[EvidencedClaim.model_validate(c) for c in row.weaknesses],
        recommendations=[Recommendation.model_validate(r) for r in row.recommendations],
        narrative=row.narrative,
        llm_model=row.llm_model,
        evidence_check_passed=row.evidence_check_passed,
        generated_at=row.generated_at,
    )
