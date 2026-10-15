import { useCallback, useEffect, useRef, useState } from "react";

import { CommandRefused, type EventOut, useClient, useEngineEvents, useReadOnly } from "../client";

type Permission = { allowed: boolean; reason: string | null };
type Running = { op_id: string; op: string; args?: Record<string, unknown> };

const RUN_EVENTS = ["started", "progress", "finished", "aborted", "error", "preflight_failed", "refused"] as const;

function message(e: unknown): string {
  return e instanceof CommandRefused ? e.detail : e instanceof Error ? e.message : String(e);
}

/**
 * Run a saved pattern on the piezo and the traps (`pattern_run`, card T-20261002-2205 stage 4),
 * see its progress and abort it. `onTime` gets the pattern time of every progress event, so an
 * overlay can follow the run. The engine decides everything again: control, session, the
 * piezo and tweezers the pattern needs, the ranges; a refusal is shown with its reason.
 */
export function PatternRunControls({ patternId, onTime }: { patternId: string; onTime?: (t: number) => void }) {
  const client = useClient();
  const readOnly = useReadOnly();
  const [perm, setPerm] = useState<Permission | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const [repeats, setRepeats] = useState(1);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const onTimeRef = useRef(onTime);
  onTimeRef.current = onTime;

  const reload = useCallback(async () => {
    try {
      const p = await client.get<Record<string, Permission>>("/api/permissions?ops=pattern_run");
      setPerm(p.pattern_run ?? null);
      const st = await client.get<{ running?: Running[] }>("/api/state");
      const mine = (st.running ?? []).find((o) => o.op === "pattern_run" && o.args?.pattern_id === patternId);
      setRunning(mine?.op_id ?? null);
    } catch (e) {
      setError(message(e));
    }
  }, [client, patternId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const onEvent = useCallback(
    (ev: EventOut) => {
      const data = (ev.data ?? {}) as Record<string, unknown>;
      if (ev.kind === "progress" && data.op === "pattern_run") {
        const d = (data.data ?? {}) as Record<string, unknown>;
        if (d.pattern_id !== patternId) return;
        setRunning(ev.op_id);
        if (typeof d.t_s === "number") onTimeRef.current?.(d.t_s);
        if (typeof d.elapsed_s === "number" && typeof d.of_s === "number")
          setStatus(`running: ${d.elapsed_s.toFixed(1)} / ${d.of_s.toFixed(1)} s`);
        return;
      }
      if (running && ev.op_id === running && ev.kind !== "progress" && ev.kind !== "started") {
        setRunning(null);
        setStatus(ev.kind === "finished" ? "finished" : `${ev.kind}${data.message ? `: ${String(data.message)}` : ""}`);
        void reload();
      }
    },
    [patternId, running, reload],
  );
  useEngineEvents(onEvent, RUN_EVENTS);

  const blocked = readOnly.readOnly ? (readOnly.why ?? "read-only") : perm === null ? "checking…" : perm.allowed ? null : perm.reason;

  const run = async () => {
    setError(null);
    setStatus(null);
    try {
      const op = await client.command({ kind: "start", op: "pattern_run", args: { pattern_id: patternId, repeats } });
      setRunning(op);
      setStatus("starting…");
      // a refusal or a fast end may have come before the reply: look at the engine once
      const st = await client.get<{ running?: Running[]; recent?: (Running & { state?: string; why?: string })[] }>(
        "/api/state",
      );
      if (!(st.running ?? []).some((o) => o.op_id === op)) {
        const ended = (st.recent ?? []).find((o) => o.op_id === op);
        if (ended) {
          setRunning(null);
          setStatus(`${ended.state ?? "ended"}${ended.why ? `: ${ended.why}` : ""}`);
        }
      }
    } catch (e) {
      setError(message(e));
    }
  };

  const abort = async () => {
    if (!running) return;
    try {
      await client.command({ kind: "abort", op_id: running });
    } catch (e) {
      setError(message(e));
    }
  };

  return (
    <div className="pattern-run" aria-label="Run pattern">
      <label className="pattern-num">
        repeats
        <input
          type="number"
          min={1}
          max={100}
          value={repeats}
          aria-label="Repeats"
          onChange={(e) => setRepeats(Math.max(1, Math.min(100, Math.round(Number(e.target.value)) || 1)))}
        />
      </label>
      <button type="button" disabled={blocked !== null || running !== null} onClick={() => void run()}>
        Run on piezo / traps
      </button>
      <button type="button" className="abort-button" disabled={running === null} onClick={() => void abort()}>
        Abort run
      </button>
      {blocked && running === null && <span className="muted">{blocked}</span>}
      {status && <span data-testid="pattern-run-status">{status}</span>}
      {error && (
        <span className="warn" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
