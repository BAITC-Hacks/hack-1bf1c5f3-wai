/**
 * The agent's entire action space: four narrow, deterministic tools.
 *
 * They are schema-agnostic on purpose. Whatever the released task turns out to
 * be, if it arrives as records with columns these still apply, so the tool
 * layer does not have to be rewritten under the clock.
 */

import { findOutliers, groupBy, inspectRecords, summarize, type Aggregation } from "@/lib/data/aggregate";
import type { Dataset } from "@/lib/data/records";
import type { Tool } from "./types";

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function requireColumn(dataset: Dataset, key: string): void {
  if (!dataset.columns.some((column) => column.key === key)) {
    throw new Error(`Unknown column "${key}". Available: ${dataset.columns.map((column) => column.key).join(", ")}`);
  }
}

export const summarizeDataset: Tool = {
  name: "summarize_dataset",
  description:
    "Return row count, column names, inferred types, and per-column statistics (sum, mean, min, max, standard deviation, missing values, most common categories). Call this first to learn what the data contains.",
  parameters: { type: "object", properties: {}, additionalProperties: false },
  run: (_args, dataset) => {
    const summary = summarize(dataset);
    return {
      value: summary,
      evidenceIds: [],
      describe: `Read ${summary.records} records and profiled ${summary.columns.length} columns from ${summary.sourceName}`,
    };
  },
};

export const groupRecords: Tool = {
  name: "group_records",
  description:
    "Aggregate a numeric column by a categorical column to compare entities against each other. Use to find which group contributes the most of something.",
  parameters: {
    type: "object",
    properties: {
      group_by: { type: "string", description: "Categorical column to group on." },
      value_column: { type: "string", description: "Numeric column to aggregate. Omit to count rows." },
      aggregation: { type: "string", enum: ["sum", "mean", "count", "max"] },
    },
    required: ["group_by"],
    additionalProperties: false,
  },
  run: (args, dataset) => {
    const groupKey = asString(args.group_by);
    requireColumn(dataset, groupKey);
    const valueKey = asString(args.value_column) || null;
    if (valueKey) requireColumn(dataset, valueKey);
    const aggregation = (asString(args.aggregation, "sum") as Aggregation) ?? "sum";
    const groups = groupBy(dataset, groupKey, valueKey, aggregation);
    const top = groups[0];
    return {
      value: groups.slice(0, 20),
      evidenceIds: top?.recordIds ?? [],
      describe: `Grouped ${aggregation} of ${valueKey ?? "records"} by ${groupKey}${top ? ` — highest is ${top.group} at ${top.value}` : ""}`,
    };
  },
};

export const detectOutliers: Tool = {
  name: "detect_outliers",
  description:
    "Flag records whose value in a numeric column is statistically unusual, or outside an explicit operating threshold when the task supplies one. Returns record ids so findings can be cited.",
  parameters: {
    type: "object",
    properties: {
      column: { type: "string", description: "Numeric column to test." },
      z_score: { type: "number", description: "Standard deviations from the mean to flag. Default 1.5." },
      min: { type: "number", description: "Optional lower operating limit." },
      max: { type: "number", description: "Optional upper operating limit." },
    },
    required: ["column"],
    additionalProperties: false,
  },
  run: (args, dataset) => {
    const key = asString(args.column);
    requireColumn(dataset, key);
    const outliers = findOutliers(dataset, key, {
      zScore: asNumber(args.z_score),
      min: asNumber(args.min),
      max: asNumber(args.max),
    });
    return {
      value: outliers.slice(0, 50),
      evidenceIds: outliers.map((outlier) => outlier.recordId),
      describe: `Tested ${key} and flagged ${outliers.length} of ${dataset.records.length} records as unusual`,
    };
  },
};

export const readRecords: Tool = {
  name: "read_records",
  description:
    "Fetch the full field values for specific record ids. Use before making a claim about a particular row so the claim can name its source.",
  parameters: {
    type: "object",
    properties: {
      ids: { type: "array", items: { type: "string" }, description: "Record ids to read." },
    },
    required: ["ids"],
    additionalProperties: false,
  },
  run: (args, dataset) => {
    const ids = Array.isArray(args.ids) ? args.ids.map((id) => String(id)) : [];
    const records = inspectRecords(dataset, ids.slice(0, 25));
    return {
      value: records,
      evidenceIds: records.map((record) => record.id),
      describe: `Read source rows ${records.map((record) => record.id).join(", ") || "(none matched)"}`,
    };
  },
};

export const TOOLS: Tool[] = [summarizeDataset, groupRecords, detectOutliers, readRecords];

export function findTool(name: string): Tool | undefined {
  return TOOLS.find((tool) => tool.name === name);
}
