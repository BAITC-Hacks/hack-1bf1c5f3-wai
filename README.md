# HackAlem starter

A small, schema-agnostic app shell for turning supplied records into an evidence-backed finding. Choose the track and user journey after the organizers release the prompt; replace the sample input and tailor the interface then.

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
