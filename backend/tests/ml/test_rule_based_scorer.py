import pytest

from app.ml.rule_based_scorer import DEFAULT_WEIGHTS, score
from app.schemas.match_features import FeatureVector


def _feature_vector(**overrides) -> FeatureVector:
    base = dict(
        required_skill_coverage=0.0,
        preferred_skill_coverage=0.0,
        semantic_experience_similarity=0.0,
        project_relevance_similarity=0.0,
        education_match=0.0,
        years_experience_match=0.0,
        domain_similarity=0.0,
        responsibility_similarity=0.0,
        seniority_match=0.0,
        skill_importance_weighted_score=0.0,
    )
    base.update(overrides)
    return FeatureVector(**base)


def test_weights_sum_to_one():
    assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)


def test_all_perfect_inputs_score_one():
    fv = _feature_vector(
        required_skill_coverage=1.0,
        preferred_skill_coverage=1.0,
        semantic_experience_similarity=1.0,
        project_relevance_similarity=1.0,
        education_match=1.0,
        years_experience_match=1.0,
        seniority_match=1.0,
    )
    assert score(fv) == pytest.approx(1.0)


def test_all_zero_inputs_score_zero():
    assert score(_feature_vector()) == pytest.approx(0.0)


def test_weighted_sum_matches_manual_calculation():
    """0.35*0.8 + 0.20*0.6 + 0.15*0.4 + 0.10*0.5 + 0.10*1.0 + 0.10*((0.6+1.0)/2) = 0.69."""
    fv = _feature_vector(
        required_skill_coverage=0.8,
        semantic_experience_similarity=0.6,
        project_relevance_similarity=0.4,
        preferred_skill_coverage=0.5,
        education_match=1.0,
        seniority_match=0.6,
        years_experience_match=1.0,
    )
    assert score(fv) == pytest.approx(0.69)


def test_domain_responsibility_and_skill_importance_are_not_used_by_the_scorer():
    """These 3 of the 10 features are computed for Phase 11's ML model but
    aren't part of the hand-designed v1 formula (docs/ARCHITECTURE.md §8's
    weight rationale only covers 6 terms) — changing them must not move
    the score."""
    baseline = _feature_vector(required_skill_coverage=0.5)
    changed = _feature_vector(
        required_skill_coverage=0.5, domain_similarity=1.0, responsibility_similarity=1.0,
        skill_importance_weighted_score=1.0,
    )
    assert score(baseline) == score(changed)


def test_required_skill_coverage_has_the_largest_weight():
    assert DEFAULT_WEIGHTS["required_skill_coverage"] == max(DEFAULT_WEIGHTS.values())


def test_custom_weights_override_default():
    fv = _feature_vector(required_skill_coverage=1.0)
    custom_weights = {**DEFAULT_WEIGHTS, "required_skill_coverage": 0.0}
    assert score(fv, weights=custom_weights) == pytest.approx(0.0)
