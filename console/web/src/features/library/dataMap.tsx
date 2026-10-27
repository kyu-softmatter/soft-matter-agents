/**
 * The data map (console card 016): the librarian generates it, the console only shows it. Coverage is counts
 * per grade and nothing more -- no score, no rank, no single number -- and the console computes nothing from it.
 */

import { useClient } from "../../app/client";
import { areaHref } from "../../app/route";
import { Loaded, useLoad } from "../questions/ui";
import { type MapOut, PATHS } from "./api";
import { ExampleNote, pageHref } from "./pages";

const GRADES = ["E1", "E2", "E3", "E4", "E5"] as const;

export function DataMap() {
  const client = useClient();
  const state = useLoad(() => client.get<MapOut>(PATHS.map), [client]);
  return (
    <Loaded state={state}>
      {(d) => (
        <section aria-label="Data map" className="lib-map">
          <ExampleNote note={d.example_note} />
          {d.state !== "built" ? (
            <p>{d.state === "not_built" ? "Not built yet. " : ""}{d.message}</p>
          ) : (
            <>
              {d.note !== null && <p role="note" className="console-reason lib-behind">{d.note}</p>}
              <p className="console-muted">
                What each subject has on record, as counts of entries by evidence grade, and how many are disputed.
                {d.evidence_page && <> <a href={areaHref("library", "pages/evidence")}>The evidence page</a> explains the grades.</>}
              </p>
              <table className="console-table" aria-label="Coverage by subject">
                <thead>
                  <tr><th>Subject</th><th>Kind</th>{GRADES.map((g) => <th key={g}>{g}</th>)}<th>Disputed</th></tr>
                </thead>
                <tbody>
                  {d.subjects.map((s) => (
                    <tr key={s.id}>
                      <td><a href={pageHref(s.page)}>{s.page}</a></td>
                      <td>{s.kind}</td>
                      {GRADES.map((g) => <td key={g}>{s.coverage[g]}</td>)}
                      <td>{s.disputed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {d.relations.length > 0 && (
                <>
                  <h4>How entries relate</h4>
                  <ul aria-label="Relations">
                    {d.relations.map((r, i) => (
                      <li key={i}>{r.from} <strong>{r.type.replace(/_/g, " ")}</strong> {r.to}<span className="console-muted"> (stated by {r.stated_by})</span></li>
                    ))}
                  </ul>
                </>
              )}
              <p className="console-muted lib-footer">{d.footer}</p>
            </>
          )}
        </section>
      )}
    </Loaded>
  );
}
