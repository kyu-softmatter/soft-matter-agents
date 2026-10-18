/**
 * Pure state for the objective screen, built only from engine events
 * (docs/screens/objective.md section 3). Nothing here guesses hardware state:
 * a step is done when an event says so, and Z comes from encoder read-backs.
 */

import type { EventOut } from "../../app/client";

type EngineEvent = EventOut;

export type StepStatus = "pending" | "running" | "done" | "failed" | "skipped";

export interface StepRow {
  status: StepStatus;
  detail: string;
}

export interface Approach {
  zUm: number;
  targetUm: number;
  index: number;
  nSteps: number;
}

export interface PendingConfirm {
  opId: string;
  key: string;
  kind: string;
  prompt: string;
  options: string[];
  context: Record<string, unknown>;
}

export interface ChangeView {
  opId: string | null;
  steps: Record<number, StepRow>;
  approach: Approach | null;
  /** the "Loading done" card (manual_step load_immersion) */
  loading: PendingConfirm | null;
  loadingDone: { by: string; at: string } | null;
  /** other confirms of this op (C6, C8) */
  confirm: PendingConfirm | null;
  zUm: number | null;
  ended: null | { state: "done" | "awaiting_return" | "aborted" | "error"; why: string };
  refusal: string | null;
}

export const STEP_NUMBERS = [1, 2, 3, 4, 5, 6, 7] as const;

export function initialChange(): ChangeView {
  const steps: Record<number, StepRow> = {};
  for (const s of STEP_NUMBERS) steps[s] = { status: "pending", detail: "" };
  return { opId: null, steps, approach: null, loading: null, loadingDone: null, confirm: null,
    zUm: null, ended: null, refusal: null };
}

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const str = (v: unknown): string => (typeof v === "string" ? v : v === undefined || v === null ? "" : String(v));

function fmt(v: unknown): string {
  const n = num(v);
  return n === null ? str(v) : n.toFixed(1);
}

/** One line of read-back per step, from the progress payload. */
export function stepDetail(d: Record<string, unknown>): string {
  const parts: string[] = [];
  if (d.axis !== undefined) parts.push(str(d.axis));
  if (d.commanded !== undefined) parts.push(`-> ${fmt(d.commanded)}`);
  if (d.readback !== undefined) parts.push(`(read ${fmt(d.readback)})`);
  if (d.label_read !== undefined) parts.push(`(read ${str(d.label_read)})`);
  if (d.pfs_in_range !== undefined) parts.push(`PFS ${str(d.pfs_in_range)}`);
  if (parts.length === 0 && d.detail !== undefined) parts.push(str(d.detail));
  return parts.join(" ");
}

function toConfirm(ev: EngineEvent): PendingConfirm {
  const d = ev.data ?? {};
  return {
    opId: ev.op_id,
    key: str(d.key),
    kind: str(d.kind),
    prompt: str(d.prompt),
    options: Array.isArray(d.options) ? d.options.map(str) : [],
    context: (d.context as Record<string, unknown>) ?? {},
  };
}

function markRunningBefore(steps: Record<number, StepRow>, upTo: number): Record<number, StepRow> {
  const out = { ...steps };
  for (const s of STEP_NUMBERS) {
    if (s < upTo && out[s].status === "running") out[s] = { ...out[s], status: "done" };
  }
  return out;
}

export function reduceChange(v: ChangeView, ev: EngineEvent): ChangeView {
  const d = ev.data ?? {};
  if (ev.kind === "started" && str(d.op) === "objective_change") {
    return { ...initialChange(), opId: ev.op_id };
  }
  if (v.opId === null || ev.op_id !== v.opId) {
    // position is shown for any op; everything else must be ours
    if (ev.kind === "position" && num(d.z_um) !== null) return { ...v, zUm: num(d.z_um) };
    if (ev.kind === "preflight_failed" && v.opId === null) return { ...v, refusal: str(d.why) };
    return v;
  }
  switch (ev.kind) {
    case "progress": {
      const step = num(d.step);
      if (step === null || !(step in v.steps)) return v;
      let steps = markRunningBefore(v.steps, step);
      if (step === 7) {
        const a: Approach = {
          zUm: num(d.z_um) ?? 0,
          targetUm: num(d.target_um) ?? 0,
          index: num(d.step_index) ?? 0,
          nSteps: num(d.n_steps) ?? 0,
        };
        steps = { ...steps, 7: { status: "running", detail: `step ${a.index} of ${a.nSteps}` } };
        return { ...v, steps, approach: a };
      }
      const status: StepStatus = str(d.status) === "running" ? "running" : "done";
      steps = { ...steps, [step]: { status, detail: stepDetail(d) } };
      return { ...v, steps };
    }
    case "position":
      return num(d.z_um) === null ? v : { ...v, zUm: num(d.z_um) };
    case "confirm_required": {
      const c = toConfirm(ev);
      if (c.key === "load_immersion") {
        const steps = { ...markRunningBefore(v.steps, 5), 5: { status: "running" as const, detail: "waiting" } };
        return { ...v, steps, loading: c };
      }
      return { ...v, confirm: c };
    }
    case "confirmed": {
      if (str(d.key) === "load_immersion") {
        const steps = { ...v.steps, 5: { status: "done" as const, detail: `by ${str(d.by)} at ${str(d.at)}` } };
        return { ...v, steps, loading: null, loadingDone: { by: str(d.by), at: str(d.at) } };
      }
      return { ...v, confirm: null };
    }
    case "finished": {
      const state = str(d.state) === "awaiting_return" ? "awaiting_return" : "done";
      const steps = { ...v.steps };
      for (const s of STEP_NUMBERS) {
        if (steps[s].status === "running") steps[s] = { ...steps[s], status: state === "done" ? "done" : "pending" };
        if (state === "done" && steps[s].status === "pending") steps[s] = { ...steps[s], status: "skipped" };
      }
      return { ...v, steps, loading: null, confirm: null, ended: { state, why: "" } };
    }
    case "aborted":
    case "error": {
      const state = str(d.state) === "awaiting_return" ? "awaiting_return" : ev.kind === "error" ? "error" : "aborted";
      const steps = { ...v.steps };
      for (const s of STEP_NUMBERS) {
        if (steps[s].status === "running") steps[s] = { status: "failed", detail: `stopped: ${str(d.why ?? d.message)}` };
      }
      return { ...v, steps, loading: null, confirm: null, ended: { state, why: str(d.why ?? d.message) } };
    }
    default:
      return v;
  }
}

// ---------- 100x focus ----------

export interface SweepPoint {
  zReadbackUm: number;
  score: number;
  saturated: boolean;
  phase: string;
}

export interface FocusView {
  opId: string | null;
  points: SweepPoint[];
  ceilingUm: number | null;
  confirm: PendingConfirm | null;
  result: null | { verdict: string; zEncoderUm: number | null; warnings: string[] };
  ended: null | { state: string; why: string };
}

export function initialFocus(): FocusView {
  return { opId: null, points: [], ceilingUm: null, confirm: null, result: null, ended: null };
}

export function reduceFocus(v: FocusView, ev: EngineEvent): FocusView {
  const d = ev.data ?? {};
  if (ev.kind === "started" && str(d.op) === "focus_100x") return { ...initialFocus(), opId: ev.op_id };
  if (v.opId === null || ev.op_id !== v.opId) return v;
  switch (ev.kind) {
    case "planned":
      return { ...v, ceilingUm: num(d.ceiling_um) };
    case "progress": {
      const z = num(d.z_readback_um);
      const s = num(d.score);
      if (z === null || s === null) return v;
      const sat = num(d.sat);
      return { ...v, points: [...v.points, { zReadbackUm: z, score: s, saturated: (sat ?? 0) > 0, phase: str(d.phase) }] };
    }
    case "confirm_required":
      return { ...v, confirm: toConfirm(ev) };
    case "confirmed":
      return { ...v, confirm: null };
    case "reading":
      if (str(d.source) !== "classical") return v;
      return { ...v, result: { verdict: str(d.verdict), zEncoderUm: num(d.z_encoder_um),
        warnings: Array.isArray(d.warnings) ? d.warnings.map(str) : [] } };
    case "finished":
    case "aborted":
    case "error":
      return { ...v, confirm: null, ended: { state: ev.kind, why: str(d.why ?? d.message) } };
    default:
      return v;
  }
}
