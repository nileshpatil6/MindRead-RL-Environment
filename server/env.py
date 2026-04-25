import json
import random
import uuid
from pathlib import Path
from enum import Enum

from server.models import (
    Secret,
    MindReadObservation,
    StepResult,
    SubmitResult,
    RewardBreakdown,
    TaskMeta,
)
from server.oracle import ask_oracle
from server.reward import compute_reward

SECRETS_PATH = Path(__file__).parent / "data" / "secrets.json"

TASK_META: dict[str, TaskMeta] = {
    "factual_easy": TaskMeta(
        id="factual_easy",
        description="Infer a hidden factual workplace secret (easy) — event, decision, or fact the Oracle knows but hasn't announced.",
        max_steps=8,
        reward_range=[0.0, 1.0],
        difficulty="easy",
        category="factual",
    ),
    "factual_hard": TaskMeta(
        id="factual_hard",
        description="Infer a precise numerical or date-bound secret. Requires specific inference, not just general direction.",
        max_steps=6,
        reward_range=[0.0, 1.0],
        difficulty="hard",
        category="factual",
    ),
    "belief_inference": TaskMeta(
        id="belief_inference",
        description="Infer what the Oracle believes about another person's internal state — emotions, plans, or intentions.",
        max_steps=8,
        reward_range=[0.0, 1.0],
        difficulty="medium",
        category="belief",
    ),
    "goal_inference": TaskMeta(
        id="goal_inference",
        description="Infer the Oracle's hidden personal or professional ambition they haven't disclosed to the team.",
        max_steps=8,
        reward_range=[0.0, 1.0],
        difficulty="medium",
        category="goal",
    ),
    "second_order": TaskMeta(
        id="second_order",
        description="Infer a recursive belief: what the Oracle believes someone else believes — second-order Theory of Mind.",
        max_steps=10,
        reward_range=[0.0, 1.0],
        difficulty="hard",
        category="second_order",
    ),
}

TASK_DESCRIPTION = {
    "factual_easy": (
        "Figure out what factual information the Oracle is privately aware of "
        "but has not publicly disclosed. Ask indirect, strategic questions."
    ),
    "factual_hard": (
        "Infer a specific fact (number, date, or precise detail) the Oracle knows privately. "
        "You need precision — vague guesses score low."
    ),
    "belief_inference": (
        "Determine what the Oracle believes about another person's state of mind, "
        "intentions, or emotional situation. The belief may not be stated but can be inferred."
    ),
    "goal_inference": (
        "Infer the Oracle's hidden personal ambition or undisclosed professional goal. "
        "They won't tell you directly but their answers will reveal it."
    ),
    "second_order": (
        "Determine what the Oracle believes that ANOTHER PERSON believes or thinks. "
        "This is second-order Theory of Mind — you must infer a belief about a belief."
    ),
}


class EpisodeState(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    SCORED = "scored"


class Episode:
    def __init__(self, episode_id: str, secret: Secret, task_id: str):
        self.episode_id = episode_id
        self.secret = secret
        self.task_id = task_id
        self.state = EpisodeState.ACTIVE
        self.conversation_history: list[dict] = []
        self.step = 0
        self.max_steps = TASK_META[task_id].max_steps
        self.reward: float | None = None
        self.breakdown: RewardBreakdown | None = None

    def questions_remaining(self) -> int:
        return max(0, self.max_steps - self.step)

    def to_observation(self) -> MindReadObservation:
        return MindReadObservation(
            episode_id=self.episode_id,
            task_id=self.task_id,
            step=self.step,
            max_steps=self.max_steps,
            context=self.secret.context,
            oracle_persona=self.secret.persona,
            conversation_history=list(self.conversation_history),
            questions_remaining=self.questions_remaining(),
            task_description=TASK_DESCRIPTION[self.task_id],
        )


class MindReadEnv:
    def __init__(self):
        self._secrets: dict[str, list[Secret]] = {}
        self._episodes: dict[str, Episode] = {}
        self._load_secrets()

    def _load_secrets(self):
        raw = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
        for item in raw:
            s = Secret(**item)
            self._secrets.setdefault(s.task_id, []).append(s)

    def get_tasks(self) -> list[TaskMeta]:
        return list(TASK_META.values())

    def reset(self, task_id: str, secret_id: str | None = None) -> MindReadObservation:
        if task_id not in TASK_META:
            raise ValueError(f"Unknown task_id: {task_id}")

        pool = self._secrets.get(task_id, [])
        if not pool:
            raise RuntimeError(f"No secrets available for task: {task_id}")

        if secret_id:
            candidates = [s for s in pool if s.id == secret_id]
            if not candidates:
                raise ValueError(f"secret_id {secret_id!r} not found in task {task_id!r}")
            secret = candidates[0]
        else:
            secret = random.choice(pool)

        episode_id = str(uuid.uuid4())
        ep = Episode(episode_id=episode_id, secret=secret, task_id=task_id)
        self._episodes[episode_id] = ep
        return ep.to_observation()

    def step(self, episode_id: str, question: str) -> StepResult:
        ep = self._get_active(episode_id)

        if ep.questions_remaining() == 0:
            obs = ep.to_observation()
            return StepResult(
                observation=obs,
                reward=0.0,
                done=True,
                info={"error": "No questions remaining. Please submit a hypothesis."},
            )

        oracle_answer = ask_oracle(ep.secret, ep.conversation_history, question)
        ep.conversation_history.append({"role": "detective", "content": question})
        ep.conversation_history.append({"role": "oracle", "content": oracle_answer})
        ep.step += 1

        done = ep.questions_remaining() == 0
        obs = ep.to_observation()
        return StepResult(
            observation=obs,
            reward=0.0,
            done=done,
            info={"oracle_response": oracle_answer},
        )

    def submit(
        self,
        episode_id: str,
        hypothesis: str,
        category_prediction: str | None = None,
    ) -> SubmitResult:
        ep = self._get_active(episode_id)

        result = compute_reward(
            hypothesis=hypothesis,
            true_secret=ep.secret.content,
            n_questions_used=ep.step,
            max_questions=ep.max_steps,
            category_predicted=category_prediction,
            category_true=ep.secret.category,
            hint_keywords=ep.secret.hint_keywords,
        )

        breakdown = RewardBreakdown(
            reward=result["reward"],
            semantic_similarity=result["components"]["semantic"],
            efficiency_bonus=result["components"]["efficiency"],
            category_bonus=result["components"]["category_bonus"],
            keyword_bonus=result["components"]["keyword_bonus"],
            questions_used=ep.step,
            hypothesis=hypothesis,
        )

        ep.reward = result["reward"]
        ep.breakdown = breakdown
        ep.state = EpisodeState.SCORED

        return SubmitResult(
            reward=result["reward"],
            breakdown=breakdown,
            true_secret=ep.secret.content,
            episode_id=episode_id,
            done=True,
        )

    def get_state(self, episode_id: str) -> MindReadObservation:
        if episode_id not in self._episodes:
            raise KeyError(f"Episode {episode_id!r} not found")
        return self._episodes[episode_id].to_observation()

    def add_secret(self, secret: Secret):
        self._secrets.setdefault(secret.task_id, []).append(secret)

    def _get_active(self, episode_id: str) -> Episode:
        if episode_id not in self._episodes:
            raise KeyError(f"Episode {episode_id!r} not found")
        ep = self._episodes[episode_id]
        if ep.state != EpisodeState.ACTIVE:
            raise ValueError(f"Episode {episode_id!r} is in state {ep.state.value}, not active")
        return ep
