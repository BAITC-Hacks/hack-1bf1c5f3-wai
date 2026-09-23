/**
 * The orchestrator layer.
 *
 * Both paths produce a trace built from tool calls that actually executed:
 * live mode lets the model choose the sequence, demo mode runs a fixed one.
 * A judge with no API key still sees a real tool trace, not a mock.
 */

import OpenAI from "openai";
import { bestGroupingColumn, mostVariableColumn, summarize } from "@/lib/data/aggregate";
import type { Dataset } from "@/lib/data/records";
import { TOOLS, findTool } from "./tools";
import type { AgentResult, Insight, TraceStep } from "./types";

const MAX_TURNS = 5;
const TIME_BUDGET_MS = 20_000;
const MAX_TOOL_OUTPUT_CHARS = 6_000;

const INSTRUCTIONS = `You are an evidence-based decision-support agent.

Rules:
- Establish facts only by calling tools. Never calculate a number yourself and never invent a reading.
- Call summarize_dataset first to learn the schema; the column names are not known in advance.
- Then use at least one more tool to test a specific hypothesis before concluding.
- Cite concrete record ids returned by the tools in the evidence field.
- Describe correlation as correlation. Do not assert a root cause as fact.
- Recommend a next step for a human reviewer. Never present a recommendation as an action already taken.
- State what you could not establish from the supplied data.`;

const RESPONSE_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["headline", "priority", "finding", "recommendation", "evidence", "disclaimer"],
  properties: {
    headline: { type: "string" },
    priority: { type: "string", enum: ["high", "medium", "low"] },
    finding: { type: "string" },
    recommendation: { type: "string" },
    evidence: { type: "array", items: { type: "string" } },
    disclaimer: { type: "string" },
  },
} as const;

type FunctionCall = { type: "function_call"; call_id: string; name: string; arguments: string };

function isFunctionCall(item: unknown): item is FunctionCall {
  return typeof item === "object" && item !== null && (item as { type?: string }).type === "function_call";
}

function execute(name: string, args: Record<string, unknown>, dataset: Dataset, trace: TraceStep[]) {
  const tool = findTool(name);
  const started = Date.now();
  if (!tool) {
    const step: TraceStep = { tool: name, args, summary: `Unknown tool "${name}"`, evidenceIds: [], ms: 0 };
    trace.push(step);
    return { error: `Unknown tool "${name}".` };
  }
  try {
    const result = tool.run(args, dataset);
    trace.push({
      tool: name,
      args,
      summary: result.describe,
      evidenceIds: result.evidenceIds.slice(0, 50),
      ms: Date.now() - started,
    });
    return result.value;
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : "Tool failed.";
    trace.push({ tool: name, args, summary: `Failed: ${message}`, evidenceIds: [], ms: Date.now() - started });
    return { error: message };
  }
}

/**
 * Deterministic fallback. Runs a fixed, sensible tool sequence over whatever
 * columns exist, so the golden demo path never depends on a key or a network.
 */
export function runDeterministic(dataset: Dataset, degraded?: string): AgentResult {
  const trace: TraceStep[] = [];
  const summary = summarize(dataset);
  execute("summarize_dataset", {}, dataset, trace);

  const target = mostVariableColumn(dataset);
  const outliers = target
    ? (execute("detect_outliers", { column: target }, dataset, trace) as { recordId: string; value: number; reason: string }[])
    : [];

  const category = bestGroupingColumn(dataset);
  const groups = category && target
    ? (execute("group_records", { group_by: category, value_column: target, aggregation: "sum" }, dataset, trace) as { group: string; value: number }[])
    : [];

  const flaggedIds = Array.isArray(outliers) ? outliers.slice(0, 5).map((outlier) => outlier.recordId) : [];
  if (flaggedIds.length) execute("read_records", { ids: flaggedIds }, dataset, trace);

  const worst = Array.isArray(groups) ? groups[0] : undefined;
  const flaggedCount = Array.isArray(outliers) ? outliers.length : 0;
  const share = summary.records ? Math.round((flaggedCount / summary.records) * 100) : 0;

  const insight: Insight = {
    headline: target
      ? `${flaggedCount} record${flaggedCount === 1 ? "" : "s"} show${flaggedCount === 1 ? "s" : ""} unusual ${target}`
      : `${summary.records} records loaded, no numeric column to test`,
    priority: share >= 20 ? "high" : share > 0 ? "medium" : "low",
    finding: target
      ? `${flaggedCount} of ${summary.records} records (${share}%) sit outside the normal range for ${target}.${worst ? ` Grouping by ${category} shows ${worst.group} with the highest total at ${worst.value}.` : ""}`
      : `The file parsed into ${summary.records} records across ${summary.columns.length} columns, but contains no numeric column to analyse.`,
    recommendation: target
      ? `Ask the responsible data owner to review the flagged records and confirm the cause before acting on the finding.`
      : `Confirm with the data owner which column carries the measurement of interest, then re-run the analysis.`,
    evidence: [
      `Source: ${summary.sourceName} (${summary.records} records${summary.skippedRows ? `, ${summary.skippedRows} rows skipped` : ""})`,
      ...(flaggedIds.length ? [`Flagged record ids: ${flaggedIds.join(", ")}`] : []),
      ...(worst ? [`Highest ${target} total by ${category}: ${worst.group} (${worst.value})`] : []),
    ],
    disclaimer:
      "Deterministic analysis of the supplied fields only. This is a prompt for human review, not an action taken by the system.",
  };

  return { ...insight, mode: "demo", trace, ...(degraded ? { degraded } : {}) };
}

export async function runAgent(dataset: Dataset, question: string): Promise<AgentResult> {
  if (!process.env.OPENAI_API_KEY) return runDeterministic(dataset);

  const trace: TraceStep[] = [];
  const deadline = Date.now() + TIME_BUDGET_MS;

  try {
    const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
    const tools = TOOLS.map((tool) => ({
      type: "function" as const,
      name: tool.name,
      description: tool.description,
      parameters: tool.parameters as unknown as Record<string, unknown>,
      strict: false,
    }));

    let input: unknown[] = [{ role: "user", content: question }];

    for (let turn = 0; turn < MAX_TURNS; turn++) {
      const remaining = deadline - Date.now();
      if (remaining <= 0) throw new Error("The analysis exceeded its time budget.");

      const response = await client.responses.create(
        {
          model: process.env.OPENAI_MODEL || "gpt-5-mini",
          instructions: INSTRUCTIONS,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          input: input as any,
          tools,
          text: { format: { type: "json_schema", name: "operations_insight", strict: true, schema: RESPONSE_SCHEMA } },
        },
        { signal: AbortSignal.timeout(remaining) },
      );

      const calls = (response.output ?? []).filter(isFunctionCall);
      if (!calls.length) {
        const parsed = JSON.parse(response.output_text) as Insight;
        if (!trace.length) throw new Error("The model answered without consulting the data.");
        return { ...parsed, mode: "live", trace };
      }

      input = [...input, ...response.output];
      for (const call of calls) {
        let args: Record<string, unknown> = {};
        try {
          args = call.arguments ? (JSON.parse(call.arguments) as Record<string, unknown>) : {};
        } catch {
          args = {};
        }
        const value = execute(call.name, args, dataset, trace);
        input.push({
          type: "function_call_output",
          call_id: call.call_id,
          output: JSON.stringify(value).slice(0, MAX_TOOL_OUTPUT_CHARS),
        });
      }
    }
    throw new Error(`The agent did not reach a conclusion within ${MAX_TURNS} turns.`);
  } catch (caught) {
    // The demo must never show a judge a red error box because a key expired,
    // a quota ran out, or the network stalled. Fall back, and say so.
    const reason = caught instanceof Error ? caught.message : "The live analysis failed.";
    return runDeterministic(dataset, `Live analysis unavailable (${reason}). Showing the deterministic result instead.`);
  }
}
