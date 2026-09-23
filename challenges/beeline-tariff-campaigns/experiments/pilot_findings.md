# Pilot policy experiment

The agents only use public profile, tariffs, channels, resource balances and
pilot responses. The official `local_eval.evaluate_agent` calculates scores.
The frozen modules in `pilot_snapshot` preserve the original candidate discovery,
belief update and final planner. The runner redirects only the historical CSV
location to the challenge directory.

These are synthetic mock results. Seeds change pilot samples/noise, not the
underlying effect model; this is not a test on the hidden judging effects.

## Results

Development seeds 0–9 selected the policy before holdout evaluation:

| Policy | Mean net result | Minimum net result |
|---|---:|---:|
| Original: 20 SMS pilots, 200 each | 4,436,423 | 3,468,395 |
| 100 customers each | 4,202,932 | 3,135,001 |
| Adaptive sample sizes, SMS | 3,985,843 | 2,146,899 |
| Adaptive samples and channels | 3,923,291 | 2,140,366 |
| Confidence-aware knowledge gradient | 4,483,137 | 4,112,122 |

Only the selected confidence-aware policy and baseline were evaluated on holdout
seeds 10–29:

| Policy | Mean net result | Median | Minimum |
|---|---:|---:|---:|
| Original | 4,211,467 | 4,341,090 | 2,897,202 |
| Confidence-aware knowledge gradient | 4,615,249 | 4,591,590 | 4,123,965 |

The selected policy won 17/20 paired holdout runs, improved the mean by 9.59%,
and kept all 20 scores positive. It still uses 20 SMS pilots of 200 customers.
Each full run took approximately one second in this environment.

## Recommendation

The final planner ranks paid opportunities using `mean - CAUTION * sd`, but the
original pilot policy values only changes in the best raw mean. That misses the
value of confirming a promising winner: a more precise estimate reduces the
planner's uncertainty penalty even if the winning target does not change.

Replace the per-belief scoring inside `next_pilot` with the logic in
`PilotAgent.confirm_choice`. Use the planner's `CAUTION` constant and the actual
channel multiplier rather than the experiment's fixed 0.5 and 0.65 values.

For belief mean `m`, standard deviation `s`, post-pilot deviation `s_post`, and
best competing conservative estimate `a`, the random future conservative
estimate has mean `u = m - CAUTION * s_post` and standard deviation
`t = sqrt(s*s - s_post*s_post)`. Its expected improvement is:

```
z = (u - a) / t
expected_best = a + t * (z * normal_cdf(z) + normal_pdf(z))
current_best = max(a, m - CAUTION * s)
pilot_value = (expected_best - current_best) * cell.arpu_sum
```

Compare alternatives and the no-campaign option on the same conservative basis.
This uses the existing normal belief model without fitting to mock effects.

Do not integrate the other sample/channel variants: reduced precision caused
larger losses than the saved resources in development runs.

## Reproduction

Run from the challenge directory:

```powershell
.venv/Scripts/python.exe -X utf8 experiments/pilot_compare.py baseline,fixed100,adaptive_sms,adaptive_channels 0 10
.venv/Scripts/python.exe -X utf8 experiments/pilot_compare.py confirm_winners 0 10
.venv/Scripts/python.exe -X utf8 experiments/pilot_compare.py baseline,confirm_winners 10 30
```

Raw per-seed results and pilot sample/channel sequences are in the adjacent
`pilot_results_*.json` files.

## Interaction with uniform uncertainty caution

After the isolated pilot experiment, the planner investigation proposed applying
the existing uncertainty discount to push as well as paid channels. Development
seeds 0–9 were used to check that interaction, keeping all other frozen baseline
behavior unchanged:

| Policy | Mean | Median | Minimum |
|---|---:|---:|---:|
| Confidence-aware pilots alone | 4,483,137 | 4,578,866 | 4,112,122 |
| Confidence-aware pilots + uniform caution | 4,770,377 | 4,808,448 | 4,435,121 |

The combination won 8/10 paired runs and increased the mean by 6.41% against
confidence-aware pilots alone. This experiment did not access reserve seeds
30–59. Reproduce with:

```powershell
.venv/Scripts/python.exe -X utf8 experiments/pilot_compare.py confirm_uniform 0 10
```

Edge checks on the production selector passed for zero-information pilots,
floating-point precision saturation, NaN/infinite observed ratios, exhausted
pilotable hypotheses and cells smaller than ten contacts. Expected conservative
best value is mathematically nondecreasing after new information; rounding can
produce a tiny negative difference, which the positive-score selection ignores.
