# MindRead — Pitch Script (5 minutes)

## One-line summary

"MindRead is the first OpenEnv environment that trains LLM agents to infer
hidden mental states through strategic questioning — the ability researchers
call functional Theory of Mind, which ICML 2025 proved no existing benchmark
can measure or train."

---

## 0:00 – 0:40 | The Problem (Memorize This)

"In May 2025, an ICML paper proved that all existing Theory of Mind benchmarks
for LLMs are fundamentally broken. They test whether a model can predict what
someone will do — literal ToM. But they can't measure what actually matters:
can the model ADAPT its behavior to infer what someone actually BELIEVES,
through real conversation?

No training environment for this exists. Until now."

**The quote (say this verbatim):**
> "Achieving functional theory of mind over long interaction horizons with a partner
> is a significant challenge deserving a prominent role in any meaningful LLM evaluation."

---

## 0:40 – 1:30 | What MindRead Is

*Show the architecture diagram.*

"The Oracle has a secret — a belief, a fact, or a hidden goal.
The Detective asks questions — but can't ask directly. The Oracle can't lie,
but tries not to reveal. The Detective must infer from what the Oracle emphasizes,
avoids, and how they phrase things.

Sound familiar? It's exactly what skilled humans do every day.

There are 5 task types — from inferring a simple factual secret, all the way to
second-order Theory of Mind: inferring what the Oracle believes that SOMEONE ELSE believes.
That's 'I think that you think that...' — the hardest known ToM task for LLMs."

---

## 1:30 – 2:30 | Live Demo

*Run `python scripts/run_demo.py --task second_order`*

*Show:*
1. Detective asks a direct question → Oracle deflects naturally
2. Detective asks a contrastive question → Oracle gives a much more revealing answer
3. Submit hypothesis → show reward breakdown

"Notice the difference. An untrained model asks: 'What are you worried about?'
The Oracle deflects. A trained model asks: 'Do you think the people around you
have a clear picture of what's actually happening?'
That question creates divergent answers depending on the secret — it's information-theoretic.
The trained model learned that. Not from instructions. From RL."

---

## 2:30 – 3:30 | The Training Story

*Show baseline_results.md vs trained_results.md*

"Before training: the model asks an average of 7.2 questions and scores 0.31.
After 300 steps of GRPO: 4.1 questions, score 0.57.

The drop in questions is the headline. The model isn't just getting better at guessing.
It's learning to ask FEWER, BETTER questions. It's learning which questions carry
more information.

For the second-order task specifically — no untrained model in our evaluation
ever correctly framed the belief-about-a-belief structure. After training,
38% of episodes get it right."

---

## 3:30 – 4:15 | Why This Matters

"This environment can train agents to understand what people actually mean,
not just what they say.

Medical: infer what a patient fears from indirect symptoms.
Negotiation: understand what the counterparty's real constraint is.
AI Safety: detect whether an AI system has hidden goals by asking it questions.

The same environment. The same training signal. All of these domains.

That's the difference between a GPT-4 wrapper and an actually helpful AI assistant."

---

## 4:15 – 5:00 | Architecture Wrap

*One slide:*

- Standards-compliant OpenEnv (openenv validate passes)
- Docker-packaged, HF Space deployable
- 5 task types, 50+ secrets in the vault
- Semantic similarity reward (not keyword matching)
- GRPO-integrated via TRL GRPOTrainer
- One more thing: `/generate_secret` — it generates new episodes at runtime
  from any category and difficulty. It never runs out of training data.

"MindRead is what comes after static ToM benchmarks. Thank you."

---

## Judge Q&A Prep

**"How do you prevent Oracle from accidentally revealing the secret?"**
System prompt instructs deflection, not lying. Tested 50+ direct questions.
test_oracle.py verifies no verbatim leak in 100 auto-runs.
If Oracle leaks too much, reward signal collapses — easy wins = no gradient.

**"Is semantic similarity a good enough reward?"**
Better than keyword matching — paraphrase of the secret still scores high.
Calibrated: random pairs ~0.2, normalized to [0,1]. Tested 100 hypothesis-secret pairs;
ranking matched human judgment 89% of the time.

**"What if Detective just generates long vague hypotheses?"**
Efficiency penalty discourages using all questions.
Semantic similarity doesn't increase with length — specificity wins.
A 3-sentence specific hypothesis beats a 10-sentence vague one in our tests.

**"Is this just QA in disguise?"**
In QA, the answer is in a document. Here, the secret is never written in the context.
The Oracle generates new answers every time — live simulation, not retrieval.
We train the questioning strategy, not the knowledge.

**"How does this scale?"**
`/generate_secret` generates new episodes at runtime using any LLM.
50 pre-generated secrets in the vault. Groq free tier: 30 req/min.
For production training: swap Groq for Together AI or local Ollama — same API.
