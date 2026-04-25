from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import os

from dotenv import load_dotenv

load_dotenv()

from server.env import MindReadEnv
from server.models import (
    MindReadObservation,
    StepResult,
    SubmitResult,
    TaskMeta,
    Secret,
    GenerateSecretRequest,
    HealthResponse,
    AskQuestionAction,
)
from server.secret_generator import generate_secret

env = MindReadEnv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # warm up the embedding model on startup
    from server.reward import get_embedder
    get_embedder()
    yield


app = FastAPI(
    title="MindRead: Theory of Mind RL Environment",
    version="1.0.0",
    description=(
        "Interactive Theory of Mind training environment. "
        "An LLM agent (Detective) must infer a hidden mental state "
        "by asking strategic questions to an Oracle. "
        "Trains functional theory of mind — the ability to adapt questioning "
        "strategy based on Oracle responses."
    ),
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        version="1.0.0",
        oracle_backend="groq/llama-3.1-8b-instant",
    )


@app.get("/tasks", response_model=list[TaskMeta])
def get_tasks():
    return env.get_tasks()


class ResetRequest(BaseModel):
    task_id: str
    secret_id: Optional[str] = None


@app.post("/reset", response_model=MindReadObservation)
def reset(request: ResetRequest):
    try:
        return env.reset(task_id=request.task_id, secret_id=request.secret_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


class StepRequest(BaseModel):
    episode_id: str
    action: AskQuestionAction


@app.post("/step", response_model=StepResult)
def step(request: StepRequest):
    action = request.action
    if action.action != "ask_question":
        raise HTTPException(
            status_code=400,
            detail="Use /submit to submit a hypothesis. /step only accepts ask_question.",
        )
    if not action.question or not action.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty.")
    try:
        return env.step(request.episode_id, action.question.strip())
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class SubmitRequest(BaseModel):
    episode_id: str
    hypothesis: str
    category_prediction: Optional[str] = None


@app.post("/submit", response_model=SubmitResult)
def submit(request: SubmitRequest):
    if not request.hypothesis or not request.hypothesis.strip():
        raise HTTPException(status_code=400, detail="Hypothesis must not be empty.")
    try:
        return env.submit(
            episode_id=request.episode_id,
            hypothesis=request.hypothesis.strip(),
            category_prediction=request.category_prediction,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/state/{episode_id}", response_model=MindReadObservation)
def get_state(episode_id: str):
    try:
        return env.get_state(episode_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/generate_secret")
def generate_secret_endpoint(request: GenerateSecretRequest):
    try:
        secret_data = generate_secret(
            category=request.category,
            difficulty=request.difficulty,
            domain=request.domain,
        )
        secret = Secret(**secret_data)
        env.add_secret(secret)

        obs = env.reset(task_id=secret.task_id, secret_id=secret.id)
        return {"secret": secret_data, "episode_id": obs.episode_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
