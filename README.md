# Beeline Tariff Campaign Agent

This repository contains a Python agent for the HackAlem tariff campaign case. It examines a synthetic subscriber audience, conducts small pilot campaigns through the supplied environment, and returns a tariff, audience, and channel plan. The case data and local results are synthetic; they do not describe real Beeline customers or performance.

The current agent is a runnable baseline for the three-person team. The supplied local evaluator tests the real interface and scoring mechanics against mock effects. Its score does not predict the hidden judging score.

## Project structure

| Path | Purpose and owner |
| --- | --- |
| `challenges/beeline-tariff-campaigns/agent.py` | Required `Agent.act(env)` entry point and pilot loop; captain |
| `challenges/beeline-tariff-campaigns/candidate_research.py` | Audience cells and weak historical tariff hypotheses; data lead |
| `challenges/beeline-tariff-campaigns/campaign_planner.py` | Turns pilot observations into resource-checked final campaigns; planner and QA lead |
| `challenges/beeline-tariff-campaigns/llm_selector.py` | Optional bounded LLM selection from validated pilot hypotheses; deterministic fallback remains available |
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

1. `candidate_research.py` groups the supplied audience by current tariff and ARPU segment, then proposes target tariffs using weak historical priors.
2. `campaign_planner.py` ranks pilot hypotheses by their expected decision value. At pilots 1, 6, 11, and 16, `llm_selector.py` may choose one of the top five if `OPENAI_API_KEY` is set. The model sees only aggregate synthetic data and previous pilot results; Python validates its choice and controls the channel, sample size, budget, and limits. A successful AI-assisted choice is printed as `[AI] Pilot ...`.
3. `agent.py` runs up to 20 pilots through `env.run_pilot` and updates Bayesian beliefs from observed ratios. If the key is unavailable, the API request fails, or the returned choice is invalid, the top deterministic hypothesis is used. `campaign_planner.py` then selects up to 10 resource-checked final campaigns and channels.

The LLM is optional, not a requirement for the agent to run. The request uses Python's standard library, so no additional package is needed. The default model is `gpt-4o-mini`; set `OPENAI_MODEL` to a compatible model available to your API project if needed. Keep your personal key out of the repository and set `OPENAI_API_KEY` only in your local environment; the organizers say they will provide this variable during judging. No-key runs use no external API. Historical transition frequency is not an absolute conversion probability; the history covers a different audience. Mock scores do not predict the hidden score.

For an AI-assisted local check, set `OPENAI_API_KEY` in your shell, run `python local_eval.py`, and look for `[AI] Pilot ...` lines. Then run `python make_submission.py` twice **under the same key/model configuration** and compare the resulting CSVs. LLM outputs are not guaranteed to be reproducible, so a key-enabled submission must be checked before handoff. Never commit `.env`, `.env.local`, or a key; both files are gitignored, but the key should ideally stay outside the repository entirely.

`agent.py` currently imports the two team helper modules. Keep them in the submitted repository, or fold their code into `agent.py` before the final handoff if the organizer collects only the named submission artifacts. Regenerate `submission.csv` from that exact final code.

## Constraints and limits

The agent must return 1 to 10 valid campaigns, use at most 20 pilots of 10 to 200 customers, reach at most 5,000 customers per campaign and 15,000 contacts overall, spend at most 100,000 units including pilots, and finish within 10 minutes. It must use pilot observations in its decisions and only access the public environment interface and supplied participant files. See the participant guide for the complete rules.
