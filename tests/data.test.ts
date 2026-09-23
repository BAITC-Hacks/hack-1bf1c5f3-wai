import assert from "node:assert/strict";
import { test } from "node:test";
import { bestGroupingColumn, findOutliers, groupBy, summarize } from "../src/lib/data/aggregate";
import { parseTabular } from "../src/lib/data/parse";
import { toNumber } from "../src/lib/data/records";
import { runDeterministic } from "../src/lib/agent/run";
import { demoCsv } from "../src/lib/demo-data";

const HEADER = "record_id,team,category,duration_minutes,quantity,date";
const ROW = "R-101,Alpha,Review,12,4,2026-09-23";

test("parses a comma-separated file and infers column kinds", () => {
  const dataset = parseTabular(`${HEADER}\n${ROW}`);
  assert.equal(dataset.records.length, 1);
  assert.equal(dataset.records[0].id, "R-101");
  assert.equal(dataset.records[0].fields.duration_minutes, 12);
  assert.equal(dataset.columns.find((column) => column.key === "duration_minutes")?.kind, "number");
  assert.equal(dataset.columns.find((column) => column.key === "category")?.kind, "text");
});

test("keeps quoted fields containing the delimiter intact", () => {
  const dataset = parseTabular(`${HEADER}\nR-1,Alpha,"Review, follow-up",12,4,2026-09-23`);
  assert.equal(dataset.records[0].fields.category, "Review, follow-up");
});

test("detects semicolon-delimited exports", () => {
  const dataset = parseTabular(`${HEADER.replace(/,/g, ";")}\n${ROW.replace(/,/g, ";")}`);
  assert.equal(dataset.records.length, 1);
  assert.equal(dataset.records[0].fields.duration_minutes, 12);
});

test("reads decimal commas without producing NaN", () => {
  const dataset = parseTabular(`${HEADER}\nR-1,Alpha,Review,"12,5",4,2026-09-23`);
  assert.equal(dataset.records[0].fields.duration_minutes, 12.5);
});

test("treats an empty numeric cell as missing, never as zero", () => {
  const dataset = parseTabular(`${HEADER}\nR-1,Alpha,Review,,4,2026-09-23`);
  assert.equal(dataset.records[0].fields.duration_minutes, null);
  const duration = summarize(dataset).columns.find((column) => column.key === "duration_minutes");
  assert.equal(duration?.missing, 1);
  assert.equal(duration?.sum, undefined);
});

test("skips one malformed row and keeps the rest", () => {
  const dataset = parseTabular(`${HEADER}\n${ROW}\nR-2,Alpha\nR-3,Beta,Intake,15,2,2026-09-23`);
  assert.equal(dataset.records.length, 2);
  assert.equal(dataset.issues.length, 1);
  assert.equal(dataset.issues[0].line, 3);
});

test("parses a JSON array of objects", () => {
  const dataset = parseTabular('[{"record_id":"R-1","quantity":4},{"record_id":"R-2","quantity":2}]');
  assert.equal(dataset.records.length, 2);
  assert.equal(dataset.records[1].id, "R-2");
  assert.equal(dataset.records[1].fields.quantity, 2);
});

test("toNumber handles separators and rejects non-numeric text", () => {
  assert.equal(toNumber("1 234"), 1234);
  assert.equal(toNumber("1.234,5"), 1234.5);
  assert.equal(toNumber("1,234"), 1234);
  assert.equal(toNumber("12,5"), 12.5);
  assert.equal(toNumber("n/a"), null);
  assert.equal(toNumber(""), null);
});

test("groupBy ranks groups and returns citable record ids", () => {
  const dataset = parseTabular(`${HEADER}\n${ROW}\nR-202,Beta,Intake,15,500,2026-09-23`);
  const groups = groupBy(dataset, "team", "quantity", "sum");
  assert.equal(groups[0].group, "Beta");
  assert.equal(groups[0].value, 500);
  assert.deepEqual(groups[0].recordIds, ["R-202"]);
});

test("findOutliers flags values outside an explicit threshold", () => {
  const dataset = parseTabular(`${HEADER}\n${ROW}\nR-202,Beta,Intake,48,2,2026-09-23\nR-303,Gamma,Review,14,1,2026-09-23`);
  const flagged = findOutliers(dataset, "duration_minutes", { max: 40 });
  assert.equal(flagged.length, 1);
  assert.equal(flagged[0].recordId, "R-202");
});

test("deterministic agent run produces a real multi-step trace with evidence", () => {
  const dataset = parseTabular(`${HEADER}\n${ROW}\nR-202,Beta,Intake,48,2,2026-09-23\nR-303,Gamma,Review,14,1,2026-09-23`);
  const result = runDeterministic(dataset);
  assert.equal(result.mode, "demo");
  assert.ok(result.trace.length >= 2, "expected at least two tool calls");
  assert.equal(result.trace[0].tool, "summarize_dataset");
  assert.ok(result.trace.some((step) => step.evidenceIds.length > 0), "expected cited record ids");
  assert.ok(result.evidence.length > 0);
});

test("bestGroupingColumn skips the unique record id and chooses a reusable category", () => {
  const dataset = parseTabular(demoCsv);
  assert.equal(bestGroupingColumn(dataset), "team");
});

test("deterministic run groups by a category, not by the record identifier", () => {
  const result = runDeterministic(parseTabular(demoCsv));
  const grouping = result.trace.find((step) => step.tool === "group_records");
  assert.ok(grouping, "expected a group_records step");
  assert.equal(grouping.args.group_by, "team");
  assert.match(result.headline, /^1 record shows unusual duration_minutes$/);
});
