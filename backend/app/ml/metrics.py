"""Ranking metrics for evaluate.py (Phase 11, docs/ARCHITECTURE.md §13).
Classification metrics (precision/recall/f1/roc_auc) are plain
sklearn.metrics calls on flat arrays — nothing group-aware needed there.
NDCG@5 and MRR are inherently query-grouped (rank jobs *for a resume*),
which sklearn's ndcg_score doesn't do across variable-length groups in
one call, so this module does the per-group loop + average by hand.
"""
from sklearn.metrics import ndcg_score

RELEVANCE_THRESHOLD = 0.5  # label >= this counts as "relevant" for MRR


def ndcg_at_k_grouped(relevance: list[float], scores: list[float], group_ids: list[str], k: int = 5) -> float | None:
    """Mean NDCG@k across groups with 2+ items. A single-item group's
    NDCG is trivially 1.0 no matter what the model predicts, which would
    inflate rather than measure anything, so those groups are excluded.
    Returns None if no group qualifies (nothing meaningful to report)."""
    values = []
    for rels, scs in _group(relevance, scores, group_ids).values():
        if len(rels) < 2:
            continue
        values.append(ndcg_score([rels], [scs], k=k))
    # float(...): ndcg_score/numpy averaging returns numpy.float64, which
    # json.dumps (used when this ends up in the experiments.metrics JSONB
    # column) can't serialize on its own — every return path here must
    # hand back a plain Python float.
    return float(sum(values) / len(values)) if values else None


def mrr_grouped(relevance: list[float], scores: list[float], group_ids: list[str], threshold: float = RELEVANCE_THRESHOLD) -> float | None:
    """Mean reciprocal rank of the first relevant (relevance >= threshold)
    item per group, ranked by descending score. A group with no relevant
    item contributes 0 (the standard MRR convention) rather than being
    skipped; only groups with < 2 items are excluded (same as NDCG)."""
    values = []
    for rels, scs in _group(relevance, scores, group_ids).values():
        if len(rels) < 2:
            continue
        order = sorted(range(len(scs)), key=lambda i: scs[i], reverse=True)
        reciprocal_rank = 0.0
        for rank, i in enumerate(order, start=1):
            if rels[i] >= threshold:
                reciprocal_rank = 1.0 / rank
                break
        values.append(reciprocal_rank)
    return float(sum(values) / len(values)) if values else None


def _group(relevance: list[float], scores: list[float], group_ids: list[str]) -> dict[str, tuple[list[float], list[float]]]:
    groups: dict[str, tuple[list[float], list[float]]] = {}
    for r, s, g in zip(relevance, scores, group_ids):
        rels, scs = groups.setdefault(g, ([], []))
        rels.append(r)
        scs.append(s)
    return groups
