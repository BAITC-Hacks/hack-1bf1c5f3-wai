# Agent strategy experiment plan

Date: 2026-09-23. Status: complete. Results: [agent-improvement-results.md](agent-improvement-results.md).

## Question

Which changes improve net simulated ARPU gain while preserving the public pilot interface, reproducibility, resource limits, and resilience to effects that differ from history?

## Work and dependencies

| Step | Question | Inputs | Estimate | Owner |
| --- | --- | --- | --- | --- |
| 1 | What does the current policy achieve? | Official evaluator, current agent, seeds 0–29 | 5 min | Coordinator |
| 2 | Can pilots buy more useful information with fewer resources? | Public pilot feedback, historical candidate estimates | 15–25 min | Pilot investigation |
| 3 | Can final allocation improve value per contact and budget unit? | Same pilot observations, profile, channel parameters | 15–25 min | Planner investigation |
| 4 | Are decisions robust to noisy observations and failures? | Public interface stubs, contract tests, source review | 10–20 min | Robustness investigation |
| 5 | Which independent improvements work together? | Selected variants and paired seeds | 10–15 min | Coordinator |
| 6 | Does the final artifact satisfy the contract? | Official single and ten-run checks, submission regeneration | 5 min | Coordinator |

Steps 2–4 run in parallel. Estimated elapsed effort: 35–50 minutes, plus approximately 15% contingency. All required participant data and the Python environment are available locally.

## Method

Use seeds 0–9 for development comparisons, then seeds 10–29 for initial validation. Compare mean, median, minimum, paired wins, contacts, cost, pilots, and runtime. Reserve additional seeds for the combined final policy. Seed variation tests pilot noise; it does not test different hidden effect models. Use public-interface synthetic scenarios for observations and failure behavior, without exposing evaluation internals to the agent. Keep organizer scripts and source data unchanged.

## Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Better mock score does not transfer to hidden judging | High | Prefer resource-aware mechanisms over tariff constants; disclose the limit of seed-only validation |
| Independently good changes interact poorly | Medium | Evaluate combined policy against the original baseline on paired runs |
| Exploration spends resources with little decision value | Medium | Compare channels and sample sizes with their opportunity cost |
| Planner relies on scorer truncation or wastes overlapping contacts | Medium | Check full requested audiences against limits and model incremental gain |
| Agent failure loses final plan after successful pilots | Medium | Exercise fallback paths with public-interface tests |

## Deliverables

Improved Python agent and helper modules, reproducible comparison evidence, updated approach documentation, passing required checks, and regenerated submission.csv. No frontend or deployment work is needed.
