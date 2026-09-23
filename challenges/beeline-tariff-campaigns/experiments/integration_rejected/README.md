# Rejected full-prior integration

Frozen first-round candidate: teammate empirical-Bayes means and target ranking,
individual tariff/ARPU cells, SD 0.15 and our pilot/planning/recovery policy.

Selected on development, then rejected on held-out worlds 1–3 because it reduced
the mean score in every artificial family. Its official mock median improved,
which was insufficient evidence of a robust improvement. Source hashes match
`integration_selection.json` and `integration_validation.json`.

Reproduce from the challenge directory:

```powershell
python experiments/integrate_prior.py --stage validation --candidate rejected
```

That command regenerates the round-one validation report with label `rejected`
in place of its original label `integrated`. These are research files, not the
active submission modules.
