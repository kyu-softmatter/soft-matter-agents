import type { components } from "../../api/schema";

export type FocusDz = components["schemas"]["FocusDz"];

/** The gauge's half range, depths of field (scripts/live_focus.py `Gauge`, the 9/30 run). */
export const GAUGE_DOF = 10;

const W = 150;
const H = 300;
const X = W / 2 - 10; // the bar, left of centre: the labels go on its right
const TOP = 28;
const BOT = H - 28;
const TICKS = Array.from({ length: 11 }, (_, i) => 10 - 2 * i); // +10, +8, ... -10
const LABELS = [10, 5, 0, -5, -10];

/** Bar height of a score: +10 at the top, -10 at the bottom; off-scale values sit on the end. */
export function gaugeY(s: number): number {
  const c = Math.max(-GAUGE_DOF, Math.min(GAUGE_DOF, s));
  return TOP + ((GAUGE_DOF - c) / (2 * GAUGE_DOF)) * (BOT - TOP);
}

export const fmtDz = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}`;

const SOURCE: Record<FocusDz["source"], string> = { mock_truth: "mock truth", model: "model" };

/**
 * The vertical -10..+10 focus gauge of the 2026-09-30 run (`Gauge` in scripts/live_focus.py):
 * dz = stage - best focus in depths of field, 0 = in focus, +10 at the top ("above") and -10 at
 * the bottom ("below"). Green band = ±1 DoF; the marker is the reading, the bar beside it its
 * sigma. `reading` null: nothing to show (no head loaded, or no frame yet). Display only.
 */
export function FocusGauge({ reading, empty = "No DINO head loaded (--head)" }: { reading: FocusDz | null; empty?: string }) {
  const dz = reading?.dz_dof ?? null;
  const sigma = reading?.sigma_dof ?? null;
  const y = dz === null ? null : gaugeY(dz);
  const off = dz !== null && Math.abs(dz) > GAUGE_DOF;
  const note = reading ? reading.note : empty;
  return (
    <div className="focus-gauge">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Focus gauge, depths of field">
        <rect x={X - 16} y={gaugeY(1)} width={32} height={gaugeY(-1) - gaugeY(1)} className="focus-gauge-band" />
        <line x1={X} x2={X} y1={TOP} y2={BOT} className="focus-gauge-track" />
        {TICKS.map((s) => {
          const major = s % 10 === 0;
          const len = major ? 10 : 5;
          return (
            <line
              key={s}
              x1={X - len}
              x2={X + len}
              y1={gaugeY(s)}
              y2={gaugeY(s)}
              className={s === 0 ? "focus-gauge-zero" : "focus-gauge-tick"}
            />
          );
        })}
        {LABELS.map((s) => (
          <text
            key={s}
            x={X + 16}
            y={gaugeY(s)}
            dominantBaseline="middle"
            className={s === 0 ? "focus-gauge-label focus-gauge-label-zero" : "focus-gauge-label"}
          >
            {s === 0 ? "0 focus" : `${s > 0 ? "+" : "−"}${Math.abs(s)}`}
          </text>
        ))}
        <text x={X} y={TOP - 12} textAnchor="middle" className="focus-gauge-label">
          above
        </text>
        <text x={X} y={BOT + 18} textAnchor="middle" className="focus-gauge-label">
          below
        </text>
        {dz !== null && sigma !== null && (
          <line x1={X - 18} x2={X - 18} y1={gaugeY(dz + sigma)} y2={gaugeY(dz - sigma)} className="focus-gauge-sigma" data-testid="gauge-sigma" />
        )}
        {y !== null && (
          <polygon
            points={`${X - 26},${y - 9} ${X - 26},${y + 9} ${X - 8},${y}`}
            className="focus-gauge-marker"
            data-testid="gauge-marker"
          />
        )}
      </svg>
      <div className="focus-gauge-read">
        <strong data-testid="gauge-value">{dz === null ? "--" : fmtDz(dz)}</strong>
        <span className="muted">depths of field{off ? ", off scale" : ""}</span>
        {reading && <span className="focus-gauge-source">{SOURCE[reading.source]}</span>}
        {note && (
          <span className="muted" data-testid="gauge-note">
            {note}
          </span>
        )}
      </div>
    </div>
  );
}
