/** Question list, question detail with card tabs, versions and numbers (ui-spec 7.1). */

import { useEffect, useMemo, useState } from "react";

import { useClient } from "../../app/client";
import { AGENTS, type Card, PATHS, type QuestionDetail, type QuestionSummary } from "./api";
import { asArray, Fields, isRecord, Json, Loaded, shortTime, show, useLoad, versionLabel } from "./ui";

// --- list -----------------------------------------------------------------------------------

export function QuestionList({ questions, onOpen }: { questions: QuestionSummary[]; onOpen: (qid: string) => void }) {
  const [agent, setAgent] = useState("");
  const [status, setStatus] = useState("");
  const [from, setFrom] = useState("");
  const statuses = useMemo(
    () => [...new Set(questions.map((q) => q.status ?? "").filter((s) => s !== ""))].sort(),
    [questions],
  );
  const shown = questions.filter(
    (q) =>
      (agent === "" || q.agent === agent) &&
      (status === "" || q.status === status) &&
      (from === "" || (q.created_at ?? "") >= from),
  );
  return (
    <section aria-label="Questions">
      <div className="console-filters">
        <label>
          Agent{" "}
          <select value={agent} onChange={(e) => setAgent(e.target.value)}>
            <option value="">All</option>
            {AGENTS.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </label>
        <label>
          Status{" "}
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>
            {statuses.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label>
          Created from <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </label>
        <span className="console-muted">{shown.length} of {questions.length}</span>
      </div>
      <table className="console-table">
        <thead>
          <tr>
            <th>qid</th><th>Agent</th><th>Status</th><th>Title</th><th>Purpose</th><th>Intent</th>
            <th>Observable</th><th>Created</th><th>Updated</th><th>Latest</th><th>Source</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((q) => (
            <tr key={q.qid}>
              <td><button className="console-link" onClick={() => onOpen(q.qid)}>{q.qid}</button></td>
              <td>{q.agent}</td>
              <td>{q.status ?? "—"}</td>
              <td>{q.title}</td>
              <td>{q.purpose ?? "—"}</td>
              <td>{q.intent ?? "—"}</td>
              <td>{q.observable_name ?? "—"}</td>
              <td>{shortTime(q.created_at)}</td>
              <td>{shortTime(q.updated_at)}</td>
              <td>{versionLabel(q.latest_version)}</td>
              <td>{q.source}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {shown.length === 0 && <p className="console-muted">No questions match.</p>}
    </section>
  );
}

// --- detail ---------------------------------------------------------------------------------

export function cardsOf(d: QuestionDetail): Card[] {
  const one = (c: Card | null) => (c === null ? [] : [c]);
  return [...one(d.goal), ...d.axes, ...one(d.plan), ...one(d.synthesis), ...d.refusals, ...d.results, ...d.others];
}

export interface QuestionSelection {
  version: number;
  card_kind?: string;
}

export function QuestionDetailView({
  qid,
  refreshKey,
  onSelect,
}: {
  qid: string;
  refreshKey: number;
  onSelect: (sel: QuestionSelection) => void;
}) {
  const client = useClient();
  const [version, setVersion] = useState<number | undefined>(undefined);
  const [compare, setCompare] = useState<number | undefined>(undefined);
  const [tab, setTab] = useState<string | undefined>(undefined);
  const state = useLoad(() => client.get<QuestionDetail>(PATHS.question(qid, version)), [client, qid, version, refreshKey]);
  const other = useLoad(
    () => (compare === undefined ? Promise.resolve(undefined) : client.get<QuestionDetail>(PATHS.question(qid, compare))),
    [client, qid, compare, refreshKey],
  );

  const detail = state.data;
  const cards = detail === undefined ? [] : cardsOf(detail);
  const card = cards.find((c) => c.name === tab) ?? cards[0];
  const shownVersion = detail?.version;
  const kind = card?.kind;
  useEffect(() => {
    if (shownVersion !== undefined) onSelect({ version: shownVersion, card_kind: kind });
  }, [shownVersion, kind, onSelect]);

  return (
    <Loaded state={state}>
      {(d) => (
        <section aria-label={`Question ${d.summary.qid}`} className="console-detail">
          <header className="console-detail-head">
            <h2>{d.summary.qid}</h2>
            <span>{d.summary.agent}</span>
            <span className="console-status">{d.summary.status ?? "—"}</span>
            {d.summary.source !== "soft-matter-agents" && <span className="console-tag">{d.summary.source}</span>}
          </header>
          <p>{d.summary.title}</p>
          <div className="console-filters">
            <label>
              Version{" "}
              <select value={d.version} onChange={(e) => { setVersion(Number(e.target.value)); setTab(undefined); }}>
                {[...d.summary.versions].sort((a, b) => a - b).map((v) => (
                  <option key={v} value={v}>
                    {versionLabel(v)}{v === d.summary.latest_version ? " (latest)" : ""}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Compare with{" "}
              <select
                value={compare ?? ""}
                onChange={(e) => setCompare(e.target.value === "" ? undefined : Number(e.target.value))}
              >
                <option value="">—</option>
                {d.summary.versions.filter((v) => v !== d.version).map((v) => (
                  <option key={v} value={v}>{versionLabel(v)}</option>
                ))}
              </select>
            </label>
          </div>
          {compare !== undefined && (
            <Loaded state={other}>{(o) => (o === undefined ? null : <VersionDiff a={d} b={o} />)}</Loaded>
          )}
          {cards.length === 0 ? (
            <p className="console-muted">This version has no cards.</p>
          ) : (
            <>
              <div role="tablist" aria-label="Cards" className="console-tabs">
                {cards.map((c) => (
                  <button
                    key={c.name}
                    role="tab"
                    aria-selected={c === card}
                    onClick={() => setTab(c.name)}
                    title={c.name}
                  >
                    {cardTabLabel(c, cards)}
                  </button>
                ))}
              </div>
              {card !== undefined && <CardView card={card} />}
            </>
          )}
          <PlanApprovals detail={d} />
          {d.documents.map((doc) => (
            <details key={doc.name} className="console-json">
              <summary>{doc.name} <span className="console-tag">generated</span></summary>
              <pre>{doc.text}</pre>
            </details>
          ))}
          {d.files.length > 0 && (
            <p className="console-muted">Not opened: {d.files.map((f) => `${f.name} (${f.size} B)`).join(", ")}</p>
          )}
        </section>
      )}
    </Loaded>
  );
}

/** What the person approved for this question (approvals/), read only: the console writes none. */
export function PlanApprovals({ detail }: { detail: QuestionDetail }) {
  const approvals = detail.approvals ?? [];
  if (detail.plan_hash == null && approvals.length === 0) return null;
  return (
    <section aria-label="Approvals" className="console-approvals">
      {detail.plan_hash != null && (
        <p className="console-muted">
          Plan hash ({versionLabel(detail.version)}, status left out): <code>{detail.plan_hash}</code>
        </p>
      )}
      {approvals.length === 0 ? (
        <p className="console-muted">No approval in approvals/ names this question.</p>
      ) : (
        <ul>
          {approvals.map((a) => (
            <li key={a.name}>
              {a.id ?? a.name} · {a.status ?? "—"} by {a.approved_by ?? "—"} at {shortTime(a.approved_at)} ·{" "}
              {a.plan_hash !== null && a.plan_hash === detail.plan_hash
                ? "signs this version's plan"
                : a.plan_found === true
                  ? "signs another version's plan"
                  : a.plan_found === false
                    ? "signs a plan that is not in the question folder"
                    : "its question folder is not here"}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** "axis a7" for the second axis card, else the kind alone. */
function cardTabLabel(c: Card, all: Card[]): string {
  if (all.filter((x) => x.kind === c.kind).length < 2) return c.kind;
  const base = c.name.replace(/^v\d+_/, "").replace(/\.json$/, "");
  const tail = base.split("_").pop() ?? base;
  return `${c.kind} ${tail}`;
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
        <tr><th>Name</th><th>Value</th><th>Unit</th><th>Source</th><th>Grade</th><th>Precision</th></tr>
      </thead>
      <tbody>
        {rows.map((n, i) => (
          <tr key={`${show(n.name)}-${i}`}>
            <td>{show(n.name)}</td>
            <td>{show(n.value)}</td>
            <td>{show(n.unit)}</td>
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

// --- version diff ---------------------------------------------------------------------------

function baseName(c: Card): string {
  return c.name.replace(/^v\d+_/, "");
}

/** Which cards differ between two versions, and in which top-level fields. */
export function VersionDiff({ a, b }: { a: QuestionDetail; b: QuestionDetail }) {
  const left = new Map(cardsOf(a).map((c) => [baseName(c), c]));
  const right = new Map(cardsOf(b).map((c) => [baseName(c), c]));
  const names = [...new Set([...left.keys(), ...right.keys()])].sort();
  const la = versionLabel(a.version);
  const lb = versionLabel(b.version);
  return (
    <table className="console-table" aria-label={`Changes ${la} to ${lb}`}>
      <thead>
        <tr><th>Card</th><th>{la} → {lb}</th></tr>
      </thead>
      <tbody>
        {names.map((n) => {
          const x = left.get(n);
          const y = right.get(n);
          let what: string;
          if (x === undefined) what = `only in ${lb}`;
          else if (y === undefined) what = `only in ${la}`;
          else {
            const changed = changedKeys(x.data, y.data);
            what = changed.length === 0 ? "same" : `changed: ${changed.join(", ")}`;
          }
          return <tr key={n}><td>{n}</td><td>{what}</td></tr>;
        })}
      </tbody>
    </table>
  );
}

export function changedKeys(x: unknown, y: unknown): string[] {
  if (!isRecord(x) || !isRecord(y)) return JSON.stringify(x) === JSON.stringify(y) ? [] : ["(whole card)"];
  const keys = [...new Set([...Object.keys(x), ...Object.keys(y)])].sort();
  return keys.filter((k) => JSON.stringify(x[k]) !== JSON.stringify(y[k]));
}
