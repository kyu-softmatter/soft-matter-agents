/** The pieces a question's cards are drawn with: a card's main fields, its numbers with their words (ui-spec 7.1). */

import type { Approval, Card, QuestionDetail } from "./api";
import { asArray, Fields, isRecord, Json, provenanceWord, show, versionLabel } from "./ui";

export function cardsOf(d: QuestionDetail): Card[] {
  const one = (c: Card | null) => (c === null ? [] : [c]);
  return [...one(d.goal), ...d.axes, ...one(d.plan), ...one(d.synthesis), ...d.refusals, ...d.results, ...d.others];
}

/** What an approval says about the plan it names, in words (read only: the console writes none). */
export function approvalSays(a: Approval, detail: QuestionDetail): string {
  if (a.plan_hash !== null && a.plan_hash === detail.plan_hash) return "signs this version's plan";
  if (a.plan_found === true) return "signs another version's plan";
  if (a.plan_found === false) return "signs a plan that is not in the question folder";
  return "its question folder is not here";
}

/** True when an approval card of this plan's fingerprint says APPROVED: a draft is not a signature. */
export function isSigned(detail: QuestionDetail): boolean {
  return (
    detail.plan_hash != null &&
    (detail.approvals ?? []).some((a) => a.plan_hash === detail.plan_hash && (a.status ?? "").toUpperCase() === "APPROVED")
  );
}

/** Whether the assistant wrote a card (its author or origin says so): such text is labelled as the assistant's. */
export function writtenByAssistant(card: Card | null): boolean {
  if (card === null || !isRecord(card.data)) return false;
  return /assistant/i.test(String(card.data.author ?? "")) || /assistant/i.test(String(card.data.origin ?? ""));
}

export function CardView({ card }: { card: Card }) {
  const data = isRecord(card.data) ? card.data : {};
  const degraded = asArray(data.degraded);
  return (
    <article aria-label={`Card ${card.name}`} className="console-card">
      {degraded.length > 0 && (
        <div role="alert" className="console-degraded">
          Degraded: {degraded.map(show).join("; ")}
        </div>
      )}
      <Fields obj={{ file: card.name, version: versionLabel(card.version), status: card.status, created_at: card.created_at }}
              keys={["file", "version", "status", "created_at"]} />
      <Fields obj={data} keys={["purpose", "intent", "stage", "reason_code", "verdict"]} />
      {isRecord(data.observable) && <Fields obj={{ observable: data.observable.name }} keys={["observable"]} />}
      <NumbersTable numbers={asArray(data.numbers)} />
      <Assumptions data={data} />
      <Json label="Card JSON" value={card.data} />
    </article>
  );
}

/** The card's numbers as written. The grade is the card's own value; the screen never re-grades. */
export function NumbersTable({ numbers }: { numbers: unknown[] }) {
  const rows = numbers.filter(isRecord);
  if (rows.length === 0) return null;
  return (
    <table className="console-table" aria-label="Numbers">
      <thead>
        <tr><th>Name</th><th>Value</th><th>Unit</th><th>How it is known</th><th>Source</th><th>Grade</th><th>Precision</th></tr>
      </thead>
      <tbody>
        {rows.map((n, i) => (
          <tr key={`${show(n.name)}-${i}`}>
            <td>{show(n.name)}</td>
            <td>{show(n.value)}</td>
            <td>{show(n.unit)}</td>
            <td>{provenanceWord(n.source)}</td>
            <td>{show(n.source)}</td>
            <td><GradeBadge grade={n.grade} /></td>
            <td>{show(n.precision)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function GradeBadge({ grade }: { grade: unknown }) {
  if (grade === undefined || grade === null) return <span className="console-muted">—</span>;
  const g = show(grade);
  const known = /^E[1-5]$/.test(g);
  return (
    <span className={`console-grade ${known ? `console-grade-${g}` : "console-grade-other"}`} title="grade as written on the card">
      {g}
    </span>
  );
}

function Assumptions({ data }: { data: Record<string, unknown> }) {
  const assumptions = asArray(data.assumptions).filter(isRecord);
  const refs = asArray(data.kb_refs).filter(isRecord);
  const gaps = asArray(data.kb_gaps).filter(isRecord);
  if (assumptions.length + refs.length + gaps.length === 0) return null;
  return (
    <div className="console-assumptions">
      {assumptions.length > 0 && (
        <>
          <h3>Assumptions</h3>
          <ul>
            {assumptions.map((a, i) => (
              <li key={i}>
                {show(a.statement)} <span className="console-muted">authorised by {show(a.authorised_by)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {refs.length > 0 && (
        <>
          <h3>Knowledge refs</h3>
          <ul>
            {refs.map((r, i) => (
              <li key={i}>
                {show(r.entry_id)} <GradeBadge grade={r.grade} /> {show(r.claim)}
              </li>
            ))}
          </ul>
        </>
      )}
      {gaps.length > 0 && (
        <>
          <h3>Knowledge gaps</h3>
          <ul>
            {gaps.map((g, i) => (
              <li key={i}>{show(g.gap_id)} ({show(g.kind)}, {show(g.observable)})</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
