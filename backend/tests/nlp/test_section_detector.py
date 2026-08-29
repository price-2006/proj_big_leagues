from pathlib import Path

from app.nlp.section_detector import detect_sections
from app.parsers.docx_parser import parse_docx
from app.parsers.pdf_parser import parse_pdf
from app.schemas.section import ResumeSection, SectionType

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "resumes"


def _first_by_type(sections: list[ResumeSection]) -> dict[SectionType, ResumeSection]:
    by_type: dict[SectionType, ResumeSection] = {}
    for section in sections:
        by_type.setdefault(section.section_type, section)
    return by_type


def test_single_column_pdf_sections() -> None:
    doc = parse_pdf((FIXTURES / "single_column.pdf").read_bytes())
    by_type = _first_by_type(detect_sections(doc).sections)

    assert by_type[SectionType.SKILLS].raw_header == "TECHNICAL SKILLS"
    assert any("Python, SQL, Docker, FastAPI, PyTorch" in l.text for l in by_type[SectionType.SKILLS].lines)

    assert by_type[SectionType.EXPERIENCE].raw_header == "EXPERIENCE"
    assert any("Software Engineer, Acme Corp" in l.text for l in by_type[SectionType.EXPERIENCE].lines)

    assert by_type[SectionType.EDUCATION].raw_header == "EDUCATION"
    assert any("University of Washington" in l.text for l in by_type[SectionType.EDUCATION].lines)


def test_two_column_pdf_sections_including_contact() -> None:
    doc = parse_pdf((FIXTURES / "two_column.pdf").read_bytes())
    by_type = _first_by_type(detect_sections(doc).sections)

    assert by_type[SectionType.CONTACT].raw_header == "CONTACT"
    assert any("taylor.morgan@example.com" in l.text for l in by_type[SectionType.CONTACT].lines)

    assert by_type[SectionType.SKILLS].raw_header == "SKILLS"
    assert any("Kubernetes" in l.text for l in by_type[SectionType.SKILLS].lines)

    assert by_type[SectionType.EXPERIENCE].raw_header == "EXPERIENCE"
    assert any("Globex Inc" in l.text for l in by_type[SectionType.EXPERIENCE].lines)

    assert by_type[SectionType.EDUCATION].raw_header == "EDUCATION"


def test_resume_docx_sections() -> None:
    doc = parse_docx((FIXTURES / "resume.docx").read_bytes())
    by_type = _first_by_type(detect_sections(doc).sections)

    assert by_type[SectionType.SKILLS].raw_header == "Skills"
    assert any("Terraform" in l.text for l in by_type[SectionType.SKILLS].lines)

    assert by_type[SectionType.EXPERIENCE].raw_header == "Experience"
    assert any("Site Reliability Engineer" in l.text for l in by_type[SectionType.EXPERIENCE].lines)

    assert by_type[SectionType.EDUCATION].raw_header == "Education"
    assert any("University of Texas at Austin" in l.text for l in by_type[SectionType.EDUCATION].lines)


def test_varied_header_wording_still_maps_to_canonical_sections() -> None:
    """'Core Competencies' vs 'Technical Skills', 'Employment History' vs
    'Experience' — the exact wording-variance case docs/ROADMAP.md Phase 2
    calls out."""
    doc = parse_pdf((FIXTURES / "varied_headers.pdf").read_bytes())
    by_type = _first_by_type(detect_sections(doc).sections)

    assert by_type[SectionType.SUMMARY].raw_header == "PROFESSIONAL SUMMARY"

    assert by_type[SectionType.SKILLS].raw_header == "CORE COMPETENCIES"
    assert any("Kafka" in l.text for l in by_type[SectionType.SKILLS].lines)

    assert by_type[SectionType.EXPERIENCE].raw_header == "EMPLOYMENT HISTORY"
    assert any("Initrode" in l.text for l in by_type[SectionType.EXPERIENCE].lines)

    assert by_type[SectionType.EDUCATION].raw_header == "ACADEMIC BACKGROUND"


def test_nonstandard_header_detected_via_layout_not_alias_table() -> None:
    doc = parse_pdf((FIXTURES / "varied_headers.pdf").read_bytes())
    sections = detect_sections(doc).sections
    other_sections = [s for s in sections if s.section_type == SectionType.OTHER]

    why_hire_me = next(s for s in other_sections if s.raw_header == "WHY HIRE ME")
    assert any("mentoring junior engineers" in l.text for l in why_hire_me.lines)

    by_type = _first_by_type(sections)
    assert "mentoring junior engineers" not in " ".join(l.text for l in by_type[SectionType.SKILLS].lines)
    assert "mentoring junior engineers" not in " ".join(l.text for l in by_type[SectionType.EXPERIENCE].lines)


def test_no_content_lost_across_section_boundaries() -> None:
    """Every extracted line ends up in exactly one section's content or as
    a header — segmentation must not silently drop text."""
    doc = parse_pdf((FIXTURES / "single_column.pdf").read_bytes())
    result = detect_sections(doc)

    accounted_for = {l.text for s in result.sections for l in s.lines}
    accounted_for |= {s.raw_header for s in result.sections if s.raw_header}

    for line in doc.lines:
        assert line.text in accounted_for
