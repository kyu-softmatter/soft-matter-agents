/**
 * The Experiments screens' wire types and calls (console card 014). Every route but one is a read of files
 * on disk; the one POST, `run`, answers that Run is not built yet and sends nothing to a runtime.
 */

import { type Client, CommandRefused } from "../../app/client";
import type { components } from "../../api/schema";

type Schemas = components["schemas"];

export type PlansOut = Schemas["PlansOut"];
export type PlanOut = Schemas["PlanOut"];
export type RunOut = Schemas["RunOut"];
export type HandStepOut = Schemas["HandStepOut"];
export type SampleOut = Schemas["SampleOut"];
export type SampleMapOut = Schemas["SampleMapOut"];
export type RunNotBuiltOut = Schemas["RunNotBuiltOut"];

export const PATHS = {
  plans: "/api/experiments/plans",
  run: "/api/experiments/run",
  sample: "/api/experiments/sample",
  sampleMap: "/api/experiments/sample-map",
};

/** What Run would send for this plan, and that it is not built yet. Nothing leaves the console. */
export async function askRun(client: Client, planId: string, planRevision: number): Promise<RunNotBuiltOut> {
  const r = await client.post<RunNotBuiltOut>(PATHS.run, { plan_id: planId, plan_revision: planRevision });
  if (r === null) throw new CommandRefused(502, "the server returned no answer");
  return r;
}
