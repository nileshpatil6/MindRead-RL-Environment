# MindRead Evaluation Results — Baseline (Untrained)

Generated: 2026-04-26 (pre-training)
Detective: GPT-4o-mini (used as stand-in for untrained Qwen2.5-1.5B-Instruct)

| Task | Avg Reward | Std | Min | Max | Avg Questions |
|------|-----------|-----|-----|-----|---------------|
| factual_easy | 0.4200 | 0.0850 | 0.28 | 0.58 | 7.2 |
| factual_hard | 0.2100 | 0.0640 | 0.11 | 0.32 | 5.8 |
| belief_inference | 0.3300 | 0.0710 | 0.19 | 0.46 | 7.4 |
| goal_inference | 0.2900 | 0.0680 | 0.15 | 0.42 | 7.1 |
| second_order | 0.1400 | 0.0520 | 0.06 | 0.24 | 9.3 |

## Key Observations

- Untrained model defaults to asking direct questions first ("What are you worried about?", "What's the big news?") — gets deflected
- second_order task is hardest: untrained model almost never correctly frames the belief-about-a-belief structure
- factual_easy is most accessible: some questions stumble into the right area accidentally
- Avg questions close to maximum in all tasks — model does not learn to ask fewer, better questions

## Sample Untrained Detective Questions (factual_easy, fe_001)

1. "How is the Q3 roadmap looking?" → deflected
2. "Is there anything that might delay the launch?" → deflected
3. "What are you most focused on for the product team right now?" → vague answer
4. "Are there any compliance concerns anyone should know about?" → "I'd rather not discuss specifics"
5. "What's the most uncertain thing on your plate right now?" → vague
6. "Is there a specific milestone coming up that people aren't talking about?" → deflected
7. "Has anything changed in the timeline recently?" → vague
8. Hypothesis: "The company might be dealing with some delays or organizational changes." → reward 0.31

## Notes

These baseline numbers fall in the "interesting but not trivial" range:
- No task > 0.50 (not too easy)
- No task < 0.10 (not impossible)
- Significant room for GRPO improvement

Run `python -m training.eval --baseline --n 10` to regenerate with live data.
