/**
 * Schema-agnostic record model.
 *
 * The supplied task data decides what the columns mean; this layer decides what type each column is and how to
 * read a cell safely.
 */

export type CellValue = string | number | null;

export type DataRecord = {
  /** Stable identifier used for evidence citation. */
  id: string;
  fields: Record<string, CellValue>;
};

export type ColumnKind = "number" | "date" | "text";

export type Column = {
  key: string;
  kind: ColumnKind;
};

export type ParseIssue = {
  line: number;
  reason: string;
};

export type Dataset = {
  sourceName: string;
  columns: Column[];
  records: DataRecord[];
  /** Rows that could not be read. Reported, never silently dropped. */
  issues: ParseIssue[];
};

export const EMPTY_DATASET: Dataset = { sourceName: "", columns: [], records: [], issues: [] };

const THOUSANDS_DOT = /^-?\d{1,3}(\.\d{3})+(,\d+)?$/;
const THOUSANDS_COMMA = /^-?\d{1,3}(,\d{3})+(\.\d+)?$/;
const DECIMAL_COMMA = /^-?\d+,\d+$/;

/**
 * Coerce a raw cell to a number, or null when it is genuinely absent.
 *
 * Returning null (not 0) for an empty cell matters: a silent zero corrupts
 * every downstream mean, sum and threshold we present as deterministic.
 * Handles the separators common in ru/kk-locale exports.
 */
export function toNumber(raw: string): number | null {
  const value = raw.trim();
  if (!value) return null;

  let normalised = value.replace(/\s| |'/g, "");
  if (THOUSANDS_DOT.test(normalised)) normalised = normalised.replace(/\./g, "").replace(",", ".");
  else if (THOUSANDS_COMMA.test(normalised)) normalised = normalised.replace(/,/g, "");
  else if (DECIMAL_COMMA.test(normalised)) normalised = normalised.replace(",", ".");

  if (!/^-?\d*\.?\d+([eE][-+]?\d+)?$/.test(normalised)) return null;
  const parsed = Number(normalised);
  return Number.isFinite(parsed) ? parsed : null;
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?/;
const SLASH_DATE = /^\d{1,2}[./]\d{1,2}[./]\d{2,4}$/;

export function looksLikeDate(raw: string): boolean {
  const value = raw.trim();
  if (!value) return false;
  return ISO_DATE.test(value) || SLASH_DATE.test(value);
}

/**
 * Infer a column's kind from its values. A column is numeric or a date only
 * when the clear majority of present values agree, so one stray "n/a" does
 * not downgrade an otherwise numeric column to text.
 */
export function inferKind(values: string[]): ColumnKind {
  const present = values.filter((value) => value.trim() !== "");
  if (!present.length) return "text";
  const numeric = present.filter((value) => toNumber(value) !== null).length;
  if (numeric / present.length >= 0.8) return "number";
  const dates = present.filter(looksLikeDate).length;
  if (dates / present.length >= 0.8) return "date";
  return "text";
}

const ID_HINTS = ["id", "_id", "code", "ref", "number", "no"];

/** Pick the column that best serves as a citable row identifier. */
export function pickIdColumn(columns: Column[], rows: string[][], headerIndex: Map<string, number>): string | null {
  const candidates = columns.filter((column) => {
    const key = column.key.toLowerCase();
    return ID_HINTS.some((hint) => key === hint || key.endsWith(hint));
  });
  for (const candidate of candidates) {
    const index = headerIndex.get(candidate.key);
    if (index === undefined) continue;
    const values = rows.map((row) => (row[index] ?? "").trim());
    const unique = new Set(values.filter(Boolean));
    if (unique.size === values.filter(Boolean).length && unique.size === rows.length) return candidate.key;
  }
  return candidates[0]?.key ?? null;
}

export function numericColumns(dataset: Dataset): Column[] {
  return dataset.columns.filter((column) => column.kind === "number");
}

export function categoricalColumns(dataset: Dataset): Column[] {
  return dataset.columns.filter((column) => column.kind === "text");
}

export function cell(record: DataRecord, key: string): CellValue {
  return record.fields[key] ?? null;
}

export function numericCell(record: DataRecord, key: string): number | null {
  const value = record.fields[key];
  return typeof value === "number" ? value : null;
}
