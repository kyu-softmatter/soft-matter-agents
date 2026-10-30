/**
 * Optics and control (console cards 012 and 023): the light path drawn in the order its source gives, and a draft for the
 * parts software may command. A draft is an ordinary plan card, checked against the schema and saved nowhere.
 */

import { useRef } from "react";

import { type LatestRun } from "./api";
import { ChangesList, ChangesProvider } from "./changes";
import { LightsOff } from "./lightsoff";
import { PartDraft, REFUSED_NO_LIMIT } from "./partdraft";
import { type DraftKind, MOVED_BY_HAND } from "./parts";
import { PathPanel } from "./path";
import { orderViewOf } from "./order";

export { PartDraft, REFUSED_NO_LIMIT };

/** Until a source gives an order to click, the drafts stay reachable below the list, as card 017 left them. */
const TRANSIENT: readonly { kind: DraftKind; label: string }[] = [
  { kind: "aura", label: "Aura III LED" },
  { kind: "dialamp", label: "Transmitted lamp" },
];

export function Optics({ run, onTab, onRefresh }: { run: LatestRun; onTab?: (tab: string) => void; onRefresh?: () => void }) {
  const drafts = useRef<HTMLDivElement>(null);
  const drawn = orderViewOf(run).state === "read";
  return (
    <ChangesProvider onTab={onTab}>
      <section aria-label="Optics and control" className="inst-optics">
        <LightsOff running={run.state === "ok" && run.running} onAnswered={onRefresh} />
        <PathPanel run={run} onDraft={() => drafts.current?.focus()} />
        <ChangesList />
        <p className="console-muted">{MOVED_BY_HAND}</p>
        {!drawn && (
          <div ref={drafts} tabIndex={-1} role="group" aria-label="Drafts" className="inst-panel">
            {TRANSIENT.map((t) => <PartDraft key={t.kind} kind={t.kind} label={t.label} />)}
          </div>
        )}
      </section>
    </ChangesProvider>
  );
}
