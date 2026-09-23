# Historical model integration plan

Date: 2026-09-23. Status: complete. Requestor: Dauren; analyst: Codex.

Question: Can main's empirical-Bayes history model improve our agent while preserving broad exploration and failure recovery?

Sequence: preserve current sources (2 min), implement three candidate adapters (5 min), freeze new development/validation effect worlds before evaluation (3 min), development comparison (5 min), select one candidate and freeze it (3 min), held-out comparison (5 min), production integration, meaningful regression tests, official checks and report (10 min). Estimate 33 min plus 5 min buffer.

Confirmed inputs: participant history and profiles, current commit e822ad1, teammate snapshot e2b864d, public environment/scorer, installed numpy/pandas. No new dependency is needed.

Keep individual tariff/ARPU cells, current pilot selector, push caution, resource planner and recovery. Compare EB top-three means with fixed SD 0.15; EB top-three with SD at least 0.15; and union of original/EB top-three targets with fixed SD. No global 30-candidate cutoff. Missing or invalid model output must retain the baseline fallback.

Development: official mock seeds 0–9 plus one fresh effect world in each of four families, two pilot seeds per world. Families: strongly predictive history, moderate shifts, history-independent effects, and reversed history. Include correlated destination and source-cell shifts as well as pair shifts. Freeze all generated tables before scoring. Existing stress tables are excluded from selection.

Validation: official mock seeds 100–129 and three different effect worlds per family, two fresh pilot seeds per world. Evaluate baseline, teammate and the selected candidate. Do not tune against validation results; retain baseline if the selected candidate has a material overall regression. Prefer a development candidate with mock mean at least baseline and no fresh-family mean decline beyond 10%; if none qualifies, report that fact and investigate before consuming validation.

Risks: artificial effect families do not model the unknown judge distribution; report by family instead of pooling incomparable score scales. Historical destination shares are proxies, not measured conversion probabilities. Wider candidate pools divide 20 pilots among more hypotheses. Numerical failures in new modeling must degrade gracefully. All scenarios and evaluator state stay outside the agent.

Round-one outcome: eb_fixed selected on development, then rejected on untouched validation: mock improved, all four artificial family means declined, reversal by roughly 65%. Code is preserved in integration_rejected. No claims of validation success will be made for it.

Round two: narrower borrowing, either EB ranking with the original direct historical mean/uncertainty, or EB means only for selected pairs with fewer than five historical events. Reuse development worlds only for selection. Freeze new validation worlds 4–6 before scoring either variant; reserve official seeds 200–229 and pilot seeds 2700–2701. Previously opened validation worlds are not a holdout for these variants. If neither option earns adoption, retain the original production policy and hand over the tested alternatives.

Final outcome: ranking-only selected in round two, then rejected on its fresh validation worlds (moderate -11.05%, independent -22.50%, reversed -57.09%; strong-history +5.15%, mock mean +2.07%). Original production source restored, model and both frozen integrations preserved. Completed 468 evaluation runs, all resource compliant; 17 tests pass; all required official checks rerun on retained production code and submission regenerated twice with matching hashes. See ../../../docs/historical-model-integration.md for full findings.
