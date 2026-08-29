"""Output contract for the JD requirement/section detector (Phase 4, docs/ARCHITECTURE.md §6)."""
from enum import Enum

from pydantic import BaseModel

from app.schemas.document import TextLine


class JDSectionType(str, Enum):
    UNLABELED = "unlabeled"  # preamble before the first detected header (job title, intro line)
    REQUIREMENTS = "requirements"
    PREFERRED = "preferred"
    RESPONSIBILITIES = "responsibilities"
    ABOUT = "about"
    BENEFITS = "benefits"
    OTHER = "other"  # header detected via layout only; wording didn't match the alias table


class JDSection(BaseModel):
    section_type: JDSectionType
    raw_header: str | None
    lines: list[TextLine]


class SectionedJD(BaseModel):
    sections: list[JDSection]
