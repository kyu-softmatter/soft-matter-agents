/**
 * The Library's list of requests (console card 020): every request in the librarian's inbox, newest first, with
 * the answers that name it and where each stands. A request is shown by its kind in words, its words, the login
 * and the time; an attached file is shown by its name as text and is never opened, served or linked. An answer on
 * disk that cannot be read is said so, with the reason. Under the mock store the requests and answers are
 * examples and each says so.
 */

import { useClient } from "../../app/client";
import { Loaded, shortTime, useLoad } from "../questions/ui";
import { AnswerItem } from "./answers";
import { PATHS, type RequestsOut, type RequestView } from "./api";
import { ExampleNote } from "./pages";

function Request({ r }: { r: RequestView }) {
  return (
    <li className="lib-request">
      <p>
        <strong>{r.kind_words}</strong>{" "}
        {r.example && <span className="console-tag">example data</span>}{" "}
        <span className="console-tag lib-state">{r.state}</span>
      </p>
      <p>{r.words}</p>
      <p className="console-muted">{r.login} · {shortTime(r.asked_at)}</p>
      {r.file !== null && <p className="console-muted">File sent: {r.file}</p>}
      {r.unreadable.length > 0 && (
        <ul aria-label="Answers that cannot be read">
          {r.unreadable.map((u) => (
            <li key={u.file}>An answer is on disk and cannot be read ({u.file}): {u.reason}</li>
          ))}
        </ul>
      )}
      {r.answers.length > 0 && (
        <ul aria-label="Answers" className="lib-answers">
          {r.answers.map((a) => <AnswerItem key={a.answer_id} a={a} />)}
        </ul>
      )}
    </li>
  );
}

/** `refresh` changes when a request was just sent, so the list is read again. */
export function Requests({ refresh }: { refresh: number }) {
  const client = useClient();
  const state = useLoad(() => client.get<RequestsOut>(PATHS.requests), [client, refresh]);
  return (
    <section aria-label="Requests" className="lib-requests">
      <h3>Requests</h3>
      <Loaded state={state}>
        {(d) => (
          <>
            <ExampleNote note={d.example_note} />
            {d.requests.length === 0 && <p className="console-muted">{d.message ?? "No requests yet."}</p>}
            {d.requests.length > 0 && (
              <ul className="lib-answers">
                {d.requests.map((r) => <Request key={r.item_id} r={r} />)}
              </ul>
            )}
            {d.orphans.length > 0 && (
              <>
                <h4>Answers that name no request in the inbox</h4>
                <ul aria-label="Answers that name no request">
                  {d.orphans.map((u) => (
                    <li key={u.file}>An answer is on disk and cannot be read ({u.file}): {u.reason}</li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </Loaded>
    </section>
  );
}
