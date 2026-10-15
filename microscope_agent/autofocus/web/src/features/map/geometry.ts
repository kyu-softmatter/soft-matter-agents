/**
 * Pure map logic: the display transform, extents and the display-only hints. Nothing here
 * decides safety; the engine's preflight does (docs/screens/map.md section 1).
 */

import type { Box, Candidate, Flag, HoleFit, MapState } from "./api";

/** A view onto stage um: centre, scale (canvas px per um) and canvas size. */
export interface View {
  cx: number;
  cy: number;
  pxPerUm: number;
  width: number;
  height: number;
}

/**
 * Stage um -> canvas px. Both axes are flipped (joystick direction, ui-spec 1.2 (d)):
 * +stage x is drawn to the left, +stage y downwards.
 */
export function toCanvas(v: View, x_um: number, y_um: number): [number, number] {
  return [(v.cx - x_um) * v.pxPerUm + v.width / 2, (y_um - v.cy) * v.pxPerUm + v.height / 2];
}

export function toStage(v: View, u: number, w: number): [number, number] {
  return [v.cx - (u - v.width / 2) / v.pxPerUm, v.cy + (w - v.height / 2) / v.pxPerUm];
}

export function boxUnion(boxes: (Box | null | undefined)[]): Box | null {
  let out: Box | null = null;
  for (const b of boxes) {
    if (!b) continue;
    out = out
      ? { x0: Math.min(out.x0, b.x0), x1: Math.max(out.x1, b.x1), y0: Math.min(out.y0, b.y0), y1: Math.max(out.y1, b.y1) }
      : { ...b };
  }
  return out;
}

export function pointBox(x: number, y: number, half: number): Box {
  return { x0: x - half, x1: x + half, y0: y - half, y1: y + half };
}

export function holeBox(h: HoleFit): Box {
  return pointBox(h.centre_um[0], h.centre_um[1], h.diameter_mm * 500);
}

/** A view that fits `box` (plus 5 %) into the canvas; a 10 mm square around `fallback` otherwise. */
export function fitView(box: Box | null, width: number, height: number, fallback: [number, number] = [0, 0]): View {
  const b = box ?? pointBox(fallback[0], fallback[1], 5000);
  const spanX = Math.max(b.x1 - b.x0, 100) * 1.05;
  const spanY = Math.max(b.y1 - b.y0, 100) * 1.05;
  return {
    cx: (b.x0 + b.x1) / 2,
    cy: (b.y0 + b.y1) / 2,
    pxPerUm: Math.min(width / spanX, height / spanY),
    width,
    height,
  };
}

export function mapExtent(state: MapState | null, extra: (Box | null | undefined)[] = []): Box | null {
  if (!state) return boxUnion(extra);
  const pts = state.boundary.map((p) => pointBox(p.x_um, p.y_um, 0));
  return boxUnion([state.hole ? holeBox(state.hole) : null, state.allowed_box_um, ...pts, ...extra]);
}

export function inBox(b: Box, x: number, y: number): boolean {
  return x >= b.x0 && x <= b.x1 && y >= b.y0 && y <= b.y1;
}

export function distanceUm(a: [number, number], b: [number, number]): number {
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

/**
 * Field of view of the current objective, for the current-field rectangle only. 4x sees about
 * 3900 um on the 2400 px sensor (2026-09-30 run); other lenses scale by magnification. Display only.
 */
export function fieldOfViewUm(objective: string | null): number {
  const m = objective ? /(\d+(?:\.\d+)?)\s*x/i.exec(objective) : null;
  const mag = m ? Number(m[1]) : 4;
  return (3900 * 4) / (mag > 0 ? mag : 4);
}

export type FitStatus = "none" | "this_session" | "previous_session";

/** ui-spec 5.1: is the hole fit from this experiment session? (The engine's preflight decides.) */
export function holeFitStatus(state: MapState | null): FitStatus {
  const h = state?.hole;
  if (!h) return "none";
  if (h.fitted_at == null || state.session_started_at == null) return "previous_session";
  return h.fitted_at >= state.session_started_at ? "this_session" : "previous_session";
}

/** operations-spec 8절 7항: warn if the fitted diameter is more than 20 % off the expected one. */
export function diameterOff(h: HoleFit | null, expectedMm: number | null): boolean {
  if (!h || !expectedMm) return false;
  return Math.abs(h.diameter_mm - expectedMm) / expectedMm > 0.2;
}

export function clock(t: number | null | undefined): string {
  if (t === null || t === undefined) return "unknown time";
  const d = new Date(t * 1000);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/** Retired flags stay in the record (T-027c) but are not in play. */
export function isRetired(f: Flag): boolean {
  return f.retired === true || f.retired_at != null;
}

/** Flags as drawn: a flag replaced by a newer one is hidden; retired ones only on request. */
export function visibleFlags(flags: Flag[], showRetired: boolean): Flag[] {
  const replaced = new Set(flags.map((f) => f.replaces).filter((r): r is string => typeof r === "string"));
  return flags.filter((f) => !replaced.has(f.flag_id) && (showRetired || !isRetired(f)));
}

/**
 * Candidates as drawn: a decision (confirm/reject) is a new entry that `decides` an earlier one,
 * which is then hidden. Rejected ones only on request. Nothing is overwritten.
 */
export function visibleCandidates(cands: Candidate[], showRejected: boolean): Candidate[] {
  const decided = new Set(cands.map((c) => c.decides).filter((d): d is string => typeof d === "string"));
  return cands.filter((c) => !decided.has(c.candidate_id) && (showRejected || c.source !== "person_rejected"));
}
