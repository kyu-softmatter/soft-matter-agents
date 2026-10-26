/**
 * A piezo move as an `operation` plan draft (console card 015; the person's choice, show / draft / stop).
 * The person writes it, the server checks it against plan.schema.json and the person's range, and it is
 * shown and saved nowhere. Nothing on this screen moves the stage: a move happens when a signed plan runs.
 */

import { useState } from "react";

import type { DraftIn } from "./api";
import { DraftError, DraftView, NumberField, num, useDraft } from "./draft";

const ROLES = ["verify_mapping", "direction_finding", "approach", "return"] as const;
const STARTS = ["centre", "minimum", "maximum"] as const;

export function PiezoDraft() {
  const { draft, error, busy, make } = useDraft();
  const [axis, setAxis] = useState<"x" | "y" | "z">("x");
  const [move, setMove] = useState<"step" | "sine">("step");
  const [role, setRole] = useState<(typeof ROLES)[number]>("verify_mapping");
  const [f, setF] = useState<Record<string, string>>({});
  const set = (k: string) => (v: string) => setF((old) => ({ ...old, [k]: v }));
  const val = (k: string) => f[k] ?? "";
  const [start, setStart] = useState<(typeof STARTS)[number]>("centre");

  const body = (): DraftIn =>
    move === "step"
      ? { kind: "piezo", axis, move, target_um: num(val("target")), role, return_um: num(val("back")), tolerance_um: num(val("tol")) }
      : {
          kind: "piezo", axis, move, centre_um: num(val("centre")), amplitude_um: num(val("amp")), period_s: num(val("period")),
          cycles: num(val("cycles")), points_per_period: num(val("ppp")), start, tolerance_um: num(val("tol")),
        };

  return (
    <div role="group" aria-label="Draft a piezo move" className="inst-part-draft">
      <strong>Draft a piezo move</strong>
      <p className="console-muted">
        A move is a plan draft: you sign it with your password and it runs as a plan. Nothing here moves the stage.
      </p>
      <div className="inst-form">
        <label className="inst-field">
          Axis
          <select value={axis} onChange={(e) => setAxis(e.target.value as typeof axis)}>
            <option value="x">x</option><option value="y">y</option><option value="z">z</option>
          </select>
        </label>
        <label className="inst-field">
          Move
          <select value={move} onChange={(e) => setMove(e.target.value as typeof move)}>
            <option value="step">step</option><option value="sine">sine</option>
          </select>
        </label>
        {move === "step" ? (
          <>
            <NumberField label="Target (µm)" value={val("target")} onChange={set("target")} />
            <label className="inst-field">
              Role
              <select value={role} onChange={(e) => setRole(e.target.value as typeof role)}>
                {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </label>
            <NumberField label="Return to (µm)" value={val("back")} onChange={set("back")} />
          </>
        ) : (
          <>
            <NumberField label="Centre (µm)" value={val("centre")} onChange={set("centre")} />
            <NumberField label="Amplitude (µm)" value={val("amp")} onChange={set("amp")} />
            <NumberField label="Period (s)" value={val("period")} onChange={set("period")} />
            <NumberField label="Cycles" value={val("cycles")} onChange={set("cycles")} />
            <NumberField label="Points per period" value={val("ppp")} onChange={set("ppp")} />
            <label className="inst-field">
              Starts at
              <select value={start} onChange={(e) => setStart(e.target.value as typeof start)}>
                {STARTS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
          </>
        )}
        <NumberField label="Read-back tolerance (µm)" value={val("tol")} onChange={set("tol")} />
        <button type="button" disabled={busy} onClick={() => void make(body())}>Draft piezo move</button>
      </div>
      <DraftError error={error} />
      {draft !== undefined && <DraftView draft={draft} />}
    </div>
  );
}
