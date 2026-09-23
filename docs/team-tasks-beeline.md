# Three person Beeline sprint plan

This is the working task board for the Beeline tariff campaigns case. The judge's primary path is the Python agent in `challenges/beeline-tariff-campaigns/`: run pilots through `env.run_pilot`, return 1 to 10 valid campaigns, and regenerate `submission.csv`. The repository has been trimmed to this Python submission path; the case does not require a frontend or deployment. Spend the five-hour window on the agent and its reproducibility.

## Current state and dependencies

| Item | Observed state | Consequence |
| --- | --- | --- |
| Challenge package | `environment.py`, `scoring_core.py`, `local_eval.py`, `make_submission.py`, and `agent_template.py` are present | The interface and scoring mechanics can be tested locally |
| Required submission | No `agent.py` or `submission.csv`; `challenges/beeline-tariff-campaigns/requirements.txt` is present | No valid submission or evaluator run exists until `agent.py` is implemented |
| Python runtime | Verify the selected Python environment can import `pandas` and `numpy` | Install dependencies from the challenge `requirements.txt` before evaluation |
| Dataset | All five case data CSVs and both dictionaries are present | Candidate research can start immediately |
| Top-level README | Describes the Python task and points to this plan | Keep setup and verification instructions aligned with the implementation |

Read [case requirements](beeline-case-requirements.md), `challenges/beeline-tariff-campaigns/PARTICIPANT_GUIDE.md`, and the evaluator code before editing the policy. Run case commands **from the challenge directory**, because the supplied scripts read `data/...` and `customer_profile.csv` relative to the current directory:

```bash
cd challenges/beeline-tariff-campaigns
python local_eval.py
python local_eval.py --runs 10
python make_submission.py
```

The first local data scan found 23,441 audience rows and a `predicted_arpu` sum of 150,641,084.25, matching the case baseline after rounding. Subscriber IDs are unique in this file. It also found 95 rows with a blank `current_tariff` and 5 with a blank `arpu_segment`; exclude or safely handle those rows when constructing target segments. The historical change file has 14,823 data rows, one fewer than the case text states; only 168 of the 420 possible ordered transitions between distinct tariffs appear. No historical subscriber ID overlaps the current audience. These are structural checks, not a completed statistical data audit.

## Work split

The three people should take separate file areas during development. The captain owns `agent.py` and the final submission; the other two deliver narrow, testable helpers for integration. By the final freeze, either fold those helpers into `agent.py` or include and document every imported file in the submitted repository. Do not modify organizer-supplied evaluator or scoring files to improve a local result.

### Person 1 — Captain and agent integration

**C1. Establish a valid baseline, 45 minutes.** Confirm `challenges/beeline-tariff-campaigns/requirements.txt` matches the actual Python libraries used and implement a minimal `agent.py` with `Agent.act(env)`. It must make at least one affordable pilot, use its observed result, and return at least one valid campaign even when a pilot is disappointing. Use only the public `env` interface and participant data. Acceptance: `python local_eval.py` finishes, reports `Пилотов проведено > 0`, and prints no `Кампания ... отброшена` message. This task unblocks everyone.

**C2. Own the pilot decision loop, 100 minutes.** Consume candidate hypotheses from Person 2, call pilots with valid segments and 10 to 200 customers, update estimates using the returned `observed_lift_ratio` and actual `n_customers`, and preserve `remaining_budget`, `remaining_contacts`, and `pilots_left`. Use the noisy observation to change the final selection; a fixed campaign list after pilots does not meet the case. Catch pilot and optional LLM failures and return a valid fallback. Acceptance: different pilot observations can change the returned plan, and a failed optional API call does not crash `act`.

**C3. Integrate and submit, 105 minutes.** Connect Person 2's priors and Person 3's planner; review the complete output and own the final `README.md`, `submission.csv`, and handoff. Describe installation, architecture, data sources, limitations, commands, and the fact that the case data are synthetic. Run `python make_submission.py` twice with no edits and confirm the generated CSV is identical. Acceptance: all required files are in the organizer repository, the README commands work from a clean environment, and a fresh run reproduces `submission.csv`.

### Person 2 — Data and candidate research

**D1. Profile inputs, 45 minutes.** Record row counts, key uniqueness, missing values, tariff and segment coverage, joins, and outliers relevant to campaign choice. Investigate the blank audience fields and the 14,823 versus 14,824 history count. Keep the audit in `docs/data-profile.md`; do not imply synthetic results describe the real operator. Acceptance: every input file has a documented grain, and candidate generation has explicit handling for missing and sparse data.

**D2. Build weak historical priors, 100 minutes.** Create an isolated helper such as `historical_priors.py` that reads only supplied participant data. Estimate transition direction and sample size by current tariff, target tariff, and ARPU segment. The share of one target among recorded changes can be used as a ranking proxy, but it is not an absolute conversion probability because the history does not contain all contacted non-converters. Use shrinkage or a fallback for rare and absent transitions; the 168 observed ordered tariff pairs do not cover the full search space. Rank a small set of plausible audience and tariff hypotheses without treating history as the true evaluation effect. Acceptance: the helper emits candidate records with valid filters, target tariff, estimated audience size, historical estimate, and support count; it works when a transition has no history.

**D3. Review pilots against priors, 75 minutes.** Compare early pilot observations with historical estimates, flag segments that reverse sign, and recommend where extra pilot sample size is worthwhile. Avoid tuning constants to the mock score. Acceptance: provide the captain a short list of candidate changes justified by participant data and pilot evidence, with counts attached.

### Person 3 — Resource planner, evaluation, and demo proof

**P1. Implement campaign selection, 100 minutes.** Create an isolated planner helper that takes candidate estimates, pilot evidence, the customer profile, and remaining resources, then returns at most 10 valid campaign dictionaries. Estimate each filtered audience before selecting it; choose channel using expected ARPU gain per contact and channel cost. Reserve room for pilot contacts, cap each campaign at 5,000, keep total contacts at or below 15,000, keep spend at or below 100,000, and avoid duplicate targeting that pays twice for one subscriber. Acceptance: the final campaigns require no evaluator clipping for campaign size, contacts, or money and have no empty audience filters.

**P2. Own the evaluation loop, 100 minutes.** Run `python local_eval.py` and then `python local_eval.py --runs 10` after integration. Check `n_pilots`, `n_campaigns`, `campaigns_detail`, caps, spend, contacts, runtime, negative-effect share, and whether the net result changes sign across seeds. Compare behavior to the supplied starter agent only as a diagnostic; mock net gain is not the hidden judging score. Report concrete failures to the owner of the relevant component. Acceptance: no crashes or dropped campaigns, 1 to 10 final campaigns, at least one pilot, no clipping, and a documented 10-seed result.

**P3. Prepare judge evidence, 50 minutes.** Update `docs/demo-script.md` to show the actual CLI run, pilots, resource accounting, final campaigns, and a reproducible CSV. Help the captain check README commands in a clean Python environment. Acceptance: a teammate can follow the two-minute script without a frontend, personal account, or API key.

## Integration contract

Agree on one candidate record within the first 20 minutes. Suggested fields: `filter_current_tariff`, `filter_arpu_segment`, optional `filter_data_segment` and `filter_call_segment`, `target_tariff`, `channel`, `audience_size`, `prior_ratio`, and `prior_count`. Person 1 adds pilot observations (`observed_lift_ratio`, actual `n_customers`, and cost); Person 3 converts the combined records to final campaign dictionaries. The actual `env.run_pilot` signature in `environment.py` accepts all three segment filters plus current tariff. It can contact fewer customers than requested when a segment or resource is exhausted, so use the returned counts.

The evaluator sanitizes unknown tariffs and channels, and silently truncates campaigns that exceed size, contact, or money limits. Therefore the acceptance check is the detailed report: no dropped campaign messages, no `capped_at_campaign_limit`, `capped_at_reach_budget`, or `capped_at_money_budget` flags, and no zero-contact final campaign. `make_submission.py` uses seed 42, so any randomness outside the environment must be seeded to keep `submission.csv` reproducible.

## Five-hour checkpoints

| Time from start | Required state |
| --- | --- |
| 0:00–0:20 | Confirm file ownership, Python environment, candidate interface, and official repository |
| 0:20–1:00 | First runnable `agent.py` with a real pilot and valid campaign; data scan and planner skeleton in parallel |
| 1:00–2:30 | Historical priors and resource planner integrated; hourly repository progress recorded |
| 2:30–3:45 | Iterate on pilot allocation, uncertainty, and overlap using 10-seed diagnostics |
| 3:45–4:30 | Freeze behavior; finish README, requirements, demo script, and reproducible CSV |
| 4:30–5:00 | Fresh install and run, final evaluator check, commit to the official repo, submit before the cutoff |

The planned work is about 250 minutes per person, leaving roughly 50 minutes for integration surprises and final verification. Commit a working intermediate result at the end of each competition hour, as required by the general rules.

## Risks and scope decisions

- **Environment mismatch:** Confirm `pandas` and `numpy` are available in the Python interpreter used for evaluation. A successful check in another runtime does not validate the submission environment.
- **Noisy pilots and hidden effects:** Small pilots can reverse the apparent sign, and judging effects differ from the mock. Use support counts and uncertainty; optimize the decision procedure rather than the seed-42 score.
- **Sparse or missing fields:** Blank profile fields and unobserved historical transitions can produce empty or misleading segments. Filter or back off explicitly.
- **Evaluator truncation:** An apparently successful run may have silently clipped campaigns. Inspect every campaign detail and leave resource headroom.
- **Conflicting time notes:** The case headline says nine hours, while the general event rules set a five-hour development window from 13:00 to 18:00. Plan against five hours unless organizers clarify otherwise.
- **Scope:** No frontend, deployment, new API routes, or presentation features are required for this case. Add them only after the Python deliverable is valid and reproducible.
