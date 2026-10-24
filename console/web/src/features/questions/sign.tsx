/**
 * The sign dialog (console card 011, plan.md 6.1, 15.1; `PSign`). It shows the plan, its steps, its
 * light and what cannot be undone, and the full fingerprint (the sha256 of the plan card with `status`
 * removed, as `contracts/validate.py`'s `card_sha` and a plan_approval's `plan_hash` have it). The
 * password is typed again and never pre-filled.
 *
 * **Sign checks the password at the server and writes nothing.** The part that writes an approval into
 * `microscope_runtime/approvals/` is part of the person's guard and waits for the person's OK, so the
 * answer is that signing is not built yet. With the mock store a practice login is shown as signed.
 * Without that folder in the tree the console reads, nothing can be signed and no other place is offered.
 */

import { type FormEvent, useRef, useState } from "react";

import { useClient } from "../../app/client";
import { type Card, type QuestionDetail, signCheck, type SignCheck, type SigningState } from "./api";
import { asArray, errorText, isRecord, provenanceWord, show } from "./ui";

export const NO_FOLDER_SENTENCE =
  "Nothing can be signed here: the folder microscope_runtime/approvals/ is not in the tree this console reads, and no other place is used.";

interface Action {
  id: string;
  device: string;
  action: string;
  reversible: boolean;
}

/** The plan card's actions, as far as each is a record with a device and an action. */
export function actionsOf(plan: Card | null): Action[] {
  const data = plan !== null && isRecord(plan.data) ? plan.data : {};
  return asArray(data.actions)
    .filter(isRecord)
    .map((a, i) => ({
      id: show(a.id ?? `step ${i + 1}`),
      device: show(a.device),
      action: show(a.action),
      reversible: a.reversible === true, // an action that does not say it is reversible is not trusted to be
    }));
}

/** One device a plan touches, and what the plan sets on it, line by line. */
export interface DeviceTouched {
  device: string;
  lines: string[];
}

/**
 * Every device the plan touches, with the value the plan sets (console card 012, step 0). It does not
 * decide what a device is for from how its name is written -- that is a role the registry gives, and a
 * light named another way would have been left out, which is the unsafe direction. A device is here
 * because an action, a condition, an operation or a trap step names it.
 */
export function devicesTouched(plan: Card | null): DeviceTouched[] {
  const data = plan !== null && isRecord(plan.data) ? plan.data : {};
  const numbers = new Map<string, string>();
  for (const n of asArray(data.numbers).filter(isRecord)) {
    numbers.set(show(n.name), `${show(n.value)} ${show(n.unit)} (${provenanceWord(n.source)})`.replace("  ", " "));
  }
  const order: string[] = [];
  const lines = new Map<string, string[]>();
  const touch = (device: unknown, line?: string) => {
    const name = show(device);
    if (!lines.has(name)) {
      lines.set(name, []);
      order.push(name);
    }
    if (line !== undefined && !lines.get(name)!.includes(line)) lines.get(name)!.push(line);
  };
  const setting = (name: unknown) => `${show(name)}: ${numbers.get(show(name)) ?? "no value given in the plan"}`;
  for (const a of asArray(data.actions).filter(isRecord)) {
    touch(a.device, `${show(a.action)}${a.reversible === true ? "" : " (cannot be undone)"}`);
    for (const p of asArray(a.parameters)) touch(a.device, setting(p));
  }
  for (const c of asArray(data.conditions).filter(isRecord)) {
    if (c.device !== undefined) touch(c.device, setting(c.number ?? c.parameter));
  }
  const op = isRecord(data.operation) ? data.operation : undefined;
  if (op !== undefined) {
    touch(op.device);
    for (const m of asArray(op.moves).filter(isRecord)) {
      touch(op.device, `${show(m.kind)} ${show(m.axis)} to ${show(m.target_um)} um (${show(m.role)})`);
    }
  }
  const traps = isRecord(data.trap_steps) ? data.trap_steps : undefined;
  if (traps !== undefined) {
    touch(traps.device);
    for (const s of asArray(traps.steps).filter(isRecord)) {
      const where = s.x_um !== undefined ? ` at ${show(s.x_um)}, ${show(s.y_um)} um` : "";
      const strength = s.strength !== undefined ? `, strength ${show(s.strength)}` : "";
      touch(traps.device, `${show(s.kind)} ${show(s.trap ?? "")}${where}${strength}`.replace("  ", " ").trim());
    }
  }
  return order.map((device) => ({ device, lines: lines.get(device) ?? [] }));
}

export function SignDialog({
  detail,
  state,
  onClose,
  onPractice,
}: {
  detail: QuestionDetail;
  state: SigningState;
  onClose: () => void;
  /** a practice login was shown as signed: nothing was written */
  onPractice: () => void;
}) {
  const client = useClient();
  const plan = detail.plan;
  const data = plan !== null && isRecord(plan.data) ? plan.data : {};
  const steps = actionsOf(plan);
  const devices = devicesTouched(plan);
  const irreversible = steps.filter((s) => !s.reversible);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  const [done, setDone] = useState<SignCheck | undefined>(undefined);
  const typed = useRef("");

  async function sign(e: FormEvent) {
    e.preventDefault();
    if (busy || password === "" || detail.plan_hash == null) return;
    typed.current = password;
    setBusy(true);
    setError(undefined);
    setDone(undefined);
    try {
      const r = await signCheck(client, { qid: detail.summary.qid, plan_hash: detail.plan_hash, password: typed.current });
      setDone(r);
      if (r.outcome === "practice_signed") onPractice();
    } catch (err) {
      setError(errorText(err));
    } finally {
      typed.current = "";
      setPassword(""); // never kept: it is typed again at every signature
      setBusy(false);
    }
  }

  return (
    <div role="dialog" aria-modal="true" aria-label="Sign the plan" className="sign-dialog">
      <h2>Sign the plan</h2>
      <p>
        {show(data.purpose ?? detail.summary.title)}
        {" · "}revision {show(data.revision ?? "—")}
      </p>
      <fieldset aria-label="Steps">
        <legend>Steps</legend>
        {steps.length === 0 ? (
          <p className="console-muted">The plan lists no steps.</p>
        ) : (
          <ol>
            {steps.map((s) => (
              <li key={s.id}>
                {s.device} · {s.action}
                {!s.reversible && <span className="console-tag"> cannot be undone</span>}
              </li>
            ))}
          </ol>
        )}
      </fieldset>
      <fieldset aria-label="Devices this plan touches">
        <legend>Devices this plan touches, and what it sets</legend>
        {devices.length === 0 ? (
          <p className="console-muted">The plan names no device.</p>
        ) : (
          <ul>
            {devices.map((d) => (
              <li key={d.device}>
                {d.device}
                {d.lines.length > 0 && (
                  <ul>
                    {d.lines.map((l) => (
                      <li key={l}>{l}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        )}
      </fieldset>
      <fieldset aria-label="What cannot be undone">
        <legend>What cannot be undone</legend>
        {irreversible.length === 0 ? (
          <p>Nothing in this plan is irreversible.</p>
        ) : (
          <ul>
            {irreversible.map((s) => (
              <li key={s.id}>
                {s.device} · {s.action}
              </li>
            ))}
          </ul>
        )}
      </fieldset>
      <p>
        Fingerprint (the plan card with its status left out):
        <br />
        <code data-testid="fingerprint">{detail.plan_hash ?? "—"}</code>
      </p>
      {!state.approvals_folder ? (
        <p role="alert" className="console-error">
          {NO_FOLDER_SENTENCE}
        </p>
      ) : (
        <form aria-label="Sign" onSubmit={sign}>
          <label>
            Your password, again
            <input
              type="password"
              value={password}
              autoComplete="off"
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <button type="submit" disabled={busy || password === ""}>
            Sign
          </button>
          {error !== undefined && (
            <p role="alert" className="console-error">
              {error}
            </p>
          )}
          {done !== undefined && <p role="status">{done.message}</p>}
        </form>
      )}
      <p>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </p>
    </div>
  );
}
