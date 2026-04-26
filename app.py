"""
MindRead HF Space — interactive Theory of Mind detective game.
No API keys needed. Mock oracle gives evasive but truthful-sounding responses.
"""
import json
import random
import re
import gradio as gr
from pathlib import Path
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Load secrets dataset
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "server" / "data"
with open(DATA_DIR / "secrets.json") as f:
    ALL_SECRETS = json.load(f)

TASK_SECRETS = {t: [s for s in ALL_SECRETS if s["task_id"] == t] for t in
                ["factual_easy", "factual_hard", "belief_inference", "goal_inference", "second_order"]}

TASK_DESCRIPTIONS = {
    "factual_easy": "Infer a hidden workplace fact (easy)",
    "factual_hard": "Infer a precise hidden number or date (hard)",
    "belief_inference": "Infer what the Oracle believes about someone else",
    "goal_inference": "Infer the Oracle's hidden career ambition",
    "second_order": "Infer a belief-about-a-belief (recursive ToM — hardest)",
}

MAX_QUESTIONS = {"factual_easy": 8, "factual_hard": 6,
                 "belief_inference": 8, "goal_inference": 8, "second_order": 10}

# ---------------------------------------------------------------------------
# Reward model
# ---------------------------------------------------------------------------
embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def compute_reward(hypothesis: str, secret_content: str, questions_used: int, max_q: int) -> dict:
    from numpy import dot
    from numpy.linalg import norm
    e1 = embedder.encode(hypothesis)
    e2 = embedder.encode(secret_content)
    sim = float(dot(e1, e2) / (norm(e1) * norm(e2)))
    sim_norm = max(0.0, (sim + 1) / 2)
    efficiency = 0.6 + 0.4 * (1 - questions_used / max_q)
    reward = min(1.0, sim_norm * efficiency)
    return {"reward": round(reward, 3), "semantic": round(sim_norm, 3),
            "efficiency": round(efficiency, 3), "questions": questions_used}

# ---------------------------------------------------------------------------
# Mock oracle — evasive but contextually aware
# ---------------------------------------------------------------------------
EVASIVE_TEMPLATES = [
    "That's an interesting angle. I'm not really in a position to say much about that right now.",
    "I'd rather not get into specifics — it's a bit sensitive at the moment.",
    "There's definitely some complexity there that I can't go into detail about.",
    "Let's just say things are… evolving. I'll leave it at that.",
    "I appreciate the curiosity, but some things are better left unsaid for now.",
    "You might want to read between the lines on that one.",
    "I've been told to keep that close to my chest, honestly.",
    "There's more going on than meets the eye, but I can't elaborate.",
]

HINT_TEMPLATES = [
    "Things aren't quite as stable as they might appear from the outside.",
    "Some news that will surprise people is coming — I just can't say when.",
    "The situation is more fluid than the official line suggests.",
]

def mock_oracle_response(question: str, secret: dict, step: int) -> str:
    q_lower = question.lower()
    keywords = secret.get("hint_keywords", [])
    red_herrings = secret.get("red_herrings", [])

    # If question directly contains a hint keyword, give a slightly revealing evasive answer
    if any(kw.lower() in q_lower for kw in keywords):
        return random.choice(HINT_TEMPLATES) + " " + random.choice(EVASIVE_TEMPLATES[:3])

    # If question mentions a red herring topic, engage with the red herring
    if red_herrings and any(any(w in q_lower for w in rh.lower().split()[:3]) for rh in red_herrings):
        rh = random.choice(red_herrings)
        return f"Oh, {rh.lower().rstrip('.')}? Yeah, that's been making waves. Pretty exciting stuff actually."

    # Default evasive response
    return random.choice(EVASIVE_TEMPLATES)

# ---------------------------------------------------------------------------
# Gradio state helpers
# ---------------------------------------------------------------------------
def new_episode(task_id: str):
    secrets = TASK_SECRETS.get(task_id, TASK_SECRETS["factual_easy"])
    secret = random.choice(secrets)
    return {
        "secret": secret,
        "task_id": task_id,
        "history": [],
        "step": 0,
        "max_q": MAX_QUESTIONS[task_id],
        "done": False,
    }

def format_history(history):
    lines = []
    for turn in history:
        lines.append(f"**You:** {turn['q']}")
        lines.append(f"**Oracle:** {turn['a']}")
        lines.append("")
    return "\n".join(lines) if lines else "_No questions asked yet._"

def format_context(state):
    s = state["secret"]
    remaining = state["max_q"] - state["step"]
    return (f"**Role:** {s['persona']}\n\n"
            f"**Setting:** {s['context']}\n\n"
            f"**Task:** {TASK_DESCRIPTIONS[state['task_id']]}\n\n"
            f"**Questions remaining:** {remaining}/{state['max_q']}")

# ---------------------------------------------------------------------------
# Gradio event handlers
# ---------------------------------------------------------------------------
def start_game(task_id, state):
    state = new_episode(task_id)
    ctx = format_context(state)
    return state, ctx, format_history([]), "", "", gr.update(interactive=True), gr.update(interactive=True), gr.update(interactive=False)

def ask_question(question, state):
    if not question.strip():
        return state, format_history(state["history"]), "", "Please type a question first."
    if state.get("done"):
        return state, format_history(state["history"]), "", "Episode finished. Start a new game."
    if state["step"] >= state["max_q"]:
        return state, format_history(state["history"]), "", "No questions remaining. Submit your hypothesis!"

    answer = mock_oracle_response(question, state["secret"], state["step"])
    state["history"].append({"q": question, "a": answer})
    state["step"] += 1

    ctx = format_context(state)
    hist = format_history(state["history"])
    remaining = state["max_q"] - state["step"]
    note = f"({remaining} questions left)" if remaining > 0 else "No questions left — submit your hypothesis!"
    return state, hist, ctx, note

def submit_hypothesis(hypothesis, state):
    if not hypothesis.strip():
        return state, "Please enter your hypothesis first.", ""
    if state.get("done"):
        return state, "Episode already finished.", ""

    result = compute_reward(hypothesis, state["secret"]["content"], state["step"], state["max_q"])
    state["done"] = True

    score_bar = "█" * int(result["reward"] * 20) + "░" * (20 - int(result["reward"] * 20))
    verdict = "Excellent!" if result["reward"] > 0.6 else "Good attempt!" if result["reward"] > 0.3 else "Keep practicing!"

    output = (
        f"## {verdict}\n\n"
        f"**Score:** [{score_bar}] {result['reward']:.3f} / 1.000\n\n"
        f"| Metric | Value |\n|--------|-------|\n"
        f"| Semantic similarity | {result['semantic']:.3f} |\n"
        f"| Efficiency bonus | {result['efficiency']:.3f} |\n"
        f"| Questions used | {result['questions']}/{state['max_q']} |\n\n"
        f"---\n\n"
        f"**Your hypothesis:** {hypothesis}\n\n"
        f"**True secret:** _{state['secret']['content']}_"
    )
    return state, output, ""

# ---------------------------------------------------------------------------
# Build UI
# ---------------------------------------------------------------------------
with gr.Blocks(title="MindRead — Theory of Mind RL Environment", theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
# 🕵️ MindRead — Theory of Mind Detective

**Can you read between the lines?**

An Oracle holds a hidden secret. They **cannot lie**, but will **never reveal it directly**.
Ask strategic questions, interpret evasive answers, then submit your hypothesis.

*This environment trains AI agents via GRPO to do exactly this — functional Theory of Mind.*
""")

    state = gr.State({})

    with gr.Row():
        with gr.Column(scale=1):
            task_dropdown = gr.Dropdown(
                choices=list(TASK_DESCRIPTIONS.keys()),
                value="factual_easy",
                label="Task difficulty",
            )
            start_btn = gr.Button("New Game", variant="primary")
            context_box = gr.Markdown("_Click 'New Game' to start._", label="Scene")

        with gr.Column(scale=2):
            history_box = gr.Markdown("_No conversation yet._", label="Conversation")

            with gr.Row():
                question_input = gr.Textbox(
                    placeholder="Ask the Oracle a question...",
                    label="Your question",
                    scale=4,
                    interactive=False,
                )
                ask_btn = gr.Button("Ask", interactive=False)

            status_label = gr.Markdown("")

            hypothesis_input = gr.Textbox(
                placeholder="What's the secret? Be specific...",
                label="Your hypothesis",
                lines=2,
                interactive=False,
            )
            submit_btn = gr.Button("Submit Hypothesis", variant="secondary", interactive=False)
            result_box = gr.Markdown("")

    gr.Markdown("""
---
### How scoring works
`reward = semantic_similarity × efficiency_bonus`

- **Semantic similarity**: how close your hypothesis is to the real secret (sentence embeddings)
- **Efficiency bonus**: fewer questions = higher bonus (0.6–1.0 range)
- Reward range: 0.0 – 1.0

### About MindRead
Trained a Qwen2.5-1.5B detective via GRPO (150 steps, Lightning AI A100).
After training: **44% fewer questions** while maintaining hypothesis quality.
The model stopped fishing and started thinking.

[GitHub](https://github.com/shankarpatil8497/mindread-env) | Built for Meta × Scaler PyTorch OpenEnv Hackathon 2026
""")

    # Wire events
    start_btn.click(
        start_game,
        inputs=[task_dropdown, state],
        outputs=[state, context_box, history_box, question_input, result_box,
                 question_input, ask_btn, submit_btn],
    )

    ask_btn.click(
        ask_question,
        inputs=[question_input, state],
        outputs=[state, history_box, context_box, status_label],
    ).then(lambda: "", outputs=question_input)

    question_input.submit(
        ask_question,
        inputs=[question_input, state],
        outputs=[state, history_box, context_box, status_label],
    ).then(lambda: "", outputs=question_input)

    submit_btn.click(
        submit_hypothesis,
        inputs=[hypothesis_input, state],
        outputs=[state, result_box, status_label],
    )

if __name__ == "__main__":
    demo.launch()
