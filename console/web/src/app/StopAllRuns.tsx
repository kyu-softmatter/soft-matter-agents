import { useRef, useState } from "react";

import type { components } from "../api/schema";
import { CommandRefused, useClient } from "./client";

type StopAllOut = components["schemas"]["StopAllOut"];

/** The one request this control makes (console card 004). It asks for nothing and sends nothing else. */
export const STOP_ALL_PATH = "/api/console/runs/stop";

/**
 * "Stop all runs", on the lock screen and the logged-out screens (console card 004, the person's
 * request at cee4f8c1). One press sends one request, to the server, which asks every running
 * followed run to stop on the stop channel the run announced. There is no confirmation, because a
 * stop that waits for a second click is a slower stop; and a second press while the first is in
 * flight does nothing. It lists nothing before it stops: a read that worked without a login
 * would show a stranger the runs.
 *
 * From the microscope PC it needs no login. From another computer the server asks for a login
 * and remote abort, and the refusal is shown in words. With the console not connected to the
 * agents' files (the mock store) the server says so and sends nothing.
 */
export function StopAllRuns() {
  const client = useClient();
  const inFlight = useRef(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<StopAllOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const press = async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setResult(null);
    setError(null);
    try {
      const out = await client.post<StopAllOut>(STOP_ALL_PATH);
      if (out === null) setError("The server answered with nothing: it is not known whether a stop was sent.");
      else setResult(out);
    } catch (e) {
      setError(e instanceof CommandRefused ? e.detail : e instanceof Error ? e.message : String(e));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  };

  return (
    <div className="stop-all">
      <button type="button" className="abort-button" disabled={busy} onClick={() => void press()}>
        Stop all runs
      </button>
      {busy && (
        <p className="stop-all-result muted" role="status">
          Sending the stop…
        </p>
      )}
      {error && (
        <p className="stop-all-result warn" role="alert">
          {error}
        </p>
      )}
      {result && (
        <div className="stop-all-result" role="status" data-testid="stop-all-result">
          <p>{result.message}</p>
          {result.runs.length > 0 && (
            <ul>
              {result.runs.map((r) => (
                <li key={r.run_id}>{r.message}</li>
              ))}
            </ul>
          )}
          {!result.audited && <p className="warn">The stop was sent, but it could not be written to the audit log.</p>}
        </div>
      )}
    </div>
  );
}
