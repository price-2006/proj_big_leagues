"""Rule-based scorer v1 (Phase 7, docs/ARCHITECTURE.md §8) — the
transparent, always-on, human-auditable baseline. Combines 6 of the
10 computed features; the other 4 (domain_similarity,
responsibility_similarity, skill_importance_weighted_score, plus
seniority_match/years_experience_match individually) exist for Phase 11's
ML model but aren't part of this hand-designed formula.

Weights live in the `scoring_weights` DB table (Phase 8+ wiring), not
hardcoded, so replacing/augmenting them with a learned model later
(Phase 11) is a data change, not a rewrite — DEFAULT_WEIGHTS below is
what gets seeded as the 'v1' row, and what pure unit tests use directly.
"""
from app.schemas.match_features import FeatureVector

# Each weight has a stated reason (docs/ARCHITECTURE.md §8), not a guess:
# required skills dominate because it's the highest-signal, lowest-noise
# filter; experience relevance over a raw keyword count; projects matter
# most for candidates without deep work history; preferred skills matter
# less than required by design (a third of the weight); education and
# seniority/experience are usually gating rather than finely graded.
DEFAULT_WEIGHTS: dict[str, float] = {
    "required_skill_coverage": 0.35,
    "semantic_experience_similarity": 0.20,
    "project_relevance_similarity": 0.15,
    "preferred_skill_coverage": 0.10,
    "education_match": 0.10,
    "seniority_and_experience_composite": 0.10,
}


def score(features: FeatureVector, weights: dict[str, float] = DEFAULT_WEIGHTS) -> float:
    # Not one of the 10 named features on its own — an equal-weighted
    # average of seniority_match and years_experience_match, since the
    # two are correlated but neither one is individually justified as a
    # full 10% weight; Architecture names the composite but doesn't spell
    # out how to combine its two inputs, so this is a documented choice.
    seniority_and_experience_composite = (features.seniority_match + features.years_experience_match) / 2

    components = {
        "required_skill_coverage": features.required_skill_coverage,
        "semantic_experience_similarity": features.semantic_experience_similarity,
        "project_relevance_similarity": features.project_relevance_similarity,
        "preferred_skill_coverage": features.preferred_skill_coverage,
        "education_match": features.education_match,
        "seniority_and_experience_composite": seniority_and_experience_composite,
    }
    return sum(weights[key] * value for key, value in components.items())
