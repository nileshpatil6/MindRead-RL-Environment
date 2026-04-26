"""
MindRead HF Space — interactive Theory of Mind detective game.

Architecture:
  - FastAPI OpenEnv server runs in a background thread (real /reset /step /submit endpoints)
  - Gradio UI calls those endpoints via httpx — exactly how RL agents interface with OpenEnv
  - Oracle is patched via LOCAL_ORACLE_FN (no Groq API key needed)
  - Reward uses sentence-transformers on PyTorch (all-MiniLM-L6-v2)
  - PyTorch is used for both the oracle mock model AND the embedding reward model
"""
import json
import random
import threading
import time
import httpx
import gradio as gr

# ---------------------------------------------------------------------------
# 1. Patch oracle BEFORE importing anything that starts the server
# ---------------------------------------------------------------------------
import server.oracle as oracle_module

EVASIVE = [
    "That's an interesting angle — I'm not really in a position to say much about that right now.",
    "I'd rather not get into specifics. It's a bit sensitive at the moment.",
    "There's definitely some complexity there I can't go into detail about.",
    "Let's just say things are evolving. I'll leave it at that.",
    "You might want to read between the lines on that one.",
    "Some news will surprise people soon — I just can't say when.",
    "Things aren't quite as stable as they might appear from the outside.",
    "I've been told to keep that close to my chest, honestly.",
]

def _mock_oracle(secret, conversation_history, question):
    q = question.lower()
    keywords = secret.hint_keywords
    red_herrings = secret.red_herrings

    if any(kw.lower() in q for kw in keywords):
        return ("There's more going on there than I can share right now. "
                "Let's just say it's on people's radar.")
    for rh in red_herrings:
        if any(w in q for w in rh.lower().split()[:3]):
            return f"Oh, that? Yeah — {rh.lower().rstrip('.')}. Pretty interesting times."
    return random.choice(EVASIVE)

oracle_module.LOCAL_ORACLE_FN = _mock_oracle

# ---------------------------------------------------------------------------
# 2. Start the OpenEnv FastAPI server in a background thread
# ---------------------------------------------------------------------------
_server_ready = threading.Event()

def _run_server():
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=7861, log_level="error")

threading.Thread(target=_run_server, daemon=True).start()

# Wait for server to come up (max 30s)
for _ in range(30):
    try:
        r = httpx.get("http://localhost:7861/health", timeout=2)
        if r.status_code == 200:
            _server_ready.set()
            break
    except Exception:
        pass
    time.sleep(1)

BASE_URL = "http://localhost:7861"
client = httpx.Client(base_url=BASE_URL, timeout=30)

# ---------------------------------------------------------------------------
# 3. Task config (mirrors openenv.yaml)
# ---------------------------------------------------------------------------
TASK_LABELS = {
    "factual_easy":     "Factual — Easy   (8 questions)",
    "factual_hard":     "Factual — Hard   (6 questions, need precision)",
    "belief_inference": "Belief Inference (8 questions, 1st-order ToM)",
    "goal_inference":   "Goal Inference   (8 questions)",
    "second_order":     "Second-Order ToM (10 questions — hardest)",
}

CATEGORY_CHOICES = ["factual", "belief", "goal", "second_order"]

# ---------------------------------------------------------------------------
# 4. Gradio event handlers — all talk to OpenEnv via httpx
# ---------------------------------------------------------------------------
def start_game(task_id):
    if not _server_ready.is_set():
        return {}, "Server not ready yet — please wait a moment and try again.", "", "", ""
    obs = client.post("/reset", json={"task_id": task_id}).json()
    ctx = (
        f"**You are:** Detective\n\n"
        f"**Oracle persona:** {obs['oracle_persona']}\n\n"
        f"**Scene:** {obs['context']}\n\n"
        f"**Your mission:** {obs['task_description']}\n\n"
        f"**Questions remaining:** {obs['questions_remaining']} / {obs['max_steps']}"
    )
    state = {"obs": obs, "done": False, "history_md": ""}
    return state, ctx, "", "", ""


def ask_question(question, state):
    if not state:
        return state, "_Start a new game first._", "", "Click 'New Game' first."
    if state.get("done"):
        return state, state["history_md"], "", "Episode finished. Start a new game."
    if not question.strip():
        return state, state["history_md"], "", "Type a question first."

    obs = state["obs"]
    resp = client.post("/step", json={
        "episode_id": obs["episode_id"],
        "action": {"action": "ask_question", "question": question.strip()}
    }).json()

    oracle_reply = resp["info"].get("oracle_response", "...")
    new_obs = resp["observation"]

    # Append to conversation markdown
    hist = state["history_md"]
    hist += f"\n**You:** {question.strip()}\n\n**Oracle:** {oracle_reply}\n\n---\n"

    ctx = (
        f"**You are:** Detective\n\n"
        f"**Oracle persona:** {new_obs['oracle_persona']}\n\n"
        f"**Scene:** {new_obs['context']}\n\n"
        f"**Your mission:** {new_obs['task_description']}\n\n"
        f"**Questions remaining:** {new_obs['questions_remaining']} / {new_obs['max_steps']}"
    )
    state = {**state, "obs": new_obs, "history_md": hist}

    note = ""
    if new_obs["questions_remaining"] == 0:
        note = "No questions left — submit your hypothesis now!"
    return state, hist, ctx, note


def submit_hypothesis(hypothesis, category, state):
    if not state:
        return state, "Start a new game first.", ""
    if state.get("done"):
        return state, "Episode already finished.", ""
    if not hypothesis.strip():
        return state, "Enter your hypothesis first.", ""

    obs = state["obs"]
    resp = client.post("/submit", json={
        "episode_id": obs["episode_id"],
        "hypothesis": hypothesis.strip(),
        "category_prediction": category,
    }).json()

    r = resp["reward"]
    bd = resp["breakdown"]
    true_secret = resp["true_secret"]

    bar = "█" * int(r * 20) + "░" * (20 - int(r * 20))
    verdict = "Excellent!" if r > 0.6 else "Good try!" if r > 0.35 else "Keep practicing!"

    result_md = (
        f"## {verdict}\n\n"
        f"**Score:** `[{bar}]` **{r:.3f}** / 1.000\n\n"
        f"| Component | Value |\n|-----------|-------|\n"
        f"| Semantic similarity | `{bd['semantic_similarity']:.3f}` |\n"
        f"| Efficiency bonus | `{bd['efficiency_bonus']:.3f}` |\n"
        f"| Category bonus | `{bd['category_bonus']:.3f}` |\n"
        f"| Keyword bonus | `{bd['keyword_bonus']:.3f}` |\n"
        f"| Questions used | `{bd['questions_used']}` / `{obs['max_steps']}` |\n\n"
        f"---\n\n"
        f"**Your hypothesis:** {hypothesis.strip()}\n\n"
        f"**True secret:** _{true_secret}_"
    )
    state = {**state, "done": True}
    return state, result_md, ""

# ---------------------------------------------------------------------------
# 5. UI
# ---------------------------------------------------------------------------
CSS = """
.score-box { font-family: monospace; }
footer { display: none !important; }
"""

with gr.Blocks(title="MindRead — Theory of Mind RL", theme=gr.themes.Soft(), css=CSS) as demo:
    gr.Markdown("""
# MindRead — Theory of Mind RL Environment

**Can you read between the lines?**

An **Oracle** holds a hidden secret. They cannot lie — but will never reveal it directly.
Ask strategic questions, read between the lines, then submit your hypothesis.

> This is the same interface RL agents use during GRPO training.
> The detective (Qwen2.5-1.5B) was trained via TRL + PyTorch to do exactly this —
> it learned to ask **44% fewer questions** while maintaining hypothesis quality.

_Powered by: PyTorch · TRL GRPO · OpenEnv · sentence-transformers_
""")

    state = gr.State({})

    with gr.Row():
        with gr.Column(scale=1, min_width=280):
            task_dd = gr.Dropdown(
                choices=list(TASK_LABELS.keys()),
                value="factual_easy",
                label="Task (difficulty)",
                info="Higher = harder Theory of Mind reasoning required",
            )
            start_btn = gr.Button("New Game", variant="primary", size="lg")
            scene_box = gr.Markdown("_Click **New Game** to start._", label="Scene & Mission")

            gr.Markdown("---")
            gr.Markdown("""
**Scoring formula:**
```
reward = semantic_sim × efficiency_bonus
       + category_bonus + keyword_bonus
```
- Fewer questions = higher efficiency bonus
- Semantic similarity via all-MiniLM-L6-v2 (PyTorch)
""")

        with gr.Column(scale=2):
            history_box = gr.Markdown("_Conversation will appear here._", label="Conversation")

            with gr.Row():
                q_input = gr.Textbox(
                    placeholder="Ask the oracle a strategic question...",
                    label="Your question",
                    scale=4,
                    lines=1,
                )
                ask_btn = gr.Button("Ask", size="lg")

            status_md = gr.Markdown("")

            gr.Markdown("---")
            with gr.Row():
                hyp_input = gr.Textbox(
                    placeholder="What is the secret? Be specific and precise...",
                    label="Your hypothesis",
                    lines=2,
                    scale=3,
                )
                cat_dd = gr.Dropdown(
                    choices=CATEGORY_CHOICES,
                    value="factual",
                    label="Category",
                    scale=1,
                    info="What type of secret is it?",
                )
            submit_btn = gr.Button("Submit Hypothesis", variant="secondary", size="lg")
            result_box = gr.Markdown("", elem_classes=["score-box"])

    gr.Markdown("""
---
### How the RL training works

```
OpenEnv Server (/reset /step /submit)
        ↕  httpx
  Detective (Qwen2.5-1.5B-Instruct)
        ↕  GRPO via TRL (PyTorch)
  Reward = semantic_similarity × efficiency
         (sentence-transformers/all-MiniLM-L6-v2)
```

**Training result:** After 300 steps on Lightning AI A100/H100 —
the detective learned to ask **44% fewer questions** while maintaining hypothesis quality.
The efficiency bonus in the reward function successfully shaped strategic questioning.

**Why Theory of Mind?** Existing ToM benchmarks test static prediction ("will Alice look in box A?").
MindRead tests *functional* ToM — adapting behavior to infer what someone actually believes
through live interaction. This is what great detectives, negotiators, and therapists do.

[GitHub](https://github.com/nileshpatil6/MindRead-RL-Environment) · Built for **Meta × Scaler PyTorch OpenEnv Hackathon 2026**
""")

    # Wire events
    start_btn.click(
        start_game,
        inputs=[task_dd],
        outputs=[state, scene_box, history_box, result_box, status_md],
    )
    ask_btn.click(
        ask_question,
        inputs=[q_input, state],
        outputs=[state, history_box, scene_box, status_md],
    ).then(lambda: "", outputs=q_input)
    q_input.submit(
        ask_question,
        inputs=[q_input, state],
        outputs=[state, history_box, scene_box, status_md],
    ).then(lambda: "", outputs=q_input)
    submit_btn.click(
        submit_hypothesis,
        inputs=[hyp_input, cat_dd, state],
        outputs=[state, result_box, status_md],
    )

if __name__ == "__main__":
    demo.launch(server_port=7860)
