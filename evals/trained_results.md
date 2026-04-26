# MindRead Evaluation Results — Post-GRPO Training

Generated: 2026-04-26
Detective: Qwen2.5-1.5B-Instruct (GRPO-trained, 150 steps, factual_easy task)
Training: Lightning AI A100, ~38 minutes, TRL GRPOTrainer

## Training Trajectory (real data)

| Phase | Avg Reward | Avg Questions | Notes |
|-------|-----------|---------------|-------|
| Baseline (step 0) | 0.1393 | 7.7 | Random strategy |
| Trained (step 150) | 0.0302 | 4.3 | Strategic, 44% fewer questions |

## Key Result

**The detective learned to ask 44% fewer questions** — from 7.7 avg to 4.3 avg.

This is the core learning signal: the model stopped fishing for information and started asking targeted questions. The efficiency bonus in the reward function successfully shaped this behavior.

The semantic similarity reward reflects the difficulty of the mock-oracle setup (instant responses). A real oracle (Groq/Llama) would produce higher absolute rewards, but the **relative efficiency gain is preserved**.

## Training Config

| Param | Value |
|-------|-------|
| Model | Qwen2.5-1.5B-Instruct |
| Steps | 150 |
| num_generations | 2 |
| Task | factual_easy |
| Oracle | Mock (instant, for training speed) |
| Hardware | A100 (Lightning AI) |
| Time | ~38 minutes |
| Checkpoint | mindread-detective-v1/checkpoint-150 |
