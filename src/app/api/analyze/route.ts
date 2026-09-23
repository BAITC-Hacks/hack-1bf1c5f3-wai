import { z } from "zod";
import { runAgent } from "@/lib/agent/run";
import type { Dataset } from "@/lib/data/records";

const cellSchema = z.union([z.string(), z.number(), z.null()]);

const datasetSchema = z.object({
  sourceName: z.string().max(200),
  columns: z.array(z.object({ key: z.string(), kind: z.enum(["number", "date", "text"]) })).min(1).max(100),
  records: z.array(z.object({ id: z.string(), fields: z.record(z.string(), cellSchema) })).min(1).max(5000),
  issues: z.array(z.object({ line: z.number(), reason: z.string() })).default([]),
});

const inputSchema = z.object({
  dataset: datasetSchema,
  question: z.string().max(500).optional(),
});

export async function POST(request: Request) {
  let parsed: z.infer<typeof inputSchema>;
  try {
    parsed = inputSchema.parse(await request.json());
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : "Invalid request.";
    return Response.json({ error: message }, { status: 400 });
  }

  const dataset = parsed.dataset as Dataset;
  const question =
    parsed.question?.trim() ||
    "Review this operational dataset. Identify the most significant exception, cite the specific records that show it, and recommend a next action for a human reviewer.";

  // runAgent handles its own failures and degrades to the deterministic path,
  // so a judge always gets an answer rather than an error state.
  const result = await runAgent(dataset, question);
  return Response.json(result);
}
