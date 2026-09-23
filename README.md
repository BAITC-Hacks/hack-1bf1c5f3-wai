# Beeline Tariff Campaign Agent

This repository contains a Python agent for the HackAlem tariff campaign case. It examines a synthetic subscriber audience, conducts small pilot campaigns through the supplied environment, and returns a tariff, audience, and channel plan. The case data and local results are synthetic; they do not describe real Beeline customers or performance.

The current agent is a runnable baseline for the three-person team. The supplied local evaluator tests the real interface and scoring mechanics against mock effects. Its score does not predict the hidden judging score.

## Project structure

| Path | Purpose and owner |
| --- | --- |
| `challenges/beeline-tariff-campaigns/agent.py` | Required `Agent.act(env)` entry point and pilot loop; captain |
| `challenges/beeline-tariff-campaigns/candidate_research.py` | Audience cells and weak historical tariff hypotheses; data lead |
| `challenges/beeline-tariff-campaigns/campaign_planner.py` | Turns pilot observations into resource-checked final campaigns; planner and QA lead |
| `challenges/beeline-tariff-campaigns/requirements.txt` | Python dependencies |
| `challenges/beeline-tariff-campaigns/submission.csv` | Reproducible output from `make_submission.py`; regenerate after every policy change |
| `challenges/beeline-tariff-campaigns/tests/` | Public-contract and reproducibility checks |
| `challenges/beeline-tariff-campaigns/data/` and `customer_profile.csv` | Organizer-supplied synthetic data; leave source files intact |
| `challenges/beeline-tariff-campaigns/environment.py`, `scoring_core.py`, `local_eval.py`, `make_submission.py` | Organizer-supplied interface and verification tools; leave intact |
| `docs/team-tasks-beeline.md` | Three-person assignments, integration contract, and checkpoints |

The [participant guide](challenges/beeline-tariff-campaigns/PARTICIPANT_GUIDE.md) is the case specification. The [requirements summary](docs/beeline-case-requirements.md) and [task board](docs/team-tasks-beeline.md) are implementation aids.

## Set up and verify

Use Python 3.9 or newer. From the repository root on macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r challenges/beeline-tariff-campaigns/requirements.txt
cd challenges/beeline-tariff-campaigns
python -m unittest discover -s tests -v
python local_eval.py
python local_eval.py --runs 10
python make_submission.py
```

On Windows PowerShell, activate the environment with `.venv\Scripts\Activate.ps1` before the `pip` command. Run the last three commands **inside** `challenges/beeline-tariff-campaigns`, because the supplied scripts use relative data paths.

The evaluator should show at least one pilot and no rejected or clipped final campaign. Inspect its campaign details as well as the final net result: the scorer can silently truncate a campaign that exceeds a resource limit. `make_submission.py` uses seed 42. Run it twice after the final agent edit and confirm `submission.csv` is unchanged.

## Current decision flow

1. `candidate_research.py` groups the supplied audience into disjoint current-tariff, ARPU, and data-use cells. It uses historical tariff changes as a weak ordering prior and omits cells with missing required filters.
2. `agent.py` pilots up to three candidate cells through the public `env.run_pilot` interface, recording the observed ratio, actual contacts, and cost.
3. `campaign_planner.py` discounts noisy observations by one pilot standard error, selects at most three disjoint final campaigns, and checks audience size, remaining contacts, and remaining money before returning them.

The baseline uses SMS for sufficiently positive pilots and a low-cost push fallback otherwise. It has no LLM or external account dependency. Historical transition frequency is not an absolute conversion probability; the history covers a different audience. The team should improve exploration, channel choice, uncertainty treatment, and resilience to hidden effects without tuning constants to the mock score.

`agent.py` currently imports the two team helper modules. Keep them in the submitted repository, or fold their code into `agent.py` before the final handoff if the organizer collects only the named submission artifacts. Regenerate `submission.csv` from that exact final code.

## Constraints and limits

The agent must return 1 to 10 valid campaigns, use at most 20 pilots of 10 to 200 customers, reach at most 5,000 customers per campaign and 15,000 contacts overall, spend at most 100,000 units including pilots, and finish within 10 minutes. It must use pilot observations in its decisions and only access the public environment interface and supplied participant files. See the participant guide for the complete rules.
