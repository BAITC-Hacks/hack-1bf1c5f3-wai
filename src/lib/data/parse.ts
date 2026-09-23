/**
 * Tolerant ingestion for whatever file the organizers hand us.
 *
 * Design rule: never abort the whole file because of one bad row. The task
 * data arrives once, under the clock, and a parser that throws on row 3 of
 * 500 costs more than a parser that reports what it skipped.
 */

import {
  type Column,
  type DataRecord,
  type Dataset,
  type ParseIssue,
  inferKind,
  pickIdColumn,
  toNumber,
} from "./records";

const DELIMITERS = [",", ";", "\t", "|"] as const;

/** Split on a delimiter while honouring RFC-4180 quoting, including "" escapes. */
export function splitDelimited(text: string, delimiter: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  let touched = false;

  for (let index = 0; index < text.length; index++) {
    const character = text[index];
    if (quoted) {
      if (character === '"') {
        if (text[index + 1] === '"') {
          field += '"';
          index++;
        } else quoted = false;
      } else field += character;
      continue;
    }
    if (character === '"') {
      quoted = true;
      touched = true;
    } else if (character === delimiter) {
      row.push(field);
      field = "";
      touched = true;
    } else if (character === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
      touched = false;
    } else if (character !== "\r") {
      field += character;
      touched = true;
    }
  }
  if (touched || field !== "") {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

/**
 * Guess the delimiter from the header line. Russian and Kazakh Excel exports
 * default to semicolons, which the previous comma-only parser rejected with a
 * misleading "expected columns" error.
 */
export function sniffDelimiter(text: string): string {
  const headerLine = text.split(/\r?\n/).find((line) => line.trim() !== "") ?? "";
  let best = ",";
  let bestCount = 0;
  for (const delimiter of DELIMITERS) {
    const count = splitDelimited(headerLine, delimiter)[0]?.length ?? 0;
    if (count > bestCount) {
      bestCount = count;
      best = delimiter;
    }
  }
  return best;
}

function uniqueHeaders(raw: string[]): string[] {
  const seen = new Map<string, number>();
  return raw.map((value, index) => {
    const base = value.trim().replace(/^﻿/, "") || `column_${index + 1}`;
    const count = seen.get(base) ?? 0;
    seen.set(base, count + 1);
    return count ? `${base}_${count + 1}` : base;
  });
}

export type ParseOptions = {
  sourceName?: string;
  /** Guard against a pasted workbook blowing up the request payload. */
  maxRecords?: number;
};

export function parseTabular(input: string, options: ParseOptions = {}): Dataset {
  const sourceName = options.sourceName ?? "uploaded file";
  const maxRecords = options.maxRecords ?? 5000;
  const text = input.replace(/^﻿/, "").trim();
  if (!text) throw new Error("The file is empty.");

  if (text.startsWith("[") || text.startsWith("{")) return parseJson(text, sourceName, maxRecords);

  const delimiter = sniffDelimiter(text);
  const rows = splitDelimited(text, delimiter);
  const headerRow = rows.shift();
  if (!headerRow) throw new Error("The file has no header row.");

  const headers = uniqueHeaders(headerRow);
  if (headers.length < 2) {
    throw new Error("Could not detect columns. Expected a delimited file (comma, semicolon, tab or pipe).");
  }

  const issues: ParseIssue[] = [];
  const dataRows: string[][] = [];
  rows.forEach((row, index) => {
    const line = index + 2;
    if (row.every((value) => value.trim() === "")) return;
    if (row.length !== headers.length) {
      issues.push({ line, reason: `expected ${headers.length} values, found ${row.length}` });
      return;
    }
    if (dataRows.length >= maxRecords) {
      issues.push({ line, reason: `beyond the ${maxRecords}-record limit for this sprint template` });
      return;
    }
    dataRows.push(row);
  });

  if (!dataRows.length) throw new Error("No readable data rows were found.");

  const headerIndex = new Map(headers.map((key, index) => [key, index] as const));
  const columns: Column[] = headers.map((key, index) => ({
    key,
    kind: inferKind(dataRows.slice(0, 200).map((row) => row[index] ?? "")),
  }));

  const idColumn = pickIdColumn(columns, dataRows, headerIndex);
  const records: DataRecord[] = dataRows.map((row, index) => {
    const fields: Record<string, string | number | null> = {};
    columns.forEach((column, columnIndex) => {
      const raw = (row[columnIndex] ?? "").trim();
      if (column.kind === "number") fields[column.key] = toNumber(raw);
      else fields[column.key] = raw === "" ? null : raw;
    });
    const identifier = idColumn ? String(fields[idColumn] ?? "").trim() : "";
    return { id: identifier || `row-${index + 1}`, fields };
  });

  return { sourceName, columns, records, issues };
}

function parseJson(text: string, sourceName: string, maxRecords: number): Dataset {
  let payload: unknown;
  try {
    payload = JSON.parse(text);
  } catch {
    throw new Error("The file looks like JSON but could not be parsed.");
  }
  const list = Array.isArray(payload)
    ? payload
    : Object.values(payload as Record<string, unknown>).find(Array.isArray);
  if (!Array.isArray(list) || !list.length) throw new Error("Expected a JSON array of objects.");

  const issues: ParseIssue[] = [];
  const objects: Record<string, unknown>[] = [];
  list.forEach((entry, index) => {
    if (typeof entry !== "object" || entry === null || Array.isArray(entry)) {
      issues.push({ line: index + 1, reason: "not an object" });
      return;
    }
    if (objects.length >= maxRecords) {
      issues.push({ line: index + 1, reason: `beyond the ${maxRecords}-record limit for this sprint template` });
      return;
    }
    objects.push(entry as Record<string, unknown>);
  });
  if (!objects.length) throw new Error("No readable objects were found.");

  const headers = uniqueHeaders([...new Set(objects.flatMap((entry) => Object.keys(entry)))]);
  const columns: Column[] = headers.map((key) => ({
    key,
    kind: inferKind(objects.slice(0, 200).map((entry) => stringify(entry[key]))),
  }));

  const rows = objects.map((entry) => headers.map((key) => stringify(entry[key])));
  const headerIndex = new Map(headers.map((key, index) => [key, index] as const));
  const idColumn = pickIdColumn(columns, rows, headerIndex);

  const records: DataRecord[] = objects.map((entry, index) => {
    const fields: Record<string, string | number | null> = {};
    columns.forEach((column) => {
      const raw = stringify(entry[column.key]).trim();
      if (column.kind === "number") fields[column.key] = toNumber(raw);
      else fields[column.key] = raw === "" ? null : raw;
    });
    const identifier = idColumn ? String(fields[idColumn] ?? "").trim() : "";
    return { id: identifier || `row-${index + 1}`, fields };
  });

  return { sourceName, columns, records, issues };
}

function stringify(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
