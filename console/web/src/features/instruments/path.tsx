/**
 * The live optical path on Optics and control (console cards 015 and 017): the path's present state as the
 * runtime reports it, and nothing else. Nothing here sends anything and no request is made of the stand, the
 * host or the frame tap; the page reads the server's reading of the run's events (or of the runtime's status
 * file outside a run).
 *
 * **The element names are the read-back's own.** No list of them lives here: an element the read-back omits
 * does not appear, and one it names without a position reads "not read" with its reason and no value. Each
 * element shows exactly one state (read back, sent, not open, not read) and, beside it, exactly one of
 * "moved by hand" (no control at all) or "no draft is offered yet" (the Aura and the transmitted lamp, card 024). On the mock
 * every state is the mock's, and says so.
 */

import { shortTime } from "../questions/ui";
import type { LatestRun } from "./api";
import { Drawing } from "./drawing";
import { ExampleDrawing } from "./example";
import { RunBanner } from "./follow";
import { type KindTable, orderViewOf } from "./order";
import { NOT_BUILT } from "./pieces";
import { NO_DRAFT_LABEL } from "./parts";
import { BY_HAND_LABEL, Reading, RunRefuses, STATE_LABEL } from "./readout";

export { BY_HAND_LABEL, RunRefuses, STATE_LABEL };

type Path = LatestRun["path"];

export const NO_ORDER = "No order is given for these elements, so this is a list, not a drawing of the path.";
export const NO_SNAPSHOT = "This run has taken no snapshot yet, so no element has been read.";
export const NO_SOURCE = `No snapshot and no status file have been written yet, so there is nothing to show: ${NOT_BUILT}.`;

/** Where this list was read from, in words, with the time each source carries. */
export function SourceLine({ path }: { path: Path }) {
  if (path.source === "none") return <p className="console-muted">{NO_SOURCE}</p>;
  if (path.source === "run") {
    return path.elements.length === 0 ? <p className="console-muted">{NO_SNAPSHOT}</p> : <p className="console-muted">From the run's latest snapshot, taken {shortTime(path.t_wall)}.</p>;
  }
  if (path.source === "status_file") {
    return (
      <div className="console-muted">
        <p>From the runtime's status file, written {shortTime(path.written_at)}: run {path.run_id}{path.ended_at ? `, ended ${shortTime(path.ended_at)}` : ""}{path.ended_how ? `: ${path.ended_how}` : ""}.</p>
        {path.detail && <p>{path.detail}</p>}
      </div>
    );
  }
  return <p className="console-muted">as of {shortTime(path.t_wall ?? path.ended_at)}, from {path.run_id}</p>;
}

/** Seventeen's list, for a source that gives no order or one the page does not understand: nothing is drawn. */
function ElementList({ path }: { path: Path }) {
  return (
    <>
      <ul aria-label="Path elements">
        {path.elements.map((e) => (
          <li key={e.key} data-element={e.key}>
            <span className="inst-name">{e.name}</span>
            {" · "}
            <span className="inst-state" data-state={e.state}>{STATE_LABEL[e.state]}</span>
            {" · "}
            <Reading e={e} />
            {e.control === "hand" && <> · <span className="inst-control" data-control="hand">{BY_HAND_LABEL}</span></>}
            {e.control === "no_draft" && <> · <span className="inst-control" data-control="no_draft">{NO_DRAFT_LABEL}</span></>}
            {e.control === "no_draft" && typeof e.words === "string" && e.words !== "" && <> · <span className="console-muted" data-control-words>{e.words}</span></>}
          </li>
        ))}
      </ul>
    </>
  );
}

/** The light path now: the drawing when the source gave an order this page understands, 017's list otherwise. `kinds` is for tests; the page's own table starts empty. */
export function PathPanel({ run, kinds }: { run: LatestRun; kinds?: KindTable }) {
  const view = orderViewOf(run);
  return (
    <section aria-label="Live optical path" className="inst-panel">
      <h3>The light path, now</h3>
      <RunBanner run={run} />
      <SourceLine path={run.path} />
      {view.state === "none" && run.path.example != null && <ExampleDrawing example={run.path.example} />}
      {view.state === "read" ? (
        <Drawing order={view.order} run={run} kinds={kinds} />
      ) : (
        <>
          <p className="console-muted">{NO_ORDER}</p>
          {view.state === "not_in_snapshot" && <p className="console-muted">Why: {view.reason}</p>}
          {view.state === "not_understood" && (
            <>
              <p className="console-muted">The order this source gave is not understood, so nothing is drawn from it.</p>
              <ul aria-label="Why the order is not understood">{view.problems.map((p) => <li key={p}>{p}</li>)}</ul>
            </>
          )}
          <ElementList path={run.path} />
        </>
      )}
      <p className="console-muted">Known trap: the turret label that names the wrong position.</p>
      <p className="console-muted">Known trap: splitter states that send no light to one camera.</p>
      <p className="console-muted">A position read back is the stand&apos;s report of that element, and not proof of which element is in the beam.</p>
    </section>
  );
}
