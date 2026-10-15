import type { Frame } from "./frame";

/** Which two axes the 2D view shows. A 3D run can be seen from any side. */
export type Plane = "xy" | "xz" | "yz";

export const TYPE_COLORS = ["#2a78d6", "#d6732a", "#3a9b5c", "#9b3a8f", "#c9a227", "#5a5a5a"];

export function typeColor(typeid: number): string {
  const k = TYPE_COLORS.length;
  return TYPE_COLORS[((typeid % k) + k) % k];
}

const AXIS: Record<Plane, [number, number]> = { xy: [0, 1], xz: [0, 2], yz: [1, 2] };

export interface Projection {
  /** canvas x, y per particle */
  xs: Float32Array;
  ys: Float32Array;
  /** radius in canvas pixels per particle */
  r: Float32Array;
  /** the box outline in canvas pixels, null when the box has no extent on these axes */
  box: { x: number; y: number; w: number; h: number } | null;
}

/**
 * Map a frame onto a `size` x `size` canvas. Positions are unwrapped in the records (a particle
 * that crossed the periodic boundary keeps going); `wrap` folds them back into the box so the
 * box stays full. Without box extent on an axis (z of a 2D run) the data range is used.
 * Canvas y grows downwards, so the second axis is flipped.
 */
export function projectFrame(frame: Frame, plane: Plane, size: number, wrap: boolean, margin = 12): Projection {
  const [a, b] = AXIS[plane];
  const n = frame.n;
  const len = [frame.box[0], frame.box[1], frame.box[2]];
  const ua = new Float64Array(n);
  const ub = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    ua[i] = frame.positions[3 * i + a];
    ub[i] = frame.positions[3 * i + b];
  }
  const fold = (u: Float64Array, l: number) => {
    if (!(l > 0)) return;
    for (let i = 0; i < u.length; i++) u[i] = ((((u[i] + l / 2) % l) + l) % l) - l / 2;
  };
  if (wrap) {
    fold(ua, len[a]);
    fold(ub, len[b]);
  }
  const span = (u: Float64Array, l: number): [number, number] => {
    if (l > 0 && wrap) return [-l / 2, l / 2];
    let lo = l > 0 ? -l / 2 : Infinity;
    let hi = l > 0 ? l / 2 : -Infinity;
    for (const v of u) {
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
    if (!Number.isFinite(lo)) return [-1, 1];
    if (hi - lo <= 0) return [lo - 1e-9, hi + 1e-9];
    return [lo, hi];
  };
  const [a0, a1] = span(ua, len[a]);
  const [b0, b1] = span(ub, len[b]);
  const inner = Math.max(size - 2 * margin, 1);
  const scale = inner / Math.max(a1 - a0, b1 - b0);
  const ox = margin + (inner - (a1 - a0) * scale) / 2;
  const oy = margin + (inner - (b1 - b0) * scale) / 2;
  const xs = new Float32Array(n);
  const ys = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    xs[i] = ox + (ua[i] - a0) * scale;
    ys[i] = oy + (b1 - ub[i]) * scale;
  }
  const d = frame.fields.diameter;
  const fallback = Math.min(Math.max((inner / Math.sqrt(Math.max(n, 1))) * 0.18, 1.5), 8);
  const r = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    r[i] = d && d.length === n ? Math.max((d[i] / 2) * scale, 1) : fallback;
  }
  const hasBox = len[a] > 0 && len[b] > 0;
  const box = hasBox
    ? { x: ox + (-len[a] / 2 - a0) * scale, y: oy + (b1 - len[b] / 2) * scale, w: len[a] * scale, h: len[b] * scale }
    : null;
  return { xs, ys, r, box };
}
