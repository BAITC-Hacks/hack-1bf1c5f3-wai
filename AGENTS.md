# Beeline challenge project instructions

## Source of truth

- Read `challenges/beeline-tariff-campaigns/PARTICIPANT_GUIDE.md` before changing the agent.
- Keep organizer-supplied challenge scripts and data unchanged unless a verified defect requires a fix. `environment.py`, `scoring_core.py`, and `local_eval.py` define the local interface and scoring mechanics.
- The project deliverable is a Python `agent.py` and reproducible `submission.csv`; no frontend or deployment is required.
- The data is synthetic and must not be described as actual Beeline customer data or business results.

## Agent requirements

- Implement `Agent.act(env)` in `challenges/beeline-tariff-campaigns/agent.py`.
- Call `env.run_pilot(...)` and base final decisions on observed pilot results.
- Respect all simultaneous limits: 10 campaigns, 5,000 customers per campaign, 15,000 total contacts, 100,000 budget units, and 20 pilots of 10–200 customers each.
- Do not inspect environment internals or bypass pilots. Handle decision-path failures so completed pilots are not wasted.
- Keep the solution runnable within the evaluator's 10-minute limit. Use only dependencies documented in the README/requirements file.

## Verification and handoff

Run the official checks from the challenge directory:

```powershell
python local_eval.py
python local_eval.py --runs 10
python make_submission.py
```

Do not report a check as passing unless it was run. Explain any remaining limitation and ensure `submission.csv` is regenerated from the final agent code.
