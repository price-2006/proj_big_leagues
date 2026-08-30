"""Resume text -> labeled sections (Phase 2, docs/ARCHITECTURE.md §6 step 2).

Two independent signals decide where a new section starts:

1. Header-alias table: normalized line text matches a known phrasing
   ("technical skills", "core competencies", "employment history", ...) ->
   canonical SectionType directly.
2. Layout heuristics: a short, visually distinct line (bold, a font size
   larger than the document's body text, a DOCX "Heading"/"Title" style, or
   ALL CAPS) that the alias table doesn't recognize still starts a new
   section — typed OTHER, with the raw text preserved — so non-standard or
   unlisted headers still segment the document instead of silently getting
   absorbed into whatever section came before them.

The segmentation algorithm itself lives in app/nlp/header_layout.py, shared
with the JD requirement detector (Phase 4) — only this alias table and the
SectionType enum are resume-specific.

Known limitation: lines are walked in the order Phase 1's parser emits
them. PyMuPDF groups text into spatially-coherent blocks and returns those
in detection order, which happens to preserve column grouping for the
two-column fixture this is tested against, but general multi-column
reading-order reconstruction is a harder layout problem this phase doesn't
attempt to solve.
"""
from app.nlp.header_layout import normalize_header, segment_by_alias_headers
from app.schemas.document import ParsedDocument
from app.schemas.section import ResumeSection, SectionedResume, SectionType

_HEADER_ALIASES: dict[SectionType, set[str]] = {
    SectionType.CONTACT: {"contact", "contact information", "contact info", "personal information"},
    SectionType.SUMMARY: {
        "summary",
        "professional summary",
        "objective",
        "career objective",
        "profile",
        "about me",
    },
    SectionType.SKILLS: {
        "skills",
        "technical skills",
        "core competencies",
        "technologies",
        "skills and tools",
        "highlights",  # common on resumes built from certain ATS/builder templates
        "areas of expertise",
        "technical proficiencies",
    },
    SectionType.EXPERIENCE: {
        "experience",
        "work experience",
        "professional experience",
        "employment history",
        "work history",
        "relevant experience",
    },
    SectionType.PROJECTS: {
        "projects",
        "personal projects",
        "academic projects",
        "key projects",
        "selected projects",
    },
    SectionType.EDUCATION: {"education", "academic background", "education and training"},
    SectionType.CERTIFICATIONS: {
        "certifications",
        "certifications and licenses",
        "licenses",
        "licenses and certifications",
    },
    SectionType.AWARDS: {"awards", "honors", "awards and honors", "honors and awards", "achievements"},
    SectionType.LANGUAGES: {"languages"},
    SectionType.PUBLICATIONS: {"publications"},
}

_ALIAS_TO_SECTION: dict[str, SectionType] = {
    alias: section for section, aliases in _HEADER_ALIASES.items() for alias in aliases
}


def detect_sections(document: ParsedDocument) -> SectionedResume:
    segments = segment_by_alias_headers(document.lines, _match_alias, SectionType.UNLABELED, SectionType.OTHER)
    return SectionedResume(
        sections=[ResumeSection(section_type=t, raw_header=h, lines=l) for t, h, l in segments]
    )


def _match_alias(text: str) -> SectionType | None:
    return _ALIAS_TO_SECTION.get(normalize_header(text))
