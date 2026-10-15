import type { ReactNode } from "react";

/**
 * Small SVG charts for the run's log columns and observables (PLAN 2절 F6.4). The numbers drawn
 * are the numbers in the records; only their position on the page is computed.
 */

export const CHART_W = 320;
export const CHART_H = 170;
const PAD = { l: 8, r: 8, t: 8, b: 8 };

export interface Scale {
  lo: number;
  hi: number;
  log: boolean;
}

/** The range of the finite values (positive ones on a log axis), or null when there are none. */
export function scaleOf(values: (number | null)[], log: boolean): Scale | null {
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values) {
    if (v == null || !Number.isFinite(v) || (log && v <= 0)) continue;
    const u = log ? Math.log10(v) : v;
    if (u < lo) lo = u;
    if (u > hi) hi = u;
  }
  if (!Number.isFinite(lo)) return null;
  if (hi === lo) {
    const d = Math.abs(lo) * 0.05 || 1;
    return { lo: lo - d, hi: hi + d, log };
  }
  return { lo, hi, log };
}

function place(v: number | null, s: Scale, from: number, to: number): number | null {
  if (v == null || !Number.isFinite(v) || (s.log && v <= 0)) return null;
  const u = s.log ? Math.log10(v) : v;
  return from + ((u - s.lo) / (s.hi - s.lo)) * (to - from);
}

/** SVG path data for a line; a missing value breaks the line. */
export function linePath(xs: (number | null)[], ys: (number | null)[], sx: Scale, sy: Scale): string {
  const parts: string[] = [];
  let pen = false;
  for (let i = 0; i < Math.min(xs.length, ys.length); i++) {
    const x = place(xs[i], sx, PAD.l, CHART_W - PAD.r);
    const y = place(ys[i], sy, CHART_H - PAD.b, PAD.t);
    if (x == null || y == null) {
      pen = false;
      continue;
    }
    parts.push(`${pen ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`);
    pen = true;
  }
  return parts.join(" ");
}

export function fmt(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "–";
  if (v === 0) return "0";
  const a = Math.abs(v);
  return a >= 1e5 || a < 1e-3 ? v.toExponential(3) : Number(v.toPrecision(4)).toString();
}

function shown(s: Scale, end: "lo" | "hi"): string {
  const u = s[end];
  return fmt(s.log ? 10 ** u : u);
}

function ChartFrame({ title, sx, sy, xLabel, children }: { title: string; sx: Scale; sy: Scale; xLabel: string; children: ReactNode }) {
  return (
    <figure className="sim-chart">
      <figcaption>{title}</figcaption>
      <svg viewBox={`0 0 ${CHART_W} ${CHART_H}`} width={CHART_W} height={CHART_H} role="img" aria-label={title}>
        <rect x={PAD.l} y={PAD.t} width={CHART_W - PAD.l - PAD.r} height={CHART_H - PAD.t - PAD.b} className="sim-chart-area" />
        {children}
      </svg>
      <div className="sim-chart-axes">
        <span>
          y {shown(sy, "lo")} … {shown(sy, "hi")}
          {sy.log ? " (log)" : ""}
        </span>
        <span>
          {xLabel} {shown(sx, "lo")} … {shown(sx, "hi")}
          {sx.log ? " (log)" : ""}
        </span>
      </div>
    </figure>
  );
}

export function LineChart({
  title,
  x,
  y,
  xLabel = "x",
  logX = false,
  logY = false,
}: {
  title: string;
  x: (number | null)[];
  y: (number | null)[];
  xLabel?: string;
  logX?: boolean;
  logY?: boolean;
}) {
  const sx = scaleOf(x, logX);
  const sy = scaleOf(y, logY);
  if (!sx || !sy) {
    return (
      <figure className="sim-chart">
        <figcaption>{title}</figcaption>
        <p className="muted">no values to draw</p>
      </figure>
    );
  }
  return (
    <ChartFrame title={title} sx={sx} sy={sy} xLabel={xLabel}>
      <path d={linePath(x, y, sx, sy)} className="sim-chart-line" />
    </ChartFrame>
  );
}

/** Bars between bin edges: `edges.length === counts.length + 1`. */
export function HistogramChart({ title, edges, counts, xLabel = "x" }: { title: string; edges: (number | null)[]; counts: (number | null)[]; xLabel?: string }) {
  const sx = scaleOf(edges, false);
  const sy = scaleOf([0, ...counts], false);
  if (!sx || !sy || edges.length !== counts.length + 1) {
    return (
      <figure className="sim-chart">
        <figcaption>{title}</figcaption>
        <p className="muted">no values to draw</p>
      </figure>
    );
  }
  const bars = counts.map((c, i) => {
    const x0 = place(edges[i], sx, PAD.l, CHART_W - PAD.r);
    const x1 = place(edges[i + 1], sx, PAD.l, CHART_W - PAD.r);
    const y = place(c, sy, CHART_H - PAD.b, PAD.t);
    const y0 = place(0, sy, CHART_H - PAD.b, PAD.t);
    if (x0 == null || x1 == null || y == null || y0 == null) return null;
    return <rect key={i} x={Math.min(x0, x1)} y={Math.min(y, y0)} width={Math.abs(x1 - x0)} height={Math.abs(y0 - y)} className="sim-chart-bar" />;
  });
  return (
    <ChartFrame title={title} sx={sx} sy={sy} xLabel={xLabel}>
      {bars}
    </ChartFrame>
  );
}
