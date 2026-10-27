/**
 * The librarian's answers (console card 016). Under the mock store they are example answers and each says so;
 * from the real store there are none yet. Every number comes with its entry, grade and source as recorded, and
 * whether the entry covers the conditions asked. The console adds no search and no grade.
 */

import { useClient } from "../../app/client";
import { Loaded, shortTime, useLoad } from "../questions/ui";
import { type AnswerOut, type AnswersOut, PATHS } from "./api";
import { ExampleNote } from "./pages";

export const OUTCOME_WORDS: Record<string, string> = {
  entered: "Entered",
  waiting_for_a_name: "Waiting for a name",
  refuted: "Refuted",
  in_conflict: "In conflict",
  superseded: "Superseded",
  kept: "Kept",
  no_entry_of_that_name: "No entry of that name",
  answered: "Answered",
  not_in_the_store: "Not in the store",
};

const COVERS: Record<string, string> = {
  yes: "covers your conditions",
  no: "does not cover your conditions",
  not_stated: "conditions not stated",
};

function Answer({ a }: { a: AnswerOut }) {
  return (
    <li className="lib-answer">
      <strong>{OUTCOME_WORDS[a.outcome] ?? a.outcome}</strong>{" "}
      {a.example && <span className="console-tag">example data</span>}{" "}
      <span className="console-muted">{shortTime(a.answered_at)}</span>
      <p>{a.reason}</p>
      {a.answer !== null && <p>{a.answer}</p>}
      {a.numbers.length > 0 && (
        <table className="console-table" aria-label="Numbers">
          <thead>
            <tr><th>Name</th><th>Value</th><th>Entry</th><th>Grade</th><th>Source</th><th>Conditions</th></tr>
          </thead>
          <tbody>
            {a.numbers.map((n, i) => (
              <tr key={i}>
                <td>{n.name}</td>
                <td>{n.value} {n.unit}</td>
                <td>{n.entry_id}</td>
                <td>{n.grade}</td>
                <td>{n.source}</td>
                <td>{COVERS[n.covers_conditions] ?? n.covers_conditions}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {a.gaps.length > 0 && (
        <ul aria-label="Not found">
          {a.gaps.map((g, i) => <li key={i}>Asked for: {g.asked_for}. Looked in: {g.looked_in}.</li>)}
        </ul>
      )}
      {a.entries_marked.length > 0 && <p className="console-muted">Entries marked: {a.entries_marked.join(", ")}</p>}
      {a.other_side.length > 0 && <p className="console-muted">Other side: {a.other_side.join(", ")}</p>}
      {a.entries_made.length > 0 && <p className="console-muted">Entries made: {a.entries_made.join(", ")}</p>}
      {a.quantity_name !== null && <p className="console-muted">Name waiting: {a.quantity_name}</p>}
    </li>
  );
}

export function Answers() {
  const client = useClient();
  const state = useLoad(() => client.get<AnswersOut>(PATHS.answers), [client]);
  return (
    <section aria-label="Answers" className="lib-answers">
      <h3>Answers</h3>
      <Loaded state={state}>
        {(d) => (
          <>
            <ExampleNote note={d.example_note} />
            {d.answers.length === 0 ? (
              <p>{d.message}</p>
            ) : (
              <ul>{d.answers.map((a) => <Answer key={a.answer_id} a={a} />)}</ul>
            )}
          </>
        )}
      </Loaded>
    </section>
  );
}
