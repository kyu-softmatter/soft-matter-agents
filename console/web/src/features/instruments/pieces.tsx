/**
 * The connection state and the runtime pieces the screens wait for (console card 015). The connection
 * state is the run's own last snapshot, read from its events; a piece the runtime has not built reads
 * "not built yet" and is never filled in from the console's side.
 */

import { shortTime } from "../questions/ui";
import type { LatestRun, StatusOut } from "./api";

export const NOT_BUILT = "not built yet";

export function Devices({ run }: { run: LatestRun }) {
  const ch = run.state === "ok" ? run.channels : null;
  return (
    <section aria-label="Connection state" className="inst-panel">
      <h3>Devices</h3>
      {ch === null || ch === undefined ? (
        <p className="console-muted">There is no run to read a connection state from.</p>
      ) : ch.rows.length === 0 ? (
        <p className="console-muted">No snapshot yet, so no connection state.</p>
      ) : (
        <>
          <p className="console-muted">From the last snapshot of {run.run_id}, as of {shortTime(ch.t_wall)}.</p>
          <table className="console-table" aria-label="Devices">
            <thead>
              <tr><th>Channel</th><th>State</th><th>Detail</th></tr>
            </thead>
            <tbody>
              {ch.rows.map((r) => (
                <tr key={r.channel}>
                  <td>{r.channel}</td>
                  <td>{r.opened ? "opened" : "not opened"}</td>
                  <td>{(r.opened ? r.backend : r.detail) ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}

function opened(run: LatestRun, channel: string): boolean {
  return run.channels?.rows.some((r) => r.channel === channel && r.opened) === true;
}

/** Each piece stays "not built yet" until the files show it. Check now and the frames per camera have no file to show. */
export function RuntimePieces({ status, run }: { status: StatusOut; run: LatestRun }) {
  const xs = new Set(run.piezo.map((p) => `${p.x_um}/${p.y_um}/${p.z_um}`));
  const pieces: [string, string | null][] = [
    ["Idle status file writer", status.state === "present" ? "built: a status file was found" : null],
    ["Check now", null],
    ["Latest frames per camera", null],
    ["Second camera (mock)", opened(run, "camera_blue") ? "present: camera_blue is in the last snapshot" : null],
    ["Piezo trace that moves (mock)", xs.size > 1 ? "present: positions differ between snapshots" : null],
    ["Trap commands echoed back (mock)", null],
    ["Confocal elements (mock)", opened(run, "confocal_csuw1") ? "present: confocal_csuw1 is in the last snapshot" : null],
  ];
  return (
    <section aria-label="Runtime pieces the screens wait for" className="inst-panel">
      <h3>Runtime pieces</h3>
      <ul aria-label="Runtime pieces">
        {pieces.map(([name, there]) => (
          <li key={name}>{name}: {there ?? NOT_BUILT}</li>
        ))}
      </ul>
    </section>
  );
}
