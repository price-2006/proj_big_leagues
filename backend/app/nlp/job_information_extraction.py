"""JD sections -> JobProfile (Phase 4, docs/ARCHITECTURE.md §6 "Job
description path"). The JD-side counterpart to Phase 3's
information_extraction.py.

Title: the leading section's detected header (an uploaded PDF/DOCX JD with
a bold/large title line) or, when nothing was layout-detected as a header
at all (the common case for plain pasted text, which carries no font/bold
metadata — see app/parsers/text_parser.py), the first line of that leading
section, by the same "title comes first" convention resumes use for names.

Seniority: detected from the title only, deliberately — a JD's
Responsibilities section routinely says things like "mentor junior
engineers" on a Staff-level posting, which would misfire if the whole
document body were scanned instead (see docs/ROADMAP.md Phase 4 tests).

Required vs preferred: each requirement line's own inline cues ("must
have", "should have", "nice to have", "a plus", ...) take precedence over
its section's default (Requirements -> required, Preferred -> preferred),
per docs/ARCHITECTURE.md §6's "section heading plus in-line cues".
"""
import re

from app.nlp.skills_gazetteer import GAZETTEER
from app.schemas.job_profile import JobProfile, RequirementItem, RequirementLevel, SeniorityLevel
from app.schemas.job_section import JDSection, JDSectionType, SectionedJD

_BULLET_PREFIX_RE = re.compile(r"^[-•*–—]\s*")

_PREFERRED_CUES = (
    "nice to have",
    "preferred",
    "strong plus",
    "a plus",
    "bonus",
    "good to have",
    "should have",
    "ideally",
)
_REQUIRED_CUES = ("must have", "must", "required", "requires", "you must", "minimum qualifications")

_STAFF_CUES = ("staff", "principal", "distinguished")
_SENIOR_CUES = ("senior", "sr.")
_JUNIOR_CUES = ("junior", "jr.", "entry level", "entry-level", "associate")
_MID_CUES = ("mid-level", "mid level", "intermediate")

_TITLE_HEADER_TYPES = {JDSectionType.UNLABELED, JDSectionType.OTHER}


def extract_job_profile(sectioned: SectionedJD) -> JobProfile:
    sections = sectioned.sections
    title = _extract_title(sections)

    return JobProfile(
        title=title,
        seniority=_detect_seniority(title),
        requirements=_extract_requirements(sections),
        responsibilities=_extract_responsibilities(sections),
    )


def _extract_title(sections: list[JDSection]) -> str | None:
    if not sections:
        return None
    first = sections[0]
    if first.section_type not in _TITLE_HEADER_TYPES:
        return None
    if first.raw_header:
        return first.raw_header
    if first.lines:
        return first.lines[0].text
    return None


def _detect_seniority(title: str | None) -> SeniorityLevel:
    if not title:
        return SeniorityLevel.UNSPECIFIED
    lowered = title.lower()
    if any(cue in lowered for cue in _STAFF_CUES):
        return SeniorityLevel.STAFF
    if any(cue in lowered for cue in _SENIOR_CUES):
        return SeniorityLevel.SENIOR
    if any(cue in lowered for cue in _JUNIOR_CUES):
        return SeniorityLevel.JUNIOR
    if any(cue in lowered for cue in _MID_CUES):
        return SeniorityLevel.MID
    return SeniorityLevel.UNSPECIFIED


def _extract_requirements(sections: list[JDSection]) -> list[RequirementItem]:
    items: list[RequirementItem] = []
    for s in sections:
        if s.section_type not in (JDSectionType.REQUIREMENTS, JDSectionType.PREFERRED):
            continue
        for line in s.lines:
            text = _BULLET_PREFIX_RE.sub("", line.text).strip()
            if not text:
                continue
            items.append(
                RequirementItem(
                    text=text,
                    level=_classify_requirement_line(text, s.section_type),
                    skills=_find_gazetteer_skills(text),
                )
            )
    return items


def _classify_requirement_line(text: str, section_type: JDSectionType) -> RequirementLevel:
    lowered = text.lower()
    if any(cue in lowered for cue in _PREFERRED_CUES):
        return RequirementLevel.PREFERRED
    if any(cue in lowered for cue in _REQUIRED_CUES):
        return RequirementLevel.REQUIRED
    if section_type == JDSectionType.PREFERRED:
        return RequirementLevel.PREFERRED
    return RequirementLevel.REQUIRED


def _find_gazetteer_skills(text: str) -> list[str]:
    lowered = text.lower()
    return [skill for skill in GAZETTEER if re.search(rf"\b{re.escape(skill.lower())}\b", lowered)]


def _extract_responsibilities(sections: list[JDSection]) -> list[str]:
    items: list[str] = []
    for s in sections:
        if s.section_type != JDSectionType.RESPONSIBILITIES:
            continue
        for line in s.lines:
            text = _BULLET_PREFIX_RE.sub("", line.text).strip()
            if text:
                items.append(text)
    return items
