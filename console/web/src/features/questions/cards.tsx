/**
 * The cards below the question field (console card 010): one per question.
 *
 * - A request written in the console: the words, who asked, when, and "request written · not picked
 *   up yet", because the agents' inbox is not open. It says every run from it waits for the person's
 *   signature. There is nothing to measure yet, so no progress bar.
 * - An agents' question already on disk, as the files say: a five-step bar -- asked (a goal card
 *   exists), designed (a plan exists), signed (an approval for that plan's hash exists), run (a run
 *   log names it), result (a result card exists). When the runs folder could not be read the run step
 *   says "not known": that is not "no run".
 */

import { ADDRESSEES, type QuestionCards, type QuestionProgress, type RequestCard } from "./api";
import { shortTime } from "./ui";

const STEPS = [
  ["asked", "Asked"],
  ["designed", "Designed"],
  ["signed", "Signed"],
  ["run", "Run"],
  ["result", "Result"],
] as const;

const addressee = (v: RequestCard["addressed_to"]) => ADDRESSEES.find((a) => a.value === v)?.label ?? v;

function Steps({ q }: { q: QuestionProgress }) {
  return (
    <ol aria-label="Progress" className="ask-steps">
      {STEPS.map(([key, label]) => {
        const unknown = key === "run" && !q.steps.run_known;
        const done = unknown ? "unknown" : String(q.steps[key]);
        return (
          <li key={key} data-done={done} title={key === "signed" ? "Only the person's own login signs." : undefined}>
            {label}
            {unknown && <span className="console-muted"> (not known: the runs folder could not be read)</span>}
          </li>
        );
      })}
    </ol>
  );
}

export function QuestionCardsView({ cards, onOpen }: { cards: QuestionCards; onOpen: (qid: string) => void }) {
  const empty = cards.requests.length === 0 && cards.questions.length === 0;
  return (
    <section aria-label="Question cards" className="ask-cards">
      {empty && <p className="console-muted">No questions yet.</p>}
      {cards.requests.map((r) => (
        <article key={r.id} className="ask-card" data-kind="request">
          <p className="ask-words">{r.words}</p>
          <p className="console-muted">
            {r.login} · {shortTime(r.asked_at)} · {addressee(r.addressed_to)}
          </p>
          <p>
            <span className="console-tag">{r.state}</span>
          </p>
          {r.runs_wait_for_signature && (
            <p className="console-muted">Every run from it waits for the person's signature.</p>
          )}
        </article>
      ))}
      {cards.questions.map((q) => (
        <article key={q.qid} className="ask-card" data-kind="agents">
          <button className="console-link" onClick={() => onOpen(q.qid)}>
            {q.title}
          </button>
          <p className="console-muted">
            {q.agent} · {q.status ?? "—"} · {shortTime(q.created_at)}
          </p>
          <Steps q={q} />
        </article>
      ))}
    </section>
  );
}
