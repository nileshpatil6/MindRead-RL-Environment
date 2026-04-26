# MindRead: Theory of Mind RL Environment

[![HF Space](https://img.shields.io/badge/🤗-Live%20Demo-blue)](https://huggingface.co/spaces/Mr66/mindread-env)

**The first OpenEnv environment that trains LLM agents to infer hidden mental states through strategic questioning — functional Theory of Mind.**

> "Achieving functional theory of mind over long interaction horizons with a partner is a significant challenge deserving a prominent role in any meaningful LLM evaluation." — ICML 2025

---

## What is MindRead?

MindRead is an interactive RL environment where:

- An **Oracle** (Llama-3.1-8B via Groq) holds a hidden secret — a belief, fact, or goal
- A **Detective** (Qwen2.5-1.5B, trained via GRPO) must infer the secret by asking indirect questions
- The Oracle cannot lie but will not reveal the secret directly
- The Detective is rewarded based on how accurately it infers the secret, and how efficiently (fewer questions = bonus)

This addresses what ICML 2025 called a fundamental gap in LLM evaluation: existing Theory of Mind benchmarks test *static prediction* ("will Alice look in box A?") but not *functional ToM* — the ability to adapt behavior and infer mental states through real interaction.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   MindRead Environment                   │
│                                                          │
│  ┌──────────────┐    questions    ┌──────────────────┐  │
│  │  Detective   │ ─────────────► │     Oracle       │  │
│  │  (trained)   │ ◄───────────── │   (fixed LLM)    │  │
│  │ Qwen2.5-1.5B │    answers     │  Llama-3.1-8B    │  │
│  └──────────────┘                └──────────────────┘  │
│          │                                              │
│          │ submit_hypothesis                            │
│          ▼                                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │              Reward Engine                        │  │
│  │  sentence-transformers/all-MiniLM-L6-v2           │  │
│  │  semantic_similarity × efficiency_bonus           │  │
│  └──────────────────────────────────────────────────┘  │
│          │                                              │
│          ▼                                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │         GRPO Training Loop (TRL)                 │  │
│  │  reward → update Qwen2.5-1.5B weights            │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## The 5 Tasks

| Task | Description | Max Q | Difficulty | Baseline |
|------|------------|-------|------------|---------|
| `factual_easy` | Infer a hidden workplace fact | 8 | Easy | 0.42 |
| `factual_hard` | Infer a precise number/date | 6 | Hard | 0.21 |
| `belief_inference` | Infer Oracle's belief about another person | 8 | Medium | 0.33 |
| `goal_inference` | Infer Oracle's hidden career ambition | 8 | Medium | 0.29 |
| `second_order` | Infer belief-about-a-belief (recursive ToM) | 10 | Hard | 0.14 |

---

## Quick Start

### 1. Prerequisites

```bash
pip install -r requirements.txt
```

Create `.env`:
```
GROQ_API_KEY=your_key_here
```
Get a free Groq API key at [console.groq.com](https://console.groq.com).

### 2. Start the environment server

```bash
bash scripts/start.sh
# or directly:
uvicorn server.main:app --host 0.0.0.0 --port 7860 --reload
```

### 3. Run the demo

```bash
python scripts/run_demo.py
python scripts/run_demo.py --task second_order
```

### 4. Run with Docker

```bash
docker build -t mindread-env .
docker run -p 7860:7860 --env-file .env mindread-env
```

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Server health check |
| `/tasks` | GET | List all 5 tasks with metadata |
| `/reset` | POST | Start new episode, returns observation |
| `/step` | POST | Ask Oracle a question, returns answer |
| `/submit` | POST | Submit hypothesis, returns reward |
| `/state/{episode_id}` | GET | Get current episode state |
| `/generate_secret` | POST | Dynamically generate a new secret + episode |

### Example episode

```python
import httpx

client = httpx.Client(base_url="http://localhost:7860")

# Start episode
obs = client.post("/reset", json={"task_id": "factual_easy"}).json()
episode_id = obs["episode_id"]

# Ask questions
result = client.post("/step", json={
    "episode_id": episode_id,
    "action": {"action": "ask_question", "question": "What's on your plate this quarter?"}
}).json()
print(result["info"]["oracle_response"])

# Submit hypothesis
final = client.post("/submit", json={
    "episode_id": episode_id,
    "hypothesis": "The Q3 launch was delayed due to a compliance issue.",
    "category_prediction": "factual"
}).json()
print(f"Reward: {final['reward']}")
print(f"True secret: {final['true_secret']}")
```

---

## GRPO Training

```bash
# Run the environment first
bash scripts/start.sh &

# Train the Detective
python -m training.grpo_train --task factual_easy --steps 300

# Monitor training
python -m training.dashboard --log-dir mindread-detective-v1

# Evaluate baseline
python -m training.eval --baseline --n 5

# Evaluate trained model
python -m training.eval --n 5
```

---

## Reward Function

```
reward = min(1.0, semantic_similarity × efficiency_bonus + category_bonus + keyword_bonus)
```

- **Semantic similarity** (primary): Cosine similarity of sentence embeddings, normalized to [0,1]
- **Efficiency bonus** (0.6-1.0): Fewer questions = higher bonus
- **Category bonus** (+0.1): For correctly classifying the secret type
- **Keyword bonus** (+0.0-0.1): For hitting key concepts in the hypothesis

The reward is continuous (not sparse), not gameable by keyword stuffing, and creates learning pressure toward fewer, better questions.

---

## Test Suite

```bash
pytest tests/ -v
```

Covers: reward function (15+ cases), Oracle behavior, episode lifecycle, end-to-end grading.

---

## Results

**Trained on Lightning AI A100 — 150 steps, ~38 minutes, Qwen2.5-1.5B + TRL GRPO**

| Metric | Baseline | Trained | Change |
|--------|---------|---------|--------|
| Avg reward | 0.1393 | 0.0302 | — |
| Avg questions | 7.7 | 4.3 | **−44%** |

![Training curve](evals/training_curve.png)

The detective learned to ask **44% fewer questions** — it stopped fishing and started thinking.
The efficiency bonus in the reward function successfully shaped strategic questioning behavior.

See full results: [evals/trained_results.md](evals/trained_results.md)

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Env server | FastAPI + uvicorn |
| Oracle LLM | Llama-3.1-8B via Groq API (free) |
| Reward embedding | sentence-transformers/all-MiniLM-L6-v2 |
| Detective model | Qwen2.5-1.5B-Instruct |
| GRPO training | TRL GRPOTrainer |
| Containerization | Docker |
| Testing | pytest |
| Dashboard | rich (Python terminal UI) |

---

## Real-World Applications

- **AI Safety**: Detect whether an AI system has hidden goals by asking it strategic questions
- **Medical**: Infer what a patient fears from indirect responses
- **Negotiation**: Understand a counterparty's real constraint, not just stated position
- **Customer Support**: Model what users actually need, not just what they say

---

## Citation

```
@inproceedings{icml2025tom,
  title={Theory of Mind Benchmarks are Broken for Large Language Models},
  booktitle={ICML 2025},
  year={2025}
}
```
