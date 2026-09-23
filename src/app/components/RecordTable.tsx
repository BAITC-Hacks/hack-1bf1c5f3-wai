"use client";

import { useEffect, useRef } from "react";
import type { Dataset } from "@/lib/types";

type Props = {
  dataset: Dataset;
  highlightIds: string[];
  selectedRecord: string | null;
};

/** Shows the rows the agent cited, so every claim can be checked against source data. */
export function RecordTable({ dataset, highlightIds, selectedRecord }: Props) {
  const selectedRef = useRef<HTMLTableRowElement>(null);

  useEffect(() => {
    if (selectedRecord) selectedRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedRecord]);

  const cited = new Set(highlightIds);
  const rows = cited.size ? dataset.records.filter((record) => cited.has(record.id)) : dataset.records.slice(0, 10);
  const columns = dataset.columns.slice(0, 8);

  return (
    <div className="panel">
      <div className="panelHeading">
        <div>
          <span className="eyebrow">EVIDENCE QUEUE</span>
          <h2>{cited.size ? "Records cited by the agent" : "First records in the file"}</h2>
        </div>
        <span className="badge">{rows.length} shown</span>
      </div>
      <div className="tableScroll">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key}>{column.key}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((record) => (
              <tr
                key={record.id}
                ref={record.id === selectedRecord ? selectedRef : undefined}
                className={record.id === selectedRecord ? "rowSelected" : undefined}
              >
                {columns.map((column) => (
                  <td key={column.key}>{record.fields[column.key] ?? <span className="null">—</span>}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
