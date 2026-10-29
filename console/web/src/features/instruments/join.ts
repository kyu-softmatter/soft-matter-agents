/**
 * How the drawing finds an order element's reading and its control (console card 023, parts 2 and 3).
 *
 * **The reading is found by exact match** of the order's element id and channel against the read-back's name and channel; no
 * normalisation and no table of names live here. What this file does hold is a short table by **channel**, not by element: the
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

export function lookup(el: OrderElement, run: LatestRun): Found {
  const row = run.path.elements.find((r) => r.name === el.element && r.channel === el.channel);
  if (row !== undefined) return { kind: "row", row };
  if (el.channel === null) return { kind: "none", state: "no_channel", reason: "this element has no channel, so there is nothing to ask of it" };
  const opened = run.channels?.rows.find((c) => c.channel === el.channel);
  if (opened !== undefined && !opened.opened) {
    return { kind: "none", state: "not_open", reason: opened.detail ?? `the run did not open the channel ${el.channel}` };
  }
  return { kind: "none", state: "not_read", reason: `the read-back names no element called ${el.element} on channel ${el.channel}` };
}

export const handSetOf = (el: OrderElement, hand: HandSet[]): HandSet | undefined =>
  hand.find((h) => h.element === el.element && h.channel === el.channel);

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
