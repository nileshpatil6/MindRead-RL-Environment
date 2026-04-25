"""
Live training dashboard using the rich library.
Reads TensorBoard logs or a metrics JSONL file and displays them in real-time.

Usage:
    python -m training.dashboard --log-dir mindread-detective-v1
"""

import argparse
import json
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich import box

console = Console()

TASK_BASELINES = {
    "factual_easy": 0.42,
    "factual_hard": 0.21,
    "belief_inference": 0.33,
    "goal_inference": 0.29,
    "second_order": 0.14,
}


def read_metrics(log_dir: Path) -> list[dict]:
    metrics_file = log_dir / "training_metrics.jsonl"
    if not metrics_file.exists():
        return []
    lines = metrics_file.read_text(encoding="utf-8").strip().split("\n")
    records = []
    for line in lines:
        try:
            records.append(json.loads(line))
        except Exception:
            pass
    return records


def build_dashboard(records: list[dict], task_id: str) -> Panel:
    if not records:
        return Panel(
            "[yellow]Waiting for training data...[/yellow]\n"
            "Make sure grpo_train.py is running and writing to training_metrics.jsonl",
            title="[bold blue]MindRead Detective — GRPO Training[/bold blue]",
        )

    latest = records[-1]
    baseline = TASK_BASELINES.get(task_id, 0.3)

    table = Table(box=box.ROUNDED, expand=True)
    table.add_column("Step", style="cyan", width=8)
    table.add_column("Avg Reward", style="green", width=12)
    table.add_column("vs Baseline", style="yellow", width=12)
    table.add_column("Avg Questions", style="blue", width=14)
    table.add_column("Semantic", style="magenta", width=12)
    table.add_column("Loss", style="red", width=10)

    for rec in records[-20:]:
        step = str(rec.get("step", "?"))
        reward = rec.get("avg_reward", 0.0)
        semantic = rec.get("avg_semantic", 0.0)
        questions = rec.get("avg_questions", 0.0)
        loss = rec.get("loss", 0.0)
        delta = reward - baseline

        delta_str = f"[green]+{delta:.3f}[/green]" if delta >= 0 else f"[red]{delta:.3f}[/red]"
        table.add_row(
            step,
            f"{reward:.4f}",
            delta_str,
            f"{questions:.1f}",
            f"{semantic:.4f}",
            f"{loss:.4f}",
        )

    current_reward = latest.get("avg_reward", 0.0)
    current_q = latest.get("avg_questions", 0.0)
    improvement = ((current_reward - baseline) / baseline * 100) if baseline > 0 else 0

    summary = (
        f"\n[bold]Step:[/bold] {latest.get('step', '?')}  "
        f"[bold]Current Reward:[/bold] [green]{current_reward:.4f}[/green]  "
        f"[bold]Baseline:[/bold] {baseline:.4f}  "
        f"[bold]Improvement:[/bold] [{'green' if improvement >= 0 else 'red'}]{improvement:+.1f}%[/]  "
        f"[bold]Avg Questions:[/bold] [blue]{current_q:.1f}[/blue]\n"
    )

    content = Text.from_markup(summary)

    return Panel(
        content.__str__() + "\n" + table.__rich_console__.__doc__ or "",
        title=f"[bold blue]MindRead GRPO Dashboard — Task: {task_id}[/bold blue]",
    )


def run_dashboard(log_dir: Path, task_id: str, refresh_seconds: float = 3.0):
    console.print(f"[bold]MindRead GRPO Training Dashboard[/bold]")
    console.print(f"Log dir: {log_dir}")
    console.print(f"Task: {task_id}")
    console.print(f"Baseline reward: {TASK_BASELINES.get(task_id, 'unknown')}")
    console.print("Refreshing every 3s. Press Ctrl+C to exit.\n")

    with Live(refresh_per_second=0.5, console=console) as live:
        while True:
            records = read_metrics(log_dir)
            table = make_rich_table(records, task_id)
            live.update(table)
            time.sleep(refresh_seconds)


def make_rich_table(records: list[dict], task_id: str):
    baseline = TASK_BASELINES.get(task_id, 0.3)

    if not records:
        return Panel(
            "[yellow]Waiting for training data...[/yellow]\n"
            "Ensure grpo_train.py is running and writing training_metrics.jsonl",
            title="[bold blue]MindRead Detective — GRPO Training[/bold blue]",
        )

    table = Table(
        title=f"MindRead GRPO — Task: {task_id} | Baseline: {baseline:.3f}",
        box=box.ROUNDED,
        expand=True,
    )
    table.add_column("Step", style="cyan", width=8)
    table.add_column("Avg Reward", style="green", width=12)
    table.add_column("vs Baseline", width=12)
    table.add_column("Avg Questions", style="blue", width=14)
    table.add_column("Semantic", style="magenta", width=12)
    table.add_column("Loss", style="red", width=10)

    for rec in records[-25:]:
        step = str(rec.get("step", "?"))
        reward = rec.get("avg_reward", 0.0)
        semantic = rec.get("avg_semantic", 0.0)
        questions = rec.get("avg_questions", 0.0)
        loss = rec.get("loss", 0.0)
        delta = reward - baseline

        delta_str = f"+{delta:.3f}" if delta >= 0 else f"{delta:.3f}"
        delta_style = "green" if delta >= 0 else "red"
        table.add_row(
            step,
            f"{reward:.4f}",
            f"[{delta_style}]{delta_str}[/{delta_style}]",
            f"{questions:.1f}",
            f"{semantic:.4f}",
            f"{loss:.4f}",
        )

    return table


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-dir", default="mindread-detective-v1")
    parser.add_argument("--task", default="factual_easy")
    parser.add_argument("--refresh", type=float, default=3.0)
    args = parser.parse_args()

    log_dir = Path(args.log_dir)
    run_dashboard(log_dir, task_id=args.task, refresh_seconds=args.refresh)


if __name__ == "__main__":
    main()
