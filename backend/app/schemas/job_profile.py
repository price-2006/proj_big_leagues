"""Job Profile — the structured output of JD requirement extraction
(Phase 4, docs/ARCHITECTURE.md §6). Stored as the `jobs.parsed_profile`
JSONB column. Scoped to exactly what Feature Engineering (Phase 7, §8)
needs: required/preferred skill coverage needs `requirements`;
`responsibility_similarity` needs `responsibilities`; `seniority_match`
needs `seniority`. JD content that isn't one of those (About/Benefits
sections) isn't specially modeled here — it's still correctly segmented
by the section detector so it doesn't corrupt the sections that are
modeled, but the raw text remains available in `jobs.raw_text` for
anything not captured in this structured shape.
"""
from enum import Enum

from pydantic import BaseModel


class SeniorityLevel(str, Enum):
    UNSPECIFIED = "unspecified"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"


class RequirementLevel(str, Enum):
    REQUIRED = "required"
    PREFERRED = "preferred"


class RequirementItem(BaseModel):
    text: str  # verbatim requirement line (bullet marker stripped)
    level: RequirementLevel
    skills: list[str] = []  # named technologies found in this line (gazetteer match, Phase 3/5)


class JobProfile(BaseModel):
    title: str | None = None
    seniority: SeniorityLevel = SeniorityLevel.UNSPECIFIED
    requirements: list[RequirementItem] = []
    responsibilities: list[str] = []
