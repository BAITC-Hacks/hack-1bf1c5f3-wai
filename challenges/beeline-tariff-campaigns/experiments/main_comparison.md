# Teammate main versus dauren

Date: 2026-09-23. All scores use synthetic challenge data; none describe actual Beeline customers or business results.

**The 4.9M+ median claim is reproducible. Main improves official mock performance, but the evidence does not support replacing our agent wholesale.** Keep the current decision policy and failure recovery; investigate historical modeling as a separate candidate-ranking improvement.

## Versions and method

- Current branch `dauren`: `e822ad18e2bfd8f93fc59e077997cefa9cbe1be0`.
- Fetched teammate `main`: `e2b864d8c326cfc1311c9a64feab1e38b4406052`.
- Exact teammate participant sources are saved in [main_snapshot](main_snapshot). The additional `transition_prior.py` is required; copying only `agent.py` would not reproduce his solution.
- Organizer environment, scoring, local evaluator, mock generator, customer profile and participant datasets have no Git differences between these versions.
- Both versions run through the same official `local_eval.evaluate_agent` with fresh environments and paired seeds. All four participant module names are isolated during loading. Source hashes and complete scores are recorded in [main_comparison_results.json](main_comparison_results.json).
- Seeds change pilot sampling/noise, not the official underlying effect table. Different policies may select different pilot audiences even on matching seeds.

## Official mock results

| Metric | Current agent | Teammate main |
|---|---:|---:|
| Median, seeds 0–9 | 4,808,448 | **4,964,549** |
| Median, seeds 0–29 | 4,820,573 | **5,070,084** |
| Mean, seeds 0–29 | 4,803,932 | **4,983,221** |
| Minimum, seeds 0–29 | 4,047,357 | **4,605,940** |
| Maximum, seeds 0–29 | **5,357,115** | 5,293,803 |
| Seed 42 | 5,063,252 | **5,155,304** |
| Paired wins, seeds 0–29 | 10/30 | **20/30** |

Main improves the 30-seed median by **5.18%** and mean by **3.73%**. Mean paired gain is 179,289. Every official run was positive and passed the independent final-plan resource check. Typical total local evaluation time was about one second per run; timing is approximate because some checks ran concurrently.

## Existing synthetic stress scenarios

We reused the three effect tables already frozen in this branch, unchanged, with paired pilot seeds 500–504. They were not constructed after observing this comparison. Each scenario is only one artificial effect table: these tests cannot estimate performance on the hidden judging distribution, and earlier development of our agent already used them.

| Scenario | Current mean | Main mean | Main paired wins |
|---|---:|---:|---:|
| History plus independent shifts | **8,079,650** | 3,890,015 | 0/5 |
| Weak relationship with history | **10,019,612** | 2,103,438 | 0/5 |
| Reversed historical relationship | **14,174,047** | 3,155,586 | 0/5 |

Both versions remained positive and resource compliant in all 15 stress runs. These are substantial adaptation differences, rather than crashes or budget violations. All 92 base comparison evaluations (46 per version) returned legal final plans.

## What changed and what the experiments show

Main adds an empirical-Bayes transition model: price-gap regression, destination effects, pair effects, conversion smoothing, and transition-specific uncertainty. It groups source tariffs with identical specifications and keeps the 30 highest-ranked candidates, with at most three targets per group. Our agent instead retains 189 candidates across 63 individual tariff/ARPU cells and uses a fixed prior standard deviation of 0.15.

On this input, main's shortlist spans 16 grouped cells and 14,738 customers, compared with 23,341 in our candidate cells. It covers 52.77M of HIGH-segment ARPU mass versus our 110.88M. Candidates outside the shortlist cannot be discovered through its pilots. Equal tariff specifications also do not guarantee equal response effects; grouping is a modeling assumption.

Main uses the earlier pilot selector, which values finding a better mean estimate. Our selector also values confirmation that reduces the uncertainty penalty used by the planner. Main applies no uncertainty penalty to push; our planner accounts for scarce contacts by applying caution to push too.

Four controlled variants changed main's participant logic only. The first variant changes two related policy components together; their separate effects were not estimated. These are exploratory results, using seeds 0–9 for the mock and 500–504 in each stress scenario.

| Variant | Mock median | History-shift mean | Weak-history mean | Reversal mean |
|---|---:|---:|---:|---:|
| Current agent | 4.808M | **8.080M** | **10.020M** | **14.174M** |
| Main unchanged | 4.965M | 3.890M | 2.103M | 3.156M |
| Main + our pilot selection and push caution | **5.052M** | 4.234M | 4.482M | 6.767M |
| Main with individual source tariffs | 4.982M | 4.242M | 2.021M | 2.913M |
| Main with shortlist cap raised to 189 | 4.986M | 4.268M | 3.198M | 2.883M |
| Main with fixed prior SD 0.15 | 4.884M | 3.922M | 4.236M | 5.630M |

All 100 variant runs returned legal plans. Removing tariff grouping alone does not explain or repair the stress-test gap. Widening the shortlist alone also does not close it. Transition-specific prior widths contribute to main's mock score, while replacing them with 0.15 improves two stress scenarios. Our decision policy materially improves main's stress performance, although even that hybrid trails the current agent there. The combined historical model, candidate selection, uncertainty and exploration choices matter; these tests do not establish a single causal explanation for the entire gap.

Main also lacks the current branch's exploration exception guard and negative-belief fallback. We injected a selection failure after three successful pilots: main raised `RuntimeError`; our agent retained those observations and returned ten final campaigns. See [main_comparison_diagnostics.json](main_comparison_diagnostics.json). This injected failure is separate from the successful normal-run limit checks.

## Recommendation and handoff

Keep the current agent as the submission base. Main is a useful source of historical-modeling ideas, but its modest mock gain comes with large regressions on the available stress tests. A next experiment should bring the empirical-Bayes ranking into our broad candidate pool while retaining our exploration, push caution and recovery, then evaluate on newly held-out effect scenarios. The small hybrid experiment above is a research result, not a selected replacement.

The active `agent.py`, `candidate_research.py`, and `campaign_planner.py` are unchanged. No branch switch, merge, commit or push was performed. Teammate code remains in an isolated experiment snapshot.

Ran the required official checks on the retained current agent using the existing challenge `.venv` (system Python lacks pandas):

- `python local_eval.py`: PASS, seed 42 net 5,063,252; 20 pilots, six final campaigns, 15,000 contacts, cost 99,932.
- `python local_eval.py --runs 10`: ten positive runs; median 4,808,448.
- `python make_submission.py`: regenerated six campaigns; `submission.csv` has no Git diff.

To reproduce the comparison from the challenge directory after activating `.venv`:

```powershell
python experiments/compare_main.py --ref e2b864d8c326cfc1311c9a64feab1e38b4406052
python experiments/main_ablations.py
```

The baseline script writes [main_comparison_results.json](main_comparison_results.json); the controlled variants write [main_ablation_results.json](main_ablation_results.json). The scripts use public evaluation APIs and never expose scoring state or synthetic effect tables to either agent.
