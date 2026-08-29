"""Phase 3 test procedure per docs/ROADMAP.md: extraction accuracy against
a small hand-labeled subset of fixture resumes (precision/recall per
field: name, email, skills, degree, experience entries), plus a
100%-schema-validation check.

The "hand-labeled" gold set below is derived from
tests/fixtures/resumes/generate_fixtures.py, which we wrote and therefore
know the exact ground truth for — a stand-in for real hand-labeled resumes
until Phase 10 brings in a real corpus (docs/DATASET_STRATEGY.md).
"""
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.nlp.information_extraction import extract_candidate_profile
from app.nlp.section_detector import detect_sections
from app.parsers.docx_parser import parse_docx
from app.parsers.pdf_parser import parse_pdf
from app.schemas.candidate_profile import CandidateProfile

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "resumes"


@dataclass
class Gold:
    parser: str  # "pdf" | "docx"
    filename: str
    name: str
    email: str
    skills: set[str]
    degree: str
    organization: str  # gold organization for the (only) experience entry


GOLD_SET = [
    Gold(
        "pdf", "single_column.pdf", "Jordan Ellis", "jordan.ellis@example.com",
        {"Python", "SQL", "Docker", "FastAPI", "PyTorch"}, "B.S.", "Acme Corp",
    ),
    Gold(
        "pdf", "two_column.pdf", "Taylor Morgan", "taylor.morgan@example.com",
        {"Java", "Spring Boot", "Kubernetes", "PostgreSQL", "AWS"}, "M.S.", "Globex Inc",
    ),
    Gold(
        "docx", "resume.docx", "Sam Rivera", "sam.rivera@example.com",
        {"Go", "gRPC", "Terraform", "GCP", "Redis"}, "B.S.", "Initech",
    ),
    Gold(
        "pdf", "varied_headers.pdf", "Morgan Lee", "morgan.lee@example.com",
        {"Go", "Kafka", "Terraform", "GCP"}, "B.S.", "Initrode",
    ),
]


def _extract(gold: Gold) -> CandidateProfile:
    data = (FIXTURES / gold.filename).read_bytes()
    parsed = parse_pdf(data) if gold.parser == "pdf" else parse_docx(data)
    return extract_candidate_profile(detect_sections(parsed))


@pytest.fixture(scope="module")
def profiles() -> dict[str, CandidateProfile]:
    return {gold.filename: _extract(gold) for gold in GOLD_SET}


def test_schema_validation_passes_on_all_fixtures(profiles) -> None:
    for filename, profile in profiles.items():
        assert isinstance(profile, CandidateProfile), filename


def test_name_accuracy(profiles) -> None:
    correct = sum(1 for g in GOLD_SET if profiles[g.filename].contact.name == g.name)
    accuracy = correct / len(GOLD_SET)
    assert accuracy == 1.0, f"name extraction accuracy {accuracy:.2f}"


def test_email_accuracy(profiles) -> None:
    correct = sum(1 for g in GOLD_SET if profiles[g.filename].contact.email == g.email)
    accuracy = correct / len(GOLD_SET)
    assert accuracy == 1.0, f"email extraction accuracy {accuracy:.2f}"


def test_skills_precision_recall(profiles) -> None:
    true_positives = predicted_total = gold_total = 0
    for g in GOLD_SET:
        extracted = {s.lower() for s in profiles[g.filename].skills}
        gold = {s.lower() for s in g.skills}
        true_positives += len(extracted & gold)
        predicted_total += len(extracted)
        gold_total += len(gold)

    recall = true_positives / gold_total if gold_total else 0.0
    precision = true_positives / predicted_total if predicted_total else 0.0
    assert recall == 1.0, f"skills recall {recall:.2f} (missed a labeled skill)"
    assert precision >= 0.8, f"skills precision {precision:.2f} below threshold"


def test_degree_accuracy(profiles) -> None:
    correct = 0
    for g in GOLD_SET:
        education = profiles[g.filename].education
        if education and education[0].degree == g.degree:
            correct += 1
    accuracy = correct / len(GOLD_SET)
    assert accuracy == 1.0, f"degree extraction accuracy {accuracy:.2f}"


def test_experience_entries_recall(profiles) -> None:
    found = 0
    for g in GOLD_SET:
        experience = profiles[g.filename].experience
        if any(e.organization == g.organization for e in experience):
            found += 1
    recall = found / len(GOLD_SET)
    assert recall == 1.0, f"experience-entry recall {recall:.2f}"


def test_experience_bullets_preserved_as_evidence_units(profiles) -> None:
    """Bullets must survive verbatim (minus the bullet marker) — they're
    what the LLM explanation layer cites as evidence in Phase 12."""
    single_column = profiles["single_column.pdf"].experience[0]
    assert single_column.bullets == [
        "Built a resume parsing pipeline processing 10k documents per day",
        "Reduced API latency by 40 percent through query optimization",
    ]


def test_docx_list_style_bullet_attaches_to_its_entry_not_a_new_one(profiles) -> None:
    """DOCX 'List Bullet' paragraphs carry no literal bullet character in
    paragraph.text (the marker is in the numbering XML, not the text), so
    a plain text-prefix check misses it and used to split it into a bogus
    second experience entry. Regression test for that fix."""
    resume_docx = profiles["resume.docx"].experience
    assert len(resume_docx) == 1
    assert resume_docx[0].organization == "Initech"
    assert resume_docx[0].bullets == [
        "Cut incident response time by 60 percent by building an on-call runbook system"
    ]
