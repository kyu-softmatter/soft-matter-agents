/**
 * The four request forms (console card 016): add a document or value, withdraw a value, offer a result, ask the
 * librarian. Every login the console allows may use them. **Send writes no file and sends nothing**: the
 * librarian's inbox is open and the console writes no item into it yet, so Send checks the form and says "Not sent". The check is the console's own and
 * calls no server.
 */

import { type FormEvent, type ReactNode, useState } from "react";

import {
  type AddForm,
  type AskForm,
  buildAdd,
  buildAsk,
  type Built,
  buildOffer,
  buildWithdraw,
  EMPTY_ADD,
  EMPTY_ASK,
  EMPTY_OFFER,
  EMPTY_WITHDRAW,
  EVIDENCE_KINDS,
  type EvidenceKind,
  type OfferForm,
  type Outcome,
  previewItemId,
  REMEMBERED_NOTE,
  sendOutcome,
  SOURCE_KINDS,
  type SourceKind,
  WORDS_ALONE_NOTE,
  type WithdrawForm,
} from "./request";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="lib-field">
      <span>{label}</span>
      {children}
    </label>
  );
}

function FilePick({ label, name, onPick }: { label: string; name: string; onPick: (n: string) => void }) {
  return (
    <Field label={label}>
      <input type="file" aria-label={label} onChange={(e) => onPick(e.target.files?.[0]?.name ?? "")} />
      {name !== "" && <span className="console-muted"> {name}</span>}
    </Field>
  );
}

function ValueUnit(p: { label: string; value: string; unit: string; onValue: (v: string) => void; onUnit: (v: string) => void }) {
  return (
    <>
      <Field label={`${p.label}: value`}>
        <input type="text" inputMode="decimal" value={p.value} onChange={(e) => p.onValue(e.target.value)} />
      </Field>
      <Field label={`${p.label}: unit`}>
        <input type="text" value={p.unit} onChange={(e) => p.onUnit(e.target.value)} />
      </Field>
    </>
  );
}

/** One form: its fields, Send, and what Send answered. Send builds the request only to check it and keeps nothing. */
function RequestForm<T>(p: {
  title: string;
  intro: string;
  initial: T;
  build: (f: T, itemId: string) => Built;
  children: (f: T, set: (patch: Partial<T>) => void) => ReactNode;
}) {
  const [form, setForm] = useState<T>(p.initial);
  const [outcome, setOutcome] = useState<Outcome | undefined>(undefined);
  function send(e: FormEvent) {
    e.preventDefault();
    setOutcome(sendOutcome(p.build(form, previewItemId(new Date()))));
  }
  return (
    <form className="console-submit lib-form" aria-label={p.title} onSubmit={send}>
      <h3>{p.title}</h3>
      <p className="console-muted">{p.intro}</p>
      <p role="note" className="console-reason">
        The console does not send to the librarian yet, so Send only checks the form. Nothing you type here is kept or sent.
      </p>
      {p.children(form, (patch) => {
        setForm({ ...form, ...patch });
        setOutcome(undefined);
      })}
      <div>
        <button type="submit">Send</button>
      </div>
      {outcome !== undefined && (
        <div role="status" className="lib-outcome">
          <p><strong>{outcome.message}</strong></p>
          {outcome.problems.length > 0 && <ul>{outcome.problems.map((x) => <li key={x}>{x}</li>)}</ul>}
        </div>
      )}
    </form>
  );
}

export function AddDocument() {
  return (
    <RequestForm<AddForm>
      title="Add a document or value"
      intro="Hand the librarian a document or a value. The librarian decides what to enter, and says why when it enters less than you asked."
      initial={EMPTY_ADD}
      build={buildAdd}
    >
      {(f, set) => (
        <>
          <Field label="What kind of source">
            <select value={f.sourceKind} onChange={(e) => set({ sourceKind: e.target.value as SourceKind })}>
              {SOURCE_KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
            </select>
          </Field>
          <Field label={f.sourceKind === "operator_recall" ? "Who remembers it" : "Who read it"}>
            <input type="text" value={f.readBy} onChange={(e) => set({ readBy: e.target.value })} />
          </Field>
          {f.sourceKind !== "operator_recall" && (
            <FilePick label="File" name={f.fileName} onPick={(fileName) => set({ fileName })} />
          )}
          {(f.sourceKind === "operator_read" || f.sourceKind === "operator_recall") && (
            <ValueUnit label="Value" value={f.value} unit={f.unit} onValue={(value) => set({ value })} onUnit={(unit) => set({ unit })} />
          )}
          {f.sourceKind === "operator_recall" && <p role="note" className="console-reason">{REMEMBERED_NOTE}</p>}
          <Field label="What to take, in your words">
            <textarea rows={3} value={f.factWanted} onChange={(e) => set({ factWanted: e.target.value })} />
          </Field>
        </>
      )}
    </RequestForm>
  );
}

export function WithdrawValue() {
  return (
    <RequestForm<WithdrawForm>
      title="Withdraw a value"
      intro="Ask the librarian to withdraw an entry. The librarian decides, and nothing is erased."
      initial={EMPTY_WITHDRAW}
      build={buildWithdraw}
    >
      {(f, set) => (
        <>
          <Field label="Entry name (typed or pasted)">
            <input type="text" value={f.entryId} onChange={(e) => set({ entryId: e.target.value })} />
          </Field>
          <Field label="Why, in your words">
            <textarea rows={3} value={f.reason} onChange={(e) => set({ reason: e.target.value })} />
          </Field>
          <Field label="Evidence">
            <select value={f.evidence} onChange={(e) => set({ evidence: e.target.value as EvidenceKind })}>
              {EVIDENCE_KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
            </select>
          </Field>
          <p role="note" className="console-reason">{WORDS_ALONE_NOTE}</p>
          {f.evidence === "reading" && (
            <>
              <Field label="Who took the reading">
                <input type="text" value={f.readBy} onChange={(e) => set({ readBy: e.target.value })} />
              </Field>
              <ValueUnit label="Reading" value={f.value} unit={f.unit} onValue={(value) => set({ value })} onUnit={(unit) => set({ unit })} />
              <FilePick label="File (optional)" name={f.fileName} onPick={(fileName) => set({ fileName })} />
            </>
          )}
          {f.evidence === "document" && (
            <>
              <Field label="What kind of document">
                <select value={f.documentKind} onChange={(e) => set({ documentKind: e.target.value as "spec" | "literature" })}>
                  <option value="spec">A maker&apos;s document</option>
                  <option value="literature">A paper</option>
                </select>
              </Field>
              <FilePick label="File" name={f.fileName} onPick={(fileName) => set({ fileName })} />
            </>
          )}
          {f.evidence === "replacing_entry" && (
            <Field label="Name of the replacing entry">
              <input type="text" value={f.replacingEntryId} onChange={(e) => set({ replacingEntryId: e.target.value })} />
            </Field>
          )}
        </>
      )}
    </RequestForm>
  );
}

export function OfferResult() {
  return (
    <RequestForm<OfferForm>
      title="Offer a result"
      intro="Offer a result card as a candidate fact. The librarian enters it by its ordinary rules."
      initial={EMPTY_OFFER}
      build={(f) => buildOffer(f)}
    >
      {(f, set) => (
        <>
          <Field label="Path of the result card">
            <input type="text" value={f.resultCard} onChange={(e) => set({ resultCard: e.target.value })} />
          </Field>
          <Field label="The fact, in words">
            <textarea rows={3} value={f.fact} onChange={(e) => set({ fact: e.target.value })} />
          </Field>
        </>
      )}
    </RequestForm>
  );
}

export function AskLibrarian() {
  return (
    <RequestForm<AskForm>
      title="Ask the librarian"
      intro="A question changes nothing in the store. An answer names the entries it rests on, with each number's grade and source, and says what the store does not hold."
      initial={EMPTY_ASK}
      build={(f) => buildAsk(f)}
    >
      {(f, set) => (
        <>
          <Field label="Your question">
            <textarea rows={3} value={f.question} onChange={(e) => set({ question: e.target.value })} />
          </Field>
          <Field label="Conditions you mean (optional)">
            <input type="text" value={f.conditions} onChange={(e) => set({ conditions: e.target.value })} />
          </Field>
        </>
      )}
    </RequestForm>
  );
}
