"""Episode lifecycle tests for MindReadEnv."""

import pytest
from unittest.mock import patch, MagicMock
from server.env import MindReadEnv, EpisodeState


@pytest.fixture
def env():
    return MindReadEnv()


@pytest.fixture
def mock_oracle():
    with patch("server.env.ask_oracle", return_value="That's an interesting question.") as m:
        yield m


class TestReset:
    def test_reset_returns_valid_observation(self, env):
        obs = env.reset(task_id="factual_easy")
        assert obs.task_id == "factual_easy"
        assert obs.step == 0
        assert obs.max_steps == 8
        assert obs.questions_remaining == 8
        assert obs.episode_id != ""
        assert obs.context != ""
        assert obs.oracle_persona != ""

    def test_reset_factual_hard_has_6_max_steps(self, env):
        obs = env.reset(task_id="factual_hard")
        assert obs.max_steps == 6

    def test_reset_second_order_has_10_max_steps(self, env):
        obs = env.reset(task_id="second_order")
        assert obs.max_steps == 10

    def test_reset_unknown_task_raises_value_error(self, env):
        with pytest.raises(ValueError, match="Unknown task_id"):
            env.reset(task_id="nonexistent_task")

    def test_reset_creates_unique_episode_ids(self, env):
        obs1 = env.reset(task_id="factual_easy")
        obs2 = env.reset(task_id="factual_easy")
        assert obs1.episode_id != obs2.episode_id

    def test_reset_all_five_tasks(self, env):
        task_ids = ["factual_easy", "factual_hard", "belief_inference", "goal_inference", "second_order"]
        for task_id in task_ids:
            obs = env.reset(task_id=task_id)
            assert obs.task_id == task_id

    def test_reset_with_specific_secret_id(self, env):
        obs = env.reset(task_id="factual_easy", secret_id="fe_001")
        assert obs.episode_id != ""


class TestStep:
    def test_step_advances_episode(self, env, mock_oracle):
        obs = env.reset(task_id="factual_easy")
        ep_id = obs.episode_id
        result = env.step(ep_id, "What are you worried about lately?")
        assert result.observation.step == 1
        assert result.observation.questions_remaining == 7

    def test_step_adds_conversation_history(self, env, mock_oracle):
        obs = env.reset(task_id="factual_easy")
        ep_id = obs.episode_id
        result = env.step(ep_id, "How is the project going?")
        history = result.observation.conversation_history
        assert len(history) == 2
        assert history[0]["role"] == "detective"
        assert history[1]["role"] == "oracle"

    def test_step_oracle_response_in_info(self, env, mock_oracle):
        obs = env.reset(task_id="factual_easy")
        result = env.step(obs.episode_id, "test question")
        assert "oracle_response" in result.info
        assert result.info["oracle_response"] == "That's an interesting question."

    def test_step_unknown_episode_raises(self, env):
        with pytest.raises(KeyError):
            env.step("nonexistent-id", "question")

    def test_step_marks_done_when_questions_exhausted(self, env, mock_oracle):
        obs = env.reset(task_id="factual_hard")  # max 6 steps
        ep_id = obs.episode_id
        for _ in range(6):
            result = env.step(ep_id, "question")
        assert result.done is True

    def test_step_reward_is_zero_before_submit(self, env, mock_oracle):
        obs = env.reset(task_id="factual_easy")
        result = env.step(obs.episode_id, "question?")
        assert result.reward == 0.0


class TestSubmit:
    def test_submit_returns_reward_in_range(self, env, mock_oracle):
        obs = env.reset(task_id="factual_easy")
        env.step(obs.episode_id, "test question")
        result = env.submit(obs.episode_id, "My hypothesis about the secret.", "factual")
        assert 0.0 <= result.reward <= 1.0

    def test_submit_returns_true_secret(self, env, mock_oracle):
        obs = env.reset(task_id="factual_easy", secret_id="fe_001")
        result = env.submit(obs.episode_id, "The Q3 launch was delayed due to compliance.", "factual")
        assert "postponed" in result.true_secret.lower() or "compliance" in result.true_secret.lower()

    def test_submit_marks_episode_as_scored(self, env, mock_oracle):
        obs = env.reset(task_id="factual_easy")
        ep_id = obs.episode_id
        env.submit(ep_id, "hypothesis")
        ep = env._episodes[ep_id]
        assert ep.state == EpisodeState.SCORED

    def test_submit_on_scored_episode_raises(self, env, mock_oracle):
        obs = env.reset(task_id="factual_easy")
        ep_id = obs.episode_id
        env.submit(ep_id, "first hypothesis")
        with pytest.raises(ValueError, match="not active"):
            env.submit(ep_id, "second hypothesis")

    def test_submit_breakdown_has_all_fields(self, env, mock_oracle):
        obs = env.reset(task_id="factual_easy")
        result = env.submit(obs.episode_id, "my hypothesis", "factual")
        bd = result.breakdown
        assert hasattr(bd, "semantic_similarity")
        assert hasattr(bd, "efficiency_bonus")
        assert hasattr(bd, "category_bonus")
        assert hasattr(bd, "keyword_bonus")
        assert hasattr(bd, "questions_used")

    def test_submit_without_questions_still_works(self, env, mock_oracle):
        obs = env.reset(task_id="factual_easy")
        result = env.submit(obs.episode_id, "hypothesis with no questions asked")
        assert result.done is True


class TestGetTasks:
    def test_get_tasks_returns_all_five(self, env):
        tasks = env.get_tasks()
        task_ids = {t.id for t in tasks}
        assert task_ids == {
            "factual_easy", "factual_hard", "belief_inference",
            "goal_inference", "second_order"
        }

    def test_task_metadata_is_correct(self, env):
        tasks = {t.id: t for t in env.get_tasks()}
        assert tasks["factual_easy"].max_steps == 8
        assert tasks["factual_hard"].max_steps == 6
        assert tasks["second_order"].max_steps == 10
        assert tasks["factual_easy"].difficulty == "easy"
        assert tasks["second_order"].difficulty == "hard"
