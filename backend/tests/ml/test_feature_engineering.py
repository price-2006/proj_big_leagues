"""Phase 7 test procedure per docs/ROADMAP.md: hand-constructed resume/JD
pairs with obvious expected outcomes (strong match, weak match,
missing-required-skill case) score in the expected direction and range;
feature values are individually inspectable and match manual calculation.

Two embedding services are used deliberately:
  - FakeEmbeddingService (deterministic, instant) for every feature that
    doesn't depend on genuine semantic understanding — education, years
    of experience, seniority, skill coverage — so those get exact,
    hand-calculated assertions without paying for real model inference.
  - The real SentenceTransformerEmbeddingService for the strong/weak/
    missing-skill scenario, since demonstrating "scores in the expected
    direction" for semantic similarity requires an embedding model that
    actually understands the text, not a stand-in.
"""
from datetime import date

import pytest

from app.ml.feature_engineering import compute_feature_vector
from app.ml.rule_based_scorer import score
from app.schemas.candidate_profile import CandidateProfile, EducationEntry, ExperienceEntry
from app.schemas.job_profile import JobProfile, RequirementItem, RequirementLevel, SeniorityLevel
from app.services.embedding_service import SentenceTransformerEmbeddingService
from app.services.skill_normalization_service import DisambiguationPair, SkillTaxonomy, TaxonomySkill
from app.services.skill_seed_data import INTERNAL_DISAMBIGUATION_PAIRS, INTERNAL_SKILLS

AS_OF = date(2026, 1, 1)


class FakeEmbeddingService:
    model_name = "fake"
    dimension = 4

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t) % 7 + 1), 1.0, 0.0, 0.0] for t in texts]


@pytest.fixture(scope="module")
def taxonomy() -> SkillTaxonomy:
    skills = [TaxonomySkill(s.canonical_name, s.category, s.aliases) for s in INTERNAL_SKILLS]
    pairs = [DisambiguationPair(a, b, r) for a, b, r in INTERNAL_DISAMBIGUATION_PAIRS]
    return SkillTaxonomy(skills, pairs)


def _job(**overrides) -> JobProfile:
    base = dict(
        title="Senior Backend Engineer",
        seniority=SeniorityLevel.SENIOR,
        requirements=[
            RequirementItem(text="5+ years of experience building backend services", level=RequirementLevel.REQUIRED),
            RequirementItem(
                text="Strong experience with Python and PostgreSQL",
                level=RequirementLevel.REQUIRED,
                skills=["Python", "PostgreSQL"],
            ),
            RequirementItem(
                text="Bachelor's degree in Computer Science or related field", level=RequirementLevel.REQUIRED
            ),
            RequirementItem(
                text="Experience with Docker and Kubernetes",
                level=RequirementLevel.PREFERRED,
                skills=["Docker", "Kubernetes"],
            ),
        ],
        responsibilities=[
            "Design and build scalable backend APIs",
            "Optimize database performance",
            "Mentor junior engineers",
        ],
        about="We are a fintech company building payment infrastructure for small businesses.",
    )
    base.update(overrides)
    return JobProfile(**base)


# --- Fast, exact-value tests (fake embeddings — non-semantic features only) ---


def test_strong_candidate_skill_and_education_features(taxonomy):
    job = _job()
    candidate = CandidateProfile(
        contact={"name": "Alex Kim"},
        summary="Backend engineer specializing in fintech payment systems",
        skills=["Python", "PostgreSQL", "Docker", "Kubernetes"],
        experience=[
            ExperienceEntry(
                title="Senior Backend Engineer",
                organization="PayCo",
                start_date="Jan 2019",
                end_date="Present",
                bullets=["Designed and built scalable backend APIs"],
            )
        ],
        education=[EducationEntry(degree="B.S.", field_of_study="Computer Science", institution="State University")],
    )
    fv = compute_feature_vector(candidate, job, taxonomy, FakeEmbeddingService(), as_of=AS_OF)

    assert fv.required_skill_coverage == pytest.approx(1.0)  # Python + PostgreSQL both present
    assert fv.preferred_skill_coverage == pytest.approx(1.0)  # Docker + Kubernetes both present
    assert fv.education_match == pytest.approx(1.0)  # B.S. meets the stated Bachelor's requirement
    assert fv.seniority_match == pytest.approx(1.0)  # "Senior Backend Engineer" title == JD's SENIOR
    assert fv.years_experience_match == pytest.approx(min(7.0 / 5, 1.5), abs=0.02)  # ~7yrs / 5 required, capped 1.5


def test_missing_required_skill_drops_coverage_to_half(taxonomy):
    """Candidate has PostgreSQL but not Python — required_skill_coverage
    must be exactly 0.5 (1 of the 2 equally-weighted required skills),
    while preferred coverage is unaffected."""
    job = _job()
    candidate = CandidateProfile(
        contact={},
        skills=["PostgreSQL", "Docker", "Kubernetes"],  # no Python
        experience=[ExperienceEntry(title="Senior Backend Engineer", start_date="Jan 2019", end_date="Present")],
        education=[EducationEntry(degree="B.S.")],
    )
    fv = compute_feature_vector(candidate, job, taxonomy, FakeEmbeddingService(), as_of=AS_OF)

    assert fv.required_skill_coverage == pytest.approx(0.5)
    assert fv.preferred_skill_coverage == pytest.approx(1.0)


def test_weak_candidate_skill_and_education_features(taxonomy):
    job = _job()
    candidate = CandidateProfile(
        contact={},
        skills=["Adobe Photoshop", "Adobe Illustrator"],
        experience=[ExperienceEntry(title="Junior Graphic Designer", start_date="Jun 2023", end_date="Present")],
        education=[],
    )
    fv = compute_feature_vector(candidate, job, taxonomy, FakeEmbeddingService(), as_of=AS_OF)

    assert fv.required_skill_coverage == pytest.approx(0.0)
    assert fv.preferred_skill_coverage == pytest.approx(0.0)
    assert fv.education_match == pytest.approx(0.3)  # JD wants Bachelor's, candidate has no listed education
    assert fv.seniority_match == pytest.approx(1 - 2 / 3)  # JUNIOR vs SENIOR: distance 2 of max 3


def test_unstated_jd_requirements_use_neutral_default_not_a_penalty(taxonomy):
    job = _job(requirements=[], seniority=SeniorityLevel.UNSPECIFIED)
    candidate = CandidateProfile(contact={}, skills=[], experience=[], education=[])
    fv = compute_feature_vector(candidate, job, taxonomy, FakeEmbeddingService(), as_of=AS_OF)

    assert fv.required_skill_coverage == pytest.approx(0.7)
    assert fv.preferred_skill_coverage == pytest.approx(0.7)
    assert fv.education_match == pytest.approx(0.7)
    assert fv.years_experience_match == pytest.approx(0.7)
    assert fv.seniority_match == pytest.approx(0.7)


def test_no_bullets_or_responsibilities_scores_zero_not_neutral(taxonomy):
    """Distinguishes 'no evidence to compare' (0.0) from 'JD stated no
    requirement' (0.7, the neutral default) — see module docstring."""
    job = _job(responsibilities=[])
    candidate = CandidateProfile(contact={}, experience=[], projects=[])
    fv = compute_feature_vector(candidate, job, taxonomy, FakeEmbeddingService(), as_of=AS_OF)

    assert fv.semantic_experience_similarity == 0.0
    assert fv.project_relevance_similarity == 0.0
    assert fv.responsibility_similarity == 0.0


# --- Real embeddings: the roadmap's actual strong/weak/missing-skill scenario ---


@pytest.fixture(scope="module")
def real_embedding_service() -> SentenceTransformerEmbeddingService:
    return SentenceTransformerEmbeddingService("all-MiniLM-L6-v2")


def _strong_candidate() -> CandidateProfile:
    return CandidateProfile(
        contact={"name": "Alex Kim"},
        summary="Backend engineer specializing in fintech payment systems",
        skills=["Python", "PostgreSQL", "Docker", "Kubernetes"],
        experience=[
            ExperienceEntry(
                title="Senior Backend Engineer",
                organization="PayCo",
                start_date="Jan 2019",
                end_date="Present",
                bullets=[
                    "Designed and built scalable backend APIs serving millions of requests",
                    "Optimized PostgreSQL database performance, reducing query latency by 50 percent",
                ],
            )
        ],
        education=[
            EducationEntry(degree="B.S.", field_of_study="Computer Science", institution="State University")
        ],
    )


def _weak_candidate() -> CandidateProfile:
    return CandidateProfile(
        contact={"name": "Jordan Lee"},
        summary="Pastry chef with a passion for French desserts",
        skills=["Adobe Photoshop", "Adobe Illustrator"],
        experience=[
            ExperienceEntry(
                title="Junior Graphic Designer",
                organization="Design Studio",
                start_date="Jun 2023",
                end_date="Present",
                bullets=[
                    "Created marketing materials for social media campaigns",
                    "Designed brand identity for small businesses",
                ],
            )
        ],
        education=[],
    )


def _missing_skill_candidate() -> CandidateProfile:
    strong = _strong_candidate()
    strong.skills = ["PostgreSQL", "Docker", "Kubernetes"]  # everything except Python
    return strong


def test_strong_match_scores_high(taxonomy, real_embedding_service):
    fv = compute_feature_vector(_strong_candidate(), _job(), taxonomy, real_embedding_service, as_of=AS_OF)
    assert score(fv) > 0.75


def test_weak_match_scores_low(taxonomy, real_embedding_service):
    fv = compute_feature_vector(_weak_candidate(), _job(), taxonomy, real_embedding_service, as_of=AS_OF)
    assert score(fv) < 0.35


def test_missing_required_skill_scores_between_weak_and_strong(taxonomy, real_embedding_service):
    """Otherwise-strong candidate, but missing one of two required
    skills — should score below the fully strong match (required skills
    are the heaviest-weighted signal) but well above the weak match."""
    job = _job()
    strong_score = score(compute_feature_vector(_strong_candidate(), job, taxonomy, real_embedding_service, as_of=AS_OF))
    weak_score = score(compute_feature_vector(_weak_candidate(), job, taxonomy, real_embedding_service, as_of=AS_OF))
    missing_skill_score = score(
        compute_feature_vector(_missing_skill_candidate(), job, taxonomy, real_embedding_service, as_of=AS_OF)
    )

    assert weak_score < missing_skill_score < strong_score

    # The gap is attributable to required_skill_coverage specifically —
    # every other feature is identical to the strong candidate.
    missing_skill_features = compute_feature_vector(
        _missing_skill_candidate(), job, taxonomy, real_embedding_service, as_of=AS_OF
    )
    assert missing_skill_features.required_skill_coverage == pytest.approx(0.5)
