"""Candidate Profile — the structured output of resume information
extraction (Phase 3, docs/ARCHITECTURE.md §5-6). Stored as the
`resumes.parsed_profile` JSONB column; every downstream feature (Phase 7)
and the LLM explanation layer (Phase 12) reads only this structured shape,
never raw resume text directly.
"""
from pydantic import BaseModel


class ContactInfo(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: list[str] = []


class ExperienceEntry(BaseModel):
    title: str | None = None
    organization: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    bullets: list[str] = []  # each bullet is one evidence unit (docs/ARCHITECTURE.md §6)


class ProjectEntry(BaseModel):
    name: str | None = None
    bullets: list[str] = []


class EducationEntry(BaseModel):
    degree: str | None = None
    field_of_study: str | None = None
    institution: str | None = None
    graduation_year: str | None = None


class CandidateProfile(BaseModel):
    contact: ContactInfo
    summary: str | None = None
    skills: list[str] = []
    experience: list[ExperienceEntry] = []
    projects: list[ProjectEntry] = []
    education: list[EducationEntry] = []
    certifications: list[str] = []
