from app.services.dataset_sources.weak_supervision import occupation_pair_label, rule_based_tier_label


def test_same_major_group_is_a_positive_pair():
    assert occupation_pair_label("15", "15") == 0.8


def test_different_major_group_is_a_negative_pair():
    assert occupation_pair_label("15", "41") == 0.2


def test_missing_occupation_on_either_side_returns_none_not_a_guess():
    assert occupation_pair_label(None, "15") is None
    assert occupation_pair_label("15", None) is None
    assert occupation_pair_label(None, None) is None


def test_rule_based_tiers_are_coarse_not_the_raw_score():
    assert rule_based_tier_label(85) == 0.9
    assert rule_based_tier_label(70) == 0.9
    assert rule_based_tier_label(55) == 0.5
    assert rule_based_tier_label(40) == 0.5
    assert rule_based_tier_label(20) == 0.1
    assert rule_based_tier_label(0) == 0.1
