"""CandidateProfile + JobProfile + SkillTaxonomy + EmbeddingService ->
the 10-feature vector (Phase 7, docs/ARCHITECTURE.md §8). A pure
function — no DB or network calls beyond what's injected via `taxonomy`
and `embedding_service` — matching every other core-logic module in this
codebase (Phases 1-6 never touch the DB in their scoring-critical paths).

Two different "no signal" conventions are used deliberately, not
inconsistently:
  - Features 1/2/10 (skill coverage) and 5/6 (education, years) default
    to NEUTRAL_DEFAULT (0.7) when the JD simply states no requirement at
    all — there's nothing to fail, so there's no reason to penalize.
  - Features 3/4/7/8 (semantic similarity) default to 0.0 when either
    side has no text to compare — that's a real absence of evidence, not
    an unstated requirement, so it isn't neutral.
"""
import re
from datetime import date

from app.ml.date_utils import total_experience_years
from app.nlp.seniority import detect_seniority_from_title
from app.schemas.candidate_profile import CandidateProfile
from app.schemas.job_profile import JobProfile, RequirementLevel, SeniorityLevel
from app.schemas.match_features import FeatureVector
from app.services.embedding_service import EmbeddingService, cosine_similarity
from app.services.skill_normalization_service import SkillTaxonomy, normalize_skill

NEUTRAL_DEFAULT = 0.7

_YEARS_RE = re.compile(r"(\d+)\+?\s*years?")

# Checked in this order (highest first) since a requirement line rarely
# names more than one degree level, but if it did, the higher one is the
# more likely intended minimum ("Master's preferred, Bachelor's required"
# style phrasing is the exception, not the rule, for a single line).
_DEGREE_PATTERNS: list[tuple[re.Pattern, int]] = [
    (re.compile(r"\bph\.?d\.?\b", re.IGNORECASE), 4),
    (re.compile(r"\bmaster'?s?\b|\bm\.?s\.?\b|\bm\.?a\.?\b|\bmba\b", re.IGNORECASE), 3),
    (re.compile(r"\bbachelor'?s?\b|\bb\.?s\.?\b|\bb\.?a\.?\b", re.IGNORECASE), 2),
    (re.compile(r"\bassociate'?s?\b", re.IGNORECASE), 1),
]

_SENIORITY_ORDER = {
    SeniorityLevel.JUNIOR: 0,
    SeniorityLevel.MID: 1,
    SeniorityLevel.SENIOR: 2,
    SeniorityLevel.STAFF: 3,
}


def compute_feature_vector(
    candidate: CandidateProfile,
    job: JobProfile,
    taxonomy: SkillTaxonomy,
    embedding_service: EmbeddingService,
    as_of: date | None = None,
) -> FeatureVector:
    as_of = as_of or date.today()

    candidate_skills = _canonicalize(candidate.skills, taxonomy)
    required_weights = _jd_skill_weights(job, taxonomy, RequirementLevel.REQUIRED)
    preferred_weights = _jd_skill_weights(job, taxonomy, RequirementLevel.PREFERRED)

    experience_bullets = [b for entry in candidate.experience for b in entry.bullets]
    project_bullets = [b for entry in candidate.projects for b in entry.bullets]

    return FeatureVector(
        required_skill_coverage=_coverage(required_weights, candidate_skills),
        preferred_skill_coverage=_coverage(preferred_weights, candidate_skills),
        semantic_experience_similarity=_max_pool_mean_similarity(
            job.responsibilities, experience_bullets, embedding_service
        ),
        project_relevance_similarity=_max_pool_mean_similarity(
            job.responsibilities, project_bullets, embedding_service
        ),
        education_match=_education_match(candidate, job),
        years_experience_match=_years_experience_match(candidate, job, as_of),
        domain_similarity=_document_similarity(candidate.summary or "", job.about or "", embedding_service),
        responsibility_similarity=_document_similarity(
            " ".join(experience_bullets), " ".join(job.responsibilities), embedding_service
        ),
        seniority_match=_seniority_match(candidate, job),
        skill_importance_weighted_score=_skill_importance_weighted_score(job, taxonomy, candidate_skills),
    )


# --- Skills (features 1, 2, 10) ------------------------------------------------


def _canonicalize(skills: list[str], taxonomy: SkillTaxonomy) -> set[str]:
    canonical = set()
    for skill in skills:
        result = normalize_skill(skill, taxonomy)
        if result.matched:
            canonical.add(result.canonical_name)
    return canonical


def _jd_skill_weights(job: JobProfile, taxonomy: SkillTaxonomy, level: RequirementLevel) -> dict[str, int]:
    weights: dict[str, int] = {}
    for item in job.requirements:
        if item.level != level:
            continue
        for raw_skill in item.skills:
            result = normalize_skill(raw_skill, taxonomy)
            if result.matched:
                weights[result.canonical_name] = weights.get(result.canonical_name, 0) + 1
    return weights


def _coverage(weights: dict[str, int], candidate_skills: set[str]) -> float:
    total = sum(weights.values())
    if total == 0:
        return NEUTRAL_DEFAULT  # JD named no (normalizable) skills at this level
    matched = sum(w for name, w in weights.items() if name in candidate_skills)
    return matched / total


def _skill_importance_weighted_score(job: JobProfile, taxonomy: SkillTaxonomy, candidate_skills: set[str]) -> float:
    """Like _coverage, but required and preferred skills are pooled into
    one score, with required mentions weighted double — 'how central is
    each skill to the JD', not just 'did we cover the required list'."""
    weights: dict[str, float] = {}
    for item in job.requirements:
        multiplier = 2.0 if item.level == RequirementLevel.REQUIRED else 1.0
        for raw_skill in item.skills:
            result = normalize_skill(raw_skill, taxonomy)
            if result.matched:
                weights[result.canonical_name] = weights.get(result.canonical_name, 0.0) + multiplier
    total = sum(weights.values())
    if total == 0:
        return NEUTRAL_DEFAULT
    matched = sum(w for name, w in weights.items() if name in candidate_skills)
    return matched / total


# --- Semantic similarity (features 3, 4, 7, 8) ---------------------------------


def _max_pool_mean_similarity(queries: list[str], candidates: list[str], embedding_service: EmbeddingService) -> float:
    """For each query (a JD responsibility), the best-matching candidate
    (a resume bullet) — then averaged across queries. No evidence on
    either side is scored 0.0, not neutral (see module docstring)."""
    if not queries or not candidates:
        return 0.0
    query_vectors = embedding_service.embed(queries)
    candidate_vectors = embedding_service.embed(candidates)
    per_query_max = [max(cosine_similarity(q, c) for c in candidate_vectors) for q in query_vectors]
    return sum(per_query_max) / len(per_query_max)


def _document_similarity(text_a: str, text_b: str, embedding_service: EmbeddingService) -> float:
    if not text_a.strip() or not text_b.strip():
        return 0.0
    [vec_a, vec_b] = embedding_service.embed([text_a, text_b])
    return cosine_similarity(vec_a, vec_b)


# --- Education (feature 5) ------------------------------------------------------


def _education_match(candidate: CandidateProfile, job: JobProfile) -> float:
    required_rank = _jd_required_degree_rank(job)
    if required_rank is None:
        return NEUTRAL_DEFAULT  # JD states no education requirement
    candidate_rank = _candidate_highest_degree_rank(candidate)
    if candidate_rank is None:
        return 0.3  # JD wants a specific level; candidate's education is unknown/unlisted
    return 1.0 if candidate_rank >= required_rank else 0.3


def _jd_required_degree_rank(job: JobProfile) -> int | None:
    for level in (RequirementLevel.REQUIRED, RequirementLevel.PREFERRED):
        for item in job.requirements:
            if item.level == level:
                rank = _detect_degree_rank(item.text)
                if rank is not None:
                    return rank
    return None


def _candidate_highest_degree_rank(candidate: CandidateProfile) -> int | None:
    ranks = [_detect_degree_rank(entry.degree) for entry in candidate.education if entry.degree]
    ranks = [r for r in ranks if r is not None]
    return max(ranks) if ranks else None


def _detect_degree_rank(text: str | None) -> int | None:
    if not text:
        return None
    for pattern, rank in _DEGREE_PATTERNS:
        if pattern.search(text):
            return rank
    return None


# --- Years of experience (feature 6) --------------------------------------------


def _years_experience_match(candidate: CandidateProfile, job: JobProfile, as_of: date) -> float:
    required_years = _jd_required_years(job)
    if not required_years:
        return NEUTRAL_DEFAULT  # JD states no number
    entries = [(entry.start_date, entry.end_date) for entry in candidate.experience]
    candidate_years = total_experience_years(entries, as_of)
    return min(candidate_years / required_years, 1.5)


def _jd_required_years(job: JobProfile) -> int | None:
    for level in (RequirementLevel.REQUIRED, RequirementLevel.PREFERRED):
        for item in job.requirements:
            if item.level == level:
                match = _YEARS_RE.search(item.text)
                if match:
                    return int(match.group(1))
    return None


# --- Seniority (feature 9) ------------------------------------------------------


def _seniority_match(candidate: CandidateProfile, job: JobProfile) -> float:
    if job.seniority == SeniorityLevel.UNSPECIFIED:
        return NEUTRAL_DEFAULT
    candidate_title = candidate.experience[0].title if candidate.experience else None
    candidate_level = detect_seniority_from_title(candidate_title)
    if candidate_level == SeniorityLevel.UNSPECIFIED:
        return NEUTRAL_DEFAULT
    max_distance = max(_SENIORITY_ORDER.values())
    distance = abs(_SENIORITY_ORDER[candidate_level] - _SENIORITY_ORDER[job.seniority])
    return 1 - (distance / max_distance)
