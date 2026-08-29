from pathlib import Path

from app.nlp.jd_section_detector import detect_jd_sections
from app.parsers.text_parser import parse_text
from app.schemas.job_section import JDSection, JDSectionType

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "jobs"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


def _first_by_type(sections: list[JDSection]) -> dict[JDSectionType, JDSection]:
    by_type: dict[JDSectionType, JDSection] = {}
    for s in sections:
        by_type.setdefault(s.section_type, s)
    return by_type


def test_junior_jd_sections() -> None:
    doc = parse_text(_load("junior_backend_engineer.txt"))
    by_type = _first_by_type(detect_jd_sections(doc).sections)

    assert by_type[JDSectionType.REQUIREMENTS].raw_header == "Requirements"
    assert any("Python or Java" in l.text for l in by_type[JDSectionType.REQUIREMENTS].lines)

    assert by_type[JDSectionType.PREFERRED].raw_header == "Preferred Qualifications"
    assert by_type[JDSectionType.RESPONSIBILITIES].raw_header == "Responsibilities"
    assert by_type[JDSectionType.BENEFITS].raw_header == "Benefits"
    assert by_type[JDSectionType.ABOUT].raw_header == "About Us"


def test_varied_jd_header_wording_still_maps_to_canonical_sections() -> None:
    """'Minimum Qualifications' vs 'Requirements', 'Nice to Have' vs
    'Preferred Qualifications' — the JD-side analog of Phase 2's header
    wording-variance test."""
    doc = parse_text(_load("senior_data_engineer.txt"))
    by_type = _first_by_type(detect_jd_sections(doc).sections)

    assert by_type[JDSectionType.REQUIREMENTS].raw_header == "Minimum Qualifications"
    assert by_type[JDSectionType.PREFERRED].raw_header == "Nice to Have"
    assert by_type[JDSectionType.RESPONSIBILITIES].raw_header == "What You'll Do"


def test_no_content_lost_across_jd_section_boundaries() -> None:
    doc = parse_text(_load("staff_platform_engineer.txt"))
    result = detect_jd_sections(doc)

    accounted_for = {l.text for s in result.sections for l in s.lines}
    accounted_for |= {s.raw_header for s in result.sections if s.raw_header}
    for line in doc.lines:
        assert line.text in accounted_for
