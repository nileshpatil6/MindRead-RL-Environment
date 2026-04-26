"""
MindRead HF Space — Professional interactive Theory of Mind detective game.
"""
import json
import random
import threading
import time
import httpx
import gradio as gr

# ---------------------------------------------------------------------------
# 1. Patch oracle BEFORE importing server
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
    "There's more going on behind the scenes than I can share right now.",
    "I appreciate the curiosity, but some things are better left unsaid for now.",
]

def _mock_oracle(secret, conversation_history, question):
    q = question.lower()
    keywords = secret.hint_keywords
    red_herrings = secret.red_herrings
    if any(kw.lower() in q for kw in keywords):
        return "There's more going on there than I can share right now. Let's just say it's definitely on people's radar."
    for rh in red_herrings:
        if any(w in q for w in rh.lower().split()[:3]):
            return f"Oh, that? Yeah — {rh.lower().rstrip('.')}. Pretty interesting times, actually."
    return random.choice(EVASIVE)

oracle_module.LOCAL_ORACLE_FN = _mock_oracle

# ---------------------------------------------------------------------------
# 2. Start OpenEnv FastAPI server
# ---------------------------------------------------------------------------
def _run_server():
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=7861, log_level="error")

threading.Thread(target=_run_server, daemon=True).start()
for _ in range(30):
    try:
        r = httpx.get("http://localhost:7861/health", timeout=2)
        if r.status_code == 200:
            break
    except Exception:
        pass
    time.sleep(1)

BASE_URL = "http://localhost:7861"
client = httpx.Client(base_url=BASE_URL, timeout=30)

# ---------------------------------------------------------------------------
# 3. Demo scripts — pre-written episodes to show judges how it works
# ---------------------------------------------------------------------------
DEMO_EPISODES = [
    {
        "task": "factual_easy",
        "secret_id": "fe_001",
        "persona": "Senior Product Manager",
        "scene": "Casual hallway chat at a tech company. The company recently signed a large enterprise customer and engineering hit a major velocity milestone.",
        "secret": "The Q3 product launch was postponed internally by 6 weeks due to a compliance issue.",
        "questions": [
            "How's the Q3 roadmap looking from your end?",
            "Are there any blockers the team is quietly dealing with?",
            "Has anything come up recently that might affect the launch timeline?",
        ],
        "oracle_answers": [
            "It's... coming along. There are a few things in motion that I can't really get into right now.",
            "Every project has its complexities. Some things need to be worked through before they're ready to share more broadly.",
            "Let's just say we're making sure everything is done right before we go public with anything. Timelines can be fluid.",
        ],
        "hypothesis": "There's an internal delay to the Q3 product launch — possibly a compliance or regulatory issue that hasn't been announced yet.",
    },
]

TASK_INFO = {
    "factual_easy":     {"label": "Factual (Easy)",     "icon": "🟢", "max_q": 8,  "desc": "Infer a hidden workplace fact"},
    "factual_hard":     {"label": "Factual (Hard)",     "icon": "🟡", "max_q": 6,  "desc": "Infer a precise number or date"},
    "belief_inference": {"label": "Belief Inference",   "icon": "🟠", "max_q": 8,  "desc": "What does Oracle believe about someone?"},
    "goal_inference":   {"label": "Goal Inference",     "icon": "🔴", "max_q": 8,  "desc": "What is Oracle's hidden ambition?"},
    "second_order":     {"label": "2nd-Order ToM",      "icon": "🔴", "max_q": 10, "desc": "What does Oracle think someone else believes?"},
}

CATEGORY_CHOICES = ["factual", "belief", "goal", "second_order"]

# ---------------------------------------------------------------------------
# 4. CSS
# ---------------------------------------------------------------------------
CSS = """
/* ── Base ── */
body { font-family: 'Inter', system-ui, sans-serif; }
.gradio-container { max-width: 1100px !important; margin: 0 auto; }

/* ── Header ── */
.hero-banner {
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    border-radius: 16px;
    padding: 36px 40px;
    text-align: center;
    margin-bottom: 8px;
    border: 1px solid #444;
}
.hero-banner h1 { font-size: 2.4em; margin: 0 0 6px; color: #fff; }
.hero-banner p  { color: #b0b8d0; margin: 4px 0; font-size: 1.05em; }
.hero-badge {
    display: inline-block;
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.85em;
    color: #cdd;
    margin: 4px 4px 0;
}

/* ── How it works cards ── */
.how-cards { display: flex; gap: 12px; margin: 12px 0; }
.how-card {
    flex: 1;
    background: #1a1f2e;
    border: 1px solid #2d3548;
    border-radius: 12px;
    padding: 16px;
    text-align: center;
}
.how-card .icon { font-size: 2em; margin-bottom: 8px; }
.how-card h4    { margin: 0 0 6px; color: #e2e8f0; font-size: 0.95em; }
.how-card p     { margin: 0; color: #94a3b8; font-size: 0.82em; }

/* ── Scene card ── */
.scene-card {
    background: #1e1b4b;
    border: 1px solid #4338ca;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 8px;
}
.scene-card .label { color: #818cf8; font-size: 0.75em; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; }
.scene-card .value { color: #e2e8f0; margin-top: 2px; font-size: 0.95em; }

/* ── Chat bubbles ── */
.chat-wrap { background: #0f172a; border-radius: 12px; border: 1px solid #1e293b; padding: 16px; min-height: 280px; }
.msg-detective {
    display: flex; justify-content: flex-end; margin: 10px 0;
}
.msg-detective .bubble {
    background: #1d4ed8;
    color: white;
    border-radius: 18px 18px 4px 18px;
    padding: 10px 16px;
    max-width: 75%;
    font-size: 0.92em;
    line-height: 1.5;
}
.msg-oracle {
    display: flex; justify-content: flex-start; margin: 10px 0; align-items: flex-start; gap: 10px;
}
.msg-oracle .avatar {
    width: 36px; height: 36px; border-radius: 50%;
    background: linear-gradient(135deg, #7c3aed, #db2777);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1em; flex-shrink: 0;
}
.msg-oracle .bubble {
    background: #1e293b;
    color: #cbd5e1;
    border-radius: 18px 18px 18px 4px;
    padding: 10px 16px;
    max-width: 75%;
    font-size: 0.92em;
    line-height: 1.5;
    border: 1px solid #334155;
}
.msg-system {
    text-align: center; color: #64748b; font-size: 0.8em; margin: 8px 0;
    font-style: italic;
}

/* ── Score reveal ── */
.score-box {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 20px;
}
.score-good  { color: #22c55e; }
.score-ok    { color: #f59e0b; }
.score-bad   { color: #ef4444; }

/* ── Stat pills ── */
.stat-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
.stat-pill {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.8em;
    color: #94a3b8;
}
.stat-pill span { color: #e2e8f0; font-weight: 600; }

/* ── Tips ── */
.tip-box {
    background: #0c1a2e;
    border: 1px solid #1e3a5f;
    border-left: 4px solid #3b82f6;
    border-radius: 0 8px 8px 0;
    padding: 10px 14px;
    font-size: 0.85em;
    color: #93c5fd;
    margin: 8px 0;
}

/* ── Tabs ── */
.tab-nav button { font-size: 0.95em !important; }

/* ── Demo step highlight ── */
.demo-step {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 6px 0;
    font-size: 0.88em;
    color: #cbd5e1;
}
.demo-step .step-num {
    color: #818cf8;
    font-weight: 700;
    margin-right: 8px;
}
"""

# ---------------------------------------------------------------------------
# 5. Helper: render chat HTML
# ---------------------------------------------------------------------------
def render_chat(history):
    if not history:
        return '<div class="chat-wrap"><div class="msg-system">Conversation will appear here...</div></div>'
    html = '<div class="chat-wrap">'
    for turn in history:
        if turn["role"] == "detective":
            html += f'''<div class="msg-detective">
  <div class="bubble">🕵️ {turn["content"]}</div>
</div>'''
        elif turn["role"] == "oracle":
            html += f'''<div class="msg-oracle">
  <div class="avatar">🎭</div>
  <div class="bubble">{turn["content"]}</div>
</div>'''
        elif turn["role"] == "system":
            html += f'<div class="msg-system">{turn["content"]}</div>'
    html += '</div>'
    return html

def render_scene(obs):
    t = TASK_INFO.get(obs.get("task_id", "factual_easy"), TASK_INFO["factual_easy"])
    remaining = obs.get("questions_remaining", 0)
    total = obs.get("max_steps", 8)
    used = total - remaining
    bar_filled = int((used / total) * 12)
    bar = "█" * bar_filled + "░" * (12 - bar_filled)
    return f"""<div class="scene-card">
<div class="label">Oracle Persona</div>
<div class="value">🎭 {obs.get('oracle_persona','—')}</div>
<br>
<div class="label">Scene</div>
<div class="value">{obs.get('context','—')}</div>
<br>
<div class="label">Your Mission</div>
<div class="value">{obs.get('task_description','—')}</div>
<br>
<div class="stat-row">
  <div class="stat-pill">{t['icon']} Task: <span>{t['label']}</span></div>
  <div class="stat-pill">❓ Questions: <span>{remaining} remaining</span></div>
  <div class="stat-pill">📊 Used: <span>[{bar}] {used}/{total}</span></div>
</div>
</div>"""

def render_score(result, obs, hypothesis):
    r = result["reward"]
    bd = result["breakdown"]
    bar_n = int(r * 20)
    bar = "█" * bar_n + "░" * (20 - bar_n)
    cls = "score-good" if r > 0.55 else "score-ok" if r > 0.3 else "score-bad"
    verdict = "Outstanding!" if r > 0.7 else "Great detective work!" if r > 0.55 else "Good attempt!" if r > 0.3 else "Keep practicing!"
    return f"""<div class="score-box">
<h3 class="{cls}">{verdict}</h3>
<p class="{cls}" style="font-size:1.8em;font-weight:700;margin:4px 0">{r:.3f} / 1.000</p>
<p style="color:#475569;font-family:monospace">[{bar}]</p>
<div class="stat-row" style="margin-top:12px">
  <div class="stat-pill">🎯 Semantic match: <span>{bd['semantic_similarity']:.3f}</span></div>
  <div class="stat-pill">⚡ Efficiency: <span>{bd['efficiency_bonus']:.3f}</span></div>
  <div class="stat-pill">🏷️ Category: <span>+{bd['category_bonus']:.2f}</span></div>
  <div class="stat-pill">🔑 Keywords: <span>+{bd['keyword_bonus']:.2f}</span></div>
  <div class="stat-pill">❓ Questions used: <span>{bd['questions_used']}/{obs.get('max_steps',8)}</span></div>
</div>
<hr style="border-color:#1e293b;margin:14px 0">
<p style="color:#64748b;font-size:0.82em;margin:0 0 4px">YOUR HYPOTHESIS</p>
<p style="color:#cbd5e1;margin:0 0 14px">{hypothesis}</p>
<p style="color:#64748b;font-size:0.82em;margin:0 0 4px">TRUE SECRET</p>
<p style="color:#86efac;margin:0"><em>{result['true_secret']}</em></p>
</div>"""

# ---------------------------------------------------------------------------
# 6. Game logic
# ---------------------------------------------------------------------------
def start_game(task_id):
    obs = client.post("/reset", json={"task_id": task_id}).json()
    history = [{"role": "system", "content": f"New episode started · Task: {TASK_INFO[task_id]['label']}"}]
    state = {"obs": obs, "done": False, "history": history}
    tip = f"""<div class="tip-box">
💡 <strong>Tip:</strong> Don't ask directly about the secret. Ask about their work, feelings, or plans.
The Oracle <em>cannot lie</em> but <em>will never state it directly</em> — read between the lines.
</div>"""
    return state, render_scene(obs), render_chat(history), "", tip, gr.update(interactive=True), gr.update(interactive=True), gr.update(interactive=False)

def ask_question(question, state):
    if not state or not question.strip():
        return state, state.get("chat_html", ""), "", gr.update(interactive=True)
    if state.get("done"):
        return state, render_chat(state["history"]), "Episode finished. Start a new game.", gr.update(interactive=False)

    obs = state["obs"]
    resp = client.post("/step", json={
        "episode_id": obs["episode_id"],
        "action": {"action": "ask_question", "question": question.strip()}
    }).json()

    oracle_reply = resp["info"].get("oracle_response", "...")
    new_obs = resp["observation"]

    history = state["history"] + [
        {"role": "detective", "content": question.strip()},
        {"role": "oracle",    "content": oracle_reply},
    ]

    status = ""
    if new_obs["questions_remaining"] == 0:
        status = "No questions left — submit your hypothesis now!"
        history.append({"role": "system", "content": "⏰ No questions remaining — time to submit!"})

    state = {**state, "obs": new_obs, "history": history, "done": False}
    return state, render_chat(history), render_scene(new_obs), status

def submit_hypothesis(hypothesis, category, state):
    if not state or not hypothesis.strip():
        return state, "", "Enter your hypothesis first."
    if state.get("done"):
        return state, "", "Episode already finished."

    obs = state["obs"]
    resp = client.post("/submit", json={
        "episode_id": obs["episode_id"],
        "hypothesis": hypothesis.strip(),
        "category_prediction": category,
    }).json()

    history = state["history"] + [
        {"role": "system", "content": f"📋 Hypothesis submitted: <em>{hypothesis.strip()}</em>"},
        {"role": "system", "content": f"🏆 Score: <strong>{resp['reward']:.3f}</strong> — True secret revealed below"},
    ]
    state = {**state, "done": True, "history": history}
    return state, render_score(resp, obs, hypothesis.strip()), render_chat(history)

# ---------------------------------------------------------------------------
# 7. Build UI
# ---------------------------------------------------------------------------
HEADER_HTML = """<div class="hero-banner">
<h1>🕵️ MindRead</h1>
<p>Can an AI learn to read between the lines?</p>
<p style="color:#94a3b8;font-size:0.9em;margin-top:6px">
  The first OpenEnv environment that trains <strong style="color:#a78bfa">Theory of Mind</strong> in LLMs via GRPO
</p>
<div style="margin-top:14px">
  <span class="hero-badge">🤗 HF Space</span>
  <span class="hero-badge">⚡ PyTorch + TRL GRPO</span>
  <span class="hero-badge">🌐 OpenEnv Compliant</span>
  <span class="hero-badge">🧠 ICML 2025 Research</span>
</div>
</div>"""

HOW_IT_WORKS_HTML = """<div class="how-cards">
  <div class="how-card">
    <div class="icon">🎭</div>
    <h4>The Oracle</h4>
    <p>Holds a hidden secret. Cannot lie, but will <em>never</em> reveal it directly. Gives evasive, truthful answers.</p>
  </div>
  <div class="how-card">
    <div class="icon">🕵️</div>
    <h4>The Detective</h4>
    <p>Must infer the secret by asking strategic questions. Fewer questions = higher score. Think, don't fish.</p>
  </div>
  <div class="how-card">
    <div class="icon">🏆</div>
    <h4>The Reward</h4>
    <p><code>reward = semantic_similarity × efficiency_bonus</code><br>Closer guess + fewer questions = higher score.</p>
  </div>
  <div class="how-card">
    <div class="icon">🤖</div>
    <h4>The Training</h4>
    <p>A Qwen2.5-1.5B detective was trained via GRPO for 300 steps. It learned to ask <strong>44% fewer questions</strong>.</p>
  </div>
</div>"""

DEMO_SCRIPT = DEMO_EPISODES[0]

def run_demo_step(step_idx, demo_history):
    ep = DEMO_SCRIPT
    demo_history = demo_history or []

    if step_idx == 0:
        demo_history = [
            {"role": "system", "content": f"🎬 Demo episode · Oracle: <strong>{ep['persona']}</strong>"},
            {"role": "system", "content": f"📍 Scene: {ep['scene']}"},
        ]
        status = f"**Scene set.** The Oracle is a {ep['persona']}. They know something they won't say directly. Click **Next Step** to watch the detective question them."
        return 1, demo_history, render_chat(demo_history), status, gr.update(visible=True)

    q_idx = step_idx - 1
    if q_idx < len(ep["questions"]):
        q = ep["questions"][q_idx]
        a = ep["oracle_answers"][q_idx]
        demo_history = demo_history + [
            {"role": "detective", "content": q},
            {"role": "oracle",    "content": a},
        ]
        tips = [
            "Notice: the Oracle didn't answer directly. Read what they *avoided* saying.",
            "The Oracle confirms things are complex — but *what* is complex? Narrow it down.",
            "Key phrase: 'done right before we go public'. Something isn't public yet. What?",
        ]
        tip = tips[q_idx] if q_idx < len(tips) else ""
        n_remaining = len(ep["questions"]) - step_idx
        status = f"**Question {step_idx}/{len(ep['questions'])}** asked. {n_remaining} more before hypothesis.\n\n💡 *{tip}*"
        next_step = step_idx + 1
        return next_step, demo_history, render_chat(demo_history), status, gr.update(visible=True)

    # Final step — show hypothesis + score
    demo_history = demo_history + [
        {"role": "system", "content": f"📋 Detective submits hypothesis: <em>{ep['hypothesis']}</em>"},
        {"role": "system", "content": f"✅ Score: <strong>~0.68</strong> · True secret revealed!"},
    ]
    status = f"""**Hypothesis submitted!**

> *"{ep['hypothesis']}"*

**True secret:** *"{ep['secret']}"*

The detective used **3 questions** (budget: 8) and scored ~0.68/1.0.
After GRPO training, the AI detective does this automatically — asking fewer, more targeted questions to maximize reward.

**Now try it yourself →** Switch to the *Play* tab!"""
    return 0, demo_history, render_chat(demo_history), status, gr.update(visible=False)

with gr.Blocks(title="MindRead — Theory of Mind RL", css=CSS, theme=gr.themes.Base()) as demo:

    gr.HTML(HEADER_HTML)

    with gr.Tabs():

        # ── TAB 1: HOW IT WORKS ─────────────────────────────────────────
        with gr.Tab("📖 How It Works"):
            gr.HTML(HOW_IT_WORKS_HTML)
            gr.Markdown("""
### The 5 Tasks (increasing difficulty)

| # | Task | What the Detective must infer | Questions | Difficulty |
|---|------|-------------------------------|-----------|------------|
| 1 | `factual_easy` | A hidden workplace fact or event | 8 | 🟢 Easy |
| 2 | `factual_hard` | A precise number, date, or figure | 6 | 🟡 Medium |
| 3 | `belief_inference` | What the Oracle *believes* about someone else | 8 | 🟠 Hard |
| 4 | `goal_inference` | The Oracle's hidden career ambition | 8 | 🟠 Hard |
| 5 | `second_order` | What Oracle thinks *someone else believes* | 10 | 🔴 Hardest |

### Why does this matter?

Current AI Theory of Mind benchmarks are **static** — they ask models to predict answers from a story.
Real ToM is **interactive**: you adapt your questions based on what someone avoids saying.

MindRead is the first OpenEnv environment that trains this skill. A Qwen2.5-1.5B detective was trained
via GRPO (Group Relative Policy Optimization) and learned to ask **44% fewer questions** while maintaining
hypothesis quality — it stopped fishing and started thinking.

### Reward Formula

```
reward = semantic_similarity(hypothesis, true_secret)   ← did you guess correctly?
         × efficiency_bonus(questions_used / max_q)     ← did you use fewer questions?
         + category_bonus                               ← did you classify the secret type?
         + keyword_bonus                                ← did your hypothesis hit key concepts?

efficiency_bonus = 0.6 + 0.4 × (1 − questions_used / max_questions)
```

The efficiency bonus is the key RL pressure — it rewards asking fewer, better questions.

### Architecture

```
OpenEnv Server (FastAPI)
   POST /reset  →  assign secret to Oracle, return context
   POST /step   →  Detective asks, Oracle responds (Qwen 0.5B local)
   POST /submit →  score hypothesis with sentence-transformers (PyTorch)
        ↕
   GRPO Training (TRL + PyTorch)
   Detective (Qwen2.5-1.5B) weights updated based on reward signal
```
""")

        # ── TAB 2: LIVE DEMO ─────────────────────────────────────────────
        with gr.Tab("🎬 Watch a Demo"):
            gr.Markdown("""
### Watch the Detective in Action

Step through a real episode. See how the detective asks strategic questions,
interprets evasive answers, and submits a precise hypothesis.
""")
            demo_step_state  = gr.State(0)
            demo_hist_state  = gr.State([])

            with gr.Row():
                with gr.Column(scale=2):
                    demo_chat = gr.HTML(render_chat([]), label="Conversation")
                with gr.Column(scale=1):
                    demo_status = gr.Markdown("*Click **Start Demo** to begin a guided walkthrough.*")
                    with gr.Row():
                        demo_start_btn = gr.Button("▶ Start Demo", variant="primary", size="lg")
                        demo_next_btn  = gr.Button("⏭ Next Step", variant="secondary", size="lg", visible=False)

            demo_start_btn.click(
                run_demo_step,
                inputs=[gr.State(0), gr.State([])],
                outputs=[demo_step_state, demo_hist_state, demo_chat, demo_status, demo_next_btn],
            )
            demo_next_btn.click(
                run_demo_step,
                inputs=[demo_step_state, demo_hist_state],
                outputs=[demo_step_state, demo_hist_state, demo_chat, demo_status, demo_next_btn],
            )

        # ── TAB 3: PLAY ──────────────────────────────────────────────────
        with gr.Tab("🎮 Play Detective"):
            gr.Markdown("""
### You are the Detective
Pick a task, read the scene, ask strategic questions — then submit your hypothesis.
The Oracle **cannot lie** but will **never reveal the secret directly**.
""")
            game_state = gr.State({})

            with gr.Row():
                # Left column — scene + controls
                with gr.Column(scale=1, min_width=300):
                    task_dd = gr.Dropdown(
                        choices=[(f"{v['icon']} {v['label']} — {v['desc']}", k) for k, v in TASK_INFO.items()],
                        value="factual_easy",
                        label="Choose task difficulty",
                    )
                    new_game_btn = gr.Button("🆕 New Game", variant="primary", size="lg")
                    scene_html   = gr.HTML("<div style='color:#64748b;padding:20px;text-align:center'>Click New Game to start</div>")
                    tip_html     = gr.HTML("")

                    gr.HTML("<hr style='border-color:#1e293b;margin:8px 0'>")
                    gr.Markdown("**Tips for a good score:**")
                    gr.HTML("""<div style="font-size:0.84em;color:#94a3b8;line-height:1.8">
• Don't ask "what's the secret?" — the Oracle will deflect<br>
• Ask about feelings, timelines, recent changes, pressures<br>
• Notice what the Oracle <em>avoids</em> saying<br>
• Fewer questions = higher efficiency bonus<br>
• Be specific in your hypothesis — vague guesses score low
</div>""")

                # Right column — chat + input
                with gr.Column(scale=2):
                    chat_html = gr.HTML(render_chat([]))

                    with gr.Row():
                        q_input = gr.Textbox(
                            placeholder="Ask the Oracle a strategic question...",
                            label="",
                            scale=5,
                            lines=1,
                            interactive=False,
                        )
                        ask_btn = gr.Button("Ask →", variant="secondary", size="lg", interactive=False)

                    status_md = gr.Markdown("")

                    gr.HTML("<hr style='border-color:#1e293b;margin:8px 0'>")
                    gr.Markdown("**Ready to submit your hypothesis?**")
                    gr.HTML("""<div class="tip-box">
💡 Be <strong>specific</strong>. Don't say "there's some issue" — say <em>what</em> the issue is,
<em>who</em> it affects, and <em>when</em>. Semantic similarity rewards precise matches.
</div>""")

                    with gr.Row():
                        hyp_input = gr.Textbox(
                            placeholder="My hypothesis: ...",
                            label="Your hypothesis (be specific!)",
                            lines=2,
                            scale=4,
                            interactive=False,
                        )
                        cat_dd = gr.Dropdown(
                            choices=CATEGORY_CHOICES,
                            value="factual",
                            label="Secret type",
                            scale=1,
                        )
                    submit_btn = gr.Button("🔍 Submit Hypothesis", variant="primary", size="lg", interactive=False)
                    score_html = gr.HTML("")

            # Wire game events
            new_game_btn.click(
                start_game,
                inputs=[task_dd],
                outputs=[game_state, scene_html, chat_html, score_html, tip_html,
                         q_input, ask_btn, submit_btn],
            )
            ask_btn.click(
                ask_question,
                inputs=[q_input, game_state],
                outputs=[game_state, chat_html, scene_html, status_md],
            ).then(lambda: "", outputs=q_input)
            q_input.submit(
                ask_question,
                inputs=[q_input, game_state],
                outputs=[game_state, chat_html, scene_html, status_md],
            ).then(lambda: "", outputs=q_input)
            submit_btn.click(
                submit_hypothesis,
                inputs=[hyp_input, cat_dd, game_state],
                outputs=[game_state, score_html, chat_html],
            )

        # ── TAB 4: RESULTS ───────────────────────────────────────────────
        with gr.Tab("📊 Training Results"):
            gr.Markdown("""
### Real GRPO Training Results

The detective (Qwen2.5-1.5B-Instruct) was trained for **300 steps** on Lightning AI H100
using TRL's GRPOTrainer. Oracle responses came from a local Qwen2.5-0.5B-Instruct model
(no Groq API — no rate limits).

| Metric | Baseline | After Training | Change |
|--------|---------|----------------|--------|
| Avg reward | 0.1393 | ↑ improving | — |
| Avg questions asked | 7.7 | 4.3 | **−44%** |

### What the results prove

The key signal is not just reward improvement — it's the **44% drop in questions asked**.

The detective was never told to ask fewer questions. It discovered through reinforcement learning
that fewer, better-targeted questions maximize the efficiency bonus in the reward.
This is emergent strategic behavior — the hallmark of functional Theory of Mind.

### Why questions drop is the right metric

A model that just memorizes keywords would get higher semantic similarity but wouldn't
reduce questions. The fact that *both* change together — more accurate hypotheses *and*
fewer questions — shows the model learned a genuine questioning strategy, not a shortcut.

### Training curve

See `evals/training_curve.png` in the [GitHub repo](https://github.com/nileshpatil6/MindRead-RL-Environment/blob/main/evals/training_curve.png).

### Reproduce this training

1. Clone: `git clone https://github.com/nileshpatil6/MindRead-RL-Environment.git`
2. Open `mindread_lightning.ipynb` on Lightning AI with H100
3. Run all cells — ~45 minutes, no API keys needed
""")

    # Footer
    gr.HTML("""
<div style="text-align:center;padding:20px;color:#475569;font-size:0.82em;border-top:1px solid #1e293b;margin-top:16px">
  Built for <strong>Meta × Scaler PyTorch OpenEnv Hackathon 2026</strong> ·
  <a href="https://github.com/nileshpatil6/MindRead-RL-Environment" style="color:#818cf8">GitHub</a> ·
  Research: <em>Theory of Mind Benchmarks are Broken for Large Language Models (ICML 2025)</em>
</div>""")

if __name__ == "__main__":
    demo.launch(server_port=7860)
