import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.match_explanation import MatchExplanation as MatchExplanationRow


class EvidencedClaimResponse(BaseModel):
    text: str
    evidence_ref: str | None
    is_inference: bool
    evidence_text: str | None  # resolved at generation time — see explanation_service._with_evidence_text.
    # Phase 13's EvidencePopover (ARCHITECTURE.md §11) reads this directly
    # rather than re-resolving evidence_ref client-side.


class RecommendationResponse(BaseModel):
    suggestion: str
    based_on: str
    fabricated_metric: bool
    evidence_text: str | None


class MatchExplanationResponse(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID
    matching_skills: list[str]
    missing_skills: list[str]
    partial_skills: list[str]
    strengths: list[EvidencedClaimResponse]
    weaknesses: list[EvidencedClaimResponse]
    recommendations: list[RecommendationResponse]
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
        strengths=[EvidencedClaimResponse.model_validate(c) for c in row.strengths],
        weaknesses=[EvidencedClaimResponse.model_validate(c) for c in row.weaknesses],
        recommendations=[RecommendationResponse.model_validate(r) for r in row.recommendations],
        narrative=row.narrative,
        llm_model=row.llm_model,
        evidence_check_passed=row.evidence_check_passed,
        generated_at=row.generated_at,
    )
