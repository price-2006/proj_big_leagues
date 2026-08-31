"""The LLM's structured-output contract (Phase 12, docs/ARCHITECTURE.md §9)
— every claim must cite an `evidence_ref` into the already-extracted
CandidateProfile/JobProfile, or be explicitly tagged `is_inference=True`.
This schema is what `LLMService.generate_structured` validates its raw
JSON response against, and what `evidence_validator.py` then checks a
second time against the actual stored data — the LLM's own claim that
something is evidenced is never trusted on its own.

`narrative` isn't in ARCHITECTURE.md §9's Pydantic snippet but is a real,
NOT NULL-adjacent column on `match_explanations` (§5) — added here since
the table needs somewhere to get it from.
"""
from pydantic import BaseModel


class EvidencedClaim(BaseModel):
    text: str
    evidence_ref: str | None  # e.g. "experience[2].bullets[1]"; None only if is_inference
    is_inference: bool = False


class Recommendation(BaseModel):
    suggestion: str
    based_on: str  # evidence_ref this suggestion improves on
    fabricated_metric: bool = False  # set True by the validator, never by the LLM itself


class MatchExplanation(BaseModel):
    narrative: str
    strengths: list[EvidencedClaim]
    weaknesses: list[EvidencedClaim]
    missing_skills: list[str]  # must be a subset of the computed missing skills — validated post-hoc
    recommendations: list[Recommendation]
