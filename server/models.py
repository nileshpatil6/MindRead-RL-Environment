from pydantic import BaseModel, Field
from typing import Literal, Optional


class Secret(BaseModel):
    id: str
    task_id: str
    content: str
    persona: str
    context: str
    difficulty: float
    category: str
    red_herrings: list[str]
    hint_keywords: list[str]


class TaskMeta(BaseModel):
    id: str
    description: str
    max_steps: int
    reward_range: list[float]
    difficulty: str
    category: str


class MindReadObservation(BaseModel):
    episode_id: str
    task_id: str
    step: int
    max_steps: int
    context: str
    oracle_persona: str
    conversation_history: list[dict]
    questions_remaining: int
    task_description: str


class AskQuestionAction(BaseModel):
    action: Literal["ask_question", "submit_hypothesis"]
    question: Optional[str] = None
    hypothesis: Optional[str] = None
    category_prediction: Optional[Literal[
        "factual", "belief", "goal", "second_order"
    ]] = None


class StepResult(BaseModel):
    observation: MindReadObservation
    reward: float = 0.0
    done: bool
    info: dict


class RewardBreakdown(BaseModel):
    reward: float
    semantic_similarity: float
    efficiency_bonus: float
    category_bonus: float
    keyword_bonus: float
    questions_used: int
    hypothesis: str


class SubmitResult(BaseModel):
    reward: float
    breakdown: RewardBreakdown
    true_secret: str
    episode_id: str
    done: bool = True


class GenerateSecretRequest(BaseModel):
    category: Literal["factual", "belief", "goal", "second_order"]
    difficulty: float = Field(ge=0.0, le=1.0)
    domain: str = "tech startup"


class HealthResponse(BaseModel):
    status: str
    version: str
    oracle_backend: str
