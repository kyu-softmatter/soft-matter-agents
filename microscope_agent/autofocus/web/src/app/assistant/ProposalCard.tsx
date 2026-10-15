import { useCallback, useState } from "react";

import { type EventOut, useEngineEvents } from "../client";
import { FocusVerdict } from "../Verdict";
import type { Proposal } from "./api";

/** The permission name the server checks for this command (T-013 tools.required_permission). */
export function commandOp(p: Proposal): string {
  return p.command.op || p.command.kind;
}

function ModelTag() {
  return (
    <span className="pb-grade" title="Written by the model, not measured">
      model
    </span>
  );
}

function ArgValue({ name, value }: { name: string; value: unknown }) {
  if (name === "verdict") return <FocusVerdict verdict={value} source="model" />;
  return (
    <>
      <code>{typeof value === "string" ? value : JSON.stringify(value)}</code> <ModelTag />
    </>
  );
}

function Gate({ gate }: { gate: Proposal["expected_gate"] }) {
  if (!gate.checked)
    return <p className="muted">Gate: not checked ({gate.reasons.join("; ") || "no reason given"})</p>;
  return (
    <p className={gate.enabled ? undefined : "pb-warn"}>
      Gate now: {gate.enabled ? "open" : "closed"}
      {gate.reasons.length > 0 && ` (${gate.reasons.join("; ")})`}
      <span className="muted"> · the engine checks again when it runs</span>
    </p>
  );
}

/** One proposed command. Nothing runs until a person confirms; the engine still decides. */
export function ProposalCard({
  proposal,
  blocked,
  onConfirm,
  onReject,
}: {
  proposal: Proposal;
  /** why Confirm and Reject are off (read-only, permission), or null */
  blocked: string | null;
  onConfirm: () => Promise<void>;
  onReject: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string | null>(null);

  const onEvent = useCallback(
    (ev: EventOut) => {
      if (proposal.op_id && ev.op_id === proposal.op_id) setProgress(ev.kind);
    },
    [proposal.op_id],
  );
  useEngineEvents(onEvent);

  const act = (fn: () => Promise<void>) => async () => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const args = Object.entries(proposal.command.args ?? {});
  const open = proposal.status === "proposed";
  return (
    <article className="pb-card" aria-label={`Proposal: ${proposal.summary}`}>
      <header>
        <strong>Proposed: {proposal.summary}</strong>
        <span className="muted"> · {proposal.status}</span>
      </header>
      <p>
        Command <code>{commandOp(proposal)}</code>
        {args.length > 0 && " with"}
      </p>
      {args.length > 0 && (
        <ul className="pb-args">
          {args.map(([k, v]) => (
            <li key={k}>
              {k}: <ArgValue name={k} value={v} />
            </li>
          ))}
        </ul>
      )}
      {proposal.reason && (
        <p>
          Why: {proposal.reason} <ModelTag />
        </p>
      )}
      <Gate gate={proposal.expected_gate} />
      {open && (
        <div className="pb-actions">
          <button type="button" disabled={busy || blocked !== null} onClick={act(onConfirm)}>
            Confirm
          </button>
          <button type="button" disabled={busy || blocked !== null} onClick={act(onReject)}>
            Reject
          </button>
          {blocked && <span className="muted pb-blocked">{blocked}</span>}
        </div>
      )}
      {proposal.status === "confirmed" && (
        <p role="status">
          Sent to the engine{proposal.op_id ? ` as ${proposal.op_id}` : ""}
          {progress ? `: ${progress}` : ""}.
        </p>
      )}
      {proposal.status === "rejected" && <p role="status">Rejected{proposal.note ? `: ${proposal.note}` : ""}.</p>}
      {proposal.status === "failed" && <p role="alert">Could not be sent: {proposal.note || "unknown reason"}.</p>}
      {error && (
        <p className="pb-warn" role="alert">
          {error}
        </p>
      )}
    </article>
  );
}
