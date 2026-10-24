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

const LIGHT_DEVICE = /lamp|led|laser|light|illum|lumin/i;
const LIGHT_NUMBER = /power|illumination|laser|intensity|exposure/i;

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

/** The light the plan uses: the light sources among its devices, and the numbers named for light. */
export function lightOf(plan: Card | null): { devices: string[]; numbers: { name: string; text: string }[] } {
  const data = plan !== null && isRecord(plan.data) ? plan.data : {};
  const config = isRecord(data.system_configuration) ? data.system_configuration : {};
  const names = new Set<string>([
    ...asArray(config.devices).map(show),
    ...actionsOf(plan).map((a) => a.device),
  ]);
  const numbers = asArray(data.numbers)
    .filter(isRecord)
    .filter((n) => LIGHT_NUMBER.test(show(n.name)))
    .map((n) => ({ name: show(n.name), text: `${show(n.value)} ${show(n.unit)} (${provenanceWord(n.source)})` }));
  return { devices: [...names].filter((d) => LIGHT_DEVICE.test(d)), numbers };
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
  const light = lightOf(plan);
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
      <fieldset aria-label="Light">
        <legend>Light</legend>
        {light.devices.length === 0 && light.numbers.length === 0 ? (
          <p className="console-muted">No light source is used.</p>
        ) : (
          <ul>
            {light.devices.map((d) => (
              <li key={d}>{d}</li>
            ))}
            {light.numbers.map((n) => (
              <li key={n.name}>
                {n.name}: {n.text}
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
