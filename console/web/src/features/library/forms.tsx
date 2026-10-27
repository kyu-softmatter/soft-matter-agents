/**
 * The four request forms (console cards 016 and 020): add a document or value, withdraw a value, offer a result,
 * ask the librarian. Every login the console allows may use them. Send checks the form, then hands the server
 * the words as typed, the request and at most one file (read in this browser and sent inside the request); the
 * server writes it into the librarian's inbox. What the server refused is shown in its words. Nothing is kept
 * here: a form that was sent is emptied.
 */

import { type FormEvent, Fragment, type ReactNode, useRef, useState } from "react";

import { useClient } from "../../app/client";
import { errorText } from "../questions/ui";
import { type RequestIn, sendRequest } from "./api";

import {
  type AddForm,
  type AskForm,
  buildAdd,
  buildAsk,
  type Built,
  buildOffer,
  buildWithdraw,
  documentOf,
  EMPTY_ADD,
  EMPTY_ASK,
  EMPTY_OFFER,
  EMPTY_WITHDRAW,
  EVIDENCE_KINDS,
  type EvidenceKind,
  type OfferForm,
  REMEMBERED_NOTE,
  SENT,
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

function FilePick({ label, name, onPick }: { label: string; name: string; onPick: (file: File | null) => void }) {
  return (
    <Field label={label}>
      <input type="file" aria-label={label} onChange={(e) => onPick(e.target.files?.[0] ?? null)} />
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

/** The bytes of a file, as base64 (no data-URL prefix). */
function base64Of(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("The file could not be read in this browser."));
    reader.onload = () => {
      const url = String(reader.result);
      resolve(url.slice(url.indexOf(",") + 1));
    };
    reader.readAsDataURL(file);
  });
}

type Outcome = { sent: true } | { sent: false; problems: string[]; refused: string | null };

/**
 * One form: its fields, Send, and what Send answered. Send builds the request, reads the one file the request
 * names (a file picked and then not named is not sent) and posts it; the form empties only when the server took it.
 */
function RequestForm<T>(p: {
  title: string;
  intro: string;
  initial: T;
  build: (f: T) => Built;
  onSent?: () => void;
  children: (f: T, set: (patch: Partial<T>, file?: File | null) => void) => ReactNode;
}) {
  const client = useClient();
  const [form, setForm] = useState<T>(p.initial);
  const [outcome, setOutcome] = useState<Outcome | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [fresh, setFresh] = useState(0);
  const picked = useRef<File | null>(null);
  async function send(e: FormEvent) {
    e.preventDefault();
    const built = p.build(form);
    if (!built.ok) {
      setOutcome({ sent: false, problems: built.problems, refused: null });
      return;
    }
    setBusy(true);
    try {
      const name = documentOf(built.request);
      const body: RequestIn = { words: built.words, request: built.request };
      if (name !== null && picked.current !== null) {
        body.file = { name, content_base64: await base64Of(picked.current) };
      }
      await sendRequest(client, body);
      setForm(p.initial);
      picked.current = null;
      setFresh(fresh + 1); // remounts the fields, so a picked file's input is empty again
      setOutcome({ sent: true });
      p.onSent?.();
    } catch (err) {
      setOutcome({ sent: false, problems: [], refused: errorText(err) });
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="console-submit lib-form" aria-label={p.title} onSubmit={send}>
      <h3>{p.title}</h3>
      <p className="console-muted">{p.intro}</p>
      <Fragment key={fresh}>
        {p.children(form, (patch, file) => {
          setForm({ ...form, ...patch });
          if (file !== undefined) picked.current = file;
          setOutcome(undefined);
        })}
      </Fragment>
      <div>
        <button type="submit" disabled={busy}>Send</button>
      </div>
      {outcome?.sent === true && <p role="status" className="lib-outcome"><strong>{SENT}</strong></p>}
      {outcome?.sent === false && outcome.refused !== null && (
        <p role="alert" className="console-error">{outcome.refused}</p>
      )}
      {outcome?.sent === false && outcome.problems.length > 0 && (
        <div role="status" className="lib-outcome">
          <p><strong>Not sent: the form needs fixing first.</strong></p>
          <ul>{outcome.problems.map((x) => <li key={x}>{x}</li>)}</ul>
        </div>
      )}
    </form>
  );
}

export function AddDocument({ onSent }: { onSent?: () => void }) {
  return (
    <RequestForm<AddForm>
      title="Add a document or value"
      intro="Hand the librarian a document or a value. The librarian decides what to enter, and says why when it enters less than you asked."
      initial={EMPTY_ADD}
      build={buildAdd}
      onSent={onSent}
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
            <FilePick label="File" name={f.fileName} onPick={(file) => set({ fileName: file?.name ?? "" }, file)} />
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

export function WithdrawValue({ onSent }: { onSent?: () => void }) {
  return (
    <RequestForm<WithdrawForm>
      title="Withdraw a value"
      intro="Ask the librarian to withdraw an entry. The librarian decides, and nothing is erased."
      initial={EMPTY_WITHDRAW}
      build={buildWithdraw}
      onSent={onSent}
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
              <FilePick label="File (optional)" name={f.fileName} onPick={(file) => set({ fileName: file?.name ?? "" }, file)} />
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
              <FilePick label="File" name={f.fileName} onPick={(file) => set({ fileName: file?.name ?? "" }, file)} />
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

export function OfferResult({ onSent }: { onSent?: () => void }) {
  return (
    <RequestForm<OfferForm>
      title="Offer a result"
      intro="Offer a result card as a candidate fact. The librarian enters it by its ordinary rules."
      initial={EMPTY_OFFER}
      build={(f) => buildOffer(f)}
      onSent={onSent}
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

export function AskLibrarian({ onSent }: { onSent?: () => void }) {
  return (
    <RequestForm<AskForm>
      title="Ask the librarian"
      intro="A question changes nothing in the store. An answer names the entries it rests on, with each number's grade and source, and says what the store does not hold."
      initial={EMPTY_ASK}
      build={(f) => buildAsk(f)}
      onSent={onSent}
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
