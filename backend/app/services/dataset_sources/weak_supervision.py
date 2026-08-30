"""Weak-supervision label generation (Phase 10, docs/DATASET_STRATEGY.md
§3). Two independent signals, each its own label_source — never blended
into one number when metrics are reported (Phase 11's job):

1. Occupation-family sampling: a resume paired with a job from the SAME
   O*NET major group is a distant-supervision positive; a DIFFERENT major
   group is a distant-supervision negative. "Distant supervision, not
   ground truth" — DATASET_STRATEGY.md §3 is explicit that occupation
   alignment is "a reasonable but imperfect proxy" for relevance.
2. Rule-based-score-derived: once a real pair's rule-based score exists
   (Phase 7), discretize it into a coarse relevance tier. Explicitly not
   eligible as the sole/headline training signal (same section) — it's
   literally the scorer Phase 11 is supposed to improve on, so treating
   it as ground truth would be circular.
"""
OCCUPATION_LABEL_SOURCE = "weak_supervision_occupation"
RULE_BASED_LABEL_SOURCE = "weak_supervision_rule_based"

_POSITIVE_LABEL = 0.8
_NEGATIVE_LABEL = 0.2


def occupation_pair_label(resume_major_group: str | None, job_major_group: str | None) -> float | None:
    """None when either side has no inferred occupation — absence of
    signal, not a guessed negative."""
    if resume_major_group is None or job_major_group is None:
        return None
    return _POSITIVE_LABEL if resume_major_group == job_major_group else _NEGATIVE_LABEL


def rule_based_tier_label(rule_based_score_0_to_100: float) -> float:
    """Coarse relevance tier from a real rule-based score (Phase 7) — a
    tier, not the raw score, per DATASET_STRATEGY.md §3's "coarse"."""
    if rule_based_score_0_to_100 >= 70:
        return 0.9
    if rule_based_score_0_to_100 >= 40:
        return 0.5
    return 0.1
