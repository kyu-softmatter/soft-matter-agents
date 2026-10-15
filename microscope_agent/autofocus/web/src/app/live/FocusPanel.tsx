import { useState } from "react";

import { type FocusDz, FocusGauge } from "./FocusGauge";
import type { CamFrame } from "./LiveView";

/** One received frame as the focus panel keeps it. */
export interface FocusSample {
  /** frame time, s (epoch) */
  t: number;
  camera: string;
  /** the server's live focus score (`focus_metric` on the binned frame), null when not computed */
  score: number | null;
  metric: string | null;
  /** ZDrive encoder read when the frame was popped, um */
  stageZ: number | null;
  /** piezo z read at the same moment, um; null with no piezo */
  piezoZ: number | null;
  /** the signed gauge reading (mock truth or a DINO head), null when the engine has none */
  dz: FocusDz | null;
}

/** How much history the Z graph keeps and draws. */
export const HISTORY_S = 60;
const MAX_SAMPLES = 2000;

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

export function sampleOf(frame: CamFrame): FocusSample {
  const m = frame.meta.meta ?? {};
  return {
    t: frame.meta.t,
    camera: frame.camera,
    score: num(frame.meta.focus_score),
    metric: frame.meta.focus_metric ?? null,
    stageZ: num(m.z_um),
    piezoZ: num(m.piezo_z_um),
    dz: frame.meta.focus_dz ?? null,
  };
}

/** The focus height: stage z + piezo z (no piezo counts as 0); null without a stage z. */
export function heightOf(s: FocusSample): number | null {
  return s.stageZ === null ? null : s.stageZ + (s.piezoZ ?? 0);
}

/** Append `s`, keeping the last `HISTORY_S` seconds (by frame time) and at most `MAX_SAMPLES`. */
export function pushSample(list: FocusSample[], s: FocusSample): FocusSample[] {
  const from = s.t - HISTORY_S;
  const kept = list.filter((x) => x.t >= from);
  kept.push(s);
  return kept.length > MAX_SAMPLES ? kept.slice(kept.length - MAX_SAMPLES) : kept;
}

const um = (v: number | null, digits = 2) => (v === null ? "—" : `${v.toFixed(digits)} µm`);

function fmtScore(v: number | null): string {
  if (v === null) return "—";
  const a = Math.abs(v);
  return a !== 0 && (a >= 1e4 || a < 1e-3) ? v.toExponential(3) : v.toPrecision(4);
}

const W = 300;
const H = 150;
const PAD = { l: 6, r: 6, t: 8, b: 8 };

/** Total Z (stage + piezo) over the last `HISTORY_S` s, one line; a missing z breaks it. */
export function ZGraph({ samples }: { samples: FocusSample[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const pts = samples
    .map((s) => ({ s, z: heightOf(s) }))
    .sort((a, b) => a.s.t - b.s.t);
  const zs = pts.flatMap((p) => (p.z === null ? [] : [p.z]));
  if (zs.length === 0) return <p className="muted">No Z reading yet.</p>;
  const tEnd = pts[pts.length - 1].s.t;
  const tStart = tEnd - HISTORY_S;
  let lo = Math.min(...zs);
  let hi = Math.max(...zs);
  if (hi - lo < 0.1) {
    // a still stage: show ±0.05 um around it rather than magnify encoder noise
    const mid = (lo + hi) / 2;
    lo = mid - 0.05;
    hi = mid + 0.05;
  }
  const x = (t: number) => PAD.l + ((t - tStart) / HISTORY_S) * (W - PAD.l - PAD.r);
  const y = (z: number) => H - PAD.b - ((z - lo) / (hi - lo)) * (H - PAD.t - PAD.b);
  const parts: string[] = [];
  let pen = false;
  for (const p of pts) {
    if (p.z === null) {
      pen = false;
      continue;
    }
    parts.push(`${pen ? "L" : "M"}${x(p.s.t).toFixed(1)},${y(p.z).toFixed(1)}`);
    pen = true;
  }
  const near =
    hover === null
      ? null
      : pts.reduce<(typeof pts)[number] | null>(
          (best, p) => (p.z !== null && (!best || Math.abs(x(p.s.t) - hover) < Math.abs(x(best.s.t) - hover)) ? p : best),
          null,
        );
  const move = (e: React.MouseEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    if (box.width > 0) setHover(((e.clientX - box.left) / box.width) * W);
  };
  return (
    <div className="focus-graph">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="Z height over time"
        onMouseMove={move}
        onMouseLeave={() => setHover(null)}
      >
        <rect x={PAD.l} y={PAD.t} width={W - PAD.l - PAD.r} height={H - PAD.t - PAD.b} className="focus-graph-area" />
        <path d={parts.join(" ")} className="focus-graph-line" data-testid="z-line" />
        {near && near.z !== null && (
          <>
            <line x1={x(near.s.t)} x2={x(near.s.t)} y1={PAD.t} y2={H - PAD.b} className="focus-graph-cross" />
            <circle cx={x(near.s.t)} cy={y(near.z)} r={4} className="focus-graph-dot" />
          </>
        )}
      </svg>
      <div className="focus-graph-axes">
        <span>
          {hi.toFixed(2)} … {lo.toFixed(2)} µm
        </span>
        <span>last {HISTORY_S} s</span>
      </div>
      {near && near.z !== null && (
        <div className="focus-graph-tip" data-testid="z-tip">
          {(near.s.t - tEnd).toFixed(1)} s: {um(near.z)} = stage {um(near.s.stageZ)} + piezo {um(near.s.piezoZ ?? 0)}
        </div>
      )}
    </div>
  );
}

/**
 * Beside the live view: the -10..+10 Z score gauge (the newest frame that has a reading), each
 * camera's live focus score and the focus height (stage z + piezo z) of the newest frame, with
 * its last minute as a graph. Display only.
 */
export function FocusPanel({ samples }: { samples: FocusSample[] }) {
  const latest = new Map<string, FocusSample>();
  for (const s of samples) {
    const had = latest.get(s.camera);
    if (!had || s.t >= had.t) latest.set(s.camera, s);
  }
  const cams = [...latest.keys()].sort();
  const newest = samples.reduce<FocusSample | null>((a, s) => (!a || s.t >= a.t ? s : a), null);
  const metric = newest?.metric ?? null;
  const withDz = samples.reduce<FocusSample | null>((a, s) => (s.dz && (!a || s.t >= a.t) ? s : a), null);
  return (
    <aside className="focus-panel" aria-label="Focus">
      <section>
        <h3>Z score</h3>
        <FocusGauge reading={withDz?.dz ?? null} empty={newest ? undefined : "No frame yet."} />
      </section>
      <section>
        <h3>Focus score</h3>
        {cams.length === 0 && <p className="muted">No score yet.</p>}
        <div className="focus-scores">
          {cams.map((c) => (
            <div key={c} className="focus-stat">
              {(cams.length > 1 || c) && <span className="muted">{c || "camera"}</span>}
              <strong data-testid={`focus-score-${c || "camera"}`}>{fmtScore(latest.get(c)!.score)}</strong>
            </div>
          ))}
        </div>
        {metric && (
          <p className="muted" title="Computed on the binned live frame: it follows the focus, but is not the sweep score">
            {metric}, live (binned frame)
          </p>
        )}
      </section>
      <section>
        <h3>Z height</h3>
        {newest && (
          <p className="focus-z" data-testid="focus-z">
            <strong>{um(heightOf(newest))}</strong>{" "}
            <span className="muted">
              = stage {um(newest.stageZ)} + piezo {newest.piezoZ === null ? "none" : um(newest.piezoZ)}
            </span>
          </p>
        )}
        <ZGraph samples={samples} />
      </section>
    </aside>
  );
}
