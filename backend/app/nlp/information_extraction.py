"""Section text -> CandidateProfile (Phase 3, docs/ARCHITECTURE.md §6 step 3).

Combines spaCy NER (PERSON/ORG/GPE/DATE), regex extractors (email/phone/
URLs/city-state), a bundled skills gazetteer, and bullet-aware line
grouping to turn the SectionedResume from Phase 2 into the structured
CandidateProfile every downstream feature depends on.

Skill extraction is intentionally simple here: split the Skills section's
own text on delimiters, plus the small gazetteer (app/nlp/skills_gazetteer.py)
for skills mentioned in Experience/Project prose. This is a Phase 3
stand-in — Phase 5 replaces it with the full three-stage normalization
pipeline against the DB-backed skill taxonomy (docs/ARCHITECTURE.md §7).

Experience/education line parsing targets the common resume conventions
("Title, Org -- Start to End", "Degree Field, Institution, Year") with a
regex-first, spaCy-NER-fallback approach for lines that don't match —
real-world format diversity gets stress-tested against a real corpus
starting Phase 10, not guessed at here.
"""
import re
from functools import lru_cache

import spacy

from app.config import get_settings
from app.nlp.skills_gazetteer import GAZETTEER
from app.schemas.candidate_profile import (
    CandidateProfile,
    ContactInfo,
    EducationEntry,
    ExperienceEntry,
    ProjectEntry,
)
from app.schemas.document import TextLine
from app.schemas.section import ResumeSection, SectionedResume, SectionType

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_CITY_STATE_RE = re.compile(r"\b[A-Z][a-zA-Z.]+(?:\s[A-Z][a-zA-Z.]+)*,\s*[A-Z]{2}\b")

_SKILL_DELIMITER_RE = re.compile(r"[,;|/]")
_BULLET_PREFIX_RE = re.compile(r"^[-•*–—]\s*")

_EXPERIENCE_HEADER_RE = re.compile(r"^(?P<title>[^,]+),\s*(?P<org>[^,]+?)\s+(?:--|–|—)\s+(?P<dates>.+)$")
_DATE_RANGE_RE = re.compile(r"^(?P<start>.+?)\s+to\s+(?P<end>.+)$", re.IGNORECASE)

_DEGREE_RE = re.compile(
    r"^(?P<degree>Ph\.D\.|B\.S\.|M\.S\.|B\.A\.|M\.A\.|MBA|Bachelor'?s?|Master'?s?|Associate'?s?)\s+(?P<rest>.+)$"
)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")

_CONTACT_HEADER_TYPES = {SectionType.UNLABELED, SectionType.OTHER}


@lru_cache
def _nlp():
    return spacy.load(get_settings().spacy_model)


def extract_candidate_profile(sectioned: SectionedResume) -> CandidateProfile:
    nlp = _nlp()
    sections = sectioned.sections

    return CandidateProfile(
        contact=_extract_contact(sections, nlp),
        summary=_extract_summary(sections),
        skills=_extract_skills(sections),
        experience=_extract_experience(sections, nlp),
        projects=_extract_projects(sections),
        education=_extract_education(sections),
        certifications=_extract_flat_list(sections, SectionType.CERTIFICATIONS),
    )


# --- Contact -----------------------------------------------------------------


def _extract_contact(sections: list[ResumeSection], nlp) -> ContactInfo:
    name = _extract_name(sections, nlp)

    contact_sections = [s for s in sections if s.section_type == SectionType.CONTACT]
    if sections and sections[0].section_type in _CONTACT_HEADER_TYPES:
        contact_sections = [sections[0], *contact_sections]
    contact_text = "\n".join(line.text for s in contact_sections for line in s.lines)

    return ContactInfo(
        name=name,
        email=_find_first(_EMAIL_RE, contact_text),
        phone=_find_first(_PHONE_RE, contact_text),
        location=_extract_location(contact_text, nlp),
        links=_URL_RE.findall(contact_text),
    )


def _extract_name(sections: list[ResumeSection], nlp) -> str | None:
    if not sections:
        return None
    first = sections[0]
    if first.section_type in _CONTACT_HEADER_TYPES and first.raw_header:
        return first.raw_header
    preamble_text = "\n".join(line.text for line in first.lines)
    persons = [ent.text for ent in nlp(preamble_text).ents if ent.label_ == "PERSON"]
    return persons[0] if persons else None


def _extract_location(text: str, nlp) -> str | None:
    match = _CITY_STATE_RE.search(text)
    if match:
        return match.group(0)
    gpes = [ent.text for ent in nlp(text).ents if ent.label_ == "GPE"]
    return gpes[0] if gpes else None


def _find_first(pattern: re.Pattern, text: str) -> str | None:
    match = pattern.search(text)
    return match.group(0) if match else None


# --- Summary / skills / certifications ----------------------------------------


def _extract_summary(sections: list[ResumeSection]) -> str | None:
    for s in sections:
        if s.section_type == SectionType.SUMMARY and s.lines:
            return " ".join(line.text for line in s.lines)
    return None


def _extract_skills(sections: list[ResumeSection]) -> list[str]:
    skills: list[str] = []
    seen: set[str] = set()

    def add(skill: str) -> None:
        key = skill.lower()
        if skill and key not in seen:
            seen.add(key)
            skills.append(skill)

    for s in sections:
        if s.section_type != SectionType.SKILLS:
            continue
        for line in s.lines:
            for token in _SKILL_DELIMITER_RE.split(line.text):
                token = _BULLET_PREFIX_RE.sub("", token).strip()
                if token:
                    add(token)

    for s in sections:
        if s.section_type not in (SectionType.EXPERIENCE, SectionType.PROJECTS):
            continue
        for line in s.lines:
            lowered = line.text.lower()
            for skill in GAZETTEER:
                if re.search(rf"\b{re.escape(skill.lower())}\b", lowered):
                    add(skill)

    return skills


def _extract_flat_list(sections: list[ResumeSection], section_type: SectionType) -> list[str]:
    items: list[str] = []
    for s in sections:
        if s.section_type != section_type:
            continue
        for line in s.lines:
            for token in _SKILL_DELIMITER_RE.split(line.text):
                token = token.strip()
                if token:
                    items.append(token)
    return items


# --- Experience / projects (bullet-grouped entries) ---------------------------


def _group_into_entries(sections: list[ResumeSection], section_type: SectionType) -> list[tuple[str, list[str]]]:
    """Within a section, a non-bullet line starts a new entry (its header);
    bullet-prefixed lines that follow are that entry's bullets."""
    entries: list[tuple[str, list[str]]] = []
    header: str | None = None
    bullets: list[str] = []

    def flush() -> None:
        if header is not None:
            entries.append((header, list(bullets)))

    for s in sections:
        if s.section_type != section_type:
            continue
        for line in s.lines:
            if _is_bullet_line(line):
                bullets.append(_BULLET_PREFIX_RE.sub("", line.text).strip())
            else:
                flush()
                header = line.text
                bullets = []
    flush()
    return entries


def _is_bullet_line(line: TextLine) -> bool:
    """PDF bullets carry a literal marker character in the text. DOCX list
    styles (e.g. "List Bullet") render one but don't put it in
    paragraph.text — the marker lives in the list-numbering XML instead —
    so a DOCX bullet is only detectable via its paragraph style name."""
    if _BULLET_PREFIX_RE.match(line.text):
        return True
    return bool(line.style_name and "list" in line.style_name.lower())


def _extract_experience(sections: list[ResumeSection], nlp) -> list[ExperienceEntry]:
    entries = []
    for header, bullets in _group_into_entries(sections, SectionType.EXPERIENCE):
        title, org, start, end = _parse_experience_header(header, nlp)
        entries.append(ExperienceEntry(title=title, organization=org, start_date=start, end_date=end, bullets=bullets))
    return entries


def _extract_projects(sections: list[ResumeSection]) -> list[ProjectEntry]:
    return [ProjectEntry(name=header, bullets=bullets) for header, bullets in _group_into_entries(sections, SectionType.PROJECTS)]


def _parse_experience_header(text: str, nlp) -> tuple[str | None, str | None, str | None, str | None]:
    match = _EXPERIENCE_HEADER_RE.match(text)
    if match:
        start, end = _split_date_range(match.group("dates"))
        return match.group("title").strip(), match.group("org").strip(), start, end

    doc = nlp(text)
    orgs = [ent.text for ent in doc.ents if ent.label_ == "ORG"]
    dates = [ent.text for ent in doc.ents if ent.label_ == "DATE"]
    start, end = _split_date_range(dates[0]) if dates else (None, None)
    title = text.split(",")[0].strip() if "," in text else text.strip()
    return title, (orgs[0] if orgs else None), start, end


def _split_date_range(text: str) -> tuple[str | None, str | None]:
    text = text.strip()
    match = _DATE_RANGE_RE.match(text)
    if match:
        return match.group("start").strip(), match.group("end").strip()
    return (text or None), None


# --- Education -----------------------------------------------------------------


def _extract_education(sections: list[ResumeSection]) -> list[EducationEntry]:
    return [
        _parse_education_line(line.text)
        for s in sections
        if s.section_type == SectionType.EDUCATION
        for line in s.lines
    ]


def _parse_education_line(text: str) -> EducationEntry:
    text = text.strip()

    year_match = _YEAR_RE.search(text)
    graduation_year = year_match.group(0) if year_match else None
    if year_match:
        text = (text[: year_match.start()] + text[year_match.end() :]).strip().rstrip(",").strip()

    degree_match = _DEGREE_RE.match(text)
    degree = degree_match.group("degree") if degree_match else None
    rest = degree_match.group("rest") if degree_match else text

    parts = [p.strip() for p in rest.split(",") if p.strip()]
    if len(parts) >= 2:
        field_of_study, institution = parts[0], ", ".join(parts[1:])
    elif len(parts) == 1:
        field_of_study, institution = None, parts[0]
    else:
        field_of_study, institution = None, None

    return EducationEntry(degree=degree, field_of_study=field_of_study, institution=institution, graduation_year=graduation_year)
