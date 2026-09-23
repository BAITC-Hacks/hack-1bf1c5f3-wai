"use client";

import { type ChangeEvent, useMemo, useState } from "react";
import { DataControls } from "./components/DataControls";
import { EmptyState } from "./components/EmptyState";
import { InsightCard } from "./components/InsightCard";
import { RecordTable } from "./components/RecordTable";
import { SummaryGrid } from "./components/SummaryGrid";
import { TracePanel } from "./components/TracePanel";
import { summarize } from "@/lib/data/aggregate";
import { parseTabular } from "@/lib/data/parse";
import { DEMO_SOURCE_NAME, demoCsv } from "@/lib/demo-data";
import type { AgentResult, Dataset } from "@/lib/types";

export default function Home() {
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [result, setResult] = useState<AgentResult | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const summary = useMemo(() => (dataset ? summarize(dataset) : null), [dataset]);
  const citedIds = useMemo(
    () => (result ? [...new Set(result.trace.flatMap((step) => step.evidenceIds))] : []),
    [result],
  );

  function reset(next: Dataset) {
    setDataset(next);
    setResult(null);
    setSelectedRecord(null);
    setError("");
  }

  function loadDemo() {
    reset(parseTabular(demoCsv, { sourceName: DEMO_SOURCE_NAME }));
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 2_000_000) {
      setError("Choose a file under 2 MB for this sprint template.");
      return;
    }
    try {
      reset(parseTabular(await file.text(), { sourceName: file.name }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not read the file.");
    }
  }

  async function analyze() {
    if (!dataset) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dataset }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? "Analysis failed.");
      setResult(data as AgentResult);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Analysis failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <header>
        <span className="eyebrow">HACKALEM · HACKATHON STARTER</span>
        <h1>
          Make supplied data
          <br />
          actionable in minutes.
        </h1>
        <p>
          Upload the task data, let the agent choose its tools, and inspect the evidence behind each recommendation.
          Input → deterministic tools → human review.
        </p>
      </header>

      <DataControls dataset={dataset} onLoadDemo={loadDemo} onUpload={upload} />

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {!dataset || !summary ? (
        <EmptyState />
      ) : (
        <>
          <SummaryGrid summary={summary} />
          <section className="workspace">
            <RecordTable dataset={dataset} highlightIds={citedIds} selectedRecord={selectedRecord} />
            <div className="panel insight">
              <span className="eyebrow">AI-ASSISTED TRIAGE</span>
              <h2>Evidence-backed next action</h2>
              {!result ? (
                <>
                  <p>
                    The agent calls narrow, deterministic tools to establish facts, then explains them. Without a key it
                    runs the same tools on a fixed sequence.
                  </p>
                  <button onClick={analyze} disabled={loading}>
                    {loading ? "Running agent…" : "Run agent"}
                  </button>
                </>
              ) : (
                <InsightCard result={result} />
              )}
            </div>
          </section>

          {result && (
            <section className="traceSection">
              <TracePanel trace={result.trace} onSelectRecord={setSelectedRecord} selectedRecord={selectedRecord} />
            </section>
          )}

          <p className="footnote">
            Template rule: numerical calculations happen in code. The model selects tools, cites record ids, and
            recommends a human-reviewed next step.
          </p>
        </>
      )}
    </main>
  );
}
