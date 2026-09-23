/**
 * Stable import surface for the rest of the app.
 *
 * The task-specific shape lives in the data, not in these types: the app works
 * on generic records so a different released schema does not require a rewrite.
 */

export type {
  CellValue,
  Column,
  ColumnKind,
  DataRecord,
  Dataset,
  ParseIssue,
} from "./data/records";

export type { ColumnSummary, DatasetSummary, GroupResult, Outlier } from "./data/aggregate";
export type { AgentResult, Insight, TraceStep } from "./agent/types";
