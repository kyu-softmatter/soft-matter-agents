/**
 * The live optical path on Optics and control (console card 015; the person's request of 2026-10-26): the
 * path's present state from the running run's read-back, and nothing else. Modelled on the old hardware
 * page's read-back panels (their wording and read time), without their buttons: nothing here sends anything.
 *
 * The elements are the Micro-Manager devices the runtime names; the registry gives no order for them, so
 * this is a list and no order is drawn. An element the run did not report reads "not built yet", and
 * nothing is filled in from the console's side. On the mock the state is the mock's own, and says so.
 */

import { shortTime } from "../questions/ui";
import type { LatestRun } from "./api";
import { asOf, RunBanner } from "./follow";
import { NOT_BUILT } from "./pieces";

/** `hand`: moved by hand, no control. Otherwise the element has this page's draft link (the lamp and the LED). */
export const PATH_ELEMENTS: readonly { device: string; hand: boolean }[] = [
  { device: "FilterTurret1", hand: true },
  { device: "FilterTurret2", hand: true },
  { device: "CSUW1-Filter_Red", hand: true },
  { device: "CSUW1-Filter_Blue", hand: true },
  { device: "LightPath", hand: true },
  { device: "CSUW1-Port", hand: true },
  { device: "CSUW1-Dichroic", hand: true },
  { device: "DiaLamp", hand: false },
  { device: "Aura", hand: false },
];

export const NO_ORDER = "No order is given for these elements, so this is a list, not a drawing of the path.";
export const DRAFT_LINK = "Draft on the Light source tab";

export function PathPanel({ run, onDraft }: { run: LatestRun; onDraft: () => void }) {
  const read = new Map(run.state === "ok" ? run.path.map((p) => [p.device, p]) : []);
  return (
    <section aria-label="Live optical path" className="inst-panel">
      <h3>The light path, now</h3>
      <RunBanner run={run} />
      {run.state === "ok" && !run.running && <p className="console-muted">{asOf(run)}</p>}
      <p className="console-muted">{NO_ORDER}</p>
      <ul aria-label="Path elements">
        {PATH_ELEMENTS.map(({ device, hand }) => {
          const p = read.get(device);
          return (
            <li key={device}>
              {device}
              {" · "}
              {p === undefined
                ? NOT_BUILT
                : `${Object.entries(p.props).map(([k, v]) => `${k} = ${v}`).join(", ")} · read ${shortTime(p.t_wall)} · ${p.backend === "mock" ? "the mock's state" : "read back"}`}
              {hand ? " · moved by hand" : (
                <>
                  {" · "}
                  <button type="button" onClick={onDraft}>{DRAFT_LINK}</button>
                </>
              )}
            </li>
          );
        })}
      </ul>
      <p className="console-muted">Known trap: the turret label that names the wrong position.</p>
      <p className="console-muted">Known trap: splitter states that send no light to one camera.</p>
      <p className="console-muted">A position read back is that element's position, and not proof of which element is in the beam.</p>
    </section>
  );
}
