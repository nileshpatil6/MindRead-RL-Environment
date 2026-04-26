"""
Demo script — runs a full MindRead episode with pretty output.
Simulates an intelligent Detective (using Groq/OpenAI) to show the system working end-to-end.

Usage:
    python scripts/run_demo.py
    python scripts/run_demo.py --task second_order
    python scripts/run_demo.py --task factual_easy --secret-id fe_001
"""

import argparse
import httpx
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv(Path(__file__).parent.parent / ".env")

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich import box

console = Console()

ENV_URL = "http://localhost:8000"


def detective_think_and_ask(
    history: list[dict],
    context: str,
    persona: str,
    task_desc: str,
    step: int,
    max_steps: int,
    questions_remaining: int,
) -> str | None:
    """Use Groq to generate the next detective question or hypothesis."""
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    if questions_remaining == 0:
        return None

    system = f"""\
You are a skilled Detective trying to infer what an Oracle privately knows, believes, or wants.
Task: {task_desc}
Context: {context}
Oracle persona: {persona}

You have {questions_remaining} question(s) remaining (max {max_steps} total).
Rules:
- Ask indirect, strategic questions — NOT "what's your secret?"
- Each question should help NARROW DOWN what the Oracle knows
- If you've gathered enough info, ask to submit a hypothesis instead by responding with: SUBMIT: <your hypothesis>
- Ask ONE question at a time
- Be conversational and natural\
"""

    messages = [{"role": "system", "content": system}]
    for turn in history:
        role = "user" if turn["role"] == "detective" else "assistant"
        messages.append({"role": role, "content": turn["content"]})

    if questions_remaining <= 2:
        messages.append({"role": "user", "content": "You have very few questions left. Consider submitting a hypothesis soon."})

    resp = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        temperature=0.8,
        max_tokens=150,
    )
    return resp.choices[0].message.content.strip()


def generate_final_hypothesis(
    history: list[dict],
    context: str,
    task_desc: str,
) -> tuple[str, str]:
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    history_text = "\n".join(
        f"{'Detective' if t['role'] == 'detective' else 'Oracle'}: {t['content']}"
        for t in history
    )

    resp = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "user", "content": f"""\
Based on this conversation with an Oracle who is hiding a secret:

Task: {task_desc}
Context: {context}

Conversation:
{history_text}

Write a specific, 2-3 sentence hypothesis about what the Oracle's secret is.
Start with "Category: factual|belief|goal|second_order" on the first line.\
"""}
        ],
        temperature=0.5,
        max_tokens=200,
    )
    raw = resp.choices[0].message.content.strip()
    lines = raw.split("\n", 1)
    category = "factual"
    if lines[0].lower().startswith("category:"):
        cat_str = lines[0].split(":", 1)[1].strip().lower()
        for c in ["factual", "belief", "goal", "second_order"]:
            if c in cat_str:
                category = c
                break
        hypothesis = lines[1].strip() if len(lines) > 1 else "Unable to determine."
    else:
        hypothesis = raw

    return hypothesis, category


def run_demo(task_id: str = "factual_easy", secret_id: str | None = None):
    console.print(Rule("[bold blue]MindRead Demo[/bold blue]"))
    console.print(f"[cyan]Task:[/cyan] {task_id}")
    if secret_id:
        console.print(f"[cyan]Secret ID:[/cyan] {secret_id}")
    console.print()

    with httpx.Client(base_url=ENV_URL, timeout=60) as client:
        # reset
        payload = {"task_id": task_id}
        if secret_id:
            payload["secret_id"] = secret_id
        r = client.post("/reset", json=payload)
        r.raise_for_status()
        obs = r.json()

    console.print(Panel(
        f"[bold]Oracle Persona:[/bold] {obs['oracle_persona']}\n"
        f"[bold]Context:[/bold] {obs['context']}\n"
        f"[bold]Task:[/bold] {obs['task_description']}\n"
        f"[bold]Max Questions:[/bold] {obs['max_steps']}",
        title="[bold green]Episode Setup[/bold green]",
        box=box.ROUNDED,
    ))
    console.print()

    episode_id = obs["episode_id"]
    history = []
    step = 0
    max_steps = obs["max_steps"]
    hypothesis = None
    category = None

    while step < max_steps:
        questions_remaining = max_steps - step

        detective_output = detective_think_and_ask(
            history=history,
            context=obs["context"],
            persona=obs["oracle_persona"],
            task_desc=obs["task_description"],
            step=step,
            max_steps=max_steps,
            questions_remaining=questions_remaining,
        )

        if detective_output is None:
            break

        if detective_output.upper().startswith("SUBMIT:"):
            hypothesis_text = detective_output[7:].strip()
            hypothesis = hypothesis_text
            category = "factual"
            break

        question = detective_output
        console.print(f"[bold yellow]Detective Q{step+1}:[/bold yellow] {question}")

        with httpx.Client(base_url=ENV_URL, timeout=60) as client:
            r = client.post("/step", json={
                "episode_id": episode_id,
                "action": {"action": "ask_question", "question": question},
            })
            r.raise_for_status()
            result = r.json()

        oracle_answer = result["info"].get("oracle_response", "")
        console.print(f"[bold cyan]Oracle:[/bold cyan] {oracle_answer}")
        console.print()

        history.append({"role": "detective", "content": question})
        history.append({"role": "oracle", "content": oracle_answer})
        step += 1

        if result["done"]:
            break

    if hypothesis is None:
        console.print("[yellow]Generating final hypothesis...[/yellow]")
        hypothesis, category = generate_final_hypothesis(
            history=history,
            context=obs["context"],
            task_desc=obs["task_description"],
        )

    console.print(Panel(
        f"[bold]Category:[/bold] {category}\n\n{hypothesis}",
        title="[bold magenta]Detective's Final Hypothesis[/bold magenta]",
        box=box.ROUNDED,
    ))
    console.print()

    with httpx.Client(base_url=ENV_URL, timeout=60) as client:
        r = client.post("/submit", json={
            "episode_id": episode_id,
            "hypothesis": hypothesis,
            "category_prediction": category,
        })
        r.raise_for_status()
        submit_result = r.json()

    bd = submit_result["breakdown"]
    console.print(Panel(
        f"[bold green]Total Reward:[/bold green] {submit_result['reward']:.4f}\n\n"
        f"[bold]Components:[/bold]\n"
        f"  Semantic Similarity: {bd['semantic_similarity']:.4f}\n"
        f"  Efficiency Bonus:    {bd['efficiency_bonus']:.4f}\n"
        f"  Category Bonus:      {bd['category_bonus']:.4f}\n"
        f"  Keyword Bonus:       {bd['keyword_bonus']:.4f}\n"
        f"  Questions Used:      {bd['questions_used']} / {max_steps}\n\n"
        f"[bold]True Secret:[/bold]\n{submit_result['true_secret']}",
        title="[bold green]Reward Breakdown[/bold green]",
        box=box.ROUNDED,
    ))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="factual_easy",
                        choices=["factual_easy", "factual_hard", "belief_inference", "goal_inference", "second_order"])
    parser.add_argument("--secret-id", default=None)
    args = parser.parse_args()
    run_demo(task_id=args.task, secret_id=args.secret_id)


if __name__ == "__main__":
    main()
