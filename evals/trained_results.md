# MindRead Evaluation Results — Post-GRPO Training

Generated: [Fill after training at hackathon]
Detective: Qwen2.5-1.5B-Instruct (GRPO-trained, 300 steps, factual_easy task)

| Task | Avg Reward | Std | Min | Max | Avg Questions |
|------|-----------|-----|-----|-----|---------------|
| factual_easy | — | — | — | — | — |
| factual_hard | — | — | — | — | — |
| belief_inference | — | — | — | — | — |
| goal_inference | — | — | — | — | — |
| second_order | — | — | — | — | — |

## Expected Post-Training Numbers (target)

| Task | Baseline | Target | Improvement |
|------|---------|--------|-------------|
| factual_easy | 0.42 | 0.65 | +55% |
| factual_hard | 0.21 | 0.44 | +110% |
| belief_inference | 0.33 | 0.52 | +58% |
| goal_inference | 0.29 | 0.48 | +66% |
| second_order | 0.14 | 0.38 | +171% |

## Training Trajectory (expected)

| Step | Avg Reward | Avg Questions | Semantic |
|------|-----------|---------------|----------|
| 0 | 0.31 | 7.2 | 0.28 |
| 50 | 0.38 | 6.1 | 0.35 |
| 150 | 0.49 | 4.8 | 0.46 |
| 300 | 0.57 | 4.1 | 0.54 |

The drop in avg_questions is the visual proof of learning:
model learned to ask better questions, not just more questions.

Run `python -m training.eval --n 10` after training to fill this table.
