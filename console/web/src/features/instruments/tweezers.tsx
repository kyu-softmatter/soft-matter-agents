/**
 * Tweezers (canvas `PTweezers`, console card 012): the laser row, the traps and their strengths and the
 * t-x, t-y and x-y plots, all from the latest run's events and all labelled "sent" (the tweezers report
 * nothing back), and a pattern as a `trap_steps` plan draft. No click-to-hold and no dragging.
 */

import { useState } from "react";

import { shortTime } from "../questions/ui";
import type { LatestRun, LimitsOut } from "./api";
import { DraftError, DraftView, NumberField, num, useDraft } from "./draft";
import { asOf, RunBanner } from "./follow";
import { Plot } from "./plot";
import { LaserRow, StrengthSent } from "./status";

type Bound = { value: number; unit: string | null } | null | undefined;
type Span = { min: Bound; max: Bound } | null | undefined;

const MISSING = "no limit in your safety file, so refused";

function unitText(u: string | null | undefined): string {
  return u === "um" ? "µm" : (u ?? "");
}

function spanText(s: Span): string {
  if (!s || !s.min || !s.max) return MISSING;
  const unit = unitText(s.max.unit ?? s.min.unit);
  return `${s.min.value} to ${s.max.value}${unit === "" ? "" : ` ${unit}`} (from your safety file)`;
}

/** What a pattern is held to, as the person's safety file states it; a limit the file lacks is a refusal. */
export function PatternAllowed({ limits }: { limits: LimitsOut }) {
  const t = limits.tweezers as { positions?: Record<string, Span>; step_max?: Bound; strength?: Span };
  const step = t.step_max;
  return (
    <div role="group" aria-label="What a pattern is allowed" className="inst-allowed">
      <strong>What a pattern is allowed</strong>
      <ul>
        {(["40x", "60x", "100x"] as const).map((o) => <li key={o}>{o}: {spanText(t.positions?.[o])}</li>)}
        <li>
          {step ? `at most ${step.value} ${unitText(step.unit)} per step (from your safety file)` : `per step: ${MISSING}`}
        </li>
        <li>Strength: {spanText(t.strength)}</li>
        <li>Trap count and flicker rate are refused until a limit exists.</li>
      </ul>
      {limits.state !== "present" && (
        <p className="console-error">There is no readable safety file in this tree, so nothing is allowed.</p>
      )}
    </div>
  );
}

function Plots({ run }: { run: LatestRun }) {
  const series = run.trap_series.filter((p) => p.t_s !== null && p.x_um !== null && p.y_um !== null);
  if (series.length === 0) return null;
  const t = (p: (typeof series)[number]) => p.t_s as number;
  const x = (p: (typeof series)[number]) => p.x_um as number;
  const y = (p: (typeof series)[number]) => p.y_um as number;
  return (
    <div className="inst-plots">
      <Plot label="t-x (sent)" points={series.map((p) => ({ x: t(p), y: x(p) }))} />
      <Plot label="t-y (sent)" points={series.map((p) => ({ x: t(p), y: y(p) }))} />
      <Plot label="x-y (sent)" points={series.map((p) => ({ x: x(p), y: y(p) }))} />
    </div>
  );
}

const onText = (on: boolean | null) => (on === null ? "unknown" : on ? "on" : "off");
const cell = (v: number | null) => (v === null ? "unknown" : String(v));

export function Tweezers({ run, limits }: { run: LatestRun; limits: LimitsOut }) {
  const { draft, error, busy, make } = useDraft();
  const [pattern, setPattern] = useState<"line" | "circle" | "grid">("line");
  const [n, setN] = useState("3");
  const [spacing, setSpacing] = useState("5");
  const [strength, setStrength] = useState("0.3");
  const [objective, setObjective] = useState<"40x" | "60x" | "100x">("100x");
  return (
    <section aria-label="Tweezers" className="inst-tweezers">
      <RunBanner run={run} />
      <LaserRow />
      <StrengthSent run={run} />
      {run.state === "ok" && run.traps.length > 0 ? (
        <>
          {run.running ? (
            <p className="console-muted">
              What was sent, from {run.run_id}{run.started_at ? `, started ${shortTime(run.started_at)}` : ""}. The tweezers report nothing back.
            </p>
          ) : (
            <p className="console-muted">{asOf(run)}</p>
          )}
          <table className="console-table" aria-label="Traps (sent)">
            <thead><tr><th>Trap</th><th>x (µm)</th><th>y (µm)</th><th>Strength</th><th>State</th></tr></thead>
            <tbody>
              {run.traps.map((t) => (
                <tr key={t.trap}><td>{t.trap}</td><td>{cell(t.x_um)}</td><td>{cell(t.y_um)}</td><td>{cell(t.strength)}</td><td>{onText(t.on)}</td></tr>
              ))}
            </tbody>
          </table>
          <Plots run={run} />
        </>
      ) : (
        <p>no trap sent</p>
      )}
      <div className="inst-form" role="group" aria-label="Draft a pattern">
        <label className="inst-field">
          Pattern
          <select value={pattern} onChange={(e) => setPattern(e.target.value as typeof pattern)}>
            <option value="line">Line</option><option value="circle">Circle</option><option value="grid">Grid</option>
          </select>
        </label>
        <NumberField label="Number of traps" value={n} onChange={setN} />
        <NumberField label="Spacing (µm)" value={spacing} onChange={setSpacing} />
        <NumberField label="Strength (0 to 1)" value={strength} onChange={setStrength} />
        <label className="inst-field">
          Objective
          <select value={objective} onChange={(e) => setObjective(e.target.value as typeof objective)}>
            <option value="40x">40x</option><option value="60x">60x</option><option value="100x">100x</option>
          </select>
        </label>
        <button
          type="button"
          disabled={busy}
          onClick={() => void make({ kind: "trap_steps", pattern, n: num(n), spacing_um: num(spacing), strength: num(strength), objective })}
        >
          Draft trap pattern
        </button>
      </div>
      <PatternAllowed limits={limits} />
      <DraftError error={error} />
      {draft !== undefined && <DraftView draft={draft} />}
    </section>
  );
}
