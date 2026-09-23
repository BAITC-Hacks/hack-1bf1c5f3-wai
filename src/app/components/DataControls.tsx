"use client";

import type { ChangeEvent } from "react";
import type { Dataset } from "@/lib/types";

type Props = {
  dataset: Dataset | null;
  onLoadDemo: () => void;
  onUpload: (event: ChangeEvent<HTMLInputElement>) => void;
};

export function DataControls({ dataset, onLoadDemo, onUpload }: Props) {
  return (
    <section className="controls" aria-label="Data controls">
      <button onClick={onLoadDemo}>Load sample data</button>
      <label className="secondary">
        Upload data
        <input className="visuallyHidden" type="file" accept=".csv,.tsv,.txt,.json,text/csv,application/json" onChange={onUpload} />
      </label>
      <span>
        {dataset
          ? `${dataset.records.length} records · ${dataset.columns.length} columns · ${dataset.sourceName}`
          : "No data loaded"}
      </span>
      {dataset && dataset.issues.length > 0 && (
        <span className="warn" title={dataset.issues.map((issue) => `line ${issue.line}: ${issue.reason}`).join("\n")}>
          {dataset.issues.length} row{dataset.issues.length === 1 ? "" : "s"} skipped
        </span>
      )}
    </section>
  );
}
