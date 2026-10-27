/**
 * The live optical path on Optics and control (console cards 015 and 017): the path's present state as the
 * runtime reports it, and nothing else. Nothing here sends anything and no request is made of the stand, the
 * host or the frame tap; the page reads the server's reading of the run's events (or of the runtime's status
 * file outside a run).
 *
 * **The element names are the read-back's own.** No list of them lives here: an element the read-back omits
 * does not appear, and one it names without a position reads "not read" with its reason and no value. Each
 * element shows exactly one state (read back, sent, not open, not read) and, beside it, exactly one of
 * "moved by hand" (no control at all) or a draft link (the Aura and the transmitted lamp only). On the mock
 * every state is the mock's, and says so.
 */

import { shortTime } from "../questions/ui";
import type { LatestRun } from "./api";
import { RunBanner } from "./follow";
import { AURA_REFUSED_LONGER, RUN_REFUSES } from "./parts";
import { NOT_BUILT } from "./pieces";

type Path = LatestRun["path"];
type Element = Path["elements"][number];

export const NO_ORDER = "No order is given for these elements, so this is a list, not a drawing of the path.";
export const DRAFT_LINK = "Draft on the Light source tab";
export const BY_HAND_LABEL = "moved by hand";
export const NO_SNAPSHOT = "This run has taken no snapshot yet, so no element has been read.";
export const NO_SOURCE = `No snapshot and no status file have been written yet, so there is nothing to show: ${NOT_BUILT}.`;
export const STATE_LABEL: Record<Element["state"], string> = {
  read_back: "read back", sent: "sent", not_open: "not open", not_read: "not read",
};

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

/** What the person is told beside every draft link for the Aura, the lamp and the red camera. */
export function RunRefuses({ aura = false }: { aura?: boolean }) {
  return (
    <span className="inst-refuses">
      {RUN_REFUSES}
      {aura && <> {AURA_REFUSED_LONGER}</>}
    </span>
  );
}

function Reading({ e }: { e: Element }) {
  const mock = e.backend === "mock" ? <> · <span className="inst-backend">the mock&apos;s state</span></> : null;
  if (e.state === "read_back") return <>{e.value} · read {shortTime(e.t_wall)}{mock}</>;
  if (e.state === "sent") {
    return (
      <>
        {e.value !== null && e.value !== undefined && <>{e.value}{e.t_wall ? ` (read ${shortTime(e.t_wall)})` : ""} · </>}
        {e.sent ? `sent ${e.sent}${e.sent_at ? ` at ${shortTime(e.sent_at)}` : ""}` : "nothing sent in this run's events"}
        {e.reason && <> · {e.reason}</>}
        {mock}
      </>
    );
  }
  return <>{e.reason}{mock}</>;
}

export function PathPanel({ run, onDraft }: { run: LatestRun; onDraft: () => void }) {
  const path = run.path;
  return (
    <section aria-label="Live optical path" className="inst-panel">
      <h3>The light path, now</h3>
      <RunBanner run={run} />
      <SourceLine path={path} />
      <p className="console-muted">{NO_ORDER}</p>
      <ul aria-label="Path elements">
        {path.elements.map((e) => (
          <li key={e.key} data-element={e.key}>
            <span className="inst-name">{e.name}</span>
            {" · "}
            <span className="inst-state" data-state={e.state}>{STATE_LABEL[e.state]}</span>
            {" · "}
            <Reading e={e} />
            {e.control === "hand" && <> · <span className="inst-control" data-control="hand">{BY_HAND_LABEL}</span></>}
            {e.control === "draft" && (
              <>
                {" · "}
                <button type="button" data-control="draft" onClick={onDraft}>{DRAFT_LINK}</button>
                {" "}
                <RunRefuses aura={e.draft === "aura"} />
              </>
            )}
          </li>
        ))}
      </ul>
      <p className="console-muted">Known trap: the turret label that names the wrong position.</p>
      <p className="console-muted">Known trap: splitter states that send no light to one camera.</p>
      <p className="console-muted">A position read back is the stand&apos;s report of that element, and not proof of which element is in the beam.</p>
    </section>
  );
}
