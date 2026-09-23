# Main branch comparison plan

Project: Beeline synthetic challenge agent comparison. Analyst: Codex. Requestor: Dauren.
Date: 2026-09-23. Target: this session. Status: complete.

Question: Does teammate main reproduce a 4.9M+ median and outperform the current dauren agent, and which approach should we retain?

| Step | Dependencies | Estimate | Output |
|---|---|---|---|
| Fetch main and verify source/data parity | Git access, participant guide | 5 min | Immutable commit and source snapshot |
| Paired official mock evaluation | Both agents, unchanged local evaluator | 10 min | Seeds 0–29, seed 42, scores and limits |
| Compare existing frozen synthetic shifts | Public environment/scorer, existing shift tables | 10 min | Five paired seeds per scenario |
| Inspect differences and targeted ablation if useful | Results and source differences | 10 min | Evidence-based recommendation |
| Official checks and report | Final current agent | 5 min | Reproduced submission and findings |

Estimated effort: 40 min plus 6 min buffer; runtime may be substantially shorter.

All required datasets are present. Main fetch succeeded. Organizer scripts and datasets have no diff between branches. Both agents use participant history and observed pilots; the evaluator alone accesses scoring state.

Completed: 92 base evaluations, 100 controlled-variant evaluations, injected failure diagnostic, all three official checks on the retained agent, and [findings](main_comparison.md). No production policy change was adopted.

Risks: pilot seeds vary observations, not the hidden effect model; mitigate using existing frozen synthetic shifts. Historical priors may fit the official mock unusually well; distinguish mock performance from stress tests. Additional module imports may silently mix versions; load each complete participant module set and record hashes. Keep working participant code intact during comparison. Hidden judging scores and wholesale integration are outside this comparison.
