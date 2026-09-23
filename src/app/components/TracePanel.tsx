"use client";

import type { TraceStep } from "@/lib/types";

type Props = {
  trace: TraceStep[];
  onSelectRecord: (id: string) => void;
  selectedRecord: string | null;
};

/**
 * The agentic proof surface.
 *
 * Every line here was produced by a tool call that actually ran — the steps are
 * recorded during execution, not described by the model afterwards. Evidence
 * ids are buttons so a reviewer can jump from any claim to its source row.
 */
export function TracePanel({ trace, onSelectRecord, selectedRecord }: Props) {
  if (!trace.length) return null;

  return (
    <div className="panel trace">
      <div className="panelHeading">
        <div>
          <span className="eyebrow">TOOL TRACE</span>
          <h2>How this conclusion was reached</h2>
        </div>
        <span className="badge">{trace.length} steps</span>
      </div>
      <ol className="traceList">
        {trace.map((step, index) => (
          <li key={`${step.tool}-${index}`}>
            <div className="traceHead">
              <code className="toolName">{step.tool}</code>
              <span className="traceMs">{step.ms} ms</span>
            </div>
            <p>{step.summary}</p>
            {step.evidenceIds.length > 0 && (
              <div className="chips">
                {step.evidenceIds.slice(0, 8).map((id) => (
                  <button
                    key={id}
                    type="button"
                    className={`chip${selectedRecord === id ? " chipActive" : ""}`}
                    onClick={() => onSelectRecord(id)}
                  >
                    {id}
                  </button>
                ))}
                {step.evidenceIds.length > 8 && <span className="chipMore">+{step.evidenceIds.length - 8} more</span>}
              </div>
            )}
          </li>
        ))}
      </ol>
      <p className="footnote">
        Calculations run in code; the model only selects tools and explains their output. Click any record id to inspect
        the source row.
      </p>
    </div>
  );
}
