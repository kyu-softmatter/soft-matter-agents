import { useCallback, useEffect, useRef, useState } from "react";

import type { components } from "../api/schema";
import { type EventOut, useClient, useEngineEvents, useEventsConnected, useEventsLocked } from "./client";

/**
 * Reading the engine's state for the status bar. `GET /api/state` returns the
 * generated `Snapshot` (T-009b), and lights have one shape everywhere (snapshot,
 * light_changed, records): `Lights`. The readers still check at run time and show
 * anything unexpected as unknown rather than guessing.
 */

export type Snapshot = components["schemas"]["Snapshot"];
export type Lights = components["schemas"]["Lights"];
export type Positions = components["schemas"]["Positions"];
type OpSummary = components["schemas"]["OpSummary"];

export interface Light {
  name: string;
  on: boolean | null; // null = unknown or unreadable
  raw: unknown;
}

export interface LightsView {
  lights: Light[];
  verified: boolean | null;
  error: string | null;
}

export interface RunningOp {
  op_id: string;
  op: string;
  state?: string;
}

export interface LastShutdown {
  t?: number;
  all_off?: boolean;
  [k: string]: unknown;
}

export interface EngineStatus {
  loaded: boolean;
  error: string | null;
  connected: boolean;
  /** the login is locked (WsLock): no events arrive, so values are not live. Optional for callers building a status by hand */
  locked?: boolean;
  positions: Positions | null;
  lights: LightsView | null;
  /** when positions / lights were last read from the server (ms since epoch) */
  positionsAt: number | null;
  lightsAt: number | null;
  running: RunningOp[];
  lastShutdown: LastShutdown | null;
}

const OFF = new Set(["0", "off", "false", "closed"]);
const ON = new Set(["1", "on", "true", "open"]);

export function lightIsOn(v: unknown): boolean | null {
  if (typeof v === "boolean") return v;
  if (typeof v === "number") return v === 0 ? false : v === 1 ? true : null;
  if (typeof v === "string") {
    const s = v.trim().toLowerCase();
    if (OFF.has(s)) return false;
    if (ON.has(s)) return true;
  }
  if (v && typeof v === "object" && "state" in v) return lightIsOn((v as { state: unknown }).state);
  return null;
}

/**
 * Lights from a snapshot `lights` value or a `light_changed` event's data: the one
 * shape `{dialamp: {state, intensity}, aura: {state, lines}, verified, records, error}`.
 * A missing lamp is left out; a state other than on/off reads as unknown.
 */
export function readLights(data: Lights | null | undefined | Record<string, unknown>): LightsView | null {
  if (!data || typeof data !== "object") return null;
  const d = data as Lights;
  const verified = typeof d.verified === "boolean" ? d.verified : null;
  const error = typeof d.error === "string" ? d.error : null;
  const lights: Light[] = [];
  if (d.dialamp) lights.push({ name: "DiaLamp", on: lightIsOn(d.dialamp.state), raw: d.dialamp });
  if (d.aura) lights.push({ name: "Aura", on: lightIsOn(d.aura.state), raw: d.aura });
  return { lights, verified, error };
}

function readPositions(data: Positions | null | undefined | Record<string, unknown>): Positions | null {
  return data && typeof data === "object" ? (data as Positions) : null;
}

function readRunning(data: OpSummary[] | undefined): RunningOp[] {
  if (!Array.isArray(data)) return [];
  return data
    .filter((o) => !!o && typeof o === "object")
    .map((o) => ({ op_id: String(o.op_id ?? ""), op: String(o.op ?? ""), state: o.state }));
}

function readLastShutdown(data: unknown): LastShutdown | null {
  return data && typeof data === "object" ? (data as LastShutdown) : null;
}

/** Kinds after which the running list may have changed: re-read the snapshot. */
const LIFECYCLE = new Set([
  "started", "finished", "aborted", "error", "refused", "confirmed", "planned", "session_changed",
  "approved", "rejected", "updated",
]);

/**
 * The engine state for the status bar. `resumed` is `useAuth().resumed` (T-105):
 * it changes after an unlock, and since the server sends no events while locked,
 * the state is re-read from GET /api/state then.
 */
export function useEngineStatus(resumed?: number): EngineStatus {
  const client = useClient();
  const connected = useEventsConnected();
  const locked = useEventsLocked();
  const [s, setS] = useState<Omit<EngineStatus, "connected">>({
    loaded: false,
    error: null,
    positions: null,
    lights: null,
    positionsAt: null,
    lightsAt: null,
    running: [],
    lastShutdown: null,
  });
  const alive = useRef(true);

  const reload = useCallback(async () => {
    try {
      const snap = await client.get<Snapshot>("/api/state");
      if (!alive.current) return;
      const t = Date.now();
      setS({
        loaded: true,
        error: null,
        positions: readPositions(snap.positions),
        lights: readLights(snap.lights),
        positionsAt: t,
        lightsAt: t,
        running: readRunning(snap.running),
        lastShutdown: readLastShutdown(snap.last_shutdown_lights),
      });
    } catch (e) {
      if (alive.current) setS((p) => ({ ...p, error: e instanceof Error ? e.message : String(e) }));
    }
  }, [client]);

  useEffect(() => {
    alive.current = true;
    void reload();
    return () => {
      alive.current = false;
    };
  }, [reload]);

  // events in a gap are lost: re-read after every (re)connect
  useEffect(() => {
    if (connected) void reload();
  }, [connected, reload]);

  // ...and after an unlock: no events came while the login was locked
  const lastResumed = useRef(resumed);
  useEffect(() => {
    if (resumed === lastResumed.current) return;
    lastResumed.current = resumed;
    void reload();
  }, [resumed, reload]);

  const onEvent = useCallback(
    (ev: EventOut) => {
      if (ev.kind === "position") setS((p) => ({ ...p, positions: readPositions(ev.data), positionsAt: Date.now() }));
      else if (ev.kind === "light_changed") setS((p) => ({ ...p, lights: readLights(ev.data), lightsAt: Date.now() }));
      else if (LIFECYCLE.has(ev.kind)) void reload();
    },
    [reload],
  );
  useEngineEvents(onEvent);

  return { ...s, connected, locked };
}

// -- assistant (PLAN D7) ----------------------------------------------------------------

export type DataStage = "prompt_only" | "text" | "images";

export interface AssistantStatus {
  available: boolean;
  provider: string | null; // "fake" | "anthropic"
  connected: boolean | null;
  data_stage: DataStage | string | null;
}

const UNAVAILABLE: AssistantStatus = {
  available: false,
  provider: null,
  connected: null,
  data_stage: null,
};

export function readAssistantStatus(body: unknown): AssistantStatus {
  if (!body || typeof body !== "object") return UNAVAILABLE;
  const b = body as Record<string, unknown>;
  const stage = b.data_stage ?? b.data_policy ?? null;
  return {
    available: true,
    provider: typeof b.provider === "string" ? b.provider : null,
    connected: typeof b.connected === "boolean" ? b.connected : null,
    data_stage: typeof stage === "string" ? stage : null,
  };
}

/** `GET /api/assistant/status` (T-013). Anything but a JSON answer reads as unavailable. */
export function useAssistantStatus(): AssistantStatus {
  const client = useClient();
  const connected = useEventsConnected();
  const [st, setSt] = useState<AssistantStatus>(UNAVAILABLE);
  useEffect(() => {
    let live = true;
    client
      .get("/api/assistant/status")
      .then((b) => live && setSt(readAssistantStatus(b)))
      .catch(() => live && setSt(UNAVAILABLE));
    return () => {
      live = false;
    };
  }, [client, connected]);
  return st;
}
