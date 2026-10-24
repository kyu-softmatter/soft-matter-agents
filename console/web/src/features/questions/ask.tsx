/**
 * The question window (console card 010, plan.md 4.5): one field, an Ask choice and Send. Send
 * writes one question request into the console's own folder, with the words exactly as typed.
 * Nothing reaches an agent until the agents' new inbox opens, and the screen says so.
 *
 * Autocomplete offers only strings already on disk -- the words of earlier requests and the
 * registered quantity names, each labelled -- never a model's completion and never the store's
 * contents. Choosing a suggestion inserts its text; it registers nothing and sends nothing.
 * The server decides who may send; this form only shows that decision and its reason.
 */

import { type FormEvent, useMemo, useState } from "react";

import { type ReadOnlyState, useClient } from "../../app/client";
import {
  ADDRESSEES,
  type Addressee,
  askQuestion,
  CHECKING_PERMISSIONS,
  NOT_PICKED_UP_SENTENCE,
  PATHS,
  PERMISSION_CHECK_UNAVAILABLE,
  type Permissions,
  type QuestionRequest,
  READ_ONLY_REMOTE,
  READ_ONLY_STORE_REASON,
  type StoreInfo,
  SUBMIT_OP,
  type Suggestion,
} from "./api";
import { errorText, type LoadState, useLoad } from "./ui";

/**
 * Why Send is off, or undefined when it is on, in ui-spec 7.0 order: the shell's read-only flag
 * (remote view), the shared permission answer (login, role), then the console's own rule, a store
 * that cannot take a request. The server checks all of these again on the POST.
 */
export function submitReason(
  readOnly: ReadOnlyState,
  perms: LoadState<Permissions>,
  store: LoadState<StoreInfo>,
): string | undefined {
  if (readOnly.readOnly) return READ_ONLY_REMOTE;
  if (perms.error !== undefined) return PERMISSION_CHECK_UNAVAILABLE;
  if (perms.data === undefined) return CHECKING_PERMISSIONS;
  const p = perms.data[SUBMIT_OP] ?? { allowed: false, reason: PERMISSION_CHECK_UNAVAILABLE };
  if (!p.allowed) return p.reason ?? PERMISSION_CHECK_UNAVAILABLE;
  if (store.error !== undefined) return `Cannot read the store: ${store.error}`;
  if (store.data === undefined) return "Reading the store…";
  if (!store.data.writable) return READ_ONLY_STORE_REASON;
  return undefined;
}

const MAX_SUGGESTIONS = 8;

/** The word being typed: the last run of non-space characters, when the field ends in one. */
function lastWord(text: string): string | undefined {
  return /(\S+)$/.exec(text)?.[1];
}

/**
 * What to offer for what is typed: an earlier question whose words contain it, and a registered
 * name that contains the word being typed. Case is ignored. Nothing for an empty field.
 */
export function suggestionsFor(text: string, all: readonly Suggestion[]): Suggestion[] {
  const typed = text.trim().toLowerCase();
  if (typed === "") return [];
  const word = lastWord(text)?.toLowerCase();
  return all
    .filter((s) =>
      s.kind === "earlier question"
        ? s.text.toLowerCase().includes(typed) && s.text !== text
        : word !== undefined && s.text.toLowerCase().includes(word) && s.text.toLowerCase() !== word,
    )
    .slice(0, MAX_SUGGESTIONS);
}

/** The field with a suggestion put in: an earlier question replaces the field, a name the word typed. */
export function insertSuggestion(text: string, s: Suggestion): string {
  if (s.kind === "earlier question") return s.text;
  const word = lastWord(text);
  return word === undefined ? text + s.text : text.slice(0, text.length - word.length) + s.text;
}

function timeOf(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function AskBox({
  reason,
  refreshKey,
  onWritten,
}: {
  reason: string | undefined;
  /** changes when the cards are read again, so a new request is offered next time */
  refreshKey: number;
  onWritten: (r: QuestionRequest) => void;
}) {
  const client = useClient();
  const [words, setWords] = useState("");
  const [to, setTo] = useState<Addressee>("agents_decide");
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  const [done, setDone] = useState<QuestionRequest | undefined>(undefined);
  const all = useLoad(() => client.get<Suggestion[]>(PATHS.suggestions), [client, refreshKey]);
  const shown = useMemo(() => (open ? suggestionsFor(words, all.data ?? []) : []), [open, words, all.data]);

  const disabled = reason !== undefined || busy || words.trim() === "";

  async function send(e: FormEvent) {
    e.preventDefault();
    if (disabled) return;
    setBusy(true);
    setError(undefined);
    setDone(undefined);
    try {
      const r = await askQuestion(client, { words, addressed_to: to });
      setWords("");
      setOpen(false);
      setDone(r);
      onWritten(r);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form aria-label="Ask a question" className="console-submit" onSubmit={send}>
      <label>
        Your question
        <textarea
          value={words}
          rows={4}
          onChange={(e) => {
            setWords(e.target.value);
            setOpen(true);
          }}
        />
      </label>
      {shown.length > 0 && (
        <ul role="listbox" aria-label="Suggestions" className="ask-suggestions">
          {shown.map((s) => (
            <li
              key={`${s.kind}:${s.text}`}
              role="option"
              aria-selected={false}
              tabIndex={-1}
              onClick={() => {
                setWords(insertSuggestion(words, s));
                setOpen(false);
              }}
            >
              <span>{s.text}</span>
              <span className="console-tag">{s.kind}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="console-filters">
        <label>
          Ask{" "}
          <select value={to} onChange={(e) => setTo(e.target.value as Addressee)}>
            {ADDRESSEES.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={disabled}>
          Send
        </button>
        {reason !== undefined && <span className="console-reason">{reason}</span>}
      </div>
      {error !== undefined && (
        <p role="alert" className="console-error">
          {error}
        </p>
      )}
      {done !== undefined && (
        <p role="status" data-testid="request-written">
          Request written · {timeOf(done.asked_at)} · as {done.asked_by.login}. {NOT_PICKED_UP_SENTENCE}
        </p>
      )}
    </form>
  );
}
