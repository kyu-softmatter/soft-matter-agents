import { useMemo } from "react";

import { useAreaPath } from "../../app/route";
import { useScreenContext } from "../../app/screenContext";
import { useSimulationClient } from "./client";
import { usePolled } from "./hooks";
import { RunDetail } from "./RunDetail";
import { RunList } from "./RunList";
import { parseSimRest, runRest } from "./simRoute";
import "./simulation.css";

/** How often the run list is read again. */
export const LIST_MS = 5000;

/**
 * Simulation status (PLAN 2절 F6): progress, download, trajectory viewer, graphs.
 * Routes: see simRoute.ts (`#/simulation/runs/<run_id>` opens a run).
 *
 * Data comes from server/api/simulation.py through the app's shared client; progress of a
 * running run is pushed by the server. A SimulationClientContext provider (tests) replaces it,
 * and without any ClientProvider the in-browser fake stands in.
 */
export default function SimulationScreen() {
  const client = useSimulationClient();
  const [rest, setRest] = useAreaPath();
  const { runId } = parseSimRest(rest);

  const details = useMemo(() => (runId ? { run_id: runId } : {}), [runId]);
  useScreenContext(details);

  const runs = usePolled(runId ? null : "list", () => client.listRuns(), LIST_MS);

  return (
    <div className="sim">
      <header className="sim-head">
        <h2>Simulation</h2>
        {client.source === "mock" ? <span className="sim-mock">mock data</span> : null}
      </header>
      {runId ? (
        <RunDetail key={runId} client={client} runId={runId} onBack={() => setRest("")} />
      ) : (
        <>
          {runs.error ? <p role="alert">{runs.error}</p> : null}
          {runs.data ? (
            <RunList runs={runs.data} onOpen={(id) => setRest(runRest(id))} />
          ) : (
            <p className="muted">Loading runs…</p>
          )}
        </>
      )}
    </div>
  );
}
