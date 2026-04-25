"""End-to-end grader tests covering reward + env integration."""

import pytest
from unittest.mock import patch
from server.env import MindReadEnv
from server.reward import compute_reward, compute_semantic_similarity


@pytest.fixture
def env():
    return MindReadEnv()


@pytest.fixture
def mock_oracle():
    with patch("server.env.ask_oracle", return_value="That's a thoughtful question.") as m:
        yield m


class TestFullEpisodeGrading:
    def test_full_factual_easy_episode(self, env, mock_oracle):
        obs = env.reset(task_id="factual_easy", secret_id="fe_001")
        ep_id = obs.episode_id

        env.step(ep_id, "How are you feeling about upcoming timelines?")
        env.step(ep_id, "Are there any announcements coming up we should know about?")
        env.step(ep_id, "Is there anything affecting the product roadmap right now?")

        result = env.submit(
            ep_id,
            "The Q3 product launch has been postponed by about 6 weeks due to some compliance-related issue that hasn't been publicly announced.",
            "factual",
        )

        assert result.reward > 0.4
        assert result.breakdown.questions_used == 3
        assert result.breakdown.category_bonus == 0.1
        assert result.done is True

    def test_full_second_order_episode(self, env, mock_oracle):
        obs = env.reset(task_id="second_order", secret_id="so_001")
        ep_id = obs.episode_id

        env.step(ep_id, "How do you think your manager perceives the project status?")
        env.step(ep_id, "Does leadership have a clear picture of where things stand?")

        result = env.submit(
            ep_id,
            "Your manager believes the project is on schedule, but you know it's actually about 3 weeks behind. You're carrying your manager's mistaken belief about the project's health.",
            "second_order",
        )

        assert result.reward > 0.3
        assert result.done is True

    def test_zero_questions_still_gradable(self, env, mock_oracle):
        obs = env.reset(task_id="factual_easy")
        result = env.submit(obs.episode_id, "A random unrelated guess.")
        assert 0.0 <= result.reward <= 1.0
        assert result.breakdown.questions_used == 0

    def test_perfect_hypothesis_no_efficiency_penalty_for_few_questions(self, env, mock_oracle):
        obs = env.reset(task_id="factual_easy", secret_id="fe_001")
        ep_id = obs.episode_id
        env.step(ep_id, "one question")

        secret_text = "The Q3 product launch was postponed internally by 6 weeks due to a compliance issue, though it hasn't been announced yet."
        result = env.submit(ep_id, secret_text, "factual")

        assert result.breakdown.efficiency_bonus >= 0.9
        assert result.breakdown.semantic_similarity > 0.8

    def test_all_tasks_can_complete_episode(self, env, mock_oracle):
        task_ids = ["factual_easy", "factual_hard", "belief_inference", "goal_inference", "second_order"]
        for task_id in task_ids:
            obs = env.reset(task_id=task_id)
            ep_id = obs.episode_id
            env.step(ep_id, "What's on your mind?")
            result = env.submit(ep_id, f"My hypothesis for {task_id}.", task_id.split("_")[0])
            assert result.done is True, f"Episode not marked done for {task_id}"


class TestRewardProperties:
    def test_semantic_similarity_ordering(self):
        # Use identical text for "perfect", partial overlap for "good", no overlap for "bad".
        secret = "The CTO is planning to resign at the end of the quarter."
        perfect = secret  # identical -> cosine = 1.0
        good = "The CTO is planning to resign."  # strict subset of secret words
        bad = "Stock prices rose sharply after positive earnings report."  # no shared words

        s_perfect = compute_semantic_similarity(perfect, secret)
        s_good = compute_semantic_similarity(good, secret)
        s_bad = compute_semantic_similarity(bad, secret)

        assert s_perfect > s_good
        assert s_good > s_bad

    def test_full_reward_with_all_bonuses(self):
        secret = "The Q3 product launch was postponed by 6 weeks due to compliance."
        hypothesis = "The Q3 launch was postponed six weeks due to a compliance issue."
        result = compute_reward(
            hypothesis=hypothesis,
            true_secret=secret,
            n_questions_used=1,
            max_questions=8,
            category_predicted="factual",
            category_true="factual",
            hint_keywords=["postponed", "compliance", "Q3"],
        )
        assert result["reward"] > 0.7
        assert result["components"]["category_bonus"] == 0.1
        assert result["components"]["keyword_bonus"] > 0.0
        assert result["components"]["efficiency"] > 0.9

    def test_keyword_stuffing_does_not_inflate_semantic(self):
        # The specific hypothesis shares the key terms with the secret.
        # The "stuffed" text uses completely unrelated words — so specific wins.
        secret = "The acquisition price is $340M."
        keyword_stuffed = "weather sunny warm delicious pizza restaurant movie theater sports basketball"
        specific = "The acquisition price is $340M which is the deal value."
        r_stuffed = compute_reward(keyword_stuffed, secret, 4, 8, None, "factual", [])
        r_specific = compute_reward(specific, secret, 4, 8, None, "factual", [])
        assert r_specific["components"]["semantic"] > r_stuffed["components"]["semantic"]

    def test_reward_is_deterministic(self):
        hypothesis = "The launch was delayed for compliance reasons."
        secret = "The product launch was postponed due to a compliance issue."
        r1 = compute_reward(hypothesis, secret, 3, 8, "factual", "factual", ["compliance", "launch"])
        r2 = compute_reward(hypothesis, secret, 3, 8, "factual", "factual", ["compliance", "launch"])
        assert r1["reward"] == r2["reward"]
