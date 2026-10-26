/**
 * Status (canvas `PInstStatus`, console card 012): what the runtime last wrote to the idle status file,
 * as data. The file's absence is "No status yet", which is not "nothing connected". Nothing here asks an
 * instrument anything; Check now is the runtime's, and says so.
 */

import { useState } from "react";

import { shortTime } from "../questions/ui";
import { RunBanner } from "./follow";
import { Devices, RuntimePieces } from "./pieces";
import { HOW_WORDS, type IdleView, type LatestRun, type Reading, type StatusOut, valueText } from "./api";

export const LASER_ROW = "Tweezers laser · set by hand · not known · assumed on";
export const CHECK_NOW_NOT_BUILT =
  "Check now is not built yet: the runtime has no check-now run, and the console is not connected to the live-view host. Nothing was sent.";

/** The tweezers laser, always: nothing reads it back, so it is assumed on whatever any file says. */
export function LaserRow() {
  return <p className="inst-laser">{LASER_ROW}</p>;
}

/** The strength the latest run last sent to the tweezers, if it sent one. */
export function StrengthSent({ run }: { run: LatestRun }) {
  if (run.strength_last_sent === null || run.strength_last_sent === undefined) return null;
  return <p>Trap strength last sent: {run.strength_last_sent} (sent through the tweezers program)</p>;
}

export function ReadingsTable({ label, readings }: { label: string; readings: Reading[] }) {
  return (
    <table className="console-table" aria-label={label}>
      <thead>
        <tr><th>Name</th><th>Value</th><th>How it was read</th><th>When</th></tr>
      </thead>
      <tbody>
        {readings.map((r) => (
          <tr key={`${r.channel}/${r.name}`}>
            <td>{r.name}</td>
            <td>{r.how === "not_read" ? "unknown" : valueText(r.value)}</td>
            <td>{HOW_WORDS[r.how] ?? r.how}</td>
            <td>{shortTime(r.t_wall)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** The status file in words, for a screen that shows more than one of its parts. */
export function StatusHead({ status, view }: { status: StatusOut; view: IdleView | null }) {
  if (status.state === "none") {
    return (
      <>
        <p><strong>No status yet</strong></p>
        <p className="console-muted">
          The runtime has not written a status file. That does not mean that nothing is connected.
        </p>
      </>
    );
  }
  if (status.state !== "present" || view === null) {
    return (
      <>
        <p role="alert" className="console-error">
          The status file is {status.state === "invalid" ? "not valid" : "not readable"}, so nothing from it is shown.
        </p>
        <ul aria-label="Why the status file is not shown">
          {status.problems.map((p) => <li key={p}>{p}</li>)}
        </ul>
      </>
    );
  }
  return <p>As of {shortTime(view.writtenAt)}, from {view.writtenByRun}</p>;
}

export function Status({
  status, view, run, isPerson, onRefresh,
}: { status: StatusOut; view: IdleView | null; run: LatestRun; isPerson: boolean; onRefresh: () => void }) {
  const [answer, setAnswer] = useState<string | null>(null);
  return (
    <section aria-label="Instrument status" className="inst-status">
      <RunBanner run={run} />
      <div className="inst-grid">
        <section aria-label="Summary" className="inst-panel">
          <h3>Summary</h3>
          <StatusHead status={status} view={view} />
          <p>
            Which program holds which instrument:{" "}
            {view !== null && view.ownership.status !== "not_built" ? view.ownership.status : "not checked yet"}
          </p>
          <LaserRow />
          <StrengthSent run={run} />
          <div className="console-bar">
            {isPerson && <button type="button" onClick={() => setAnswer(CHECK_NOW_NOT_BUILT)}>Check now</button>}
            <button type="button" onClick={onRefresh}>Refresh</button>
          </div>
          {answer !== null && <p role="status">{answer}</p>}
        </section>
        <Devices run={run} />
        {view !== null && (
          <section aria-label="Readings of the status file" className="inst-panel">
            <h3>Readings</h3>
            {view.snapshot.length > 0 ? (
              <ReadingsTable label="Readings" readings={view.snapshot} />
            ) : (
              <p className="console-muted">The last run took no snapshot, so there is no reading to show.</p>
            )}
            {view.checkNow !== null && (
              <>
                <p>Last check now: {view.checkNow.runId}, {shortTime(view.checkNow.at)}</p>
                <ReadingsTable label="Check now readings" readings={view.checkNow.readings} />
              </>
            )}
          </section>
        )}
        <RuntimePieces status={status} run={run} />
      </div>
    </section>
  );
}
