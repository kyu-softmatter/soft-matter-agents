/**
 * The changes the person has collected by clicking (console card 023, parts 3 and 4): one list, in the order added, each item
 * removable. A change is either a **setting** (one of the three drafts) or a **required state** (a slot of a part moved by hand,
 * which software never writes: it becomes a selector in the plan, shown at the bench hand-over and set by the person's hand).
 * The list is kept on this screen only. Nothing in this file sends anything.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { useClient } from "../../app/client";
import { errorText } from "../questions/ui";
import { type ChangesIn, type DraftIn, type DraftOut, makeChanges } from "./api";
import { DraftView } from "./draft";
import type { Slot } from "./order";
import type { DraftKind } from "./parts";

export const CANNOT_SIGN_YET = "This draft cannot be signed yet, because it is saved nowhere.";
export const RUN_SENDS_NOTHING =
  "Nothing is sent. Starting a run has its own card, and on the instrument a run starts only after the bench hand-over at the microscope.";
export const NOT_SAVED_WORDS = "Not saved. This draft exists only on this screen.";
export const SELECTOR_SAYS = "set by your hand at the bench hand-over, then read and compared; software never writes it";

export type Change =
  | { id: number; kind: "part"; part: DraftKind; body: DraftIn; words: string }
  | { id: number; kind: "selector"; element: string; channel: string | null; value: string; slot: number; words: string };

interface Changes {
  items: Change[];
  /** Returns the reason it was refused, or undefined when it was added. */
  addPart: (part: DraftKind, body: DraftIn, words: string) => string | undefined;
  addSelector: (element: string, channel: string | null, slot: Slot) => string | undefined;
  remove: (id: number) => void;
  /** Open a section tab by its id. */
  go: (tab: string) => void;
}

const Ctx = createContext<Changes | undefined>(undefined);

export function useChanges(): Changes {
  const c = useContext(Ctx);
  if (c === undefined) throw new Error("useChanges needs a ChangesProvider");
  return c;
}

export function ChangesProvider({ onTab, children }: { onTab?: (tab: string) => void; children: ReactNode }) {
  const [items, setItems] = useState<Change[]>([]);
  const next = useRef(1);
  const addPart = useCallback((part: DraftKind, body: DraftIn, words: string) => {
    if (items.some((c) => c.kind === "part" && c.part === part)) return "Not added: this part is already in the changes. Remove it first to draft it again.";
    setItems([...items, { id: next.current++, kind: "part", part, body, words }]);
    return undefined;
  }, [items]);
  const addSelector = useCallback((element: string, channel: string | null, slot: Slot) => {
    if (!slot.resolves || slot.name === null) {
      const word = slot.name ?? `slot ${slot.slot}`;
      return `Refused: ${word} cannot be named in a plan (${slot.why ?? "the order gives no reason"}), so no required state is added.`;
    }
    if (items.some((c) => c.kind === "selector" && c.element === element)) {
      return "Not added: this element already has a required state in the changes. Remove it first to choose another slot.";
    }
    setItems([...items, { id: next.current++, kind: "selector", element, channel, value: slot.name, slot: slot.slot, words: `${element} set by hand to ${slot.name} (slot ${slot.slot})` }]);
    return undefined;
  }, [items]);
  const remove = useCallback((id: number) => setItems((cur) => cur.filter((c) => c.id !== id)), []);
  const go = useCallback((tab: string) => onTab?.(tab), [onTab]);
  const value = useMemo(() => ({ items, addPart, addSelector, remove, go }), [items, addPart, addSelector, remove, go]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/**
 * [Check the draft] and [Apply]. Both ask the server once, on the press, to build the one plan draft from the list and check it;
 * neither sends anything to an instrument. [Apply] is signing and then the run button, and signing waits on a place to keep a
 * draft (a signature is over a plan card on disk, and this draft is saved nowhere): until a card names that place, [Apply] is shown
 * and refused. `signed` is the seam for what comes after signing; nothing sets it today.
 */
export function ApplyPanel({ signed = false }: { signed?: boolean }) {
  const { items } = useChanges();
  const client = useClient();
  const key = items.map((c) => c.id).join(",");
  const [checked, setChecked] = useState<{ key: string; draft: DraftOut; applied: boolean } | undefined>(undefined);
  const [error, setError] = useState<string | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [runSays, setRunSays] = useState(false);
  const here = checked !== undefined && checked.key === key ? checked : undefined;
  // an answer belongs to the list it was asked of: when the list changes, it goes, and it does not come back if the list does
  useEffect(() => setChecked(undefined), [key]);
  async function ask(applied: boolean) {
    if (busy || items.length === 0) return;
    const body: ChangesIn = {
      parts: items.flatMap((c) => (c.kind === "part" ? [c.body as ChangesIn["parts"][number]] : [])),
      selectors: items.flatMap((c) => (c.kind === "selector" ? [{ element: c.element, value: c.value }] : [])),
    };
    setBusy(true);
    setError(undefined);
    setChecked(undefined);
    try {
      setChecked({ key, draft: await makeChanges(client, body), applied });
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  const none = items.length === 0;
  return (
    <div className="inst-apply">
      <button type="button" disabled={busy || none} onClick={() => void ask(false)}>Check the draft</button>
      {" "}
      <button type="button" disabled={busy || none} onClick={() => void ask(true)}>Apply</button>
      {none && <p className="console-muted">Add a change first: there is nothing yet to check or apply.</p>}
      {error !== undefined && <p role="alert" className="console-error">{error}</p>}
      {here !== undefined && <DraftView draft={here.draft} />}
      {here?.applied === true && (
        <p role="alert" className="console-error" data-testid="apply-refused">
          {here.draft.valid ? "" : "Not signed: this draft is refused before it can be signed. "}
          {CANNOT_SIGN_YET}
        </p>
      )}
      {signed && (
        <p>
          <button type="button" onClick={() => setRunSays(true)}>Run</button>{" "}
          {runSays && <span data-testid="run-says" className="console-muted">{RUN_SENDS_NOTHING}</span>}
        </p>
      )}
    </div>
  );
}

export function ChangesList({ signed = false }: { signed?: boolean }) {
  const { items, remove } = useChanges();
  return (
    <section role="region" aria-label="Changes" className="inst-panel inst-changes">
      {items.length === 0 ? (
        <p className="console-muted">Nothing has been added. Click an element in the drawing to add a change.</p>
      ) : (
        <>
          <p>These changes will be made:</p>
          <ol>
            {items.map((c) => (
              <li key={c.id} data-change-kind={c.kind}>
                <span data-words>{c.words}</span>
                {" · "}
                <span className="console-tag">{c.kind === "part" ? "setting" : "required state"}</span>
                {c.kind === "selector" && <> · <span className="console-muted">{SELECTOR_SAYS}</span></>}
                {" "}
                <button type="button" aria-label={`Remove ${c.words}`} onClick={() => remove(c.id)}>Remove</button>
              </li>
            ))}
          </ol>
        </>
      )}
      <p className="console-muted">{NOT_SAVED_WORDS}</p>
      <ApplyPanel signed={signed} />
    </section>
  );
}
