/**
 * How the drawing finds an order element's reading and its control (console card 023, parts 2 and 3).
 *
 * **The reading is found by the pair the order gives** (`read_back.channel` and `read_back.name`), matched exactly against a
 * row's channel and name; never by the element's id. No normalisation and no table of names live here. What this file does hold
 * is a short table by **the element's own channel**, not by element: the
 * three parts software may draft, the two channels that have no control at all, and the channels that have a section tab of their
 * own. A channel is the runtime's name for a device group, so a table of them says nothing about which element the order names.
 */

import type { LatestRun } from "./api";
import type { HandSet, OrderElement } from "./order";
import type { DraftKind } from "./parts";
import type { Element } from "./readout";

export type Found =
  | { kind: "row"; row: Element }
  | { kind: "none"; state: "no_channel" | "not_open" | "not_read"; reason: string };

/** Whether the run opened a channel: false only where its own channels row says so, and `undefined` where the run says nothing. */
function notOpen(run: LatestRun, channel: string): string | undefined {
  const opened = run.channels?.rows.find((c) => c.channel === channel);
  return opened !== undefined && !opened.opened ? (opened.detail ?? `the run did not open the channel ${channel}`) : undefined;
}

/**
 * The reading of an order element: **the row its `read_back` pair names, by exact match of both parts**, and no other. The
 * element's id says nothing here, and a null pair joins no row, whatever a row is called. The pair's channel may differ from the
 * element's own, which still keys the tables below.
 */
export function lookup(el: OrderElement, run: LatestRun): Found {
  const pair = el.read_back;
  if (pair === null) {
    if (el.channel === null) return { kind: "none", state: "no_channel", reason: "this element has no channel, so there is nothing to ask of it" };
    const why = notOpen(run, el.channel);
    if (why !== undefined) return { kind: "none", state: "not_open", reason: why };
    return { kind: "none", state: "not_read", reason: `the order names no pair for ${el.element}, so no row of the read-back is its reading` };
  }
  const row = run.path.elements.find((r) => r.name === pair.name && r.channel === pair.channel);
  if (row !== undefined) return { kind: "row", row };
  const why = notOpen(run, pair.channel);
  if (why !== undefined) return { kind: "none", state: "not_open", reason: why };
  return { kind: "none", state: "not_read", reason: `the read-back names no element called ${pair.name} on channel ${pair.channel}` };
}

/** The `hand_set` entry for an element: the entry whose pair is the element's pair. A null pair on either side joins nothing. */
export const handSetOf = (el: OrderElement, hand: HandSet[]): HandSet | undefined =>
  el.read_back === null ? undefined : hand.find((h) => h.read_back !== null && h.read_back.channel === el.read_back?.channel && h.read_back.name === el.read_back.name);

/** The draft forms there are. An element on one of these channels opens that form, whatever the read-back calls its control. */
export const CHANNEL_DRAFT: Record<string, DraftKind> = { camera_red: "camera_exposure" };
const PARTS: readonly string[] = ["aura", "dialamp", "camera_exposure"];

/** Channels that have no control at all: a click explains why and shows what was last sent. */
export const NO_CONTROL_CHANNELS: readonly string[] = ["laser_combiner", "optical_tweezers"];

/** Channels that have a section tab of their own, by the tab's id and the words the link says. */
export const CHANNEL_TAB: Record<string, { tab: string; label: string }> = {
  camera_red: { tab: "cameras", label: "Cameras" },
  camera_blue: { tab: "cameras", label: "Cameras" },
  optical_tweezers: { tab: "tweezers", label: "Tweezers" },
  confocal_csuw1: { tab: "confocal", label: "Confocal" },
  piezo_stage: { tab: "piezo", label: "Piezo stage" },
};

export const tabOf = (channel: string | null) =>
  channel !== null && Object.hasOwn(CHANNEL_TAB, channel) ? CHANNEL_TAB[channel] : undefined;

export type Control = { kind: "draft"; part: DraftKind | null } | { kind: "hand" } | { kind: "none" };

/** The one control an element has: moved by hand, drafted, or none given. The order's `hand_set` is the strongest word. */
export function controlOf(el: OrderElement, found: Found, hand: HandSet[]): Control {
  if (handSetOf(el, hand) !== undefined) return { kind: "hand" };
  if (el.channel !== null && Object.hasOwn(CHANNEL_DRAFT, el.channel)) return { kind: "draft", part: CHANNEL_DRAFT[el.channel] };
  if (el.channel !== null && NO_CONTROL_CHANNELS.includes(el.channel)) return { kind: "none" };
  if (found.kind === "row" && found.row.control === "draft") {
    const part = found.row.draft;
    return { kind: "draft", part: part !== null && part !== undefined && PARTS.includes(part) ? (part as DraftKind) : null };
  }
  if (found.kind === "row" && found.row.control === "hand") return { kind: "hand" };
  return { kind: "none" };
}
