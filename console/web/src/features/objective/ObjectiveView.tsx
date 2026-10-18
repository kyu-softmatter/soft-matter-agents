import { useCallback, useEffect, useMemo, useReducer, useState } from "react";

import {
  type CommandIn,
  CommandRefused,
  type EventOut,
  useClient,
  useEngineEvents,
  useEventsConnected,
  useReadOnly,
} from "../../app/client";
import { EncoderZ, FocusVerdict } from "../../app/Verdict";
import { useScreenContext } from "../../app/screenContext";
import {
  type Focus100xDefaults,
  type LensRow,
  type ObjectivePlan,
  type ObjectiveState,
  type Permission,
  type Permissions,
  permissionOf,
  readFocusDefaults,
  readLenses,
  readPermissions,
  readPlan,
  readState,
} from "./api";
import {
  type ChangeView,
  type FocusView,
  initialChange,
  initialFocus,
  type PendingConfirm,
  reduceChange,
  reduceFocus,
} from "./model";
import "./objective.css";

type Args = Record<string, unknown>;
/** the buttons a refusal can belong to */
type Action = "rotate" | "reload" | "return" | "confirm" | "focus";

function Refused({ text }: { text: string | null }) {
  return text === null ? null : (
    <span className="refusal" role="alert">
      {" "}
      {text}
    </span>
  );
}

function command(kind: CommandIn["kind"], op = "", op_id = "", args: Args = {}): CommandIn {
  return { kind, op, op_id, args }; // the server sets origin (human) and the user
}

const startChange = (args: Args) => command("start", "objective_change", "", args);
const confirm = (c: PendingConfirm, ok: boolean) => command("confirm", "", c.opId, { key: c.key, ok });

/** engine events that change what the permission check would answer (busy, awaiting return) */
const STATE_EVENTS = new Set(["started", "finished", "aborted", "error"]);

/**
 * The objective area (docs/screens/objective.md, ui-spec 7.5): objective change
 * with immersion loading, and the 100x focus sweep. All state comes from the read
 * endpoints and engine events on the shell's client; the screen never decides a
 * motion limit or a permission.
 */
export function ObjectiveView() {
  const client = useClient();
  const { readOnly, why } = useReadOnly();
  const connected = useEventsConnected();
  const [state, setState] = useState<ObjectiveState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [lenses, setLenses] = useState<LensRow[]>([]);
  const [change, dispatchChange] = useReducer(reduceChange, undefined, initialChange);
  const [focus, dispatchFocus] = useReducer(reduceFocus, undefined, initialFocus);
  // the last refusal, shown next to the action that caused it; no global state changes here
  const [refusal, setRefusal] = useState<{ action: Action; text: string } | null>(null);
  // undefined: first check loading; null: it could not be read (every control off, progress stays)
  const [perms, setPerms] = useState<Permissions | null | undefined>(undefined);
  const [reread, setReread] = useState(0);

  // (re)read the screen state on mount, and again whenever the event socket comes back:
  // events in the gap are lost (web/README "Talking to the server")
  useEffect(() => {
    if (connected) setReread((n) => n + 1);
  }, [connected]);

  useEffect(() => {
    let live = true;
    readState(client).then(
      (s) => live && (setState(s), setLoadError(null)),
      (e) => live && setLoadError(e instanceof CommandRefused ? e.detail : String(e)),
    );
    readLenses(client).then(
      (l) => live && setLenses(l),
      () => live && setLenses([]),
    );
    readPermissions(client).then(
      (p) => live && setPerms(p),
      () => live && setPerms(null),
    );
    return () => {
      live = false;
    };
  }, [client, reread]);

  const onEvent = useCallback((ev: EventOut) => {
    dispatchChange(ev);
    dispatchFocus(ev);
    if (STATE_EVENTS.has(ev.kind)) setReread((n) => n + 1);
  }, []);
  useEngineEvents(onEvent);

  const send = useCallback(
    async (action: Action, cmd: CommandIn) => {
      try {
        await client.command(cmd);
        setRefusal(null);
      } catch (e) {
        // a remote_view 403 also switches the shell to read-only (client.tsx); any other refusal is
        // this action's reason only
        setRefusal({ action, text: e instanceof CommandRefused ? e.detail : String(e) });
      }
    },
    [client],
  );
  const refusedFor = (action: Action): string | null => (refusal?.action === action ? refusal.text : null);

  const details = useMemo(
    () => ({
      objective: state?.label,
      op_id: change.opId ?? focus.opId ?? undefined,
      step: currentStep(change),
    }),
    [state?.label, change, focus.opId],
  );
  useScreenContext(details);

  if (state === null) {
    return <p className="muted">{loadError ? `Objective state unavailable: ${loadError}` : "Loading objective…"}</p>;
  }
  // a remote screen never sends: the shell's read-only flag wins over any permission answer (D2)
  const perm = (op: string): Permission =>
    readOnly ? { allowed: false, reason: `Read-only: ${why ?? "remote view"}` } : permissionOf(perms, op);
  const changePerm = perm("objective_change");
  const awaiting = state.awaiting_return !== null || change.ended?.state === "awaiting_return";
  const awaitingReason = awaiting ? "Return to the sample position first" : null;

  return (
    <div className="objective">
      {!changePerm.allowed && changePerm.reason && (
        <p className="readonly" role="status">
          {changePerm.reason}
        </p>
      )}
      <CurrentPanel state={state} zUm={change.zUm ?? state.z_um} />
      {awaiting && <ReturnBanner perm={changePerm} refused={refusedFor("return")}
                                 onReturn={() => send("return", startChange({ resume: true }))} />}
      <ChangePanel lenses={lenses} perm={changePerm} disabledBy={awaitingReason}
                   refusedRotate={refusedFor("rotate")} refusedReload={refusedFor("reload")}
                   onRotate={(target, escape) => send("rotate", startChange({ target_state: target, escape }))}
                   onReload={() => send("reload", startChange({ reload: true }))} />
      <StepsPanel view={change} confirmPerm={perm("confirm")} remote={readOnly} refused={refusedFor("confirm")}
                  onLoadingDone={(c) => send("confirm", confirm(c, true))}
                  onAnswer={(c, ok) => send("confirm", confirm(c, ok))} />
      <Focus100xPanel perm={perm("focus_100x")} confirmPerm={perm("confirm")} view={focus} disabledBy={awaitingReason}
                      refused={refusedFor("focus")}
                      onStart={(args) => send("focus", command("start", "focus_100x", "", args))}
                      onAnswer={(c, ok) => send("confirm", confirm(c, ok))} />
    </div>
  );
}

function currentStep(v: ChangeView): number | undefined {
  for (const s of [7, 6, 5, 4, 3, 2, 1]) if (v.steps[s].status === "running") return s;
  return undefined;
}

function CurrentPanel({ state, zUm }: { state: ObjectiveState; zUm: number | null }) {
  return (
    <section aria-label="Current objective">
      <h3>Current</h3>
      <p>
        <strong data-testid="current-label">{state.label}</strong> · {state.pixel_um} µm/px ·{" "}
        <EncoderZ readbackUm={zUm} /> · PFS {state.pfs.enabled ? "on" : "off"}, {state.pfs.in_range}
      </p>
    </section>
  );
}

function ReturnBanner({ perm, refused, onReturn }: { perm: Permission; refused: string | null; onReturn: () => void }) {
  return (
    <section className="banner" role="alert" aria-label="Awaiting return">
      <p>Objective change interrupted: return to the sample position.</p>
      <button type="button" disabled={!perm.allowed} onClick={onReturn}>
        Return to sample position
      </button>
      {!perm.allowed && perm.reason && <span className="reason"> {perm.reason}</span>}
      <Refused text={refused} />
    </section>
  );
}

/**
 * Default for the Y step-out: the plan's escape.default (T-029). Before the plan
 * arrives, on for an immersion lens and off between dry lenses (ui-spec 7.5).
 */
export function escapeDefault(plan: ObjectivePlan | null, lens: LensRow | null): boolean {
  if (plan !== null) return plan.escape.default;
  return lens !== null && lens.immersion !== "dry";
}

/**
 * The engine's refusal of the step-out, or null. It comes in the plan payload
 * (T-029: plan(cmd).escape, from guards.step_out_target, the stage Y limit).
 */
export function escapeRefusal(plan: ObjectivePlan | null): string | null {
  if (plan === null || plan.escape.allowed) return null;
  return plan.escape.reason ?? "step-out refused";
}

function ChangePanel({
  lenses,
  perm,
  disabledBy,
  refusedRotate,
  refusedReload,
  onRotate,
  onReload,
}: {
  lenses: LensRow[];
  perm: Permission;
  disabledBy: string | null;
  refusedRotate: string | null;
  refusedReload: string | null;
  onRotate: (target: number, escape: boolean) => void;
  onReload: () => void;
}) {
  const client = useClient();
  const [target, setTarget] = useState<number | null>(null);
  const [plan, setPlan] = useState<ObjectivePlan | null>(null);
  // null until the operator ticks or unticks it; then their choice wins
  const [escapeChoice, setEscapeChoice] = useState<boolean | null>(null);
  const firstSelectable = lenses.find((l) => l.selectable)?.nosepiece_state ?? null;
  const chosen = target ?? firstSelectable;
  const lens = lenses.find((l) => l.nosepiece_state === chosen) ?? null;
  const wantEscape = escapeChoice ?? escapeDefault(plan, lens);

  useEffect(() => {
    if (chosen === null) return;
    let live = true;
    readPlan(client, chosen, wantEscape).then(
      (p) => live && setPlan(p),
      () => live && setPlan(null),
    );
    return () => {
      live = false;
    };
  }, [client, chosen, wantEscape]);
  // the step-out runs only when wanted and the engine does not refuse it
  const refusal = escapeRefusal(plan);
  const escape = wantEscape && plan !== null && refusal === null;

  const blocked = !perm.allowed ? (perm.reason ?? "not allowed") : disabledBy ?? plan?.refusal ?? null;
  return (
    <section aria-label="Change objective">
      <h3>Change objective</h3>
      <ul className="lenses">
        {lenses.map((l) => (
          <li key={l.nosepiece_state}>
            <label>
              <input type="radio" name="lens" value={l.nosepiece_state} disabled={!l.selectable}
                     checked={chosen === l.nosepiece_state}
                     onChange={() => {
                       setTarget(l.nosepiece_state);
                       setEscapeChoice(null); // a new target starts from its own default
                     }} />
              {l.label} ({l.immersion}, WD {l.working_distance_um === null ? "not set" : `${l.working_distance_um} µm`})
            </label>
            {l.disabled_reason && <span className="reason"> {l.disabled_reason}</span>}
          </li>
        ))}
      </ul>
      {plan && (
        <p data-testid="escape">
          <label>
            <input type="checkbox" checked={escape} disabled={refusal !== null || !perm.allowed}
                   onChange={(e) => setEscapeChoice(e.target.checked)} />{" "}
            Step out {plan.escape.sign} {plan.escape.dy_um / 1000} mm for loading
          </label>{" "}
          <span className="muted">({plan.escape.mark})</span>
          {refusal !== null && <span className="reason" data-testid="escape-reason"> {refusal}</span>}
          {refusal === null && plan.escape.note && <span className="muted"> {plan.escape.note}</span>}
        </p>
      )}
      {plan && (
        <>
          <ol className="plan" aria-label="Plan">
            {plan.steps.map((s) => (
              <li key={s.step} value={s.step}>
                {s.name}
                {s.target && ` · ${s.target}`}
              </li>
            ))}
          </ol>
          <p className="muted">
            Approach Z to {plan.approach_target_um} µm in steps of {plan.approach_step_um} µm ({plan.approach_step_mark})
          </p>
        </>
      )}
      <button type="button" disabled={chosen === null || blocked !== null} onClick={() => chosen !== null && onRotate(chosen, escape)}>
        Rotate
      </button>
      <Refused text={refusedRotate} />{" "}
      <button type="button" disabled={!perm.allowed || disabledBy !== null} onClick={onReload}>
        Re-load immersion
      </button>
      <Refused text={refusedReload} />
      {blocked && <span className="reason"> {blocked}</span>}
    </section>
  );
}

const STEP_NAMES: Record<number, string> = {
  1: "Record position and objective; lights off",
  2: "PFS off, retract Z",
  3: "Step out in Y",
  4: "Rotate",
  5: "Load immersion",
  6: "Return XY",
  7: "Approach Z",
};

function StepsPanel({
  view,
  confirmPerm,
  remote,
  refused,
  onLoadingDone,
  onAnswer,
}: {
  view: ChangeView;
  confirmPerm: Permission;
  remote: boolean;
  refused: string | null;
  onLoadingDone: (c: PendingConfirm) => void;
  onAnswer: (c: PendingConfirm, ok: boolean) => void;
}) {
  if (view.opId === null) return null;
  // "Loading done" is pressed by the person at the microscope: never remotely (ui-spec 7.5)
  const canLoad = confirmPerm.allowed && !remote;
  return (
    <section aria-label="Progress">
      <h3>Progress</h3>
      <ol className="steps">
        {[1, 2, 3, 4, 5, 6, 7].map((s) => (
          <li key={s} value={s} data-testid={`step-${s}`} data-status={view.steps[s].status}>
            {STEP_NAMES[s]} <span className="status">{view.steps[s].status}</span>{" "}
            <span className="detail">{view.steps[s].detail}</span>
          </li>
        ))}
      </ol>
      {view.loading && (
        <div className="loading-card" role="dialog" aria-label="Load immersion">
          <p>{view.loading.prompt}</p>
          {canLoad ? (
            <button type="button" className="big" onClick={() => onLoadingDone(view.loading as PendingConfirm)}>
              Loading done
            </button>
          ) : (
            <p className="muted">
              {remote || confirmPerm.allowed ? "Waiting for the operator at the microscope PC" : confirmPerm.reason}:{" "}
              {view.loading.prompt}
            </p>
          )}
        </div>
      )}
      <Refused text={refused} />
      {view.confirm && <ConfirmBox confirm={view.confirm} perm={confirmPerm} onAnswer={onAnswer} />}
      {view.approach && (
        <div aria-label="Z approach">
          <progress max={view.approach.nSteps} value={view.approach.index} />{" "}
          <EncoderZ readbackUm={view.zUm} /> → target {view.approach.targetUm} µm (step {view.approach.index} of{" "}
          {view.approach.nSteps})
        </div>
      )}
      {view.ended && (
        <p data-testid="change-ended">
          {view.ended.state === "done" ? "Done" : `Stopped (${view.ended.state})`}
          {view.ended.why && `: ${view.ended.why}`}
        </p>
      )}
    </section>
  );
}

function ConfirmBox({
  confirm: c,
  perm,
  onAnswer,
}: {
  confirm: PendingConfirm;
  perm: Permission;
  onAnswer: (c: PendingConfirm, ok: boolean) => void;
}) {
  if (!perm.allowed) {
    return <p className="muted">Waiting for the operator at the microscope PC: {c.prompt}</p>;
  }
  return (
    <div className="confirm" role="dialog" aria-label="Confirm">
      <p>{c.prompt}</p>
      <button type="button" onClick={() => onAnswer(c, true)}>
        {c.options[0] ?? "Yes"}
      </button>{" "}
      <button type="button" onClick={() => onAnswer(c, false)}>
        {c.options[1] ?? "Cancel"}
      </button>
    </div>
  );
}

// ---------- 100x focus ----------

type FocusForm = {
  centre_um: string;
  half_um: number;
  step_um: number;
  fine_half_um: number;
  fine_step_um: number;
  exposure_ms: number;
  metric: "peak" | "vollath";
};

function Focus100xPanel({
  perm,
  confirmPerm,
  view,
  disabledBy,
  refused,
  onStart,
  onAnswer,
}: {
  perm: Permission;
  confirmPerm: Permission;
  view: FocusView;
  disabledBy: string | null;
  refused: string | null;
  onStart: (args: Args) => void;
  onAnswer: (c: PendingConfirm, ok: boolean) => void;
}) {
  const client = useClient();
  const [defaults, setDefaults] = useState<Focus100xDefaults | null>(null);
  const [form, setForm] = useState<FocusForm | null>(null);

  useEffect(() => {
    let live = true;
    readFocusDefaults(client).then(
      (d) => {
        if (!live) return;
        setDefaults(d);
        setForm({ centre_um: d.centre_um === null ? "" : String(d.centre_um), half_um: d.half_um, step_um: d.step_um,
          fine_half_um: d.fine_half_um, fine_step_um: d.fine_step_um, exposure_ms: d.exposure_ms, metric: d.metric });
      },
      () => undefined,
    );
    return () => {
      live = false;
    };
  }, [client]);

  const centre = form && form.centre_um.trim() !== "" ? Number(form.centre_um) : null;
  useEffect(() => {
    if (centre === null || !Number.isFinite(centre)) return;
    let live = true;
    readFocusDefaults(client, centre).then(
      (d) => live && setDefaults(d),
      () => undefined,
    );
    return () => {
      live = false;
    };
  }, [client, centre]);

  if (defaults === null || form === null) return null;
  const centreOk = centre !== null && Number.isFinite(centre);
  const blocked = !perm.allowed ? (perm.reason ?? "not allowed") : disabledBy ?? (centreOk ? null : "Enter the sweep centre");
  return (
    <section aria-label="100x focus">
      <h3>100x focus</h3>
      <table className="refs">
        <tbody>
          <tr>
            <th>4x focus here</th>
            <td>{defaults.z_4x_focus_um === null ? "not set" : `${defaults.z_4x_focus_um} µm`}</td>
          </tr>
          <tr>
            <th>Lab offset</th>
            <td>{defaults.lab_offset_um} µm (lab offset, to be re-measured)</td>
          </tr>
          <tr>
            <th>Ceiling</th>
            <td data-testid="ceiling">{defaults.ceiling_um === null ? "—" : `${defaults.ceiling_um} µm`}</td>
          </tr>
          <tr>
            <th>Immersion this session</th>
            <td>{defaults.immersion_loaded_this_session ? "loaded" : "no loading recorded"}</td>
          </tr>
        </tbody>
      </table>
      <p>
        <label>
          Centre (µm){" "}
          <input aria-label="Centre" value={form.centre_um} placeholder="not set" disabled={!perm.allowed}
                 onChange={(e) => setForm({ ...form, centre_um: e.target.value })} />
        </label>{" "}
        {defaults.above_4x_focus && centreOk && (
          <span className="reason">above the 4x focus; 100x focus is usually 60-100 µm below</span>
        )}
      </p>
      <p className="muted">
        half {form.half_um} µm · step {form.step_um} µm · fine ±{form.fine_half_um} µm at {form.fine_step_um} µm ·{" "}
        {form.exposure_ms} ms · metric {form.metric}
      </p>
      <button type="button" disabled={blocked !== null}
              onClick={() => onStart({ centre_um: centre, half_um: form.half_um, step_um: form.step_um,
                fine_half_um: form.fine_half_um, fine_step_um: form.fine_step_um, exposure_ms: form.exposure_ms,
                metric: form.metric })}>
        Find 100x focus
      </button>
      <Refused text={refused} />
      {blocked && <span className="reason"> {blocked}</span>}
      {view.confirm && <ConfirmBox confirm={view.confirm} perm={confirmPerm} onAnswer={onAnswer} />}
      {view.points.length > 0 && <SweepCurve view={view} ceilingUm={view.ceilingUm ?? defaults.ceiling_um} />}
      {view.result && (
        <p data-testid="focus-result">
          <FocusVerdict verdict={view.result.verdict} source="computed" /> <EncoderZ readbackUm={view.result.zEncoderUm} />
          {view.result.warnings.map((w) => (
            <span key={w} className="reason">
              {" "}
              {w}
            </span>
          ))}
        </p>
      )}
    </section>
  );
}

function SweepCurve({ view, ceilingUm }: { view: FocusView; ceilingUm: number | null }) {
  const W = 360;
  const H = 140;
  const zs = view.points.map((p) => p.zReadbackUm).concat(ceilingUm === null ? [] : [ceilingUm]);
  const ss = view.points.map((p) => p.score);
  const z0 = Math.min(...zs);
  const z1 = Math.max(...zs, z0 + 1);
  const s0 = Math.min(...ss);
  const s1 = Math.max(...ss, s0 + 1e-9);
  const x = (z: number) => 20 + ((z - z0) / (z1 - z0)) * (W - 40);
  const y = (s: number) => H - 15 - ((s - s0) / (s1 - s0)) * (H - 30);
  return (
    <svg width={W} height={H} role="img" aria-label="Sweep: score against Z read-back">
      {ceilingUm !== null && (
        <line data-testid="ceiling-line" x1={x(ceilingUm)} x2={x(ceilingUm)} y1={5} y2={H - 10} stroke="#e34948" strokeDasharray="4 3" />
      )}
      {view.points.map((p, i) => (
        <circle key={i} cx={x(p.zReadbackUm)} cy={y(p.score)} r={3}
                fill={p.saturated ? "#eb6834" : "#2a78d6"} data-saturated={p.saturated ? "true" : undefined} />
      ))}
      <text x={20} y={H - 2} fontSize={10}>{z0.toFixed(0)} µm (read)</text>
      <text x={W - 20} y={H - 2} fontSize={10} textAnchor="end">{z1.toFixed(0)}</text>
    </svg>
  );
}
