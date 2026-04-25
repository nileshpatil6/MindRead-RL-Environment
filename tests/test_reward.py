"""15+ unit tests for the reward function."""

import pytest
from server.reward import compute_reward, compute_semantic_similarity


def _reward(
    hypothesis: str,
    secret: str,
    n_q: int = 4,
    max_q: int = 8,
    cat_pred: str | None = None,
    cat_true: str = "factual",
    keywords: list[str] | None = None,
) -> dict:
    return compute_reward(
        hypothesis=hypothesis,
        true_secret=secret,
        n_questions_used=n_q,
        max_questions=max_q,
        category_predicted=cat_pred,
        category_true=cat_true,
        hint_keywords=keywords or [],
    )


class TestSemanticSimilarity:
    def test_identical_text_scores_high(self):
        secret = "The Q3 launch was postponed by 6 weeks due to compliance."
        score = compute_semantic_similarity(secret, secret)
        assert score > 0.9

    def test_paraphrase_scores_moderate_to_high(self):
        # Uses overlapping words — paraphrase must share key terms to work with BoW embedder in tests.
        # Real sentence-transformers handles true synonyms; BoW requires shared words.
        secret = "The Q3 product launch was postponed by six weeks for compliance reasons."
        hyp = "The Q3 product launch was postponed six weeks due to a compliance issue."
        score = compute_semantic_similarity(hyp, secret)
        assert score > 0.3

    def test_unrelated_text_scores_low(self):
        secret = "The acquisition price is $340M."
        hyp = "The weather today is sunny and warm."
        score = compute_semantic_similarity(hyp, secret)
        assert score < 0.3

    def test_score_is_normalized_to_0_1(self):
        secret = "Some secret content here."
        hyp = "Completely different content with no relation."
        score = compute_semantic_similarity(hyp, secret)
        assert 0.0 <= score <= 1.0


class TestEfficiencyBonus:
    def test_fewer_questions_gives_higher_efficiency(self):
        r_few = _reward("The secret is about a delay.", "The product launch was delayed.", n_q=2, max_q=8)
        r_many = _reward("The secret is about a delay.", "The product launch was delayed.", n_q=7, max_q=8)
        assert r_few["components"]["efficiency"] > r_many["components"]["efficiency"]

    def test_efficiency_range_is_0_6_to_1_0(self):
        r_min = _reward("x", "y", n_q=8, max_q=8)
        r_max = _reward("x", "y", n_q=0, max_q=8)
        assert abs(r_min["components"]["efficiency"] - 0.6) < 0.01
        assert abs(r_max["components"]["efficiency"] - 1.0) < 0.01

    def test_efficiency_with_half_questions_used(self):
        r = _reward("x", "y", n_q=4, max_q=8)
        assert abs(r["components"]["efficiency"] - 0.8) < 0.01


class TestCategoryBonus:
    def test_correct_category_gives_bonus(self):
        r = _reward("hypothesis", "secret", cat_pred="factual", cat_true="factual")
        assert r["components"]["category_bonus"] == 0.1

    def test_wrong_category_gives_no_bonus(self):
        r = _reward("hypothesis", "secret", cat_pred="belief", cat_true="factual")
        assert r["components"]["category_bonus"] == 0.0

    def test_none_category_gives_no_bonus(self):
        r = _reward("hypothesis", "secret", cat_pred=None, cat_true="factual")
        assert r["components"]["category_bonus"] == 0.0


class TestKeywordBonus:
    def test_keyword_hit_gives_bonus(self):
        r = _reward("The launch was postponed", "secret", keywords=["postponed", "launch"])
        assert r["components"]["keyword_bonus"] > 0.0

    def test_no_keyword_hit_gives_zero_bonus(self):
        r = _reward("The acquisition price changed", "secret", keywords=["postponed", "compliance"])
        assert r["components"]["keyword_bonus"] == 0.0

    def test_keyword_bonus_capped_at_0_1(self):
        keywords = ["a", "b", "c", "d", "e", "f", "g", "h"]
        hyp = "a b c d e f g h"
        r = _reward(hyp, "secret", keywords=keywords)
        assert r["components"]["keyword_bonus"] <= 0.1

    def test_keyword_matching_is_case_insensitive(self):
        r = _reward("The LAUNCH was Postponed", "secret", keywords=["launch", "postponed"])
        assert r["components"]["keyword_bonus"] > 0.0


class TestTotalReward:
    def test_reward_is_in_0_1_range(self):
        r = _reward("any hypothesis", "any secret")
        assert 0.0 <= r["reward"] <= 1.0

    def test_perfect_match_scores_near_1(self):
        s = "The Q3 product launch was postponed by 6 weeks due to compliance."
        r = _reward(s, s, n_q=1, max_q=8, cat_pred="factual", cat_true="factual", keywords=["launch", "postponed", "compliance"])
        assert r["reward"] > 0.8

    def test_empty_hypothesis_scores_low(self):
        r = _reward("", "The Q3 launch was postponed.", n_q=8, max_q=8)
        assert r["reward"] < 0.3

    def test_reward_dict_has_all_keys(self):
        r = _reward("hypothesis", "secret")
        assert "reward" in r
        assert "components" in r
        assert "semantic" in r["components"]
        assert "efficiency" in r["components"]
        assert "category_bonus" in r["components"]
        assert "keyword_bonus" in r["components"]

    def test_more_specific_hypothesis_beats_vague_one(self):
        secret = "The acquisition price of TechCorp is $340M, 17% below the initial bid."
        specific = "TechCorp was acquired for $340M, which is 17% less than the original bid."
        vague = "The company made some kind of deal that was below expectations."
        r_specific = _reward(specific, secret)
        r_vague = _reward(vague, secret)
        assert r_specific["reward"] > r_vague["reward"]

    def test_reward_rounds_to_4_decimal_places(self):
        r = _reward("hypothesis", "secret")
        s = str(r["reward"])
        if "." in s:
            assert len(s.split(".")[1]) <= 4

    def test_all_bonuses_combined_dont_exceed_1(self):
        secret = "something"
        r = _reward(
            secret, secret,
            n_q=1, max_q=8,
            cat_pred="factual", cat_true="factual",
            keywords=["something"],
        )
        assert r["reward"] <= 1.0
