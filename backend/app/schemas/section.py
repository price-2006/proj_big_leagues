"""Output contract for the section detector (Phase 2, docs/ARCHITECTURE.md §6 step 2)."""
from enum import Enum

from pydantic import BaseModel

from app.schemas.document import TextLine


class SectionType(str, Enum):
    UNLABELED = "unlabeled"  # preamble before the first detected header (name, contact block)
    CONTACT = "contact"
    SUMMARY = "summary"
    SKILLS = "skills"
    EXPERIENCE = "experience"
    PROJECTS = "projects"
    EDUCATION = "education"
    CERTIFICATIONS = "certifications"
    AWARDS = "awards"
    LANGUAGES = "languages"
    PUBLICATIONS = "publications"
    OTHER = "other"  # header detected via layout only; wording didn't match the alias table


class ResumeSection(BaseModel):
    section_type: SectionType
    raw_header: str | None  # verbatim header text as it appeared; None only for the leading UNLABELED section
    lines: list[TextLine]


class SectionedResume(BaseModel):
    sections: list[ResumeSection]
