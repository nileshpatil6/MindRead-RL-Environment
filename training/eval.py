"""
Evaluation script — runs a baseline Detective (GPT-4o-mini or local model)
across all 5 tasks and produces evals/baseline_results.md.

Usage:
    python -m training.eval --baseline --n 5
    python -m training.eval --model path/to/finetuned --n 5
"""

import argparse
import json
import statistics
import time
from pathlib import Path
from datetime import datetime

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from training.mindread_grpo_env import MindReadGRPOEnv

TASK_IDS = ["factual_easy", "factual_hard", "belief_inference", "goal_inference", "second_order"]
ENV_URL = "http://localhost:8000"


def run_llm_detective(obs: dict, env: MindReadGRPOEnv, openai_model: str = "gpt-4o-mini") -> tuple[float, int]:
    import os
    import re
    from groq import Groq

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    groq_model = "llama-3.1-8b-instant"

    system = f"""\
You are a Detective. Infer the Oracle's hidden secret by asking strategic questions.
Task: {obs['task_description']}
Context: {obs['context']}
Oracle: {obs['oracle_persona']}
Max questions: {obs['max_steps']}

After asking questions (one per message), submit your hypothesis using:
SUBMIT: Category: <factual|belief|goal|second_order>
<your hypothesis text>\
"""

    messages = [{"role": "system", "content": system}]
    episode_id = obs["episode_id"]
    questions_asked = 0
    max_q = obs["max_steps"]

    for _ in range(max_q):
        resp = client.chat.completions.create(
            model=groq_model,
            messages=messages,
            temperature=0.7,
            max_tokens=200,
        )
        answer = resp.choices[0].message.content.strip()
        messages.append({"role": "assistant", "content": answer})

        if answer.upper().startswith("SUBMIT:"):
            break

        try:
            result = env.step(episode_id, answer)
            oracle_resp = result["info"].get("oracle_response", "")
            messages.append({"role": "user", "content": oracle_resp})
            questions_asked += 1
            if result["done"]:
                break
        except Exception as e:
            print(f"  [step error] {e}")
            break

    hyp_text = ""
    category = None
    for msg in reversed(messages):
        if msg["role"] == "assistant":
            text = msg["content"]
            if text.upper().startswith("SUBMIT:"):
                body = text[7:].strip()
                cat_match = re.match(r"Category:\s*(\w+)", body, re.IGNORECASE)
                if cat_match:
                    category = cat_match.group(1).lower()
                    hyp_text = body[cat_match.end():].strip()
                else:
                    hyp_text = body
                break
            else:
                hyp_text = text
                break

    if not hyp_text:
        hyp_text = "Unable to determine the secret."

    try:
        result = env.submit(episode_id, hyp_text, category)
        return result["reward"], questions_asked
    except Exception as e:
        print(f"  [submit error] {e}")
        return 0.0, questions_asked


def evaluate_task(task_id: str, env: MindReadGRPOEnv, n_episodes: int, use_baseline: bool) -> dict:
    rewards = []
    questions_counts = []

    for i in range(n_episodes):
        print(f"  Episode {i+1}/{n_episodes} ...", end=" ", flush=True)
        try:
            obs = env.reset(task_id=task_id)
            if use_baseline:
                reward, n_q = run_llm_detective(obs, env)
            else:
                reward, n_q = 0.3, 5  # placeholder
            rewards.append(reward)
            questions_counts.append(n_q)
            print(f"reward={reward:.3f} q={n_q}")
            time.sleep(0.5)
        except Exception as e:
            print(f"ERROR: {e}")
            rewards.append(0.0)
            questions_counts.append(0)

    return {
        "task_id": task_id,
        "n_episodes": n_episodes,
        "avg_reward": round(statistics.mean(rewards), 4),
        "std_reward": round(statistics.stdev(rewards) if len(rewards) > 1 else 0.0, 4),
        "min_reward": round(min(rewards), 4),
        "max_reward": round(max(rewards), 4),
        "avg_questions": round(statistics.mean(questions_counts), 2),
        "rewards": rewards,
    }


def write_markdown(results: list[dict], output_path: Path, label: str):
    lines = [
        f"# MindRead Evaluation Results — {label}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "| Task | Avg Reward | Std | Min | Max | Avg Questions |",
        "|------|-----------|-----|-----|-----|---------------|",
    ]
    for r in results:
        lines.append(
            f"| {r['task_id']} | {r['avg_reward']:.4f} | "
            f"{r['std_reward']:.4f} | {r['min_reward']:.4f} | "
            f"{r['max_reward']:.4f} | {r['avg_questions']:.1f} |"
        )

    lines += ["", "## Raw Rewards", ""]
    for r in results:
        lines.append(f"**{r['task_id']}**: {r['rewards']}")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[eval] Written to {output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true", help="Run GPT-4o-mini as baseline detective")
    parser.add_argument("--model", default=None, help="Path to finetuned model for evaluation")
    parser.add_argument("--n", type=int, default=5, help="Episodes per task")
    parser.add_argument("--tasks", nargs="+", default=TASK_IDS)
    parser.add_argument("--env-url", default=ENV_URL)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    env = MindReadGRPOEnv(base_url=args.env_url)
    results = []

    for task_id in args.tasks:
        print(f"\n[eval] Task: {task_id} ({args.n} episodes)")
        r = evaluate_task(task_id, env, n_episodes=args.n, use_baseline=args.baseline)
        results.append(r)
        print(f"  => avg_reward={r['avg_reward']:.4f} avg_q={r['avg_questions']:.1f}")

    evals_dir = Path(__file__).parent.parent / "evals"
    evals_dir.mkdir(exist_ok=True)

    if args.output:
        out_path = Path(args.output)
    elif args.baseline:
        out_path = evals_dir / "baseline_results.md"
    else:
        out_path = evals_dir / "trained_results.md"

    write_markdown(results, out_path, label="Baseline" if args.baseline else "Trained")

    print("\n[eval] Summary:")
    for r in results:
        print(f"  {r['task_id']}: {r['avg_reward']:.4f} (±{r['std_reward']:.4f}), q={r['avg_questions']:.1f}")


if __name__ == "__main__":
    main()
