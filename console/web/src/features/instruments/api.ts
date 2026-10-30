/**
 * The Instruments screens' wire types and calls (console card 012): the idle status file, the person's
 * limits, the latest run's events, and a plan draft. Every route is a read or a composition, except [Lights off]
 * (`lightsOff`, card 023 part 5): the one press that asks the live-view host to turn the lights off. A draft is
 * returned and saved nowhere.
 */

import { type Client, CommandRefused } from "../../app/client";
import type { components } from "../../api/schema";

type Schemas = components["schemas"];

export type StatusOut = Schemas["StatusOut"];
export type LimitsOut = Schemas["LimitsOut"];
export type LatestRun = Schemas["LatestRunOut"];
export type DraftIn = Schemas["DraftIn"];
export type DraftOut = Schemas["DraftOut"];
export type ChangesIn = Schemas["ChangesIn"];
export type LightsOffOut = Schemas["LightsOffOut"];
export type LightSourceOut = Schemas["LightSourceOut"];

export const PATHS = {
  lightsOff: "/api/instruments/lights-off",
  status: "/api/instruments/status",
  limits: "/api/instruments/limits",
  latestRun: "/api/instruments/latest-run",
  draft: "/api/instruments/draft",
  changes: "/api/instruments/changes",
};

/** One reading of the idle status file (`idle_status.schema.json`, `$defs/reading`). */
export interface Reading {
  channel: string;
  name: string;
  how: "read_back" | "not_readable" | "not_read";
  t_wall: string | null;
  value: unknown;
}

/** The three `how` words, as the person reads them. */
export const HOW_WORDS: Record<Reading["how"], string> = {
  read_back: "read back",
  not_readable: "sent, cannot be read",
  not_read: "not read",
};

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/** The readings of an idle status file, as far as each is a record (the schema accepted the file). */
export function readingsOf(list: unknown): Reading[] {
  return Array.isArray(list) ? (list.filter(isRecord) as unknown as Reading[]) : [];
}

export interface IdleView {
  writtenAt: string;
  writtenByRun: string;
  snapshotAt: string | null;
  snapshot: Reading[];
  checkNow: { runId: string; at: string; readings: Reading[] } | null;
  ownership: { status: string; verdicts: unknown[] };
}

/** The pieces of a validated idle status file the screens show. */
export function idleView(data: Record<string, unknown>): IdleView {
  const last = isRecord(data.last_run) ? data.last_run : null;
  const snap = last !== null && isRecord(last.last_snapshot) ? last.last_snapshot : null;
  const cn = isRecord(data.check_now) ? data.check_now : null;
  const own = isRecord(data.ownership) ? data.ownership : {};
  return {
    writtenAt: String(data.written_at ?? ""),
    writtenByRun: String(data.written_by_run ?? ""),
    snapshotAt: snap !== null && typeof snap.t_wall === "string" ? snap.t_wall : null,
    snapshot: snap !== null ? readingsOf(snap.channels) : [],
    checkNow:
      cn !== null ? { runId: String(cn.run_id ?? ""), at: String(cn.t_wall ?? ""), readings: readingsOf(cn.channels) } : null,
    ownership: { status: String(own.status ?? "not_built"), verdicts: Array.isArray(own.verdicts) ? own.verdicts : [] },
  };
}

/** A value as a person reads it: strings and numbers as they are, an object as compact JSON, null as unknown. */
export function valueText(v: unknown): string {
  if (v === null || v === undefined) return "unknown";
  if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") return String(v);
  return JSON.stringify(v);
}

/** `POST /api/instruments/draft`: a plan draft, checked against plan.schema.json and saved nowhere. */
export async function makeDraft(client: Client, body: DraftIn): Promise<DraftOut> {
  const r = await client.post<DraftOut>(PATHS.draft, body);
  if (r === null) throw new CommandRefused(502, "the server returned no draft");
  return r;
}

/** `POST /api/instruments/changes`: the collected clicks as one plan draft, checked and saved nowhere. */
export async function makeChanges(client: Client, body: ChangesIn): Promise<DraftOut> {
  const r = await client.post<DraftOut>(PATHS.changes, body);
  if (r === null) throw new CommandRefused(502, "the server returned no draft");
  return r;
}

export type Range = { min: { value: number; unit: string | null }; max: { value: number; unit: string | null } } | null;

/** `limits.piezo[axis]`, or null when the safety file holds no range for that axis. */
export function piezoRange(limits: LimitsOut | undefined, axis: "x" | "y" | "z"): Range {
  const r = limits?.piezo?.[axis];
  return (r ?? null) as Range;
}
