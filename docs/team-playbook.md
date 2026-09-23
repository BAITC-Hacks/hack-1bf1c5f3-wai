# Team playbook

For the current Beeline case, use the [three-person task board](team-tasks-beeline.md). Its Python evaluator and submission tasks replace the generic UI and deployment milestones below; the released case does not require a frontend.

## Roles

| Role | Owns | Shares |
| --- | --- | --- |
| Orchestrator (captain) | Scope, task breakdown, GitHub Issues, prioritization, integration, deployment coordination, API coordination, submission | Kickoff sheet, README, demo script, pitch, deployed URL |
| Builder 1 | Implementation of assigned issues; often data and agent work | Commits, issue status, evidence and tests |
| Builder 2 | Implementation of assigned issues; often UI, interaction, and deployment setup | Commits, issue status, demo path |

The orchestrator creates and assigns implementation tasks as GitHub Issues. Builders own their assigned issues and implement in the organizer-provided team repository. Split by component when that reduces conflicts, but let the released task, dependencies, and team capacity decide the actual assignment.

## Issue format and flow

Each issue should be small enough to implement and review independently. Include:

- User and action
- Visible outcome
- Acceptance test
- Relevant files or area, if known
- Dependencies and priority

The orchestrator or agent derives these fields from the feature request, released task, and repository. Do not make teammates write acceptance tests or dependency lists before asking for implementation. For a direct implementation request, briefly state the inferred user/action/outcome, acceptance check, and any dependencies, then proceed. Use a manual acceptance check when that is the fastest reliable verification; add automated tests when they protect important behavior and fit the task. Ask only when a material ambiguity blocks a safe, useful implementation; otherwise state the assumption and continue.

Builders keep commits focused, update the issue with progress, and raise blockers or scope changes promptly. The orchestrator reviews and integrates completed work continuously, resolving conflicts and keeping the end-to-end demo runnable.

## Sprint checkpoints

- Before choosing scope, read `docs/00-kickoff.md` and the released organizer task and criteria. Record one judge journey and its acceptance test in the kickoff sheet.
- Maintain a working intermediate result in the official repository at the end of each competition hour.
- Treat a working deployed version as a must-have deliverable. Create a deployment issue early, verify the hosting path and required configuration, and keep the deployed judge journey aligned with the repository version.
- Deployment issue acceptance test: the public URL loads, the core journey works in a clean browser session, and the no-key sample path is usable; verify live API behavior separately if the task requires it.
- Keep the key judge flow verifiable without personal accounts or subscriptions. Preserve no-key sample mode; any API key belongs server-side and must not be committed.
- Disclose third-party code, libraries, models, datasets, templates, and other reused components in the project materials.
- Keep the README accurate to the repository and sufficient for an evaluator to install, configure, run, and check the project. Document limitations and include the working deployed URL.
- Stop adding scope early enough to verify the final setup and rehearse the demo before the submission cutoff.

Keep the integrated app runnable at each handoff. Prefer one reliable judge journey over parallel feature growth.

## Time gates (300 minutes)

| Clock | Outcome |
| --- | --- |
| 00–20 | Orchestrator transcribes the prompt, records per-criterion evidence in `docs/00-kickoff.md`, chooses one journey, opens prioritized issues, and confirms the deployment target. |
| 20–75 | Builders establish the supplied-input path and runnable core mechanic; deployment setup begins against the smallest working version. |
| 75–195 | Builders implement only issues that strengthen the integrated core; orchestrator reviews and integrates continuously; deploy early increments where practical. |
| 195–235 | Orchestrator locks a reproducible happy path and failure state; builders fix integration gaps and deployment configuration. |
| 235–260 | Orchestrator completes the README and demo script from verified repository behavior, including the deployed URL. |
| 260–280 | Verify clean local setup, sample data, live deployment, key judge flow, and submission requirements. |
| 280–300 | Rehearse twice and submit early. |

## Issue task card examples

**Data/agent issue:** “Make the supplied file work end-to-end. Return typed, deterministic metrics, include row/source IDs, cover relevant edge cases, and state how to verify it.”

**UI issue:** “Implement this screen from the acceptance test. Use existing data types, preserve Load sample data, include loading/empty/error states, and provide a short verification checklist.”

**Integration issue:** “Integrate the proven judge path, keep the trace truthful, and remove any behavior that cannot be explained or verified against the task criteria.”
