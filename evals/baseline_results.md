# MindRead Evaluation Results — Baseline
Generated: 2026-04-26 07:20

| Task | Avg Reward | Std | Min | Max | Avg Questions |
|------|-----------|-----|-----|-----|---------------|
| factual_easy | 0.1393 | 0.0929 | 0.0330 | 0.2048 | 7.7 |
| factual_hard | 0.1124 | 0.1936 | 0.0000 | 0.3359 | 6.0 |
| belief_inference | 0.0949 | 0.1368 | 0.0000 | 0.2517 | 5.3 |
| goal_inference | 0.0562 | 0.0494 | 0.0000 | 0.0929 | 5.7 |
| second_order | 0.1734 | 0.0525 | 0.1225 | 0.2273 | 10.0 |

## Raw Rewards

**factual_easy**: [0.033, 0.18, 0.2048]
**factual_hard**: [0.0013, 0.0, 0.3359]
**belief_inference**: [0.2517, 0.0329, 0.0]
**goal_inference**: [0.0758, 0.0, 0.0929]
**second_order**: [0.2273, 0.1703, 0.1225]

## Key Observations

- **second_order uses all 10 questions every time** — untrained model has no strategy
- **goal_inference is hardest** (0.056) — hidden ambitions hardest to infer cold
- All avg_questions near maximum — no efficiency learned without RL
- Connection timeouts on some episodes = Groq rate limit (30 req/min), not a system error

## Target Post-GRPO Numbers

| Task | Baseline | Target | Expected Improvement |
|------|---------|--------|---------------------|
| factual_easy | 0.139 | 0.40+ | +188% |
| factual_hard | 0.112 | 0.30+ | +168% |
| belief_inference | 0.095 | 0.28+ | +195% |
| goal_inference | 0.056 | 0.22+ | +293% |
| second_order | 0.173 | 0.38+ | +120% |

Expected avg_questions after GRPO: 4-5 (down from 7-10 now).
The drop in questions is the visual proof that RL worked.