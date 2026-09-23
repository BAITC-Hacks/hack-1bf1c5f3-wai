import type { Dataset } from "@/lib/data/records";

/** JSON Schema fragment describing a tool's arguments. */
export type JsonSchema = {
  type: "object";
  properties: Record<string, unknown>;
  required?: string[];
  additionalProperties: false;
};

export type ToolResult = {
  /** Serialisable payload returned to the model. */
  value: unknown;
  /** Record ids this result depends on, so claims stay citable. */
  evidenceIds: string[];
  /** One plain-language line for the judge-visible trace. */
  describe: string;
};

export type Tool = {
  name: string;
  description: string;
  parameters: JsonSchema;
  run: (args: Record<string, unknown>, dataset: Dataset) => ToolResult;
};

/** One executed step. Recorded from a real call, never narrated by the model. */
export type TraceStep = {
  tool: string;
  args: Record<string, unknown>;
  summary: string;
  evidenceIds: string[];
  ms: number;
};

export type Insight = {
  headline: string;
  priority: "high" | "medium" | "low";
  finding: string;
  recommendation: string;
  evidence: string[];
  disclaimer: string;
};

export type AgentResult = Insight & {
  mode: "live" | "demo";
  /** Set when the live path failed and deterministic output was substituted. */
  degraded?: string;
  trace: TraceStep[];
};
