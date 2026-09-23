# HackAlem sprint rules

This is a five-hour, three-person hackathon project. Optimize for one reliable judge journey.

## Before changing scope

- Read `docs/00-kickoff.md` and the prompt released by the organizers.
- Keep `OPENAI_API_KEY` server-side. Never commit `.env.local`, keys, or private challenge data.
- Keep calculations deterministic in `src/lib/data/aggregate.ts`; the model selects tools and explains their output.
- Add capabilities as narrow tools in `src/lib/agent/tools.ts`, not as new API routes.
- Keep `src/lib/data/parse.ts` schema-agnostic; do not add a fixed column schema.
- Name evidence for every AI claim shown in the UI: record ids, source file, or calculated metric.
- Record tool calls in the trace as they execute. Do not let the model narrate steps it did not take.
- Preserve no-key demo mode. A judge must be able to click **Load sample data** and see a real tool trace without credentials.
- When asked to implement a feature, derive a short task contract from the request and repository: user, action, visible outcome, acceptance check, relevant files, and dependencies. State it briefly before coding, then proceed; teammates should not have to write specs, acceptance tests, or dependency lists by hand.
- Infer acceptance checks and dependencies by inspecting the existing app, tests, and task constraints. Use a repeatable manual check when an automated test is not warranted; do not turn every feature into a new test-suite task.
- Ask for clarification only when an unresolved choice materially changes scope, user-visible behavior, or a risky architectural decision. Otherwise state a reasonable assumption and keep moving.

## Fast task loop

1. Derive and state the requested change and its acceptance check in one sentence; include relevant dependencies when they affect implementation.
2. Inspect relevant files and make the smallest coherent change.
3. Run `npm run typecheck` and `npm run test`; run `npm run build` before handoff if time permits.
4. Report changed files, how to test, and any remaining risk. Do not claim unrun checks passed.

## Ownership

- Captain: scope, integration, API route, README, demo, and submission.
- Data lead: ingestion, types, deterministic metrics, demo data, and evidence ids.
- UI lead: page/components, visual hierarchy, states, and demo polish.

`src/app/page.tsx` is thin orchestration; screens live in `src/app/components/`. Work in separate component files where possible.

## Done means

- Works with supplied input and sample data.
- Has loading, empty, and error states.
- Makes no ungrounded numerical claim.
- Is documented in the README and demo script and fits the released rubric.
