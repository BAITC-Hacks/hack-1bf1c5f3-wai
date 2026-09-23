# Agent strategy improvements

Date: 2026-09-23. Baseline: Git commit `0655b5c`.

All data and results are synthetic. These experiments assess local mechanics and behavior; they do not establish the hidden judging score or real Beeline business performance.

## Changes retained

- **Pilot selection aligned with final decisions.** The old selector valued changes to the best raw effect estimate. The planner discounts uncertainty, so the new selector also values confirming a promising target: reducing uncertainty can justify allocating more valuable contacts to it. The uncertainty discount remains 0.5 standard deviations; no tariff-specific scoring constants were introduced.
- **Caution for push as well as paid channels.** Free push still consumes scarce contacts. Applying the same uncertainty discount prevents untested push audiences from displacing better supported opportunities.
- **Failure recovery.** Selection and feedback-processing failures preserve completed estimates and still produce a final plan. When all estimates are negative, the fallback chooses a small legal audience with the least estimated loss, as the guide still requires a campaign.
- **Missing-history candidate fix.** Equal neutral priors preserve price proximity instead of sorting tariff identifiers alphabetically.

Normal evaluated runs still use twenty SMS pilots of 200 customers each. The evidence did not support replacing them with smaller or adaptive samples in this iteration.

## Experiment design

Three independent investigations examined pilots, final allocation, and robustness. Seeds 0–9 were used for development; 10–29 for initial validation. The combined policy was then evaluated on reserved seeds 30–59 against the original agent, using `local_eval.evaluate_agent` for both. Each evaluation starts a fresh environment. Matching seeds pair evaluation conditions; policies that choose different pilots can sample different customers.

Variants rejected on development results included fixed 100-customer pilots, adaptive sample/channel choices based on estimated resource opportunity costs, budget shadow-price searches, and local channel pair reassignment. Their runners and raw results remain in the experiments directory. Stronger historical-prior changes and candidate expansion were not adopted without supporting evidence.

## Reserved evaluation: seeds 30–59

| Metric | Original | Improved |
| --- | ---: | ---: |
| Mean net gain | 4,370,574 | 4,711,896 |
| Median net gain | 4,468,833 | 4,724,710 |
| Minimum net gain | 3,428,559 | 3,612,083 |
| Maximum net gain | 4,867,215 | 5,392,501 |
| Positive runs | 30/30 | 30/30 |
| Mean spending | 98,310 | 99,824 |
| Mean total contacts | 15,000 | 14,840 |
| Mean evaluator runtime | 1.03 s | 1.05 s |

The new agent won 27/30 paired comparisons, improving mean gain by **7.81%**. It is not better on every seed: its largest paired decline was 964,135 on seed 59. Runtime includes local evaluation and is comfortably within the ten-minute agent limit.

Raw results, baseline commit, and source hashes: [final_comparison_30_59.json](../challenges/beeline-tariff-campaigns/experiments/final_comparison_30_59.json).

Reproduce from the challenge directory:

```powershell
python benchmark_agents.py --baseline-ref 0655b5c --start-seed 30 --runs 30 --output experiments/recheck.json
```

## Independent synthetic effect scenarios

Seed changes in the official mock environment vary pilot samples and noise, not the underlying effects. To test a broader behavior change, a separate harness generated and froze three artificial effect tables before evaluating the final policy. These tables are kept outside the agent and supplied only to the environment/scorer. Each scenario uses five pilot seeds, 500–504.

| Scenario | Original mean net gain | Improved mean net gain | Change |
| --- | ---: | ---: | ---: |
| History plus independent shifts | 6,834,402 | 8,079,650 | +18.2% |
| Weak relationship with history | 8,128,585 | 10,019,612 | +23.3% |
| Reversed relationship with history | 13,302,934 | 14,174,047 | +6.5% |

The improved agent won all 15 paired runs, with valid plans in every run. These are three constructed scenarios, not a representative distribution of judging effects. Model/source hashes and per-run outcomes are in [robustness_shift_results.json](../challenges/beeline-tariff-campaigns/experiments/robustness_shift_results.json). Reproduce with `python experiments/robustness_shift.py --current`.

## Verification and remaining limitations

The official single evaluation passes with net gain **5,063,252** on seed 42, compared with **4,650,822** before. It runs twenty pilots and six final campaigns, uses 15,000 contacts, spends 99,932, and reports no clipped campaigns. The official ten-run evaluation is positive on all ten seeds. Seven contract/resilience tests pass, covering reproducibility, resource limits, missing feedback, selection/planner failure, negative fallback, and missing history. `submission.csv` is regenerated from the final code and checked for identical output on a second generation.

The agent still considers three targets per audience cell (189 of 1,260 nonidentity transitions for this input). Fixed historical prior variance can outweigh small pilots in tiny cells. The planner is greedy and lacks the pilot customers' identities through the public interface, so some overlap between pilot and final contacts remains. Those constraints and unseen effects leave room for improvement; the gains above are evidence for this implementation, not a guarantee of winning.
