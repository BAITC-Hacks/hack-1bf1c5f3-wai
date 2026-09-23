# Public-interface robustness audit

These checks use synthetic participant data and controlled observations. They
do not reveal or predict hidden judging effects. Organizer files were unchanged.

## Findings and repairs

`robustness_public_contract.py` reproduced two crashes in baseline commit
`0655b5c`: selecting a pilot after three completed observations could raise out
of `Agent.act`; a missing feedback field after the fourth completed pilot could
raise `KeyError`. The hardened agent now returns resource-compliant final plans
in both cases. An injected planner failure also returns a valid fallback.

The old fallback returned no campaign when every belief was negative, although
the guide requires at least one final campaign. A controlled six-customer
fixture now confirms that fallback chooses the best available target and the
single customer with the lowest estimated loss, through free push.

Without historical data, all candidate means are zero. Baseline sorting by the
whole `(mean, target)` tuple discarded nearest-price order and selected tariff
IDs lexicographically. This affected 45 of 63 audience cells. The fixed ordering
has zero mismatches against nearest-price selection in the same check.

Replacing every pilot response by +0.3 versus -0.3 changes the final plan. This
checks actual dependence on observations, supporting guide section 7.3.

## Prior strength

For the original 189 candidates, historical prior means have median 0.03169,
90th percentile 0.28619 and maximum 0.64871. The large values concentrate in LOW
ARPU cells: HIGH has mean 0.00144 and maximum 0.03584; LOW has mean 0.18908 and
maximum 0.64871. MID's maximum is 0.30825.

With prior standard deviation 0.15, observation noise 0.804 and SMS multiplier
0.65, the prior precision equals 68 SMS customer observations:

`effective_prior_n = 0.804**2 / (0.65**2 * 0.15**2)`.

Its weight after one pilot is 25.37% for 200 customers, 62.96% for 40 customers,
and 78.16% for 19 customers. Thus it is weak for large cells but can dominate
small-cell observations. The largest mean, 0.64871 in tariff_1/LOW (40 customers),
still becomes +0.32298 after a contradictory observed SMS effect of -0.15.

A principled optional alternative caps the prior weight after a feasible pilot
at 25% by setting prior standard deviation to at least
`0.804 * sqrt(3) / (0.65 * sqrt(min(200, cell.size)))`.
However, increasing uncertainty for tiny LOW cells can divert pilots away from
larger valuable cells. This is a hypothesis for separate validation, not an
automatic improvement. The strongest priors cover relatively little ARPU mass.

The original candidate pool contains 189 of 1,260 possible nonidentity
transitions. Historical top-three pruning is consequently a generalization
constraint even with weak beliefs. Broadening the pool also divides only 20
pilots among more choices; its benefit must be measured on independent effects.

## Independent synthetic effects

`robustness_shift.py` freezes three independently generated scenario tables in
`robustness_shift_models.csv`: noisy positive history correlation, weak history
correlation, and reversal of historical effects. The tables are evaluator inputs;
the agent receives only the documented environment interface and pilot feedback.
They are independent of the official mock effect construction.

Run `python experiments/robustness_shift.py --current --runs 5` from the challenge
directory to compare the current agent against Git baseline `0655b5c`. The same
five seeds are used for each agent within each frozen scenario. Reports include
source and model hashes, resource compliance and total score including pilots.

Both baseline and improved agents completed all 15 runs with legal final plans
and positive results. The improved agent won all 15 paired runs.

| Artificial scenario | Baseline mean net | Improved mean net | Difference |
|---|---:|---:|---:|
| Noisy historical correlation | 6,834,402 | 8,079,650 | +18.2% |
| Weak historical correlation | 8,128,585 | 10,019,612 | +23.3% |
| Reversed historical effects | 13,302,934 | 14,174,047 | +6.5% |

`robustness_shift_results.json` records every run and the source/model hashes.
These values have meaning only within these artificial scenarios. Three fixed
effect tables and five noise seeds each are a stress check, not a confidence
estimate for the judging distribution.
