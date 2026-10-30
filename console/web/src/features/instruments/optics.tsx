/**
 * Optics and control (console cards 012, 023 and 024): the light path drawn in the order its source gives, and the changes
 * collected from it. No draft panel stands here: the red camera's draft is reached from its element and the Cameras tab, and
 * the Aura and the transmitted lamp have none (card 024). A draft is an ordinary plan card, checked against the schema and
 * saved nowhere.
 */

import { type LatestRun } from "./api";
import { ChangesList, ChangesProvider } from "./changes";
import { LightsOff } from "./lightsoff";
import { PartDraft, REFUSED_NO_LIMIT } from "./partdraft";
import { MOVED_BY_HAND } from "./parts";
import { PathPanel } from "./path";

export { PartDraft, REFUSED_NO_LIMIT };

export function Optics({ run, onTab, onRefresh }: { run: LatestRun; onTab?: (tab: string) => void; onRefresh?: () => void }) {
  return (
    <ChangesProvider onTab={onTab}>
      <section aria-label="Optics and control" className="inst-optics">
        <LightsOff running={run.state === "ok" && run.running} onAnswered={onRefresh} />
        <PathPanel run={run} />
        <ChangesList />
        <p className="console-muted">{MOVED_BY_HAND}</p>
      </section>
    </ChangesProvider>
  );
}
