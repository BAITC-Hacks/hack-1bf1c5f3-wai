# HackAlem starter

A schema-agnostic web starter for turning supplied records into an evidence-backed finding. The Beeline case has now been released; its required deliverable is a Python agent, which has not yet been implemented.

The released Beeline case package is in `challenges/beeline-tariff-campaigns/`. The [three-person sprint plan](docs/team-tasks-beeline.md) tracks the required Python agent, evaluation, and submission work. The web app below is still the original starter and is not the case submission.

## Run locally

Requires Node.js 20.11 or newer.

```powershell
npm install
npm run dev
```

Open http://localhost:3000, load the sample data, and run the agent. The no-key mode uses deterministic tools and shows the same evidence trace as live mode. To enable live analysis, copy `.env.example` to `.env.local` and set `OPENAI_API_KEY` there. Keep the key server-side and out of Git.

## What's here

- `src/lib/data/` parses CSV, TSV, and JSON records and calculates reproducible summaries.
- `src/lib/agent/` exposes narrow tools and records each call in the trace.
- `src/app/` provides upload, evidence, and analysis screens.
- `sample-data/` contains neutral synthetic data for a quick smoke test.
- `docs/00-kickoff.md` is the task and rubric intake sheet.

Before building a feature, fill the kickoff sheet, choose one judge journey, and write its acceptance test. Keep the first change small and runnable.
