/**
 * The Sample map page (console card 014). Each part of the map says it is not built yet and why. Nothing
 * is drawn: no move, no flag, no candidate, and a model's guess is never shown as one. The sample's record
 * view is a panel here; it says there is no record yet and invents no path.
 */

import { useClient } from "../../app/client";
import { Loaded, shortTime, useLoad } from "../questions/ui";
import { PATHS, type SampleMapOut, type SampleOut } from "./api";
import { ExampleNote } from "./plan";

const PART_NAMES: Record<string, string> = {
  frames_with_stage_readback: "Frames with the stage's read-back position",
  hole_fitter: "Hole fitter",
  candidate_finder: "Candidate finder",
  flags_and_confirmations: "Flags and candidate confirmations",
};

function SamplePanel() {
  const client = useClient();
  const state = useLoad(() => client.get<SampleOut>(PATHS.sample), [client]);
  return (
    <section aria-label="Sample" className="exp-sample">
      <h3>Sample</h3>
      <Loaded state={state}>
        {(d) => (
          <>
            <ExampleNote note={d.example_note} />
            <p>{d.message}</p>
            {d.loading_checks.length > 0 && (
              <ul aria-label="Loading checks">
                {d.loading_checks.map((c) => (
                  <li key={`${c.run_id}/${c.sheet_id}`}>
                    {c.words} ({c.confirmed_by ?? "unknown"}, {shortTime(c.confirmed_at)})
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Loaded>
    </section>
  );
}

export function SampleMap() {
  const client = useClient();
  const state = useLoad(() => client.get<SampleMapOut>(PATHS.sampleMap), [client]);
  return (
    <>
      <Loaded state={state}>
        {(d) => (
          <section aria-label="Sample map">
            <h3>Sample map</h3>
            <ExampleNote note={d.example_note} />
            <p>{d.message}</p>
            <ul aria-label="Parts of the sample map">
              {d.parts.map((p) => (
                <li key={p.part}>
                  <strong>{PART_NAMES[p.part] ?? p.part}</strong> <span className="console-tag">not built yet</span>
                  <br />
                  <span className="console-muted">{p.why}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </Loaded>
      <SamplePanel />
    </>
  );
}
