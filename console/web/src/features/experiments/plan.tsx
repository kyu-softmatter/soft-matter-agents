/**
 * The Plan page (console card 014): every plan on disk with where it stands, the runs with how they ended,
 * and the draft composer from the Instruments screens. It reads files and sends nothing to a runtime: Run
 * is offered on an approved plan and answers "not built yet". A hand step at the microscope is shown and
 * never confirmed from here.
 */

import { useState } from "react";

import { useClient } from "../../app/client";
import { PartDraft } from "../instruments/optics";
import { TrapDraft } from "../instruments/tweezers";
import { PiezoDraft } from "../instruments/piezoDraft";
import { errorText, Loaded, shortTime, useLoad } from "../questions/ui";
import { askRun, type PlanOut, PATHS, type PlansOut, type RunNotBuiltOut, type RunOut } from "./api";

export function ExampleNote({ note }: { note: string | null }) {
  return note === null ? null : (
    <p role="note" className="console-muted exp-example">
      <span className="console-tag">example data</span> {note}
    </p>
  );
}

function approvalCell(p: PlanOut): string {
  if (p.approval === null) return "no approval on disk";
  const a = p.approval;
  return [a.signed_words, a.approved_by, a.approved_at ? shortTime(a.approved_at) : null].filter((x) => x).join(", ");
}

function RunOffer({ plan }: { plan: PlanOut }) {
  const client = useClient();
  const [answer, setAnswer] = useState<RunNotBuiltOut | undefined>(undefined);
  const [error, setError] = useState<string | undefined>(undefined);
  const offer = plan.run_offer;
  if (!offer.offered) return <span className="console-muted">{offer.why_not}</span>;
  async function press() {
    setError(undefined);
    setAnswer(undefined);
    try {
      setAnswer(await askRun(client, plan.plan_id, plan.revision ?? 0));
    } catch (e) {
      setError(errorText(e));
    }
  }
  return (
    <>
      <button type="button" onClick={() => void press()}>Run</button> <span className="console-tag">not built yet</span>
      {answer !== undefined && (
        <div role="status" aria-label={`Run ${plan.plan_id}`}>
          <p>{answer.message}</p>
          <p className="console-muted">Would send: {JSON.stringify(answer.would_send)}</p>
        </div>
      )}
      {error !== undefined && <p role="alert" className="console-error">{error}</p>}
    </>
  );
}

function Plans({ plans }: { plans: PlanOut[] }) {
  if (plans.length === 0) return <p>No plan on disk.</p>;
  return (
    <>
      <table className="console-table" aria-label="Plans">
        <thead>
          <tr><th>Plan</th><th>Revision</th><th>State</th><th>Approval</th><th>Runs</th><th>Run</th></tr>
        </thead>
        <tbody>
          {plans.map((p) => (
            <tr key={`${p.qid}/${p.version}/${p.plan_id}/${p.revision}`}>
              <td>{p.plan_id}</td>
              <td>{p.revision ?? "none"}</td>
              <td>{p.state_words}</td>
              <td>{approvalCell(p)}</td>
              <td>{p.run_ids.length > 0 ? p.run_ids.join(", ") : "none"}</td>
              <td><RunOffer plan={p} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      {plans.filter((p) => p.void_approvals.length > 0).map((p) => (
        <ul key={p.plan_id} aria-label={`Approvals that do not cover ${p.plan_id}`}>
          {p.void_approvals.map((v) => (
            <li key={v.name}>{v.name}: {v.why}</li>
          ))}
        </ul>
      ))}
    </>
  );
}

function RunRow({ run }: { run: RunOut }) {
  return (
    <section aria-label={`Run ${run.run_id}`} className="exp-run">
      <h4>{run.run_id}</h4>
      <p>
        {run.plan_id !== null ? `Plan ${run.plan_id}` : "No plan named"}
        {run.plan_id !== null && !run.plan_on_disk && " (that plan is not on disk)"}
      </p>
      <p>{run.state === "running" ? "running now" : run.how_words ?? "ended; how is not recorded"}</p>
      <p className="console-muted">
        Started {shortTime(run.started_at)}{run.finished_at !== null ? `, ended ${shortTime(run.finished_at)}` : ""}
      </p>
      {run.approval !== null && <p>{run.approval.signed_words}</p>}
      {run.refusal !== null && <p>Refused: {run.refusal}</p>}
      <p>{run.events.words}</p>
      {run.waiting_line !== null && <p role="status" className="exp-waiting">{run.waiting_line}</p>}
      {run.tweezers_note !== null && <p role="note">{run.tweezers_note}</p>}
      {run.hand_steps.length > 0 && (
        <ul aria-label="Hand steps">
          {run.hand_steps.map((s) => (
            <li key={s.sheet_id}>
              {s.channel}{s.element ? ` / ${s.element}` : ""}: {s.instruction}
              {s.confirmed
                ? ` — confirmed by ${s.confirmed_by ?? "unknown"}, ${shortTime(s.confirmed_at)}${s.observed ? `; observed: ${s.observed}` : ""}`
                : " — not confirmed yet"}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

type Kind = "trap_steps" | "camera_exposure" | "piezo";
const KINDS: { id: Kind; label: string }[] = [
  { id: "trap_steps", label: "Trap pattern" },
  { id: "camera_exposure", label: "Camera red arm exposure" },
  { id: "piezo", label: "Piezo stage" },
];

/** The Instruments composer, reused: every draft is shown and saved nowhere. */
function Composer() {
  const [kind, setKind] = useState<Kind>("trap_steps");
  return (
    <section aria-label="Draft a plan">
      <h4>Draft a plan</h4>
      <label className="inst-field">
        Kind of draft
        <select value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
          {KINDS.map((k) => (
            <option key={k.id} value={k.id}>{k.label}</option>
          ))}
        </select>
      </label>
      {kind === "trap_steps" && <TrapDraft />}
      {kind === "camera_exposure" && (
        <PartDraft key={kind} kind={kind} label={KINDS.find((k) => k.id === kind)?.label ?? kind} />
      )}
      {kind === "piezo" && <PiezoDraft />}
    </section>
  );
}

export function Plan() {
  const client = useClient();
  const state = useLoad(() => client.get<PlansOut>(PATHS.plans), [client]);
  return (
    <Loaded state={state}>
      {(d) => (
        <>
          <ExampleNote note={d.example_note} />
          {d.problems.length > 0 && (
            <ul aria-label="Problems reading the files" className="console-error">
              {d.problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
          <section aria-label="Plans on disk">
            <h3>Plans</h3>
            <Plans plans={d.plans} />
          </section>
          <section aria-label="Runs on disk">
            <h3>Runs</h3>
            {d.runs.length === 0 ? <p>No run on disk.</p> : d.runs.map((r) => <RunRow key={r.run_id} run={r} />)}
          </section>
          <section aria-label="Drafts">
            <h3>Drafts waiting for a signature</h3>
            <p className="console-muted">{d.drafts_note}</p>
            <Composer />
          </section>
        </>
      )}
    </Loaded>
  );
}
