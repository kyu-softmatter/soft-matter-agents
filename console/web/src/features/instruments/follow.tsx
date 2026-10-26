/**
 * Following a run (console card 015). The Instruments screens read the newest run that is still running,
 * and with none running the newest run there is, as of when it ended. They start no run and write no
 * event; what leaves the console is the stop channel and the frame tap's `get`, and only elsewhere.
 */

import { useEffect, useRef, useState } from "react";

import { shortTime } from "../questions/ui";
import type { LatestRun } from "./api";

/** How often the run's files are read again while it runs. A file read, never a device. */
export const FOLLOW_MS = 2000;

export interface Followed<T> {
  data?: T;
  error?: string;
}

/**
 * Load, and read again on `reload` and every FOLLOW_MS while `running(data)` is true. A read that fails after
 * one succeeded keeps what was shown; nothing flickers back to "Loading" on a refresh.
 */
export function useFollow<T>(load: () => Promise<T>, running: (d: T) => boolean): { state: Followed<T>; reload: () => void } {
  const [state, setState] = useState<Followed<T>>({});
  const [tick, setTick] = useState(0);
  const loadRef = useRef(load);
  loadRef.current = load;
  const isRunning = state.data !== undefined && running(state.data);

  useEffect(() => {
    let live = true;
    loadRef.current().then(
      (data) => live && setState({ data }),
      (e: unknown) => live && setState((s) => (s.data !== undefined ? s : { error: e instanceof Error ? e.message : String(e) })),
    );
    return () => {
      live = false;
    };
  }, [tick]);

  useEffect(() => {
    if (!isRunning) return;
    const timer = setInterval(() => setTick((k) => k + 1), FOLLOW_MS);
    return () => clearInterval(timer);
  }, [isRunning]);

  return { state, reload: () => setTick((k) => k + 1) };
}

/** When a run's values are from: the time it ended, else the time it started. */
export function asOf(run: LatestRun): string {
  return `as of ${shortTime(run.ended_at ?? run.started_at)}, from ${run.run_id}`;
}

/** What the screen is following, at the top of every live tab. */
export function RunBanner({ run }: { run: LatestRun }) {
  if (run.state === "ok" && run.running) return <p className="inst-banner">Following {run.run_id} (running)</p>;
  const why = run.state === "runs_not_found" ? `: ${run.message ?? "the runs folder was not found"}` : "";
  return (
    <div className="inst-banner">
      <p>No run is running{why}.</p>
      {run.state === "ok" && <p className="console-muted">Last run: {run.run_id}, {run.ended_how ?? "ended"}.</p>}
    </div>
  );
}
