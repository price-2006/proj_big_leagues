"""Phase 5 test procedure per docs/ROADMAP.md: a confusable-pairs test
suite (Java/JavaScript, React/React Native, PyTorch/TensorFlow, and more)
asserting these are never merged, and an alias test suite asserting known
variants normalize correctly.

Built against the real seed data (app/services/skill_seed_data.py) rather
than a toy taxonomy, so this doubles as a regression check on the seed
data itself.
"""
import pytest

from app.schemas.skill_normalization import MatchStage
from app.services.skill_normalization_service import (
    DisambiguationPair,
    SkillTaxonomy,
    TaxonomySkill,
    normalize_skill,
    normalize_term,
)
from app.services.skill_seed_data import INTERNAL_DISAMBIGUATION_PAIRS, INTERNAL_SKILLS


@pytest.fixture(scope="module")
def taxonomy() -> SkillTaxonomy:
    skills = [TaxonomySkill(s.canonical_name, s.category, s.aliases) for s in INTERNAL_SKILLS]
    pairs = [DisambiguationPair(a, b, reason) for a, b, reason in INTERNAL_DISAMBIGUATION_PAIRS]
    return SkillTaxonomy(skills, pairs)


# ---- normalize_term ----------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Python 3", "python"),
        ("Python 3.11", "python"),
        ("React 18", "react"),
        ("Node.js", "node.js"),  # trailing ".js" isn't a version-number token — untouched
        ("C++", "c++"),
    ],
)
def test_normalize_term_strips_trailing_version_numbers(raw, expected):
    assert normalize_term(raw) == expected


# ---- Stage 1: exact/alias match -----------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Python", "Python"),
        ("python", "Python"),
        ("Python 3", "Python"),
        ("python programming", "Python"),
        ("React.js", "React"),
        ("reactjs", "React"),
        ("k8s", "Kubernetes"),
        ("golang", "Go"),
        ("postgres", "PostgreSQL"),
        ("node", "Node.js"),
    ],
)
def test_exact_alias_match(taxonomy, raw, expected):
    result = normalize_skill(raw, taxonomy)
    assert result.matched
    assert result.stage == MatchStage.EXACT
    assert result.canonical_name == expected
    assert result.confidence == 1.0


# ---- Stage 2: fuzzy match (typos not yet in the alias table) -----------------


@pytest.mark.parametrize(
    "typo,expected",
    [
        ("Pyhton", "Python"),
        ("Kuberentes", "Kubernetes"),
        ("Dcoker", "Docker"),
    ],
)
def test_fuzzy_match_catches_typos(taxonomy, typo, expected):
    result = normalize_skill(typo, taxonomy)
    assert result.matched
    assert result.stage == MatchStage.FUZZY
    assert result.canonical_name == expected
    assert 0.0 < result.confidence < 1.0


# ---- Confusable pairs: stage 1 and 2 must never merge these ------------------


@pytest.mark.parametrize(
    "raw,forbidden_match",
    [
        ("Java", "JavaScript"),
        ("JavaScript", "Java"),
        ("React", "React Native"),
        ("React Native", "React"),
        ("PyTorch", "TensorFlow"),
        ("TensorFlow", "PyTorch"),
        ("Angular", "AngularJS"),
        ("AngularJS", "Angular"),
        ("C++", "C#"),
        ("C#", "C++"),
    ],
)
def test_confusable_pairs_never_merge(taxonomy, raw, forbidden_match):
    result = normalize_skill(raw, taxonomy)
    assert result.canonical_name != forbidden_match


# ---- Stage 3: embedding-assisted suggestion -----------------------------------


def test_stage3_returns_no_suggestions_when_embedding_service_not_wired_up(taxonomy):
    """Phase 6 doesn't exist yet — embedding_lookup=None must degrade
    cleanly, not crash."""
    result = normalize_skill("some totally unheard-of skill name", taxonomy)
    assert not result.matched
    assert result.stage == MatchStage.UNMATCHED
    assert result.suggestions == []


def test_stage3_blocklist_suppresses_confusable_suggestion():
    """A fake embedding model wrongly suggests 'Zeltron' for input that's
    actually closer to its registered confusable partner 'Marquize' —
    the disambiguation rule must suppress the suggestion. Isolated with a
    synthetic taxonomy: the confusable relationship stage 3 guards against
    is semantic (embedding-space), same as PyTorch/TensorFlow, not
    textual, so unlike Java/JavaScript these two share no substring —
    which also avoids the input accidentally being a stage-1/2 match for
    anything and reaching stage 3 through some other path.
    """
    skills = [TaxonomySkill("Zeltron", "x", []), TaxonomySkill("Marquize", "x", [])]
    pairs = [DisambiguationPair("Zeltron", "Marquize", "synthetic test pair")]
    small_taxonomy = SkillTaxonomy(skills, pairs)

    def fake_embedding_lookup(raw_text, taxonomy, top_k):
        return [("Zeltron", 0.9)]

    # "marqu" is 0.769 similar to "marquize" (Zeltron's disambiguation
    # partner) — above the 0.75 blocklist threshold — and only 0.167
    # similar to "zeltron", so it doesn't fuzzy-match anything at stage 2.
    result = normalize_skill("marqu", small_taxonomy, embedding_lookup=fake_embedding_lookup)
    assert result.stage == MatchStage.UNMATCHED
    assert result.suggestions == []


def test_stage3_suggestion_allowed_when_not_blocked(taxonomy):
    """A legitimate suggestion with no disambiguation conflict must still
    come through — the blocklist shouldn't over-suppress."""

    def fake_embedding_lookup(raw_text, taxonomy, top_k):
        return [("Django", 0.9)]

    result = normalize_skill("some obscure python web thing", taxonomy, embedding_lookup=fake_embedding_lookup)
    assert result.stage == MatchStage.UNMATCHED
    assert not result.matched  # stage 3 never auto-confirms
    assert len(result.suggestions) == 1
    assert result.suggestions[0].canonical_name == "Django"
    assert result.suggestions[0].similarity == 0.9


def test_stage3_threshold_matches_real_embedding_model_scale(taxonomy):
    """Regression test for a real calibration bug: this threshold was
    originally set to 0.6 (a guess made before Phase 6's embedding
    service existed). Running the real all-MiniLM-L6-v2 model against the
    real seed data showed genuinely relevant suggestions score 0.42-0.57
    ("container orchestration" -> Docker 0.569, Kubernetes 0.423) while
    clearly irrelevant ones top out near 0.33 ("competitive figure
    skating" -> Scrum 0.331) — 0.6 filtered out every real suggestion,
    making stage 3 dead code in practice. Fixed to 0.4. This test uses
    those actual observed scores via a fake lookup so it doesn't need the
    real model to catch a regression back to an uncalibrated threshold.
    """

    def fake_embedding_lookup(raw_text, taxonomy, top_k):
        return [("Docker", 0.569), ("Kubernetes", 0.423), ("Scrum", 0.331)]

    result = normalize_skill("container orchestration", taxonomy, embedding_lookup=fake_embedding_lookup)
    suggested_names = {s.canonical_name for s in result.suggestions}
    assert suggested_names == {"Docker", "Kubernetes"}


def test_stage3_filters_below_similarity_threshold(taxonomy):
    def fake_embedding_lookup(raw_text, taxonomy, top_k):
        return [("Django", 0.2)]

    result = normalize_skill("something", taxonomy, embedding_lookup=fake_embedding_lookup)
    assert result.suggestions == []


# ---- Stage 2 must not silently guess between two confusable near-ties --------


def test_fuzzy_match_refuses_to_guess_between_close_disambiguation_partners():
    """Regression test: 'Angular' and 'AngularJS' score 0.875 similar to
    *each other* as bare strings (found by scanning the real seed data
    for the highest cross-skill similarity) — higher than several real
    typo cases this service is supposed to auto-correct. An input whose
    best and second-best fuzzy scores are both against a registered
    disambiguation pair must not be silently resolved to either one.
    Isolated with a small synthetic taxonomy so the assertion doesn't
    depend on exact scores drifting if the real seed data changes.
    """
    skills = [
        TaxonomySkill("Angular", "framework", []),
        TaxonomySkill("AngularJS", "framework", []),
    ]
    pairs = [DisambiguationPair("Angular", "AngularJS", "Angular 2+ vs. AngularJS 1.x — different frameworks.")]
    small_taxonomy = SkillTaxonomy(skills, pairs)

    result = normalize_skill("angularj", small_taxonomy)  # missing the final "s" — 0.933 vs. 0.941, a genuine toss-up
    assert result.stage == MatchStage.UNMATCHED
    assert result.canonical_name is None
