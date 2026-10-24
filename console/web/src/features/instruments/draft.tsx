/**
 * Plan drafts on the Instruments screens (console card 012). A draft is an ordinary plan card, built by the
 * server from what the person chose and checked against `plan.schema.json` read from the tree. It is shown in
 * full and **saved nowhere**: where a console draft goes before the person signs it is still to be designed.
 */

import { useState } from "react";

import { useClient } from "../../app/client";
import { errorText } from "../questions/ui";
import { type DraftIn, type DraftOut, makeDraft } from "./api";

export function useDraft() {
  const client = useClient();
  const [draft, setDraft] = useState<DraftOut | undefined>(undefined);
  const [error, setError] = useState<string | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  async function make(body: DraftIn) {
    setBusy(true);
    setError(undefined);
    setDraft(undefined);
    try {
      setDraft(await makeDraft(client, body));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return { draft, error, busy, make };
}

export function DraftView({ draft }: { draft: DraftOut }) {
  return (
    <section aria-label="Plan draft" className="inst-draft">
      <h3>Plan draft</h3>
      {draft.valid ? (
        <p>
          <span className="console-tag">checked</span> plan.schema.json accepts this card, and every position and strength is
          inside your safety file's limits.
        </p>
      ) : (
        <p role="alert" className="console-error">
          This draft is not offered for signing.
        </p>
      )}
      {draft.problems.length > 0 && (
        <>
          <p>plan.schema.json refuses it:</p>
          <ul aria-label="What the schema refuses">
            {draft.problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </>
      )}
      {draft.range_problems.length > 0 && (
        <ul aria-label="What your safety file refuses">
          {draft.range_problems.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}
      <ul aria-label="Refused until a limit exists">
        {draft.refused_today.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
      <p className="console-muted">{draft.note}</p>
      <p>
        <strong>Not saved.</strong> This draft exists only on this screen.
      </p>
      <pre aria-label="Draft plan card" className="console-text">
        {JSON.stringify(draft.card, null, 2)}
      </pre>
    </section>
  );
}

export function DraftError({ error }: { error: string | undefined }) {
  return error === undefined ? null : (
    <p role="alert" className="console-error">
      {error}
    </p>
  );
}

/** A labelled number field kept as text, so a half-typed value is not rewritten under the person's hand. */
export function NumberField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="inst-field">
      {label}
      <input type="text" inputMode="decimal" value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

export function num(text: string): number | undefined {
  const n = Number(text);
  return text.trim() !== "" && Number.isFinite(n) ? n : undefined;
}
