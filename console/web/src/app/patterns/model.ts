// Motion patterns, shared by the Patterns area (the designer) and the live view (the overlay).
// The shape and the checks are the server's (src/dino_autofocus/engine/patterns.py); the types
// come from gen:api. Display only: nothing here moves hardware.

import type { components } from "../../api/schema";

type Schemas = components["schemas"];
export type PatternOut = Schemas["PatternOut"];
export type PatternIn = Schemas["PatternIn"];
export type PatternSummary = Schemas["PatternSummary"];
export type Track = Schemas["TrackIO"];
/** [t_s, x_um, y_um, z_um] */
export type Pt = [number, number, number, number];

export const MAX_TRAPS = 8;
/** as in engine/patterns.py */
export const MAX_POINTS = 20_000;
export const MAX_DURATION_S = 3600;
export const TARGETS = ["piezo", ...Array.from({ length: MAX_TRAPS }, (_, i) => `trap:${i}`)];

/** PROVISIONAL ranges, as in engine/patterns.py (not measured); the server checks them again. */
export const RANGE_UM = {
  piezo: { x: [-100, 100], y: [-100, 100], z: [-50, 50] },
  trap: { x: [-60, 60], y: [-60, 60], z: [-10, 10] },
} as const;

export const rangeOf = (target: string) => (target === "piezo" ? RANGE_UM.piezo : RANGE_UM.trap);

export function targetLabel(target: string): string {
  return target === "piezo" ? "Piezo XYZ" : `Trap ${target.slice(5)}`;
}

const pt = (p: number[]): Pt => [p[0] ?? 0, p[1] ?? 0, p[2] ?? 0, p[3] ?? 0];

export function trackDuration(track: Track): number {
  return track.points.length ? track.points[track.points.length - 1][0] : 0;
}

export function patternDuration(p: { tracks: Track[] }): number {
  return Math.max(0, ...p.tracks.map(trackDuration));
}

/** The position at `t` (clamped; the last point holds), linear between points. */
export function sampleTrack(track: Track, t: number): Pt {
  const pts = track.points;
  if (pts.length === 0) return [t, 0, 0, 0];
  if (t <= pts[0][0]) return pt(pts[0]);
  if (t >= pts[pts.length - 1][0]) return pt(pts[pts.length - 1]);
  let lo = 0;
  let hi = pts.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (pts[mid][0] <= t) lo = mid;
    else hi = mid;
  }
  const a = pt(pts[lo]);
  const b = pt(pts[hi]);
  const f = (t - a[0]) / (b[0] - a[0]);
  return [t, a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2]), a[3] + f * (b[3] - a[3])];
}

/** Pattern time for a clock time: wraps when the pattern loops, else holds at the end. */
export function patternTime(p: { tracks: Track[]; loop?: boolean }, t: number): number {
  const d = patternDuration(p);
  if (d <= 0) return 0;
  return p.loop ? ((t % d) + d) % d : Math.min(Math.max(t, 0), d);
}

/**
 * What the browser can say before saving; the server's check is the one that counts.
 * Returns the first problem, or null.
 */
export function firstProblem(p: { tracks: Track[] }): string | null {
  if (p.tracks.length === 0) return "add at least one track";
  const seen = new Set<string>();
  for (const tr of p.tracks) {
    const name = targetLabel(tr.target);
    if (seen.has(tr.target)) return `${name}: each target may have one track only`;
    seen.add(tr.target);
    if (tr.points.length === 0) return `${name}: no points`;
    if (tr.points.length > MAX_POINTS) return `${name}: ${tr.points.length} points (at most ${MAX_POINTS})`;
    if (trackDuration(tr) > MAX_DURATION_S) return `${name}: lasts ${trackDuration(tr)} s (at most ${MAX_DURATION_S} s)`;
    if (tr.points[0][0] !== 0) return `${name}: the first point must be at t = 0 s`;
    const r = rangeOf(tr.target);
    for (let i = 0; i < tr.points.length; i++) {
      const [t, x, y, z] = pt(tr.points[i]);
      if (![t, x, y, z].every(Number.isFinite)) return `${name} point ${i}: not a number`;
      if (i > 0 && t <= tr.points[i - 1][0]) return `${name} point ${i}: time must go up`;
      const axes: [string, number, readonly number[]][] = [["x", x, r.x], ["y", y, r.y], ["z", z, r.z]];
      for (const [axis, v, [lo, hi]] of axes)
        if (v < lo || v > hi) return `${name} point ${i}: ${axis} ${v} µm is outside ${lo}..${hi} µm (provisional)`;
    }
  }
  return null;
}

// -- time colour: gray at the start, dark green at the end ------------------------------------

export const START_COLOR = [0x9e, 0x9e, 0x9e] as const; // #9e9e9e
export const END_COLOR = [0x1b, 0x5e, 0x20] as const; // #1b5e20

/** The colour at fraction `f` (0 = start, 1 = end) of the pattern's time. */
export function timeColor(f: number): string {
  const k = Math.min(Math.max(Number.isFinite(f) ? f : 0, 0), 1);
  const c = START_COLOR.map((s, i) => Math.round(s + k * (END_COLOR[i] - s)));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

export const GRADIENT_CSS = `linear-gradient(to right, ${timeColor(0)}, ${timeColor(1)})`;
