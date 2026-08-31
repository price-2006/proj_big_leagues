"""Phase 11: NDCG@k/MRR are computed per query group (one resume's set
of scored jobs) and averaged — these tests hand-construct small groups
with known-correct answers rather than asserting against real dataset
output, so a regression here is unambiguous.
"""
from app.ml.metrics import mrr_grouped, ndcg_at_k_grouped


def test_ndcg_is_1_when_scores_perfectly_match_relevance_order():
    relevance = [3, 2, 1]
    scores = [3, 2, 1]  # same order as relevance -> perfect ranking
    group_ids = ["r1", "r1", "r1"]
    assert ndcg_at_k_grouped(relevance, scores, group_ids, k=3) == 1.0


def test_ndcg_is_less_than_1_when_ranking_is_reversed():
    relevance = [3, 2, 1]
    scores = [1, 2, 3]  # exactly backwards
    group_ids = ["r1", "r1", "r1"]
    ndcg = ndcg_at_k_grouped(relevance, scores, group_ids, k=3)
    assert ndcg < 1.0


def test_ndcg_excludes_single_item_groups():
    # r1 has 1 item (excluded); r2 has 2 items, perfectly ranked
    relevance = [5, 3, 1]
    scores = [5, 3, 1]
    group_ids = ["r1", "r2", "r2"]
    assert ndcg_at_k_grouped(relevance, scores, group_ids, k=5) == 1.0  # only r2 counted, and it's perfect


def test_ndcg_returns_none_when_no_group_has_2plus_items():
    assert ndcg_at_k_grouped([1, 1], [1, 1], ["r1", "r2"], k=5) is None


def test_mrr_is_1_when_top_scored_item_is_relevant():
    relevance = [1.0, 0.0]  # first item relevant (>=0.5), second isn't
    scores = [0.9, 0.1]  # ranked in the same order
    group_ids = ["r1", "r1"]
    assert mrr_grouped(relevance, scores, group_ids) == 1.0


def test_mrr_is_reciprocal_of_rank_of_first_relevant_item():
    relevance = [0.0, 1.0, 0.0]  # only the 2nd item is relevant
    scores = [0.9, 0.5, 0.1]  # ranks: item0 (irrelevant) 1st, item1 (relevant) 2nd
    group_ids = ["r1", "r1", "r1"]
    assert mrr_grouped(relevance, scores, group_ids) == 0.5


def test_mrr_is_0_when_group_has_no_relevant_item():
    relevance = [0.2, 0.1]
    scores = [0.9, 0.1]
    group_ids = ["r1", "r1"]
    assert mrr_grouped(relevance, scores, group_ids) == 0.0


def test_mrr_averages_across_groups_and_excludes_single_item_groups():
    relevance = [1.0, 0.0, 1.0]  # r1: relevant item ranked 1st (RR=1.0); r2 excluded (1 item)
    scores = [0.9, 0.1, 0.5]
    group_ids = ["r1", "r1", "r2"]
    assert mrr_grouped(relevance, scores, group_ids) == 1.0
