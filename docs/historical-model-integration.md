# Historical-model integration investigation

Date: 2026-09-23. Synthetic challenge data and effects only; these are not actual Beeline business results or predictions of hidden judging scores.

**Built and tested five ways to borrow teammate main's empirical-Bayes model. Two selected integrations improved official mock scores but failed separate reserved scenario comparisons. Neither was adopted; the production agent remains the original dauren version.**

## What was implemented

The reusable [transition_prior.py](../challenges/beeline-tariff-campaigns/experiments/transition_prior.py) comes from teammate commit `e2b864d`. It models historical transitions using price-gap regression, destination effects, pair effects and smoothed destination shares. No dependencies beyond existing numpy and pandas were added.

Both selected integrations kept individual source-tariff/ARPU cells, 189 target hypotheses across all 63 cells, the existing pilot selector, uncertainty penalty for push, resource allocation, and recovery after completed pilots. They also fall back to the original historical/price candidate logic if the new model fails or produces no finite estimates for a cell.

1. **Full-prior integration:** empirical-Bayes means select the top three targets per cell and initialize beliefs; uncertainty stays at the original SD 0.15. [Frozen source](../challenges/beeline-tariff-campaigns/experiments/integration_rejected/).
2. **Ranking-only integration:** empirical-Bayes estimates rank targets, but belief means retain the original count-shrunk direct historical estimates. Previously unseen transitions start at zero, to be learned through pilots. It changes 62 of 189 targets; the other 127 retain identical priors. [Frozen source](../challenges/beeline-tariff-campaigns/experiments/integration_rank_snapshot/).

Other development variants used larger model-dependent uncertainty, the union of original and model-ranked targets, or model means only for selected transitions with fewer than five historical events. They were not selected for reserved evaluation.

The model module is available for further experiments, but the active `agent.py`, `candidate_research.py` and `campaign_planner.py` do not import it and are unchanged from `e822ad1`.

## Evaluation design

The earlier three stress-test tables were excluded from selection and validation. New tables were frozen before evaluating candidates. Four families represent strongly predictive history, moderate change, history-independent effects, and reversal. Their shifts include shared destination and source-cell components plus independent transition components. This is a constructed test suite, not a representative sample of the unknown judge distribution.

Development used one world per family, two pilot seeds per world, and official mock seeds 0–9. Round one compared baseline, teammate, and three variants. Its selected candidate was frozen before evaluating mock seeds 100–129 and three reserved worlds per family, using pilot seeds 1700–1701.

After rejecting that candidate, round two tested two narrower approaches on the development set. Its selected ranking-only version was frozen before evaluating different mock seeds 200–229 and entirely new worlds 4–6, using pilot seeds 2700–2701. Round-one validation results were already known and were not represented as a holdout for round two. Model/source hashes and selection decisions are recorded before each reserved comparison.

There are 28 distinct artificial worlds in total: four development worlds and 24 reserved worlds. Every comparison uses the same effect table and pilot seed for all agents, with fresh environments. Matching seeds do not force identical pilot audiences when policies choose different campaigns. The agents receive only the documented environment; effect tables and scorer state remain in the evaluator.

## First integration: promising development, failed reserved comparison

On development, the full-prior integration increased mock median from 4.808M to 5.115M and improved three artificial-family means. The strongly predictive family declined 4.42%. This candidate was selected for validation without inspecting the reserved results.

Reserved mock seeds 100–129:

| Metric | Original dauren | Teammate main | Full-prior integration |
|---|---:|---:|---:|
| Mean | 4,679,420 | 4,872,685 | 4,846,554 |
| Median | 4,792,641 | 4,778,281 | 4,907,207 |

The integration won 19/30 paired mock runs, but every reserved artificial-family mean declined:

| Family, six runs each | Original mean | Integration mean | Change |
|---|---:|---:|---:|
| Strongly predictive history | 5,259,283 | 5,078,877 | -3.43% |
| Moderate shifts | 4,232,350 | 3,936,713 | -6.99% |
| Independent of history | 3,520,771 | 3,200,910 | -9.08% |
| Reversed history | 4,545,562 | 1,597,976 | -64.85% |

The candidate was rejected. Its source remains frozen; its validation report calls it `integrated`, reflecting the name used during evaluation.

## Second integration: ranking alone still changes exploration materially

The ranking-only version improved all five development means, including the official mock. It kept historical beliefs unchanged for retained targets and made extrapolated targets neutral, addressing the first version's tendency to treat model predictions as campaign gains.

Reserved mock seeds 200–229:

| Metric | Original dauren | Teammate main | Ranking-only integration |
|---|---:|---:|---:|
| Mean | 4,612,223 | 4,953,938 | 4,707,633 |
| Median | 4,721,151 | 4,939,696 | 4,821,538 |

The integration won 21/30 paired mock runs and improved mean by 2.07%. However:

| Family, six runs each | Original mean | Integration mean | Change | Integration wins |
|---|---:|---:|---:|---:|
| Strongly predictive history | 5,554,386 | 5,840,655 | +5.15% | 5/6 |
| Moderate shifts | 5,467,968 | 4,863,499 | -11.05% | 1/6 |
| Independent of history | 4,277,579 | 3,315,296 | -22.50% | 1/6 |
| Reversed history | 2,701,176 | 1,159,171 | -57.09% | 1/6 |

This candidate was also rejected. Keeping the number of candidates constant does not preserve the same exploration opportunities: 62 target changes still alter which effects can be discovered within 20 pilots. These results support that concern, but do not isolate every cause of the score differences.

## Decision and limitations

Keep our original policy as the active submission. The initial recommendation to investigate borrowing the model was a hypothesis; these experiments did not establish a robust improvement from the tested integrations. The model and runnable alternatives are preserved for review instead of silently replacing the submission based on favorable development scores.

The official mock continues to favor teammate main on mean score in both reserved batches. Artificial tests do not prove our original agent will beat it at judging. The tests contain only three reserved worlds per family per round and two pilot seeds per world. All agents have some negative artificial runs, so none is universally robust. No aggregate across incompatible family score scales is used to claim a judging advantage.

All **468 development and reserved evaluations** returned resource-compliant final plans. Numerical-model failure, unsupported cells, neutral unseen transitions, retained belief means, pilot dependence and broad cell coverage have dedicated tests. Existing selection/feedback/planning recovery tests remain in place.

After restoring the production policy, ran:

- `python -m unittest discover -s tests -v`: **17 passed**. Experimental ranking tests explicitly import the frozen candidate; production contract/recovery tests use the active agent.
- `python local_eval.py`: **PASS**, seed 42 net **5,063,252**, 20 pilots, six final campaigns, 15,000 contacts and 99,932 budget units.
- `python local_eval.py --runs 10`: **10/10 positive**, median **4,808,448**.
- `python make_submission.py` twice: matching hashes; regenerated submission has no change from the original tracked CSV.

The checks used the existing challenge `.venv`. Organizer files and supplied datasets were not changed. No commit or push was made.

## Reproduction and artifacts

From the challenge directory with its virtual environment activated:

```powershell
python experiments/integrate_prior.py --stage development
python experiments/integrate_prior.py --stage validation --candidate rejected
python experiments/integrate_prior.py --round 2 --stage development
python experiments/integrate_prior.py --round 2 --stage validation --candidate rank_rejected
```

These commands rewrite their corresponding result reports. Frozen candidate labels `rejected` and `rank_rejected` replace the original evaluation label `integrated`, without changing the tested source. The active submission is not temporarily overwritten during reproduction.

- [Round-one development](../challenges/beeline-tariff-campaigns/experiments/integration_development.json) and [validation](../challenges/beeline-tariff-campaigns/experiments/integration_validation.json).
- [Round-two development](../challenges/beeline-tariff-campaigns/experiments/integration_development_round2.json) and [validation](../challenges/beeline-tariff-campaigns/experiments/integration_validation_round2.json).
- [First selection record](../challenges/beeline-tariff-campaigns/experiments/integration_selection.json), [second selection record](../challenges/beeline-tariff-campaigns/experiments/integration_selection_round2.json), and [comparison summary](../challenges/beeline-tariff-campaigns/experiments/integration_conclusion.json).
- [Plan and chronology](../challenges/beeline-tariff-campaigns/experiments/prior_integration_plan.md).
