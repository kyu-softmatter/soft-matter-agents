// Shape generators for the pattern designer: each returns timed points [t_s, x_um, y_um, z_um]
// that start at t = 0 and end at `duration_s`. z goes linearly from z0 to z1 over the shape,
// so the same shapes serve the XYZ piezo (a helix is a circle with a z ramp) and the traps.

import type { Pt } from "./model";

export type ShapeKind = "line" | "circle" | "raster" | "spiral" | "hold";

export interface ShapeParams {
  kind: ShapeKind;
  duration_s: number;
  /** points per second of the generated track (the run interpolates between them) */
  rate_hz: number;
  cx: number;
  cy: number;
  z0: number;
  z1: number;
  /** line: the end point */
  x1: number;
  y1: number;
  /** circle / spiral: radius; raster: width */
  r: number;
  /** raster: height */
  h: number;
  /** circle / spiral: turns; raster: lines */
  n: number;
}

export const DEFAULT_SHAPE: ShapeParams = {
  kind: "circle",
  duration_s: 10,
  rate_hz: 20,
  cx: 0,
  cy: 0,
  z0: 0,
  z1: 0,
  x1: 10,
  y1: 0,
  r: 10,
  h: 10,
  n: 1,
};

const round = (v: number) => Math.round(v * 1000) / 1000;

/** `f` in 0..1 -> [x, y] for each shape */
function pathOf(p: ShapeParams): (f: number) => [number, number] {
  switch (p.kind) {
    case "line":
      return (f) => [p.cx + f * (p.x1 - p.cx), p.cy + f * (p.y1 - p.cy)];
    case "circle":
      return (f) => {
        const a = 2 * Math.PI * p.n * f;
        return [p.cx + p.r * Math.cos(a), p.cy + p.r * Math.sin(a)];
      };
    case "spiral":
      return (f) => {
        const a = 2 * Math.PI * p.n * f;
        return [p.cx + p.r * f * Math.cos(a), p.cy + p.r * f * Math.sin(a)];
      };
    case "raster": {
      // boustrophedon: n lines across the width, stepping down the height
      const lines = Math.max(1, Math.round(p.n));
      return (f) => {
        const u = Math.min(f * lines, lines - 1e-9);
        const i = Math.floor(u);
        const along = u - i;
        const x = p.cx - p.r / 2 + (i % 2 === 0 ? along : 1 - along) * p.r;
        const y = lines === 1 ? p.cy : p.cy - p.h / 2 + (i / (lines - 1)) * p.h;
        return [x, y];
      };
    }
    case "hold":
      return () => [p.cx, p.cy];
  }
}

export function generate(p: ShapeParams): Pt[] {
  const d = Math.max(p.duration_s, 0.001);
  const steps = Math.max(1, Math.min(20_000 - 1, Math.round(d * Math.max(p.rate_hz, 0.1))));
  const at = pathOf(p);
  const out: Pt[] = [];
  for (let i = 0; i <= steps; i++) {
    const f = i / steps;
    const [x, y] = at(f);
    out.push([round(f * d), round(x), round(y), round(p.z0 + f * (p.z1 - p.z0))]);
  }
  return out;
}

/** Points as CSV lines "t, x, y, z" for hand edits, and back. */
export function toCsv(points: number[][]): string {
  return points.map((p) => p.join(", ")).join("\n");
}

export function fromCsv(text: string): Pt[] {
  return text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith("#"))
    .map((l) => {
      const v = l.split(/[,\s]+/).map(Number);
      return [v[0] ?? NaN, v[1] ?? 0, v[2] ?? 0, v[3] ?? 0] as Pt;
    });
}
