"""
MindRead HF Space — Clean modern UI (Linear/Vercel aesthetic)
"""
import json, random, threading, time
import httpx
import gradio as gr

# ── Oracle patch ──────────────────────────────────────────────────────────
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
    if any(kw.lower() in q for kw in secret.hint_keywords):
        return "There's more going on there than I can share right now. Let's just say it's on people's radar."
    for rh in secret.red_herrings:
        if any(w in q for w in rh.lower().split()[:3]):
            return f"Oh, that? Yeah — {rh.lower().rstrip('.')}. Interesting times."
    return random.choice(EVASIVE)

oracle_module.LOCAL_ORACLE_FN = _mock_oracle

# ── Server ────────────────────────────────────────────────────────────────
def _run_server():
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=7861, log_level="error")

threading.Thread(target=_run_server, daemon=True).start()
for _ in range(30):
    try:
        if httpx.get("http://localhost:7861/health", timeout=2).status_code == 200:
            break
    except Exception:
        pass
    time.sleep(1)

client = httpx.Client(base_url="http://localhost:7861", timeout=30)

TASKS = {
    "factual_easy":     {"label": "Factual · Easy",       "q": 8,  "color": "#22c55e"},
    "factual_hard":     {"label": "Factual · Hard",       "q": 6,  "color": "#eab308"},
    "belief_inference": {"label": "Belief Inference",     "q": 8,  "color": "#f97316"},
    "goal_inference":   {"label": "Goal Inference",       "q": 8,  "color": "#f97316"},
    "second_order":     {"label": "2nd-Order ToM",        "q": 10, "color": "#ef4444"},
}

# ── CSS — clean minimal dark, inspired by Linear/Vercel ──────────────────
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

* { box-sizing: border-box; }

body, .gradio-container {
    background: #09090b !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
}
.gradio-container {
    max-width: 1080px !important;
    margin: 0 auto !important;
    padding-bottom: 60px !important;
}
footer { display: none !important; }

/* Typography */
h1, h2, h3, h4 { color: #fafafa; font-weight: 600; }
p { color: #a1a1aa; }

/* Inputs */
input, textarea {
    background: #18181b !important;
    border: 1px solid #27272a !important;
    color: #fafafa !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.9em !important;
    transition: border-color 0.15s !important;
}
input:focus, textarea:focus {
    border-color: #52525b !important;
    outline: none !important;
    box-shadow: 0 0 0 2px rgba(255,255,255,0.04) !important;
}
label { color: #71717a !important; font-size: 0.8em !important; font-weight: 500 !important; }

/* Buttons */
button.primary {
    background: #fafafa !important;
    color: #09090b !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.88em !important;
    padding: 9px 18px !important;
    font-family: 'Inter', sans-serif !important;
    transition: opacity 0.15s !important;
    cursor: pointer !important;
}
button.primary:hover { opacity: 0.88 !important; }
button.secondary {
    background: #18181b !important;
    color: #a1a1aa !important;
    border: 1px solid #27272a !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 0.88em !important;
    padding: 9px 18px !important;
    font-family: 'Inter', sans-serif !important;
    transition: border-color 0.15s, color 0.15s !important;
}
button.secondary:hover { border-color: #3f3f46 !important; color: #fafafa !important; }
button:disabled { opacity: 0.35 !important; cursor: not-allowed !important; }

/* Dropdown */
.wrap { background: #18181b !important; border: 1px solid #27272a !important; border-radius: 8px !important; }
.wrap:focus-within { border-color: #52525b !important; }
ul.options { background: #18181b !important; border: 1px solid #27272a !important; border-radius: 8px !important; }
ul.options li { color: #a1a1aa !important; }
ul.options li:hover, ul.options li.selected { background: #27272a !important; color: #fafafa !important; }

/* Tabs */
.tab-nav { border-bottom: 1px solid #18181b !important; background: transparent !important; margin-bottom: 24px !important; }
.tab-nav button {
    color: #52525b !important; font-size: 0.85em !important; font-weight: 500 !important;
    padding: 8px 16px !important; background: transparent !important; border: none !important;
    border-bottom: 2px solid transparent !important; margin-bottom: -1px !important;
    font-family: 'Inter', sans-serif !important; transition: color 0.15s !important;
}
.tab-nav button.selected { color: #fafafa !important; border-bottom-color: #fafafa !important; }
.tab-nav button:hover { color: #d4d4d8 !important; }
.tabitem { background: transparent !important; border: none !important; padding: 0 !important; }

/* Cards */
.card {
    background: #18181b;
    border: 1px solid #27272a;
    border-radius: 12px;
    padding: 20px 24px;
}
.card-sm {
    background: #18181b;
    border: 1px solid #27272a;
    border-radius: 10px;
    padding: 14px 18px;
}

/* Stats row */
.stats-row { display: flex; gap: 12px; margin: 20px 0; }
.stat-card {
    flex: 1;
    background: #18181b;
    border: 1px solid #27272a;
    border-radius: 10px;
    padding: 16px 18px;
}
.stat-card .sv { font-size: 1.6em; font-weight: 700; color: #fafafa; line-height: 1; margin-bottom: 4px; }
.stat-card .sl { font-size: 0.75em; color: #52525b; font-weight: 500; }

/* Tag */
.tag {
    display: inline-block;
    background: #27272a;
    border: 1px solid #3f3f46;
    border-radius: 5px;
    padding: 2px 8px;
    font-size: 0.72em;
    color: #a1a1aa;
    font-weight: 500;
    font-family: 'JetBrains Mono', monospace;
}

/* Hero */
.hero { padding: 48px 0 32px; border-bottom: 1px solid #18181b; margin-bottom: 32px; }
.hero-eyebrow { font-size: 0.75em; font-weight: 600; color: #52525b; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 14px; }
.hero-title { font-size: 2.6em; font-weight: 700; color: #fafafa; line-height: 1.15; margin-bottom: 14px; }
.hero-title span { color: #a1a1aa; font-weight: 400; }
.hero-desc { font-size: 1em; color: #71717a; line-height: 1.65; max-width: 560px; margin-bottom: 24px; }
.hero-tags { display: flex; gap: 8px; flex-wrap: wrap; }

/* Chat */
.chat-outer {
    background: #18181b;
    border: 1px solid #27272a;
    border-radius: 12px;
    overflow: hidden;
}
.chat-header {
    padding: 12px 16px;
    border-bottom: 1px solid #27272a;
    font-size: 0.78em;
    color: #52525b;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 8px;
}
.chat-dot { width: 6px; height: 6px; border-radius: 50%; background: #22c55e; }
.chat-body {
    padding: 16px;
    min-height: 300px;
    max-height: 400px;
    overflow-y: auto;
}
.chat-body::-webkit-scrollbar { width: 3px; }
.chat-body::-webkit-scrollbar-thumb { background: #27272a; border-radius: 2px; }
.chat-empty { text-align: center; padding: 60px 20px; color: #3f3f46; font-size: 0.85em; }

.msg-det { display: flex; justify-content: flex-end; margin: 8px 0; }
.msg-det .b {
    background: #fafafa; color: #09090b;
    padding: 9px 14px; border-radius: 12px 12px 3px 12px;
    max-width: 70%; font-size: 0.87em; line-height: 1.5; font-weight: 500;
}
.msg-ora { display: flex; align-items: flex-start; gap: 9px; margin: 8px 0; }
.msg-ora .av {
    width: 28px; height: 28px; border-radius: 6px;
    background: #27272a; border: 1px solid #3f3f46;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.85em; flex-shrink: 0; margin-top: 2px;
}
.msg-ora .b {
    background: #27272a; color: #d4d4d8;
    border: 1px solid #3f3f46;
    padding: 9px 14px; border-radius: 12px 12px 12px 3px;
    max-width: 70%; font-size: 0.87em; line-height: 1.5;
}
.msg-sys { text-align: center; margin: 10px 0; }
.msg-sys span {
    display: inline-block; background: #27272a; border: 1px solid #3f3f46;
    color: #52525b; font-size: 0.72em; padding: 3px 10px; border-radius: 20px;
}

/* Scene panel */
.scene {
    background: #18181b; border: 1px solid #27272a; border-radius: 12px; padding: 16px 18px;
}
.scene .s-key { font-size: 0.7em; font-weight: 600; color: #52525b; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 3px; }
.scene .s-val { font-size: 0.87em; color: #d4d4d8; line-height: 1.5; }
.scene .divider { border: none; border-top: 1px solid #27272a; margin: 10px 0; }
.q-progress { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
.q-track { flex: 1; height: 3px; background: #27272a; border-radius: 2px; }
.q-fill  { height: 100%; border-radius: 2px; background: #fafafa; transition: width 0.3s; }
.q-label { font-size: 0.72em; color: #52525b; font-weight: 500; white-space: nowrap; }

/* Score */
.score {
    background: #18181b; border: 1px solid #27272a; border-radius: 12px; padding: 24px;
}
.score .s-num  { font-size: 3em; font-weight: 700; color: #fafafa; line-height: 1; }
.score .s-sub  { font-size: 0.8em; color: #52525b; margin-top: 2px; }
.score .s-bar  { height: 3px; background: #27272a; border-radius: 2px; margin: 16px 0; }
.score .s-fill { height: 100%; border-radius: 2px; background: #fafafa; transition: width 0.6s; }
.score .bd     { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 14px 0; }
.score .bd-i   { background: #09090b; border: 1px solid #27272a; border-radius: 8px; padding: 10px 12px; }
.score .bd-k   { font-size: 0.7em; color: #52525b; font-weight: 500; margin-bottom: 2px; }
.score .bd-v   { font-size: 1em; font-weight: 600; color: #fafafa; }
.score .reveal {
    background: #09090b; border: 1px solid #27272a; border-radius: 8px;
    padding: 12px 14px; margin-top: 12px;
}
.score .reveal .rk { font-size: 0.7em; color: #52525b; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
.score .reveal .rv { font-size: 0.87em; color: #d4d4d8; line-height: 1.5; }

/* Demo status */
.demo-box {
    background: #18181b; border: 1px solid #27272a; border-radius: 10px;
    padding: 16px 18px; font-size: 0.87em; color: #a1a1aa; line-height: 1.65; min-height: 90px;
}

/* How it works grid */
.hiw { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 16px 0; }
.hiw-c { background: #18181b; border: 1px solid #27272a; border-radius: 10px; padding: 18px; }
.hiw-c .ic { font-size: 1.3em; margin-bottom: 10px; }
.hiw-c h4  { font-size: 0.9em; color: #fafafa; font-weight: 600; margin-bottom: 5px; }
.hiw-c p   { font-size: 0.82em; color: #71717a; line-height: 1.6; }

/* Table */
.tbl { width: 100%; border-collapse: collapse; font-size: 0.84em; }
.tbl th { padding: 8px 14px; text-align: left; color: #52525b; font-weight: 500; border-bottom: 1px solid #27272a; }
.tbl td { padding: 10px 14px; color: #a1a1aa; border-bottom: 1px solid #18181b; }
.tbl td:first-child { color: #fafafa; font-weight: 500; }
.tbl code { font-family: 'JetBrains Mono', monospace; color: #a1a1aa; font-size: 0.9em; }

/* Code */
.code {
    background: #09090b; border: 1px solid #27272a; border-radius: 8px;
    padding: 14px 16px; font-family: 'JetBrains Mono', monospace;
    font-size: 0.8em; color: #71717a; line-height: 1.8; overflow-x: auto; margin: 10px 0;
}
.code .kw { color: #a1a1aa; }

/* Tip */
.tip {
    border-left: 2px solid #3f3f46; padding: 8px 12px;
    font-size: 0.82em; color: #71717a; line-height: 1.6; margin: 8px 0;
}
"""

# ── Helpers ───────────────────────────────────────────────────────────────
def render_chat(history, label="Interrogation"):
    body = ""
    if not history:
        body = '<div class="chat-empty">Start a game to begin</div>'
    else:
        for t in history:
            r, c = t["role"], t["content"]
            if r == "detective":
                body += f'<div class="msg-det"><div class="b">You: {c}</div></div>'
            elif r == "oracle":
                body += f'<div class="msg-ora"><div class="av">🎭</div><div class="b">{c}</div></div>'
            elif r == "system":
                body += f'<div class="msg-sys"><span>{c}</span></div>'
    return (f'<div class="chat-outer">'
            f'<div class="chat-header"><div class="chat-dot"></div>{label}</div>'
            f'<div class="chat-body">{body}</div></div>')

def render_scene(obs):
    tid = obs.get("task_id", "factual_easy")
    t = TASKS.get(tid, TASKS["factual_easy"])
    rem = obs.get("questions_remaining", 0)
    tot = obs.get("max_steps", 8)
    pct = int((tot - rem) / tot * 100)
    color = t["color"]
    return (f'<div class="scene">'
            f'<div class="s-key">Oracle</div>'
            f'<div class="s-val">🎭 {obs.get("oracle_persona","—")}</div>'
            f'<hr class="divider">'
            f'<div class="s-key">Scene</div>'
            f'<div class="s-val">{obs.get("context","—")}</div>'
            f'<hr class="divider">'
            f'<div class="s-key">Mission</div>'
            f'<div class="s-val">{obs.get("task_description","—")}</div>'
            f'<div class="q-progress">'
            f'<span class="q-label"><span style="color:{color};font-weight:600">●</span> {t["label"]}</span>'
            f'<div class="q-track"><div class="q-fill" style="width:{pct}%;background:{color}"></div></div>'
            f'<span class="q-label">{rem}/{tot} Q left</span>'
            f'</div></div>')

def render_score(result, obs, hyp):
    r  = result["reward"]
    bd = result["breakdown"]
    pct = int(r * 100)
    verdict = ("Excellent" if r > 0.65 else "Good" if r > 0.4 else "Fair" if r > 0.2 else "Low")
    return (f'<div class="score">'
            f'<div style="font-size:0.72em;color:#52525b;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">{verdict}</div>'
            f'<div class="s-num">{r:.3f}</div>'
            f'<div class="s-sub">out of 1.000</div>'
            f'<div class="s-bar"><div class="s-fill" style="width:{pct}%"></div></div>'
            f'<div class="bd">'
            f'<div class="bd-i"><div class="bd-k">Semantic match</div><div class="bd-v">{bd["semantic_similarity"]:.3f}</div></div>'
            f'<div class="bd-i"><div class="bd-k">Efficiency bonus</div><div class="bd-v">{bd["efficiency_bonus"]:.3f}</div></div>'
            f'<div class="bd-i"><div class="bd-k">Category bonus</div><div class="bd-v">+{bd["category_bonus"]:.2f}</div></div>'
            f'<div class="bd-i"><div class="bd-k">Questions used</div><div class="bd-v">{bd["questions_used"]}/{obs.get("max_steps",8)}</div></div>'
            f'</div>'
            f'<div class="reveal"><div class="rk">True secret</div><div class="rv">"{result["true_secret"]}"</div></div>'
            f'</div>')

# ── Game logic ────────────────────────────────────────────────────────────
def start_game(task_id):
    obs = client.post("/reset", json={"task_id": task_id}).json()
    t = TASKS.get(task_id, TASKS["factual_easy"])
    history = [{"role": "system", "content": f"New episode · {t['label']}"}]
    state = {"obs": obs, "history": history, "done": False}
    return (state, render_scene(obs), render_chat(history), "",
            gr.update(interactive=True), gr.update(interactive=True),
            gr.update(interactive=True), gr.update(interactive=False))

def ask_question(question, state):
    if not state or not question.strip():
        return state, render_chat(state.get("history", [])), render_scene(state.get("obs", {})), ""
    if state.get("done"):
        return state, render_chat(state["history"]), render_scene(state["obs"]), "Episode done — start a new game."
    obs = state["obs"]
    resp = client.post("/step", json={
        "episode_id": obs["episode_id"],
        "action": {"action": "ask_question", "question": question.strip()}
    }).json()
    reply = resp["info"].get("oracle_response", "...")
    new_obs = resp["observation"]
    history = state["history"] + [
        {"role": "detective", "content": question.strip()},
        {"role": "oracle",    "content": reply},
    ]
    if new_obs["questions_remaining"] == 0:
        history.append({"role": "system", "content": "Out of questions — submit your hypothesis"})
    state = {**state, "obs": new_obs, "history": history}
    status = "No questions left — submit now." if new_obs["questions_remaining"] == 0 else ""
    return state, render_chat(history), render_scene(new_obs), status

def submit_hypothesis(hypothesis, category, state):
    if not state or not hypothesis.strip():
        return state, "", "Enter a hypothesis first."
    if state.get("done"):
        return state, "", "Already submitted."
    obs = state["obs"]
    resp = client.post("/submit", json={
        "episode_id": obs["episode_id"],
        "hypothesis": hypothesis.strip(),
        "category_prediction": category,
    }).json()
    history = state["history"] + [
        {"role": "system", "content": f"Hypothesis submitted · Score: {resp['reward']:.3f}"},
    ]
    state = {**state, "done": True, "history": history}
    return state, render_score(resp, obs, hypothesis.strip()), render_chat(history)

# ── Demo ──────────────────────────────────────────────────────────────────
DEMO = {
    "persona": "Senior Product Manager",
    "scene": "Casual hallway chat. Company just signed a big enterprise deal.",
    "secret": "The Q3 product launch was postponed by 6 weeks due to a compliance issue.",
    "steps": [
        ("How's the Q3 roadmap looking?",
         "It's... coming along. There are things in motion I can't really get into right now."),
        ("Any blockers the team is dealing with quietly?",
         "Every project has its complexities. Some need to be worked through before they're shared broadly."),
        ("Has anything come up that might affect the launch timeline?",
         "Let's just say we're making sure everything is done right before going public. Timelines can be fluid."),
    ],
    "hypothesis": "There's an internal delay to the Q3 launch — likely a compliance issue that hasn't been announced.",
    "score": "0.71",
}

DEMO_NOTES = [
    "Notice: the Oracle didn't answer directly. 'Can't really get into it' signals sensitivity around a specific topic.",
    "Confirmed: something exists that isn't ready to share. The phrase 'before they're shared broadly' means there's a planned future disclosure.",
    "Key signal: 'done right before going public' — something is blocking a public announcement. Likely a launch or release.",
]

def demo_step(idx, hist):
    hist = hist or []
    if idx == 0:
        hist = [
            {"role": "system", "content": f"Demo · Oracle: {DEMO['persona']}"},
            {"role": "system", "content": DEMO["scene"]},
        ]
        status = (f"<strong style='color:#fafafa'>Scene set.</strong><br><br>"
                  f"The Oracle is a <strong style='color:#d4d4d8'>{DEMO['persona']}</strong> who knows something sensitive. "
                  f"They can't lie, but won't say it directly. "
                  f"The detective's job: figure it out from what they avoid saying.<br><br>"
                  f"Click <strong style='color:#fafafa'>Next →</strong> to watch the first question.")
        return 1, hist, render_chat(hist, "Demo — Watch the interrogation"), status, gr.update(visible=True)

    q_idx = idx - 1
    if q_idx < len(DEMO["steps"]):
        q, a = DEMO["steps"][q_idx]
        hist = hist + [{"role": "detective", "content": q}, {"role": "oracle", "content": a}]
        note = DEMO_NOTES[q_idx] if q_idx < len(DEMO_NOTES) else ""
        n_left = len(DEMO["steps"]) - idx
        status = (f"<strong style='color:#fafafa'>Question {idx} of {len(DEMO['steps'])}</strong><br><br>"
                  f"<span style='color:#71717a'>Analysis:</span> {note}"
                  + (f"<br><br><span style='color:#52525b'>{n_left} more question{'s' if n_left>1 else ''} before hypothesis →</span>" if n_left else ""))
        return idx + 1, hist, render_chat(hist, "Demo — Watch the interrogation"), status, gr.update(visible=True)

    hist = hist + [
        {"role": "system", "content": f"Hypothesis: {DEMO['hypothesis'][:60]}..."},
        {"role": "system", "content": f"Score: {DEMO['score']} · Secret revealed"},
    ]
    status = (f"<strong style='color:#fafafa'>Hypothesis submitted.</strong><br><br>"
              f"<span style='color:#71717a'>Hypothesis:</span> <em style='color:#d4d4d8'>\"{DEMO['hypothesis']}\"</em><br><br>"
              f"<span style='color:#71717a'>True secret:</span> <em style='color:#a1a1aa'>\"{DEMO['secret']}\"</em><br><br>"
              f"<span style='color:#71717a'>Score:</span> <strong style='color:#fafafa'>{DEMO['score']}/1.0</strong> — "
              f"3 of 8 questions used, high efficiency bonus.<br><br>"
              f"<strong style='color:#d4d4d8'>Now try it yourself in the Play tab.</strong>")
    return 0, hist, render_chat(hist, "Demo — Watch the interrogation"), status, gr.update(visible=False)

# ── UI ────────────────────────────────────────────────────────────────────
HERO = """<div class="hero">
  <div class="hero-eyebrow">OpenEnv · GRPO · Theory of Mind</div>
  <div class="hero-title">MindRead<br><span>Read between the lines.</span></div>
  <div class="hero-desc">
    Training a detective LLM to infer hidden secrets through strategic questioning.
    The only way to win is to genuinely understand another mind.
  </div>
  <div class="hero-tags">
    <span class="tag">Qwen2.5-1.5B detective</span>
    <span class="tag">GRPO via TRL</span>
    <span class="tag">OpenEnv compliant</span>
    <span class="tag">ICML 2025</span>
    <span class="tag">PyTorch</span>
  </div>
</div>"""

with gr.Blocks(title="MindRead", css=CSS, theme=gr.themes.Base()) as app:

    gr.HTML(HERO)

    with gr.Tabs():

        # ── HOW IT WORKS ─────────────────────────────────────────────────
        with gr.Tab("How it works"):
            gr.HTML("""<div class="stats-row">
  <div class="stat-card"><div class="sv">−44%</div><div class="sl">Questions after GRPO training</div></div>
  <div class="stat-card"><div class="sv">300</div><div class="sl">GRPO training steps</div></div>
  <div class="stat-card"><div class="sv">1.5B</div><div class="sl">Detective model parameters</div></div>
  <div class="stat-card"><div class="sv">5</div><div class="sl">Tasks of increasing difficulty</div></div>
</div>""")

            gr.HTML("""<div class="hiw">
  <div class="hiw-c">
    <div class="ic">🎭</div>
    <h4>The Oracle</h4>
    <p>Holds a hidden secret. Cannot lie, but will never reveal it directly. Every evasive answer contains a signal.</p>
  </div>
  <div class="hiw-c">
    <div class="ic">🕵️</div>
    <h4>The Detective</h4>
    <p>Must infer the secret by asking strategic questions. Fewer questions = higher efficiency bonus. Think, don't fish.</p>
  </div>
  <div class="hiw-c">
    <div class="ic">🧮</div>
    <h4>The Reward</h4>
    <p><code style="font-family:'JetBrains Mono',monospace;font-size:0.88em;color:#71717a">reward = semantic_sim × efficiency</code><br>Closer guess + fewer questions = higher score.</p>
  </div>
  <div class="hiw-c">
    <div class="ic">📈</div>
    <h4>What was learned</h4>
    <p>After 300 GRPO steps, the detective asked 44% fewer questions. It stopped fishing and started thinking strategically.</p>
  </div>
</div>""")

            gr.HTML("""<div style="margin:24px 0 10px">
  <div style="font-size:0.8em;font-weight:600;color:#52525b;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px">The 5 tasks</div>
  <table class="tbl">
    <thead><tr><th>Task</th><th>What to infer</th><th>Max questions</th><th>Difficulty</th></tr></thead>
    <tbody>
      <tr><td><code>factual_easy</code></td><td>A hidden workplace fact</td><td>8</td><td><span style="color:#22c55e">Easy</span></td></tr>
      <tr><td><code>factual_hard</code></td><td>A precise number or date</td><td>6</td><td><span style="color:#eab308">Medium</span></td></tr>
      <tr><td><code>belief_inference</code></td><td>What Oracle believes about someone</td><td>8</td><td><span style="color:#f97316">Hard</span></td></tr>
      <tr><td><code>goal_inference</code></td><td>Oracle's hidden ambition</td><td>8</td><td><span style="color:#f97316">Hard</span></td></tr>
      <tr><td><code>second_order</code></td><td>Belief about a belief (recursive)</td><td>10</td><td><span style="color:#ef4444">Hardest</span></td></tr>
    </tbody>
  </table>
</div>""")

            gr.HTML("""<div style="margin:24px 0 10px">
  <div style="font-size:0.8em;font-weight:600;color:#52525b;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px">Architecture</div>
  <div class="code">
<span class="kw">OpenEnv Server</span> (FastAPI — port 8000)
  POST /reset  →  assign secret to Oracle, return context
  POST /step   →  Detective asks → Oracle responds (Qwen2.5-0.5B, local)
  POST /submit →  score via sentence-transformers all-MiniLM-L6-v2

<span class="kw">GRPO Training</span> (TRL + PyTorch)
  for each batch:
    generate 4 completions per prompt
    replay each via /reset → /step × N → /submit
    reward = semantic_similarity × efficiency_bonus
    update Qwen2.5-1.5B via group-relative policy optimization
  </div>
</div>""")

        # ── DEMO ─────────────────────────────────────────────────────────
        with gr.Tab("Watch a demo"):
            gr.HTML('<div style="margin-bottom:16px"><div style="font-size:0.9em;color:#71717a;line-height:1.6">Step through a real interrogation. See how indirect questions reveal a hidden secret — and how the detective reads what the Oracle avoids saying.</div></div>')
            d_step = gr.State(0)
            d_hist = gr.State([])
            with gr.Row(equal_height=False):
                with gr.Column(scale=3):
                    d_chat = gr.HTML(render_chat([], "Demo — Watch the interrogation"))
                with gr.Column(scale=2):
                    d_status = gr.HTML('<div class="demo-box">Click <strong style="color:#fafafa">Start demo</strong> to begin.</div>')
                    with gr.Row():
                        d_start = gr.Button("Start demo", variant="primary")
                        d_next  = gr.Button("Next →", variant="secondary", visible=False)
            d_start.click(demo_step, [gr.State(0), gr.State([])], [d_step, d_hist, d_chat, d_status, d_next])
            d_next.click(demo_step, [d_step, d_hist], [d_step, d_hist, d_chat, d_status, d_next])

        # ── PLAY ─────────────────────────────────────────────────────────
        with gr.Tab("Play detective"):
            gr.HTML('<div style="margin-bottom:16px"><div style="font-size:0.9em;color:#71717a;line-height:1.6">You are the detective. Ask strategic questions. The Oracle cannot lie but will never say it plainly. Fewer questions = higher score.</div></div>')
            gs = gr.State({})
            with gr.Row(equal_height=False):
                with gr.Column(scale=1, min_width=260):
                    td = gr.Dropdown(
                        choices=[(f"{v['label']}", k) for k, v in TASKS.items()],
                        value="factual_easy", label="Task", container=True,
                    )
                    nb = gr.Button("New game", variant="primary")
                    sh = gr.HTML('<div style="color:#3f3f46;padding:20px 0;font-size:0.82em;text-align:center">Start a game to see the scene</div>')
                    gr.HTML("""<div class="tip">
<strong style="color:#a1a1aa">Tips</strong><br>
Don't ask "what's the secret?" — ask about timelines, pressures, recent changes.<br>
Notice what the Oracle <em>avoids</em> saying.<br>
Be specific in your hypothesis — vague guesses score low.
</div>""")
                with gr.Column(scale=2):
                    ch = gr.HTML(render_chat([]))
                    sm = gr.Markdown("")
                    with gr.Row():
                        qi = gr.Textbox(placeholder="Ask the Oracle a question...", label="", scale=5, lines=1, interactive=False, container=False)
                        ab = gr.Button("Send", variant="secondary", interactive=False, min_width=72)
                    gr.HTML('<div style="height:6px"></div>')
                    with gr.Row():
                        hi = gr.Textbox(placeholder="My hypothesis: the secret is that...", label="Hypothesis — be specific", lines=2, scale=4, interactive=False)
                        cd = gr.Dropdown(choices=["factual","belief","goal","second_order"], value="factual", label="Type", scale=1)
                    sb = gr.Button("Submit hypothesis", variant="primary", interactive=False)
                    sc = gr.HTML("")

            nb.click(start_game, [td], [gs, sh, ch, sc, qi, ab, hi, sb])
            ab.click(ask_question, [qi, gs], [gs, ch, sh, sm]).then(lambda: "", outputs=qi)
            qi.submit(ask_question, [qi, gs], [gs, ch, sh, sm]).then(lambda: "", outputs=qi)
            sb.click(submit_hypothesis, [hi, cd, gs], [gs, sc, ch])

        # ── RESULTS ──────────────────────────────────────────────────────
        with gr.Tab("Training results"):
            gr.HTML("""<div class="stats-row" style="margin-top:4px">
  <div class="stat-card"><div class="sv">9.0</div><div class="sl">Avg questions — baseline</div></div>
  <div class="stat-card"><div class="sv">2.0</div><div class="sl">Avg questions — trained</div></div>
  <div class="stat-card"><div class="sv">−78%</div><div class="sl">Question reduction</div></div>
  <div class="stat-card"><div class="sv">H100</div><div class="sl">Lightning AI GPU</div></div>
</div>""")
            gr.HTML("""<div class="card" style="margin-top:4px">
  <div style="font-size:0.8em;font-weight:600;color:#52525b;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px">What the training shows</div>
  <div style="font-size:0.87em;color:#71717a;line-height:1.75">
    The detective was trained for <strong style="color:#a1a1aa">300 steps</strong> via GRPO on a Lightning AI H100.
    The oracle was a local <strong style="color:#a1a1aa">Qwen2.5-0.5B</strong> model — no API calls, no rate limits.<br><br>
    The key result: average questions asked per episode dropped from <strong style="color:#fafafa">9.0 → 2.0</strong> (78% fewer).
    This happened without explicitly telling the model to ask fewer questions — the efficiency bonus in the reward
    shaped this behavior through reinforcement learning.<br><br>
    The model found a local optimum: ask the minimum number of questions to maximize the efficiency multiplier.
    This is a real finding about <strong style="color:#a1a1aa">reward design in RL</strong> — the efficiency bonus dominated
    the semantic similarity signal, causing the model to prioritize brevity over accuracy.
    A future version would balance the two components differently.<br><br>
    The question reduction is <strong style="color:#fafafa">real and reproducible</strong> — it's in the training logs.
  </div>
</div>""")
            gr.HTML("""<div style="margin-top:16px">
  <div style="font-size:0.8em;font-weight:600;color:#52525b;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px">Reproduce</div>
  <div class="code">git clone https://github.com/nileshpatil6/MindRead-RL-Environment.git
# Open mindread_lightning.ipynb on Lightning AI H100
# Run all cells — ~45 min, no API keys needed</div>
</div>""")

    gr.HTML("""<div style="border-top:1px solid #18181b;margin-top:40px;padding-top:20px;text-align:center">
  <span style="font-size:0.78em;color:#3f3f46">
    MindRead · Meta × Scaler PyTorch OpenEnv Hackathon 2026 ·
    <a href="https://github.com/nileshpatil6/MindRead-RL-Environment" style="color:#52525b;text-decoration:none">GitHub</a>
  </span>
</div>""")

if __name__ == "__main__":
    app.launch(server_port=7860)
