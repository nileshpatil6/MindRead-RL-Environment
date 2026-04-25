"""
GRPO training script for the MindRead Detective.

The Detective (Qwen2.5-1.5B-Instruct) generates full episode trajectories
in one completion. The reward function executes each trajectory against the
live Oracle environment and returns a score in [0.0, 1.0].

Usage:
    python -m training.grpo_train --task factual_easy --steps 300

Run the environment server first:
    bash scripts/start.sh
"""

import argparse
import json
from pathlib import Path

import torch
from datasets import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import GRPOConfig, GRPOTrainer

from training.mindread_grpo_env import MindReadGRPOEnv, DETECTIVE_SYSTEM, DETECTIVE_USER_TEMPLATE

MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
ENV_URL = "http://localhost:7860"

TASK_IDS = ["factual_easy", "factual_hard", "belief_inference", "goal_inference", "second_order"]


def build_prompt_dataset(env: MindReadGRPOEnv, task_id: str, n_episodes: int = 200) -> Dataset:
    prompts = []
    meta_list = []

    for _ in range(n_episodes):
        try:
            obs = env.reset(task_id=task_id)
        except Exception as e:
            print(f"[warn] reset failed: {e}")
            continue

        system, user = env.build_prompt(obs)
        prompt = f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"
        prompts.append({"prompt": prompt})
        meta_list.append({"episode_id": obs["episode_id"], "obs": obs})

    dataset = Dataset.from_list(prompts)
    dataset = dataset.add_column("episode_meta", [json.dumps(m) for m in meta_list])
    return dataset


def make_reward_fn(env: MindReadGRPOEnv):
    def mindread_reward(completions: list[str], episode_meta: list[str], **kwargs) -> list[float]:
        rewards = []
        for completion, meta_str in zip(completions, episode_meta):
            meta = json.loads(meta_str)
            episode_id = meta["episode_id"]
            obs = meta["obs"]
            try:
                result = env.evaluate_completion(episode_id, completion, obs)
                rewards.append(result.reward)
            except Exception as e:
                print(f"[warn] reward eval failed for {episode_id}: {e}")
                rewards.append(0.0)
        return rewards
    return mindread_reward


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="factual_easy", choices=TASK_IDS)
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--episodes", type=int, default=200)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--output", default="mindread-detective-v1")
    parser.add_argument("--env-url", default=ENV_URL)
    args = parser.parse_args()

    env = MindReadGRPOEnv(base_url=args.env_url)

    print(f"[grpo] Loading model: {MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )

    print(f"[grpo] Building prompt dataset: {args.episodes} episodes for task={args.task}")
    dataset = build_prompt_dataset(env, task_id=args.task, n_episodes=args.episodes)

    config = GRPOConfig(
        output_dir=args.output,
        learning_rate=args.lr,
        max_steps=args.steps,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        num_generations=4,
        max_completion_length=512,
        bf16=torch.cuda.is_available(),
        logging_steps=5,
        save_steps=50,
        report_to=["tensorboard"],
        remove_unused_columns=False,
    )

    reward_fn = make_reward_fn(env)

    trainer = GRPOTrainer(
        model=model,
        args=config,
        train_dataset=dataset,
        reward_funcs=reward_fn,
        processing_class=tokenizer,
    )

    print(f"[grpo] Training for {args.steps} steps...")
    trainer.train()

    model.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output)
    print(f"[grpo] Saved to {args.output}")


if __name__ == "__main__":
    main()
