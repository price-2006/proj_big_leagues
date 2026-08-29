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

Known limitation: lines are walked in the order Phase 1's parser emits
them. PyMuPDF groups text into spatially-coherent blocks and returns those
in detection order, which happens to preserve column grouping for the
two-column fixture this is tested against, but general multi-column
reading-order reconstruction is a harder layout problem this phase doesn't
attempt to solve.
"""
import re
from statistics import median

from app.schemas.document import ParsedDocument, TextLine
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

_MAX_HEADER_WORDS = 5
_FONT_SIZE_HEADER_RATIO = 1.15


def detect_sections(document: ParsedDocument) -> SectionedResume:
    body_font_size = _estimate_body_font_size(document.lines)

    sections: list[ResumeSection] = []
    current_type = SectionType.UNLABELED
    current_header: str | None = None
    current_lines: list[TextLine] = []

    for line in document.lines:
        matched_type = _match_alias(line.text)
        if matched_type is None and _looks_like_header(line, body_font_size):
            matched_type = SectionType.OTHER

        if matched_type is not None:
            sections.append(ResumeSection(section_type=current_type, raw_header=current_header, lines=current_lines))
            current_type = matched_type
            current_header = line.text
            current_lines = []
        else:
            current_lines.append(line)

    sections.append(ResumeSection(section_type=current_type, raw_header=current_header, lines=current_lines))

    # Drop only the degenerate leading placeholder (no header, no content);
    # a real header with zero content lines under it is kept.
    sections = [s for s in sections if s.lines or s.raw_header]
    return SectionedResume(sections=sections)


def _match_alias(text: str) -> SectionType | None:
    return _ALIAS_TO_SECTION.get(_normalize_header(text))


def _normalize_header(text: str) -> str:
    text = text.lower().strip().replace("&", "and")
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _estimate_body_font_size(lines: list[TextLine]) -> float | None:
    sizes = [line.font_size for line in lines if line.font_size is not None]
    return median(sizes) if sizes else None


def _looks_like_header(line: TextLine, body_font_size: float | None) -> bool:
    word_count = len(line.text.split())
    if word_count == 0 or word_count > _MAX_HEADER_WORDS:
        return False
    if line.style_name and line.style_name.lower().startswith(("heading", "title")):
        return True
    if line.bold:
        return True
    if body_font_size and line.font_size and line.font_size > body_font_size * _FONT_SIZE_HEADER_RATIO:
        return True
    if line.text.isupper():
        return True
    return False
