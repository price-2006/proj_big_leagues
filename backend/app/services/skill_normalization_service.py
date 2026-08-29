"""Three-stage skill normalization pipeline (Phase 5, docs/ARCHITECTURE.md
§7). Each stage only handles what the previous one couldn't:

1. Exact/alias match — normalize (lowercase, strip trailing version
   numbers) and look up against every skill's canonical name + aliases.
   Handles "Python 3" -> Python directly; "python programming" -> Python
   because that exact phrase is a seeded alias, not because "programming"
   is stripped as generic noise — stage 1 doesn't guess, it looks up.
2. Fuzzy match — character-level (difflib) and token-set similarity
   against every known term, for near-misses not yet in the alias table
   (typos, minor formatting differences). This is deliberately NOT where
   well-known variants like "React.js" belong — those get seeded as
   aliases (stage 1); stage 2 is for what wasn't anticipated. A fuzzy
   winner is only auto-confirmed if it decisively beats any registered
   disambiguation partner on the same input — "Angular" and "AngularJS"
   score 0.875 similar to *each other* as bare strings, well above the
   fuzzy threshold, so an input close to both must not get silently
   guessed at (see _has_competitive_partner below).
3. Embedding-assisted suggestion — only runs if an `embedding_lookup` is
   supplied (Phase 6 provides the real one; None here means "not wired up
   yet," not a crash). Never auto-confirms a match. Every candidate is
   checked against the disambiguation blocklist first: if the candidate
   has a registered confusable partner whose own name/aliases are
   textually close to the raw input, the suggestion is dropped — this is
   exactly the Java-vs-JavaScript, React-vs-React-Native failure mode
   embeddings alone produce.

The matching logic here is pure and DB-free by design (operates on an
in-memory SkillTaxonomy), same as every other NLP component in this
codebase — app/services/skill_seed_data.py + app/services/onet_loader.py
build the taxonomy that scripts/seed_skills.py writes to Postgres, and
that DB data is what a future SkillTaxonomy.from_db() (Phase 8) will load
back into this same shape.
"""
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Callable

from app.schemas.skill_normalization import MatchStage, NormalizationResult, SkillSuggestion

_VERSION_SUFFIX_RE = re.compile(r"\s+v?\d+(?:\.\d+)*\+?$", re.IGNORECASE)

_FUZZY_THRESHOLD = 0.80
_DISAMBIGUATION_MARGIN = 0.1
_BLOCK_TEXTUAL_SIMILARITY = 0.75

# Empirically calibrated against real all-MiniLM-L6-v2 output (Phase 6),
# not guessed: cosine similarity between a descriptive phrase and a bare
# 1-3-word skill name runs much lower than between two full sentences.
# Genuinely relevant matches ("container orchestration" -> Docker) scored
# 0.42-0.57; clearly irrelevant ones ("competitive figure skating" ->
# Scrum) topped out around 0.33. The two bands overlap in the 0.3-0.4
# range — real evidence for why stage 3 is suggestion-only and never
# auto-confirms, not just a theoretical caveat.
_DEFAULT_SUGGESTION_SIMILARITY = 0.4


@dataclass
class TaxonomySkill:
    canonical_name: str
    category: str
    aliases: list[str] = field(default_factory=list)


@dataclass
class DisambiguationPair:
    skill_a: str  # canonical_name
    skill_b: str  # canonical_name
    reason: str


# (raw_text, taxonomy, top_k) -> [(canonical_name, similarity), ...], caller-provided.
EmbeddingCandidateLookup = Callable[[str, "SkillTaxonomy", int], list[tuple[str, float]]]


class SkillTaxonomy:
    """In-memory index over the skills/skill_aliases/skill_disambiguation_rules
    data — built once, reused across normalize_skill() calls."""

    def __init__(self, skills: list[TaxonomySkill], disambiguation_pairs: list[DisambiguationPair]):
        self.skills = skills
        self.disambiguation_pairs = disambiguation_pairs

        self._normalized_to_canonical: dict[str, str] = {}
        self._all_normalized_terms: list[tuple[str, str]] = []
        self._terms_by_canonical: dict[str, list[str]] = {}

        for skill in skills:
            terms = [skill.canonical_name, *skill.aliases]
            self._terms_by_canonical[skill.canonical_name] = terms
            for term in terms:
                normalized = normalize_term(term)
                self._normalized_to_canonical.setdefault(normalized, skill.canonical_name)
                self._all_normalized_terms.append((normalized, skill.canonical_name))

        self._partners: dict[str, set[str]] = {}
        for pair in disambiguation_pairs:
            self._partners.setdefault(pair.skill_a, set()).add(pair.skill_b)
            self._partners.setdefault(pair.skill_b, set()).add(pair.skill_a)

    def lookup_normalized(self, normalized: str) -> str | None:
        return self._normalized_to_canonical.get(normalized)

    def all_normalized_terms(self) -> list[tuple[str, str]]:
        return self._all_normalized_terms

    def disambiguation_partners(self, canonical_name: str) -> set[str]:
        return self._partners.get(canonical_name, set())

    def terms_for(self, canonical_name: str) -> list[str]:
        return self._terms_by_canonical.get(canonical_name, [canonical_name])


def normalize_term(text: str) -> str:
    text = text.strip().lower()
    text = _VERSION_SUFFIX_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_skill(
    raw_text: str,
    taxonomy: SkillTaxonomy,
    embedding_lookup: EmbeddingCandidateLookup | None = None,
) -> NormalizationResult:
    exact = _stage1_exact(raw_text, taxonomy)
    if exact:
        return NormalizationResult(raw_text=raw_text, matched=True, stage=MatchStage.EXACT, canonical_name=exact, confidence=1.0)

    fuzzy = _stage2_fuzzy(raw_text, taxonomy)
    if fuzzy:
        canonical_name, score = fuzzy
        return NormalizationResult(
            raw_text=raw_text, matched=True, stage=MatchStage.FUZZY, canonical_name=canonical_name, confidence=round(score, 3)
        )

    suggestions = _stage3_suggest(raw_text, taxonomy, embedding_lookup)
    return NormalizationResult(raw_text=raw_text, matched=False, stage=MatchStage.UNMATCHED, suggestions=suggestions)


def _stage1_exact(raw_text: str, taxonomy: SkillTaxonomy) -> str | None:
    return taxonomy.lookup_normalized(normalize_term(raw_text))


def _stage2_fuzzy(raw_text: str, taxonomy: SkillTaxonomy) -> tuple[str, float] | None:
    normalized = normalize_term(raw_text)
    best_name, best_score = None, 0.0
    for candidate_normalized, canonical_name in taxonomy.all_normalized_terms():
        score = _similarity(normalized, candidate_normalized)
        if score > best_score:
            best_name, best_score = canonical_name, score

    if best_score < _FUZZY_THRESHOLD:
        return None
    if _has_competitive_partner(normalized, best_name, best_score, taxonomy):
        return None  # too close to call between confusable options — don't guess
    return best_name, best_score


def _has_competitive_partner(normalized_input: str, winner: str, winner_score: float, taxonomy: SkillTaxonomy) -> bool:
    """True if a registered disambiguation partner of `winner` scores
    within _DISAMBIGUATION_MARGIN of it on the same input — i.e. the fuzzy
    match isn't decisive enough to auto-confirm without risking exactly
    the false-merge failure mode stage 3's blocklist exists to prevent."""
    for partner in taxonomy.disambiguation_partners(winner):
        partner_score = max(
            (_similarity(normalized_input, normalize_term(term)) for term in taxonomy.terms_for(partner)),
            default=0.0,
        )
        if partner_score >= winner_score - _DISAMBIGUATION_MARGIN:
            return True
    return False


def _stage3_suggest(
    raw_text: str,
    taxonomy: SkillTaxonomy,
    embedding_lookup: EmbeddingCandidateLookup | None,
    top_k: int = 3,
    min_similarity: float = _DEFAULT_SUGGESTION_SIMILARITY,
) -> list[SkillSuggestion]:
    if embedding_lookup is None:
        return []  # Phase 6 not wired up yet — an honest "no suggestion," not a crash

    suggestions = []
    for canonical_name, similarity in embedding_lookup(raw_text, taxonomy, top_k):
        if similarity < min_similarity:
            continue
        if _is_blocked(raw_text, canonical_name, taxonomy):
            continue
        suggestions.append(SkillSuggestion(canonical_name=canonical_name, similarity=similarity))
    return suggestions


def _is_blocked(raw_text: str, candidate_canonical: str, taxonomy: SkillTaxonomy) -> bool:
    normalized_input = normalize_term(raw_text)
    for partner in taxonomy.disambiguation_partners(candidate_canonical):
        for term in taxonomy.terms_for(partner):
            if _similarity(normalized_input, normalize_term(term)) >= _BLOCK_TEXTUAL_SIMILARITY:
                return True
    return False


def _similarity(a: str, b: str) -> float:
    return max(SequenceMatcher(None, a, b).ratio(), _token_set_ratio(a, b))


def _token_set_ratio(a: str, b: str) -> float:
    tokens_a, tokens_b = set(a.split()), set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
