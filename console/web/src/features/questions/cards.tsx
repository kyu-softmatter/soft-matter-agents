/**
 * The cards below the question field (console card 010): one per question.
 *
 * - A request written in the console (a question left to the agents): the words, who asked, when, and
 *   "written in the console · not delivered", because it went to no agent. It says every run from it
 *   waits for the person's signature. No progress bar: nothing to measure.
 * - An item delivered to the microscope's or the simulation's inbox (card 019): the words, login, time,
 *   agent and question id, and exactly one state the server read from the agent's answers: "delivered
 *   · not answered yet", "taken up as <id>", "refused · <reason>", or "an answer is on disk and cannot
 *   be read". The server orders them, newest first; the cards keep that order.
 * - A question delivered to the librarian (card 020) is such an item with no question id and no signature
 *   note (an `ask` runs nothing); its state is the Library's, and its latest answer is shown as the
 *   Library shows one.
 * - An agents' question already on disk, as the files say: a five-step bar -- asked (a goal card
 *   exists), designed (a plan exists), signed (an approval for that plan's hash exists), run (a run
 *   log names it), result (a result card exists). When the runs folder could not be read the run step
 *   says "not known": that is not "no run".
 */

import { AnswerItem } from "../library/answers";
import "../library/library.css";
import { addresseeLabel, type QuestionCards, type QuestionProgress } from "./api";
import { shortTime } from "./ui";

const STEPS = [
  ["asked", "Asked"],
  ["designed", "Designed"],
  ["signed", "Signed"],
  ["run", "Run"],
  ["result", "Result"],
] as const;

export function QuestionStepsList({ q }: { q: QuestionProgress }) {
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

export function QuestionCardsView({
  cards,
  onOpen,
  onOpenRequest,
}: {
  cards: QuestionCards;
  onOpen: (qid: string) => void;
  onOpenRequest: (id: string) => void;
}) {
  const empty = cards.requests.length === 0 && cards.items.length === 0 && cards.questions.length === 0;
  return (
    <section aria-label="Question cards" className="ask-cards">
      {empty && <p className="console-muted">No questions yet.</p>}
      {cards.requests.map((r) => (
        <article key={r.id} className="ask-card" data-kind="request">
          <button className="console-link ask-words" onClick={() => onOpenRequest(r.id)}>
            {r.words}
          </button>
          <p className="console-muted">
            {r.login} · {shortTime(r.asked_at)} · {addresseeLabel(r.addressed_to)}
          </p>
          <p>
            <span className="console-tag">{r.state}</span>
          </p>
          {r.runs_wait_for_signature && (
            <p className="console-muted">Every run from it waits for the person's signature.</p>
          )}
        </article>
      ))}
      {cards.items.map((i) => (
        <article key={i.item_id} className="ask-card" data-kind="item">
          <p className="console-link ask-words">{i.words}</p>
          <p className="console-muted">
            {i.login} · {shortTime(i.asked_at)} · {addresseeLabel(i.agent)}
            {i.question_id !== null && ` · ${i.question_id}`}
          </p>
          <p>
            <span className="console-tag">{i.state}</span>
          </p>
          {i.runs_wait_for_signature && (
            <p className="console-muted">Every run from it waits for the person's signature.</p>
          )}
          {i.latest_answer != null && (
            <ul aria-label="Latest answer" className="lib-answers">
              <AnswerItem a={i.latest_answer} />
            </ul>
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
          <QuestionStepsList q={q} />
        </article>
      ))}
    </section>
  );
}
