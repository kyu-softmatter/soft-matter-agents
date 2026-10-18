/**
 * A plain SVG x-y plot: several lines on one shared scale, measured ones solid with points,
 * theory ones dashed, and horizontal dashed lines for drawn targets. No chart library.
 */

import type { Num } from "./extract";

export const PLOT_W = 420;
export const PLOT_H = 240;
const PAD = { l: 52, r: 12, t: 12, b: 38 };

export interface Line {
  label: string;
  x: Num[];
  y: Num[];
  dashed?: boolean;
  /** CSS colour; defaults by position */
  color?: string;
}

export interface HLine {
  label: string;
  y: number;
}

export interface Scale {
  lo: number;
  hi: number;
  log: boolean;
}

export const COLORS = ["#1f6feb", "#d1242f", "#1a7f37", "#8250df", "#bf8700", "#0a7ea4"];

/** The range of the finite values (positive ones on a log axis), or null when there are none. */
export function scaleOf(values: Iterable<Num>, log: boolean): Scale | null {
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
  const m = (hi - lo) * 0.04;
  return { lo: lo - m, hi: hi + m, log };
}

function place(v: Num, s: Scale, from: number, to: number): number | null {
  if (v == null || !Number.isFinite(v) || (s.log && v <= 0)) return null;
  const u = s.log ? Math.log10(v) : v;
  return from + ((u - s.lo) / (s.hi - s.lo)) * (to - from);
}

/** About five round tick values inside the scale (decades on a log axis). */
export function ticks(s: Scale): number[] {
  if (s.log) {
    const out: number[] = [];
    for (let e = Math.ceil(s.lo); e <= Math.floor(s.hi); e++) out.push(10 ** e);
    return out.length >= 2 ? out : [10 ** s.lo, 10 ** s.hi];
  }
  const raw = (s.hi - s.lo) / 5;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((k) => k * mag).find((k) => k >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(s.lo / step) * step; v <= s.hi + step * 1e-9; v += step) out.push(Math.abs(v) < step * 1e-9 ? 0 : v);
  return out;
}

export function fmt(v: number): string {
  if (v === 0) return "0";
  const a = Math.abs(v);
  if (a >= 1e4 || a < 1e-3) return v.toExponential(1);
  return Number(v.toPrecision(3)).toString();
}

export function Plot({ lines, hlines = [], xLabel, yLabel, logX = false, logY = false, title }: {
  lines: Line[];
  hlines?: HLine[];
  xLabel: string;
  yLabel: string;
  logX?: boolean;
  logY?: boolean;
  title?: string;
}) {
  const sx = scaleOf(lines.flatMap((l) => l.x), logX);
  const sy = scaleOf([...lines.flatMap((l) => l.y), ...hlines.map((h) => h.y)], logY);
  const x0 = PAD.l;
  const x1 = PLOT_W - PAD.r;
  const y0 = PLOT_H - PAD.b;
  const y1 = PAD.t;
  return (
    <figure className="res-plot">
      {title ? <figcaption>{title}</figcaption> : null}
      {sx === null || sy === null ? (
        <p className="res-empty">No values to draw{logX || logY ? " (a log axis drops values ≤ 0)" : ""}.</p>
      ) : (
        <svg viewBox={`0 0 ${PLOT_W} ${PLOT_H}`} role="img" aria-label={title ?? `${yLabel} vs ${xLabel}`}>
          <rect x={x0} y={y1} width={x1 - x0} height={y0 - y1} className="res-frame" />
          {ticks(sx).map((t) => {
            const px = place(t, sx, x0, x1);
            return px === null ? null : (
              <g key={`x${t}`}>
                <line x1={px} x2={px} y1={y0} y2={y1} className="res-gridline" />
                <text x={px} y={y0 + 14} textAnchor="middle" className="res-tick">{fmt(t)}</text>
              </g>
            );
          })}
          {ticks(sy).map((t) => {
            const py = place(t, sy, y0, y1);
            return py === null ? null : (
              <g key={`y${t}`}>
                <line x1={x0} x2={x1} y1={py} y2={py} className="res-gridline" />
                <text x={x0 - 4} y={py + 3} textAnchor="end" className="res-tick">{fmt(t)}</text>
              </g>
            );
          })}
          <text x={(x0 + x1) / 2} y={PLOT_H - 6} textAnchor="middle" className="res-axis">{xLabel}{logX ? " (log)" : ""}</text>
          <text x={12} y={(y0 + y1) / 2} textAnchor="middle" className="res-axis"
            transform={`rotate(-90 12 ${(y0 + y1) / 2})`}>{yLabel}{logY ? " (log)" : ""}</text>
          {hlines.map((h) => {
            const py = place(h.y, sy, y0, y1);
            return py === null ? null : (
              <g key={`h${h.label}`} data-testid="target-line">
                <line x1={x0} x2={x1} y1={py} y2={py} className="res-target" />
                <text x={x1 - 2} y={py - 3} textAnchor="end" className="res-tick">{h.label}</text>
              </g>
            );
          })}
          {lines.map((l, i) => {
            const color = l.color ?? COLORS[i % COLORS.length];
            const pts: [number, number][] = [];
            const parts: string[] = [];
            let pen = false;
            for (let k = 0; k < Math.min(l.x.length, l.y.length); k++) {
              const px = place(l.x[k], sx, x0, x1);
              const py = place(l.y[k], sy, y0, y1);
              if (px === null || py === null) {
                pen = false;
                continue;
              }
              parts.push(`${pen ? "L" : "M"}${px.toFixed(1)},${py.toFixed(1)}`);
              pts.push([px, py]);
              pen = true;
            }
            return (
              <g key={l.label} data-testid={l.dashed ? "theory-line" : "data-line"}>
                <path d={parts.join(" ")} fill="none" stroke={color} strokeWidth={1.6}
                  strokeDasharray={l.dashed ? "6 4" : undefined} />
                {l.dashed ? null : pts.map(([px, py], k) => <circle key={k} cx={px} cy={py} r={2} fill={color} />)}
              </g>
            );
          })}
        </svg>
      )}
      <ul className="res-legend">
        {lines.map((l, i) => (
          <li key={l.label}>
            <svg width="22" height="8" aria-hidden="true">
              <line x1="0" x2="22" y1="4" y2="4" stroke={l.color ?? COLORS[i % COLORS.length]} strokeWidth={2}
                strokeDasharray={l.dashed ? "5 3" : undefined} />
            </svg>
            {l.label}
          </li>
        ))}
        {hlines.map((h) => <li key={`h${h.label}`}><span className="res-legend-target" /> {h.label}</li>)}
      </ul>
    </figure>
  );
}
