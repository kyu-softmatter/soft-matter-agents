/**
 * The light-path order as the page reads it (console card 023): `light_path_order` in
 * `contracts/schemas/idle_status.schema.json`, given by the server exactly as the source wrote it and the schema
 * accepted it, in one of four states. **The server has judged it against the schema already; this file only
 * narrows what it gives into types, and anything that does not narrow is "not understood" and is never drawn
 * in part.** No element, branch, place or slot is named here: they all come from the order.
 */

import type { LatestRun } from "./api";

/** The row of the read-back an element is read from, named by the runtime: both parts matched exactly, never the element's id. */
export interface ReadBack {
  channel: string;
  name: string;
}

export interface OrderElement {
  element: string;
  channel: string | null;
  entry_ref: string[];
  /** Null says the runtime names no row for this element, and then no row is its reading. */
  read_back: ReadBack | null;
}

export interface OrderBranch {
  branch: string;
  elements: OrderElement[];
  place_not_recorded: OrderElement[];
}

export interface Slot {
  slot: number;
  name: string | null;
  resolves: boolean;
  entry_ref?: string;
  why?: string;
}

export interface HandSet {
  element: string;
  channel: string | null;
  slots: Slot[];
  read_back: ReadBack | null;
}

export interface ReadOrder {
  entry_ref: string;
  grade: string;
  source: string;
  source_kind: string;
  branches: OrderBranch[];
  hand_set: HandSet[];
}

export type OrderView =
  | { state: "none" }
  | { state: "not_in_snapshot"; reason: string; hand_set: HandSet[] }
  | { state: "not_understood"; problems: string[] }
  | { state: "read"; order: ReadOrder };

/** What the page says of a source kind it has words for. The table starts empty: a kind enters it only once the store has used it. */
export interface KindWords {
  /** "description": the order was written from a description. "observed": it was read at the microscope. */
  kind: "description" | "observed";
}
export type KindTable = Record<string, KindWords>;
export const KIND_WORDS: KindTable = {};

export const DESCRIPTION_WORDS = "from a description, not checked on this microscope";

/** The banner's words and its class: never "observed" for a kind the table does not hold. */
export function bannerOf(order: ReadOrder, table: KindTable = KIND_WORDS): { how: "description" | "observed" | "unknown"; text: string } {
  const known = Object.hasOwn(table, order.source_kind) ? table[order.source_kind] : undefined;
  if (known?.kind === "description") return { how: "description", text: DESCRIPTION_WORDS };
  if (known?.kind === "observed") return { how: "observed", text: `observed at this microscope, grade ${order.grade}` };
  return { how: "unknown", text: `its source is of a kind this page does not know (${order.source_kind}); its grade as given is ${order.grade}` };
}

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isStr = (v: unknown): v is string => typeof v === "string" && v !== "";
const isChannel = (v: unknown): v is string | null => v === null || typeof v === "string";
const isStrings = (v: unknown): v is string[] => Array.isArray(v) && v.every((x) => typeof x === "string");

const CHANNEL_NAME = /^[a-z0-9_]+$/;

/** A pair, or the null the runtime gives for an element it names no row for. `undefined` is a pair that is not there or does not narrow. */
function readBackOf(v: unknown): ReadBack | null | undefined {
  if (v === null) return null;
  if (!isRecord(v) || typeof v.channel !== "string" || !CHANNEL_NAME.test(v.channel) || !isStr(v.name)) return undefined;
  return { channel: v.channel, name: v.name };
}

function elementOf(v: unknown): OrderElement | null {
  if (!isRecord(v) || !isStr(v.element) || !isChannel(v.channel) || !isStrings(v.entry_ref)) return null;
  const read_back = readBackOf(v.read_back);
  return read_back === undefined ? null : { element: v.element, channel: v.channel, entry_ref: v.entry_ref, read_back };
}

function listOf<T>(v: unknown, one: (x: unknown) => T | null): T[] | null {
  if (!Array.isArray(v)) return null;
  const out: T[] = [];
  for (const x of v) {
    const got = one(x);
    if (got === null) return null;
    out.push(got);
  }
  return out;
}

function branchOf(v: unknown): OrderBranch | null {
  if (!isRecord(v) || !isStr(v.branch)) return null;
  const elements = listOf(v.elements, elementOf);
  const holes = listOf(v.place_not_recorded, elementOf);
  return elements === null || holes === null ? null : { branch: v.branch, elements, place_not_recorded: holes };
}

function slotOf(v: unknown): Slot | null {
  if (!isRecord(v) || typeof v.slot !== "number" || typeof v.resolves !== "boolean") return null;
  if (v.name !== null && typeof v.name !== "string") return null;
  return {
    slot: v.slot, name: v.name as string | null, resolves: v.resolves,
    ...(typeof v.entry_ref === "string" ? { entry_ref: v.entry_ref } : {}),
    ...(typeof v.why === "string" ? { why: v.why } : {}),
  };
}

function handSetOf(v: unknown): HandSet | null {
  if (!isRecord(v) || !isStr(v.element) || !isChannel(v.channel)) return null;
  const slots = listOf(v.slots, slotOf);
  const read_back = readBackOf(v.read_back);
  return slots === null || read_back === undefined ? null : { element: v.element, channel: v.channel, slots, read_back };
}

const NOT_NARROWED = "the page could not read the order it was given";

/** The order the run's source gave, as one of four states; the server's `state` and `data` narrowed, never completed. */
export function orderViewOf(run: LatestRun): OrderView {
  const o = run.path.order as LatestRun["path"]["order"] | undefined;
  if (o === undefined || o.state === "none") return { state: "none" };
  const bad = (): OrderView => ({ state: "not_understood", problems: o.problems.length > 0 ? o.problems : [NOT_NARROWED] });
  if (o.state === "not_understood" || !isRecord(o.data)) return bad();
  const d = o.data;
  const hand = listOf(d.hand_set, handSetOf);
  if (hand === null) return bad();
  if (o.state === "not_in_snapshot") return isStr(d.reason) ? { state: "not_in_snapshot", reason: d.reason, hand_set: hand } : bad();
  const branches = listOf(d.branches, branchOf);
  if (branches === null || !isStr(d.entry_ref) || !isStr(d.grade) || !isStr(d.source) || !isStr(d.source_kind)) return bad();
  return { state: "read", order: { entry_ref: d.entry_ref, grade: d.grade, source: d.source, source_kind: d.source_kind, branches, hand_set: hand } };
}
