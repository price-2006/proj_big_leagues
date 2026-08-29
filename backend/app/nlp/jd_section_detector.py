"""JD text -> labeled requirement sections (Phase 4, docs/ARCHITECTURE.md §6
"Job description path"). Mirrors the resume section detector (Phase 2):
the same header-alias + layout-heuristic segmentation from
app/nlp/header_layout.py, with a JD-specific alias table and section type.

Sections not modeled further in JobProfile (ABOUT, BENEFITS) are still
detected here so their content doesn't bleed into the adjacent
REQUIREMENTS/RESPONSIBILITIES sections — segmentation is complete even
where the profile schema deliberately doesn't carry every section's
content forward.
"""
from app.nlp.header_layout import normalize_header, segment_by_alias_headers
from app.schemas.document import ParsedDocument
from app.schemas.job_section import JDSection, JDSectionType, SectionedJD

_HEADER_ALIASES: dict[JDSectionType, set[str]] = {
    JDSectionType.REQUIREMENTS: {
        "requirements",
        "required qualifications",
        "minimum qualifications",
        "basic qualifications",
        "qualifications",
        "must haves",
    },
    JDSectionType.PREFERRED: {
        "preferred qualifications",
        "nice to have",
        "preferred skills",
        "bonus points",
        "good to have",
        "preferred",
        "pluses",
    },
    JDSectionType.RESPONSIBILITIES: {
        "responsibilities",
        "key responsibilities",
        "what you ll do",
        "duties",
        "role overview",
        "the role",
        "job duties",
    },
    JDSectionType.ABOUT: {
        "about us",
        "about the company",
        "company overview",
        "who we are",
        "about",
    },
    JDSectionType.BENEFITS: {
        "benefits",
        "perks",
        "what we offer",
        "compensation and benefits",
    },
}

_ALIAS_TO_SECTION: dict[str, JDSectionType] = {
    alias: section for section, aliases in _HEADER_ALIASES.items() for alias in aliases
}


def detect_jd_sections(document: ParsedDocument) -> SectionedJD:
    segments = segment_by_alias_headers(document.lines, _match_alias, JDSectionType.UNLABELED, JDSectionType.OTHER)
    return SectionedJD(sections=[JDSection(section_type=t, raw_header=h, lines=l) for t, h, l in segments])


def _match_alias(text: str) -> JDSectionType | None:
    return _ALIAS_TO_SECTION.get(normalize_header(text))
