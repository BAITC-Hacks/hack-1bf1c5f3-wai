# Beeline Tariff Campaign Agent

A Python agent for the HackAlem Beeline tariff marketing campaigns case. It uses noisy pilot campaigns to learn which subscriber segments and tariff offers are worth contacting, then returns up to 10 campaigns while respecting the budget and contact limits. The supplied data is synthetic and does not represent real Beeline customers or performance.

## Challenge package

The organizer-provided task, data, environment, and evaluation scripts are in [`challenges/beeline-tariff-campaigns`](challenges/beeline-tariff-campaigns):

- `PARTICIPANT_GUIDE.md` is the authoritative task description.
- `customer_profile.csv` and `data/*.csv` contain the supplied synthetic audience and historical data.
- `environment.py` defines the agent-facing pilot interface.
- `mock_environment.py` and `scoring_core.py` support local evaluation; mock effects validate mechanics, not the judging score.
- `local_eval.py` checks the agent against the mock environment.
- `make_submission.py` generates the reproducible `submission.csv` artifact.
- `agent_template.py` is a deliberately weak example, not a finished solution.

The [three-person sprint plan](docs/team-tasks-beeline.md) contains proposed ownership, dependencies, data findings, and acceptance checks.

## Required implementation

Create `agent.py` in `challenges/beeline-tariff-campaigns` with an `Agent` class and an `act(env)` method. It must run at least one pilot through `env.run_pilot(...)`, use the observed pilot results in its choices, and return 1–10 valid campaign dictionaries. Keep all decisions within the simultaneous limits described in the participant guide. The judge journey is command-line based; this task does not require a frontend or web deployment.

## Run and verify

Run commands from the challenge directory so the supplied scripts can resolve their relative data paths:

```powershell
cd challenges/beeline-tariff-campaigns
python -m pip install -r requirements.txt
python local_eval.py
python local_eval.py --runs 10
python make_submission.py
```

The evaluator should report at least one pilot, no rejected campaigns, and no resource-limit violations. Check its detailed output for silently clipped campaigns. The multi-run command checks stability across random pilot seeds. Regenerate `submission.csv` from the final `agent.py` before submission.

## Current status

The organizer package and task documentation are present. The required team implementation `challenges/beeline-tariff-campaigns/agent.py` has not yet been created, so the evaluator and submission commands will not work until that file is implemented. No frontend is part of the case requirements.
