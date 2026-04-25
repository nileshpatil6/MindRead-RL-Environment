"""
OpenEnv adapter that converts MindRead multi-turn episodes into
single GRPO trajectories. The Detective generates the ENTIRE
conversation (all questions + hypothesis) in one completion,
formatted as a structured dialogue. The reward function parses
the response, executes it against the Oracle, and returns the final score.
"""

import asyncio
import re
import httpx
from dataclasses import dataclass


DETECTIVE_SYSTEM = """\
You are a Detective. Your job is to figure out what an Oracle is secretly \
thinking, knowing, or intending — by asking indirect, strategic questions.

The Oracle follows these rules:
- They CANNOT reveal their secret directly.
- Everything they say is TRUE — they can deflect but not lie.
- They respond naturally, like a professional in a real conversation.

Your job is to ask questions that narrow down possibilities. \
Think contrastively: if two different secrets would produce the SAME answer, \
that question gives you no information. Ask questions where different secrets \
would produce DIFFERENT answers.

Output format — use these exact XML tags:
<think>
  Your step-by-step reasoning about what questions to ask and why.
</think>
<question>Your first question here</question>
<question>Your second question here (optional)</question>
... (up to max_steps questions total)
<hypothesis>
Category: factual|belief|goal|second_order
[Your final hypothesis about the Oracle's secret/belief/goal in 2-4 sentences]
</hypothesis>

Rules:
- You MUST end with a <hypothesis> block.
- Ask AT MOST {max_steps} questions (fewer = efficiency bonus).
- Ask the most informative questions first.
- The hypothesis should be specific, not vague.\
"""

DETECTIVE_USER_TEMPLATE = """\
Context: {context}
Oracle's role: {oracle_persona}
Task: {task_description}
Max questions allowed: {max_steps}

Begin your investigation now.\
"""


@dataclass
class EpisodeResult:
    episode_id: str
    reward: float
    questions_asked: int
    hypothesis: str
    true_secret: str
    conversation: list[dict]
    breakdown: dict


class MindReadGRPOEnv:
    def __init__(self, base_url: str = "http://localhost:7860"):
        self.base_url = base_url.rstrip("/")

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=60.0)

    def reset(self, task_id: str, secret_id: str | None = None) -> dict:
        with self._client() as c:
            r = c.post("/reset", json={"task_id": task_id, "secret_id": secret_id})
            r.raise_for_status()
            return r.json()

    def step(self, episode_id: str, question: str) -> dict:
        with self._client() as c:
            r = c.post("/step", json={
                "episode_id": episode_id,
                "action": {"action": "ask_question", "question": question},
            })
            r.raise_for_status()
            return r.json()

    def submit(self, episode_id: str, hypothesis: str, category: str | None = None) -> dict:
        with self._client() as c:
            r = c.post("/submit", json={
                "episode_id": episode_id,
                "hypothesis": hypothesis,
                "category_prediction": category,
            })
            r.raise_for_status()
            return r.json()

    def build_prompt(self, obs: dict) -> tuple[str, str]:
        system = DETECTIVE_SYSTEM.format(max_steps=obs["max_steps"])
        user = DETECTIVE_USER_TEMPLATE.format(
            context=obs["context"],
            oracle_persona=obs["oracle_persona"],
            task_description=obs["task_description"],
            max_steps=obs["max_steps"],
        )
        return system, user

    def parse_completion(self, completion: str) -> tuple[list[str], str, str | None]:
        questions = re.findall(r"<question>(.*?)</question>", completion, re.DOTALL)
        questions = [q.strip() for q in questions if q.strip()]

        hyp_match = re.search(r"<hypothesis>(.*?)</hypothesis>", completion, re.DOTALL)
        hypothesis_raw = hyp_match.group(1).strip() if hyp_match else ""

        category = None
        cat_match = re.match(r"Category:\s*(factual|belief|goal|second_order)", hypothesis_raw, re.IGNORECASE)
        if cat_match:
            category = cat_match.group(1).lower()
            hypothesis = hypothesis_raw[cat_match.end():].strip()
        else:
            hypothesis = hypothesis_raw

        return questions, hypothesis, category

    def evaluate_completion(self, episode_id: str, completion: str, obs: dict) -> EpisodeResult:
        questions, hypothesis, category = self.parse_completion(completion)

        if not hypothesis:
            hypothesis = "Unable to determine the secret."

        conversation = []
        max_q = obs["max_steps"]

        for i, question in enumerate(questions[:max_q]):
            try:
                result = self.step(episode_id, question)
                oracle_answer = result["info"].get("oracle_response", "")
                conversation.append({"role": "detective", "content": question})
                conversation.append({"role": "oracle", "content": oracle_answer})
            except Exception:
                break

        try:
            submit_result = self.submit(episode_id, hypothesis, category)
            reward = submit_result["reward"]
            true_secret = submit_result["true_secret"]
            breakdown = submit_result["breakdown"]
        except Exception:
            reward = 0.0
            true_secret = ""
            breakdown = {}

        return EpisodeResult(
            episode_id=episode_id,
            reward=reward,
            questions_asked=len(questions),
            hypothesis=hypothesis,
            true_secret=true_secret,
            conversation=conversation,
            breakdown=breakdown,
        )
