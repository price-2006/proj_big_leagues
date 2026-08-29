"""Phase 4 test procedure per docs/ROADMAP.md: hand-labeled fixture JDs
across seniority levels; assert required/preferred classification
accuracy and schema validation.

The fixtures (tests/fixtures/jobs/) are synthetically written, not real
postings — same rationale as Phase 3's until a real corpus arrives in
Phase 10 (docs/DATASET_STRATEGY.md).
"""
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.nlp.jd_section_detector import detect_jd_sections
from app.nlp.job_information_extraction import extract_job_profile
from app.parsers.text_parser import parse_text
from app.schemas.job_profile import JobProfile, RequirementLevel, SeniorityLevel

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "jobs"


@dataclass
class Gold:
    filename: str
    title: str
    seniority: SeniorityLevel
    required_count: int
    preferred_count: int


GOLD_SET = [
    Gold("junior_backend_engineer.txt", "Junior Backend Engineer", SeniorityLevel.JUNIOR, 4, 3),
    Gold("senior_data_engineer.txt", "Senior Data Engineer", SeniorityLevel.SENIOR, 4, 3),
    Gold("staff_platform_engineer.txt", "Staff Platform Engineer", SeniorityLevel.STAFF, 4, 3),
    Gold("product_analyst.txt", "Product Analyst", SeniorityLevel.UNSPECIFIED, 4, 3),
    Gold("mixed_qualifications.txt", "Full Stack Engineer", SeniorityLevel.UNSPECIFIED, 2, 3),
]


def _extract(gold: Gold) -> JobProfile:
    text = (FIXTURES / gold.filename).read_text()
    return extract_job_profile(detect_jd_sections(parse_text(text)))


@pytest.fixture(scope="module")
def profiles() -> dict[str, JobProfile]:
    return {gold.filename: _extract(gold) for gold in GOLD_SET}


def test_schema_validation_passes_on_all_fixtures(profiles) -> None:
    for filename, profile in profiles.items():
        assert isinstance(profile, JobProfile), filename


def test_title_accuracy(profiles) -> None:
    correct = sum(1 for g in GOLD_SET if profiles[g.filename].title == g.title)
    accuracy = correct / len(GOLD_SET)
    assert accuracy == 1.0, f"title extraction accuracy {accuracy:.2f}"


def test_seniority_accuracy_ignores_body_mentions(profiles) -> None:
    """staff_platform_engineer.txt and senior_data_engineer.txt both
    mention 'junior' engineers in their Responsibilities section on a
    Senior/Staff posting — seniority must come from the title, not get
    confused by that."""
    correct = sum(1 for g in GOLD_SET if profiles[g.filename].seniority == g.seniority)
    accuracy = correct / len(GOLD_SET)
    assert accuracy == 1.0, f"seniority extraction accuracy {accuracy:.2f}"


def test_required_preferred_classification_counts(profiles) -> None:
    for g in GOLD_SET:
        requirements = profiles[g.filename].requirements
        required = [r for r in requirements if r.level == RequirementLevel.REQUIRED]
        preferred = [r for r in requirements if r.level == RequirementLevel.PREFERRED]
        assert len(required) == g.required_count, f"{g.filename}: required count"
        assert len(preferred) == g.preferred_count, f"{g.filename}: preferred count"


def test_inline_cues_override_section_default(profiles) -> None:
    """mixed_qualifications.txt puts everything under one 'Qualifications'
    header (which defaults to required) and relies entirely on per-line
    cues ('should have', 'nice to have', 'bonus') to mark three of the
    five lines preferred despite the section-level default."""
    by_text = {r.text: r.level for r in profiles["mixed_qualifications.txt"].requirements}

    assert by_text["Must have 3+ years of experience with React and Node.js"] == RequirementLevel.REQUIRED
    assert by_text["Must have strong understanding of REST APIs"] == RequirementLevel.REQUIRED
    assert by_text["Should have experience with TypeScript"] == RequirementLevel.PREFERRED
    assert by_text["Nice to have: experience with GraphQL"] == RequirementLevel.PREFERRED
    assert by_text["Bonus: contributions to open source"] == RequirementLevel.PREFERRED


def test_skills_extracted_from_requirement_lines(profiles) -> None:
    requirements = profiles["staff_platform_engineer.txt"].requirements
    kubernetes_line = next(r for r in requirements if "Kubernetes" in r.text)
    assert set(kubernetes_line.skills) == {"Kubernetes", "Docker"}


def test_responsibilities_kept_separate_from_requirements(profiles) -> None:
    profile = profiles["junior_backend_engineer.txt"]
    assert any("Build and maintain backend services" in r for r in profile.responsibilities)

    requirement_texts = " ".join(r.text for r in profile.requirements)
    assert "Build and maintain backend services" not in requirement_texts
