# Two-minute challenge demo

Run these commands from `challenges/beeline-tariff-campaigns`:

| Time | Say | Show |
| --- | --- | --- |
| 0:00–0:20 | A marketing analyst needs to choose profitable tariff campaigns despite uncertain outcomes and contact costs. | State the objective: net ARPU uplift minus communication spend. Mention all data is synthetic. |
| 0:20–0:50 | The agent explores candidate audience/offer pairs with limited pilots. | Run `python local_eval.py`; point to pilot count, campaign choices, spend, and score. |
| 0:50–1:20 | Pilot results inform the final plan, subject to the hard budget and reach limits. | Show the relevant decision logic in `agent.py` and the accepted campaign rows in the evaluator output. |
| 1:20–1:45 | The result is reproducible and the agent handles noisy pilot outcomes. | Run `python local_eval.py --runs 10`; summarize spread and positive runs without claiming mock results predict judging results. |
| 1:45–2:00 | The delivered artifacts are runnable code and its generated plan. | Run `python make_submission.py`; show `submission.csv`. |

The local evaluator uses mock effects. It demonstrates the interface, pilot use, constraints, scoring mechanics, and reproducibility; it does not predict the hidden judging score. There is no frontend or deployed URL because the case requires a Python agent and CSV submission.
