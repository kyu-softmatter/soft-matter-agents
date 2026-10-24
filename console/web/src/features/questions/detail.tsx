/**
 * One question (console card 011; `PQuestionDetail`): the question verbatim, who asked and when, the
 * five steps, a summary put together from the cards, a box for a plan waiting for a signature, and
 * every card made from the question, one row each, opening on a click to its main fields.
 *
 * Nothing here writes. The Sign button shows only to the login the console's settings name as the
 * person's own, and the dialog behind it checks a password and writes nothing (`sign.tsx`).
 */

import { useEffect, useMemo, useState } from "react";

import { useClient } from "../../app/client";
import {
  type Card,
  type InboxThread,
  PATHS,
  type QuestionCards,
  type QuestionDetail,
  type RequestCard,
  type RunSummary,
  type SigningState,
} from "./api";
import { QuestionStepsList } from "./cards";
import { approvalSays, CardView, isSigned, writtenByAssistant } from "./questions";
import { actionsOf, SignDialog } from "./sign";
import { asArray, Fields, isRecord, Loaded, shortTime, show, useLoad, versionLabel } from "./ui";

const ASSISTANT = "Written by the assistant";

function AssistantTag() {
  return <span className="console-tag"> {ASSISTANT}</span>;
}

/** The question exactly as the goal card holds it: its own words, else the person's note, else the title. */
export function questionWords(d: QuestionDetail): string {
  const data = d.goal !== null && isRecord(d.goal.data) ? d.goal.data : {};
  const notes = asArray(data.constraint_notes);
  return show(data.question ?? (typeof notes[0] === "string" ? notes[0] : undefined) ?? d.summary.title);
}

interface RowSpec {
  key: string;
  label: string;
  tag?: string | null;
  assistant?: boolean;
  body: () => React.ReactNode;
}

function planLabel(c: Card): string {
  const data = isRecord(c.data) ? c.data : {};
  return `Plan · revision ${show(data.revision ?? c.version)}`;
}

/** Every card made from the question, as one row each. */
export function rowsOf(d: QuestionDetail, runs: RunSummary[], threads: InboxThread[]): RowSpec[] {
  const rows: RowSpec[] = [];
  const card = (c: Card, label: string) =>
    rows.push({
      key: c.name, label, tag: c.status, assistant: writtenByAssistant(c), body: () => <CardView card={c} />,
    });
  if (d.goal !== null) card(d.goal, "Goal");
  for (const a of d.axes) card(a, `Design · ${a.name.replace(/^v\d+_/, "").replace(/\.json$/, "").split("_").pop()}`);
  if (d.synthesis !== null) card(d.synthesis, "Synthesis");
  for (const c of [d.plan, ...d.others.filter((o) => o.kind === "plan")]) if (c !== null) card(c, planLabel(c));
  for (const c of d.refusals) card(c, "Refusal");
  for (const a of d.approvals ?? []) {
    rows.push({
      key: `approval:${a.name}`, label: `Approval · revision ${a.revision ?? "—"}`, tag: a.status,
      body: () => (
        <>
          <Fields
            obj={{ approved_by: a.approved_by, approved_at: shortTime(a.approved_at), plan_hash: a.plan_hash, says: approvalSays(a, d) }}
            keys={["approved_by", "approved_at", "plan_hash", "says"]}
          />
        </>
      ),
    });
  }
  for (const r of runs) {
    rows.push({
      key: `run:${r.run_id}`, label: `Run · ${r.run_id}`, tag: r.status,
      body: () => (
        <Fields
          obj={{ status: r.status, backend: r.backend, started: shortTime(r.created_at), finished: shortTime(r.finished_at) }}
          keys={["status", "backend", "started", "finished"]}
        />
      ),
    });
  }
  for (const c of d.results) card(c, `Result · ${c.name.replace(/^v\d+_/, "").replace(/^result_/, "").replace(/\.json$/, "")}`);
  for (const c of d.others.filter((o) => o.kind !== "plan")) card(c, `Other card · ${c.kind}`);
  for (const t of threads) {
    for (const m of t.messages) {
      rows.push({
        key: `bridge:${t.thread}:${m.name}`, label: `Bridge · round ${m.round ?? "—"} · ${m.kind.replace(/_/g, " ")}`,
        body: () => (m.card !== null ? <CardView card={{ name: m.name, kind: m.kind, version: m.round ?? 1, status: null, created_at: null, data: m.card }} /> : <pre className="console-text">{m.text ?? "(not readable)"}</pre>),
      });
    }
  }
  return rows;
}

function Row({ spec }: { spec: RowSpec }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="ask-row">
      <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        {spec.label}
        {spec.tag != null && <span className="console-tag"> {spec.tag}</span>}
        {spec.assistant === true && <AssistantTag />}
      </button>
      {open && <div className="ask-row-body">{spec.body()}</div>}
    </li>
  );
}

/** The summary: only what the cards say, labelled as put together from them. */
function Summary({ d }: { d: QuestionDetail }) {
  const data = d.goal !== null && isRecord(d.goal.data) ? d.goal.data : {};
  const steps = actionsOf(d.plan);
  const observable = isRecord(data.observable) ? data.observable.name : undefined;
  return (
    <section aria-label="Summary" className="ask-summary">
      <h3>Summary</h3>
      <p className="console-muted">Put together from the cards' fields. Nobody wrote it.</p>
      <Fields obj={{ purpose: data.purpose, observable }} keys={["purpose", "observable"]} />
      {writtenByAssistant(d.goal) && (
        <p>
          <AssistantTag /> (the goal)
        </p>
      )}
      {steps.length > 0 && (
        <>
          <h4>The plan's steps</h4>
          <ol>
            {steps.map((s) => (
              <li key={s.id}>
                {s.device} · {s.action}
              </li>
            ))}
          </ol>
          {writtenByAssistant(d.plan) && (
            <p>
              <AssistantTag /> (the plan)
            </p>
          )}
        </>
      )}
    </section>
  );
}

function PlanBox({
  d,
  state,
  practice,
  onSign,
}: {
  d: QuestionDetail;
  state: SigningState | undefined;
  practice: boolean;
  onSign: () => void;
}) {
  if (d.plan === null || d.plan_hash === null || isSigned(d)) return null;
  return (
    <section aria-label="Plan waiting for a signature" className="ask-plan-box">
      <h3>A plan is waiting for a signature</h3>
      {practice ? (
        <p>Signed (practice): nothing was written.</p>
      ) : state === undefined ? null : state.is_person ? (
        <button type="button" onClick={onSign}>
          Review and sign
        </button>
      ) : !state.person_named ? (
        <p>The person's login is not named yet, so no one can sign.</p>
      ) : (
        <p>Waits for the person's signature.</p>
      )}
    </section>
  );
}

export function QuestionPage({
  qid,
  refreshKey,
  onSelect,
}: {
  qid: string;
  refreshKey: number;
  onSelect: (version: number) => void;
}) {
  const client = useClient();
  const [version, setVersion] = useState<number | undefined>(undefined);
  const [signing, setSigning] = useState(false);
  const [practice, setPractice] = useState(false);
  const detail = useLoad(() => client.get<QuestionDetail>(PATHS.question(qid, version)), [client, qid, version, refreshKey]);
  const cards = useLoad(() => client.get<QuestionCards>(PATHS.questionCards), [client, refreshKey]);
  const runs = useLoad(() => client.get<RunSummary[]>(PATHS.runs()), [client, refreshKey]);
  const inbox = useLoad(() => client.get<InboxThread[]>(PATHS.inbox), [client, refreshKey]);
  const state = useLoad(() => client.get<SigningState>(PATHS.signing), [client, refreshKey]);

  const shown = detail.data?.version;
  useEffect(() => {
    if (shown !== undefined) onSelect(shown);
  }, [shown, onSelect]);

  const rows = useMemo(() => {
    const d = detail.data;
    if (d === undefined) return [];
    const thread = d.goal !== null && isRecord(d.goal.data) ? d.goal.data.thread : undefined;
    const mine = (runs.data ?? []).filter((r) => r.qid === qid);
    const threads = typeof thread === "string" ? (inbox.data ?? []).filter((t) => t.thread === thread) : [];
    return rowsOf(d, mine, threads);
  }, [detail.data, runs.data, inbox.data, qid]);

  return (
    <Loaded state={detail}>
      {(d) => {
        const mine = cards.data?.questions.find((q) => q.qid === qid);
        const data = d.goal !== null && isRecord(d.goal.data) ? d.goal.data : {};
        return (
          <section aria-label={`Question ${d.summary.qid}`} className="console-detail">
            <header className="console-detail-head">
              <h2 className="ask-words">{questionWords(d)}</h2>
              {writtenByAssistant(d.goal) && <AssistantTag />}
            </header>
            <p className="console-muted">
              Asked by {show(data.requested_by ?? data.author ?? "—")} · {shortTime(d.goal?.created_at ?? d.summary.created_at)} ·{" "}
              {d.summary.agent}
              {d.summary.source !== "soft-matter-agents" && <span className="console-tag">{d.summary.source}</span>}
            </p>
            {mine !== undefined && <QuestionStepsList q={mine} />}
            {d.summary.versions.length > 1 && (
              <label>
                Version{" "}
                <select value={d.version} onChange={(e) => setVersion(Number(e.target.value))}>
                  {[...d.summary.versions].sort((a, b) => a - b).map((v) => (
                    <option key={v} value={v}>
                      {versionLabel(v)}
                      {v === d.summary.latest_version ? " (latest)" : ""}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <Summary d={d} />
            <PlanBox d={d} state={state.data} practice={practice} onSign={() => setSigning(true)} />
            <ul aria-label="Cards made from this question" className="ask-rows">
              {rows.map((r) => (
                <Row key={r.key} spec={r} />
              ))}
            </ul>
            {rows.length === 0 && <p className="console-muted">This version has no cards.</p>}
            {signing && state.data !== undefined && (
              <SignDialog
                detail={d}
                state={state.data}
                onClose={() => setSigning(false)}
                onPractice={() => setPractice(true)}
              />
            )}
          </section>
        );
      }}
    </Loaded>
  );
}

/** A request written in the console, opened: nothing has started, and no run starts without the person's signature. */
export function RequestPage({ id, cards }: { id: string; cards: RequestCard[] }) {
  const r = cards.find((c) => c.id === id);
  if (r === undefined) return <p className="console-muted">No such request.</p>;
  return (
    <section aria-label="Question request" className="console-detail">
      <h2 className="ask-words">{r.words}</h2>
      <p className="console-muted">
        Asked by {r.login} · {shortTime(r.asked_at)} · {r.addressed_to.replace(/_/g, " ")}
      </p>
      <p>
        <span className="console-tag">{r.state}</span>
      </p>
      <p>Nothing has started: no agent has picked this up yet.</p>
      {r.runs_wait_for_signature && <p className="console-muted">Every run from it waits for the person's signature.</p>}
    </section>
  );
}
