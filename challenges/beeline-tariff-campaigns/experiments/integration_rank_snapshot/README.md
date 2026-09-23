# Rejected ranking-only integration

The second frozen integration borrows empirical-Bayes target ranking, retaining
189 candidates across 63 individual cells, the original direct historical means,
neutral priors for unseen transitions, SD 0.15, and our decision/recovery policy.
It replaces 62 targets and leaves the other 127 priors identical to baseline.

It improved development results, but on reserved worlds 4–6 it lost mean score
in the independent, moderately shifted and reversed families. Production was
restored to the original policy. Hashes match `integration_selection_round2.json`
and `integration_validation_round2.json` (where this candidate is labeled
`integrated`).

Reproduce from the challenge directory:

```powershell
python experiments/integrate_prior.py --round 2 --stage validation --candidate rank_rejected
```

The new report uses label `rank_rejected` instead of the original `integrated`.
