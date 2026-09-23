/**
 * Deterministic calculations. The model never computes a number; it chooses
 * which of these to call and explains the result. Every function that makes a
 * claim about specific rows returns their ids so the claim stays citable.
 */

import {
  type Column,
  type Dataset,
  type DataRecord,
  numericCell,
} from "./records";

export type ColumnSummary = {
  key: string;
  kind: Column["kind"];
  present: number;
  missing: number;
  sum?: number;
  mean?: number;
  min?: number;
  max?: number;
  stdDev?: number;
  distinct?: number;
  top?: { value: string; count: number }[];
};

export type DatasetSummary = {
  sourceName: string;
  records: number;
  skippedRows: number;
  columns: ColumnSummary[];
};

function round(value: number): number {
  return Math.round(value * 1000) / 1000;
}

export function summarize(dataset: Dataset): DatasetSummary {
  const columns = dataset.columns.map<ColumnSummary>((column) => {
    const values = dataset.records.map((record) => record.fields[column.key]);
    const present = values.filter((value) => value !== null && value !== "");
    const base = {
      key: column.key,
      kind: column.kind,
      present: present.length,
      missing: values.length - present.length,
    };

    if (column.kind === "number") {
      const numbers = present.filter((value): value is number => typeof value === "number");
      if (!numbers.length) return base;
      const sum = numbers.reduce((total, value) => total + value, 0);
      const mean = sum / numbers.length;
      const variance = numbers.reduce((total, value) => total + (value - mean) ** 2, 0) / numbers.length;
      return {
        ...base,
        sum: round(sum),
        mean: round(mean),
        min: round(Math.min(...numbers)),
        max: round(Math.max(...numbers)),
        stdDev: round(Math.sqrt(variance)),
      };
    }

    const counts = new Map<string, number>();
    for (const value of present) {
      const key = String(value);
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return {
      ...base,
      distinct: counts.size,
      top: [...counts.entries()]
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
        .slice(0, 5)
        .map(([value, count]) => ({ value, count })),
    };
  });

  return {
    sourceName: dataset.sourceName,
    records: dataset.records.length,
    skippedRows: dataset.issues.length,
    columns,
  };
}

export type Aggregation = "sum" | "mean" | "count" | "max";

export type GroupResult = {
  group: string;
  value: number;
  count: number;
  recordIds: string[];
};

export function groupBy(
  dataset: Dataset,
  groupKey: string,
  valueKey: string | null,
  aggregation: Aggregation = "sum",
): GroupResult[] {
  const buckets = new Map<string, { values: number[]; ids: string[] }>();
  for (const record of dataset.records) {
    const rawGroup = record.fields[groupKey];
    if (rawGroup === null || rawGroup === undefined || rawGroup === "") continue;
    const group = String(rawGroup);
    const bucket = buckets.get(group) ?? { values: [], ids: [] };
    const value = valueKey ? numericCell(record, valueKey) : null;
    if (value !== null) bucket.values.push(value);
    bucket.ids.push(record.id);
    buckets.set(group, bucket);
  }

  return [...buckets.entries()]
    .map(([group, bucket]) => {
      const { values, ids } = bucket;
      let value = ids.length;
      if (aggregation === "sum") value = values.reduce((total, current) => total + current, 0);
      else if (aggregation === "mean") value = values.length ? values.reduce((total, current) => total + current, 0) / values.length : 0;
      else if (aggregation === "max") value = values.length ? Math.max(...values) : 0;
      return { group, value: round(value), count: ids.length, recordIds: ids.slice(0, 50) };
    })
    .sort((a, b) => b.value - a.value || a.group.localeCompare(b.group));
}

export type Outlier = {
  recordId: string;
  value: number;
  zScore: number;
  reason: string;
};

/**
 * Flag records whose value sits far from the column mean, or outside an
 * explicit operating threshold when the task supplies one.
 */
export function findOutliers(
  dataset: Dataset,
  key: string,
  options: { zScore?: number; min?: number; max?: number } = {},
): Outlier[] {
  const threshold = options.zScore ?? 1.5;
  const pairs = dataset.records
    .map((record) => ({ record, value: numericCell(record, key) }))
    .filter((entry): entry is { record: DataRecord; value: number } => entry.value !== null);
  if (!pairs.length) return [];

  const mean = pairs.reduce((total, entry) => total + entry.value, 0) / pairs.length;
  const stdDev = Math.sqrt(pairs.reduce((total, entry) => total + (entry.value - mean) ** 2, 0) / pairs.length);

  const outliers: Outlier[] = [];
  for (const { record, value } of pairs) {
    const zScore = stdDev === 0 ? 0 : (value - mean) / stdDev;
    const reasons: string[] = [];
    if (options.max !== undefined && value > options.max) reasons.push(`above the supplied maximum of ${options.max}`);
    if (options.min !== undefined && value < options.min) reasons.push(`below the supplied minimum of ${options.min}`);
    if (!reasons.length && Math.abs(zScore) >= threshold) {
      reasons.push(`${round(Math.abs(zScore))} standard deviations from the mean of ${round(mean)}`);
    }
    if (reasons.length) {
      outliers.push({ recordId: record.id, value: round(value), zScore: round(zScore), reason: reasons.join("; ") });
    }
  }
  return outliers.sort((a, b) => Math.abs(b.zScore) - Math.abs(a.zScore));
}

export function inspectRecords(dataset: Dataset, ids: string[]): DataRecord[] {
  const wanted = new Set(ids);
  return dataset.records.filter((record) => wanted.has(record.id));
}

/**
 * Choose the numeric column most worth investigating: the one with the most
 * relative spread. Used by demo mode, which has no model to make the choice.
 */
export function mostVariableColumn(dataset: Dataset): string | null {
  const summary = summarize(dataset);
  const candidates = summary.columns
    .filter((column) => column.kind === "number" && column.stdDev !== undefined && column.mean)
    .map((column) => ({ key: column.key, spread: (column.stdDev ?? 0) / Math.abs(column.mean || 1) }))
    .sort((a, b) => b.spread - a.spread);
  return candidates[0]?.key ?? null;
}

/**
 * Choose a column worth grouping on.
 *
 * Excludes identifier-like columns whose values are all distinct: grouping by a
 * unique row id produces one bucket per record and tells a reviewer nothing.
 * Among the rest, prefer the most granular column that still aggregates.
 */
export function bestGroupingColumn(dataset: Dataset): string | null {
  const total = dataset.records.length;
  if (!total) return null;

  const candidates = summarize(dataset)
    .columns.filter((column) => column.kind !== "number" && (column.distinct ?? 0) > 1 && (column.distinct ?? 0) < total)
    .map((column) => ({ key: column.key, distinct: column.distinct ?? 0 }));

  const aggregating = candidates.filter((column) => column.distinct <= Math.max(2, total / 2));
  const pool = aggregating.length ? aggregating : candidates;
  return pool.sort((a, b) => b.distinct - a.distinct || a.key.localeCompare(b.key))[0]?.key ?? null;
}
