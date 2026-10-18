/**
 * Click-to-move (F4.3) as seen on screen: ui-spec 7.4 steps 2-6, driven only by engine events
 * (docs/screens/map.md section 6). The screen never raises Z; after arrival it shows a refocus hint.
 */

/** An engine event as this screen reads it (the shared EventOut, kind widened to string). */
export interface EngineEvent {
  kind: string;
  op_id: string;
  data: Record<string, unknown>;
}

export type Phase =
  | "idle"
  | "submitting" // POST sent, op_id not known yet
  | "planned" // POST accepted; the engine has planned or is about to
  | "refused" // preflight_failed or the POST was refused
  | "confirm" // C12: retract first?
  | "retracting"
  | "moving"
  | "arrived"
  | "ended"; // aborted or error

export interface Plan {
  distance_um?: number;
  large_move?: boolean;
  retract_needed?: boolean;
  z_safe_um?: number;
  provisional?: boolean;
}

export interface ClickMove {
  phase: Phase;
  target: [number, number] | null;
  op_id: string | null;
  plan: Plan | null;
  why: string | null;
  confirmKey: string | null;
  /** ZDrive read-back when the confirm was asked (for the dialog text) */
  zReadUm: number | null;
  arrived: { x_um: number | null; y_um: number | null; z_um: number | null; retracted: boolean } | null;
  /** events that arrived before the POST returned the op_id */
  buffered: EngineEvent[];
}

export const IDLE: ClickMove = {
  phase: "idle",
  target: null,
  op_id: null,
  plan: null,
  why: null,
  confirmKey: null,
  zReadUm: null,
  arrived: null,
  buffered: [],
};

export type Action =
  | { type: "click"; x_um: number; y_um: number }
  | { type: "submitted"; op_id: string }
  | { type: "submit_failed"; why: string }
  | { type: "event"; ev: EngineEvent }
  | { type: "answered" }
  | { type: "clear" };

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const str = (v: unknown): string | null => (typeof v === "string" ? v : null);

const ACTIVE: Phase[] = ["planned", "confirm", "retracting", "moving"];

function onEvent(s: ClickMove, ev: EngineEvent): ClickMove {
  const d = ev.data ?? {};
  switch (ev.kind) {
    case "planned":
      return { ...s, phase: "planned", plan: d as Plan };
    case "preflight_failed":
      return { ...s, phase: "refused", why: str(d.why) ?? "refused by the engine" };
    case "confirm_required":
      return {
        ...s,
        phase: "confirm",
        confirmKey: str(d.key),
        zReadUm: num(d.z_um),
        plan: { ...(s.plan ?? {}), z_safe_um: num(d.z_safe_um) ?? s.plan?.z_safe_um },
      };
    case "progress": {
      const step = str(d.step);
      if (step === "retract") return { ...s, phase: "retracting" };
      if (step === "move_xy") return { ...s, phase: "moving" };
      return s;
    }
    case "finished":
      return {
        ...s,
        phase: "arrived",
        arrived: { x_um: num(d.x_um), y_um: num(d.y_um), z_um: num(d.z_um), retracted: d.retracted === true },
      };
    case "aborted":
    case "error":
      return { ...s, phase: "ended", why: str(d.why) ?? str(d.message) ?? ev.kind };
    default:
      return s;
  }
}

export function clickMoveReducer(s: ClickMove, a: Action): ClickMove {
  switch (a.type) {
    case "click":
      if (s.phase === "submitting" || ACTIVE.includes(s.phase)) return s; // one move at a time
      return { ...IDLE, phase: "submitting", target: [a.x_um, a.y_um] };
    case "submitted": {
      if (s.phase !== "submitting") return s;
      let next: ClickMove = { ...s, phase: "planned", op_id: a.op_id, buffered: [] };
      for (const ev of s.buffered) if (ev.op_id === a.op_id) next = onEvent(next, ev);
      return next;
    }
    case "submit_failed":
      return s.phase === "submitting" ? { ...s, phase: "refused", why: a.why, buffered: [] } : s;
    case "event":
      if (s.phase === "submitting") return { ...s, buffered: [...s.buffered, a.ev] };
      if (s.op_id === null || a.ev.op_id !== s.op_id) return s;
      if (!ACTIVE.includes(s.phase)) return s;
      return onEvent(s, a.ev);
    case "answered":
      return s.phase === "confirm" ? { ...s, phase: "planned", confirmKey: null } : s;
    case "clear":
      return IDLE;
  }
}

/** The one-line status the screen shows for each step (ui-spec 7.4 click-move table). */
export function clickMoveText(s: ClickMove): string | null {
  const t = s.target ? `(${s.target[0].toFixed(0)}, ${s.target[1].toFixed(0)})` : "";
  switch (s.phase) {
    case "idle":
      return null;
    case "submitting":
    case "planned":
      return `Move to ${t} requested`;
    case "refused":
      return s.why;
    case "confirm":
      return `Retract Z, then move to ${t}?`;
    case "retracting":
      return "Retracting Z";
    case "moving":
      return `Moving to ${t}`;
    case "arrived": {
      const a = s.arrived;
      const xy = a && a.x_um !== null && a.y_um !== null ? `(${a.x_um.toFixed(1)}, ${a.y_um.toFixed(1)} read back)` : t;
      return `Arrived ${xy}.`;
    }
    case "ended":
      return `Move stopped: ${s.why}`;
  }
}
