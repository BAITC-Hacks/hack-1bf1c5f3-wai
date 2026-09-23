import type { DatasetSummary } from "@/lib/types";

type Props = { summary: DatasetSummary };

/**
 * Tiles are derived from whatever columns exist rather than hardcoded to one
 * schema, so the headline numbers survive a different released dataset.
 */
export function SummaryGrid({ summary }: Props) {
  const numeric = summary.columns.filter((column) => column.kind === "number" && column.sum !== undefined).slice(0, 2);

  return (
    <section className="metrics" aria-label="Dataset summary">
      <article className="metric">
        <span>Records loaded</span>
        <strong>{summary.records.toLocaleString()}</strong>
        <small>{summary.skippedRows ? `${summary.skippedRows} unreadable rows skipped` : "all rows parsed"}</small>
      </article>
      {numeric.map((column) => (
        <article className="metric" key={column.key}>
          <span>Total {column.key}</span>
          <strong>{(column.sum ?? 0).toLocaleString()}</strong>
          <small>
            mean {column.mean} · range {column.min}–{column.max}
            {column.missing ? ` · ${column.missing} missing` : ""}
          </small>
        </article>
      ))}
      {!numeric.length && (
        <article className="metric">
          <span>Columns</span>
          <strong>{summary.columns.length}</strong>
          <small>no numeric column detected</small>
        </article>
      )}
    </section>
  );
}
