# Kickoff sheet

This project addresses the Beeline tariff marketing campaigns case. The detailed implementation and submission checklist is in [beeline-case-requirements.md](beeline-case-requirements.md).

The three-person ownership and timed task board is in [team-tasks-beeline.md](team-tasks-beeline.md).

## Prompt and constraints

- Track: Beeline tariff marketing campaigns.
- Exact task prompt: Build an agent that uses pilots to choose up to 10 tariff migration campaigns, deciding whom to target, which tariff to offer, and which communication channel to use while maximizing net ARPU uplift after contact costs.
- Required inputs and outputs: Consume the supplied environment and synthetic subscriber data; return 1 to 10 valid campaign dictionaries from `Agent.act(env)` and generate `submission.csv` with `python make_submission.py`.
- Rules, deadline, and submission format: Work in the organizer-provided repository during the official 13:00-18:00 window. Respect the 100,000-unit budget, 15,000-contact limit, 20-pilot limit, 10-200 customers per pilot, 5,000 customers per campaign, and 10-minute evaluation runtime. Submit runnable `agent.py` and reproducible `submission.csv`.
- Required proof of tool use or AI use: The evaluation output must show more than zero pilots, and the code must visibly use `env.run_pilot(...)` results. LLM use is optional; if used, the key must come from `OPENAI_API_KEY` and the agent must retain a fallback path.

## Rubric

| Criterion | Weight | Evidence we will show |
| --- | ---: | --- |
| Task fit and functionality | 25 | Successful evaluator run, valid campaign plan, and no `Кампания ... отброшена` messages |
| Technical implementation | 25 | Traceable pilot-selection, uncertainty, allocation, and fallback logic |
| README and reproducibility | 25 | Fresh-clone setup, run, evaluation, and submission instructions |
| Value and applicability | 15 | Net-uplift objective with explicit communication economics |
| Development potential and originality | 10 | Adaptive exploration and extensible decision policy |

## Chosen journey

- User: A marketing analyst planning next month's tariff campaigns.
- User action: Runs the agent on the current subscriber audience and supplied historical data.
- Visible outcome: A reproducible plan of up to 10 campaigns with audience filters, target tariffs, communication channels, and resource use informed by live pilots.
- Why it matters: It replaces slow manual scenario selection with a budget-aware policy that learns uncertain effects before committing campaign spend.

## Scope

| Must demo | If time allows | Cut |
| --- | --- | --- |
| Valid `Agent.act(env)`; adaptive pilot use; hard-limit enforcement; valid campaigns; deterministic fallback; reproducible submission | Confidence-aware allocation; sequential pilot refinement; segment-specific channel choice; multi-run robustness reporting | Extra dashboards, unrelated APIs, and features that do not improve evaluator performance or reproducibility |

## Acceptance test

In one minute, a judge can run `python local_eval.py`, see that the agent conducts pilots, stays within every limit, and returns 1 to 10 accepted campaigns. We prove reproducibility with `python local_eval.py --runs 10` and `python make_submission.py`.
