/**
 * The light path drawn in the order light travels (console card 023, part 2).
 *
 * **Everything drawn comes from the order the run's source gave**: which branches there are, which elements each holds and in
 * what sequence, and which have no recorded place. No element, branch or place is named in this file, and nothing is drawn that
 * the order does not name. **Lines show order only**: a join between two neighbours carries no state, so no source being on or off
 * changes one, none ends in a detector, and none says which camera a state reaches. A branch with a hole is drawn only as far as
 * its order goes; an element with no recorded place is listed beside the branch, with its live value, and never drawn into one.
 *
 * An element's state is the read-back's, found by **exact match** of the order's element id and channel against the read-back's
 * name and channel; no normalisation and no table of names live here. An element the read-back omits reads "not open" (its channel
 * was not opened), "no channel" (it has none) or "not read", with the reason, and **never a value**.
 */

import type { LatestRun } from "./api";
import {
  type HandSet, type KindTable, type OrderBranch, type OrderElement, type ReadOrder, bannerOf,
} from "./order";
import { BY_HAND_LABEL, type Element, Reading, RunRefuses, STATE_LABEL } from "./readout";

export const NO_CONTROL = "control not given";

type Found =
  | { kind: "row"; row: Element }
  | { kind: "none"; state: "no_channel" | "not_open" | "not_read"; reason: string };

const NONE_LABEL: Record<"no_channel" | "not_open" | "not_read", string> = {
  no_channel: "no channel", not_open: "not open", not_read: "not read",
};

function lookup(el: OrderElement, run: LatestRun): Found {
  const row = run.path.elements.find((r) => r.name === el.element && r.channel === el.channel);
  if (row !== undefined) return { kind: "row", row };
  if (el.channel === null) return { kind: "none", state: "no_channel", reason: "this element has no channel, so there is nothing to ask of it" };
  const opened = run.channels?.rows.find((c) => c.channel === el.channel);
  if (opened !== undefined && !opened.opened) {
    return { kind: "none", state: "not_open", reason: opened.detail ?? `the run did not open the channel ${el.channel}` };
  }
  return { kind: "none", state: "not_read", reason: `the read-back names no element called ${el.element} on channel ${el.channel}` };
}

const isHand = (el: OrderElement, hand: HandSet[]) => hand.some((h) => h.element === el.element && h.channel === el.channel);

function Control({ el, found, hand }: { el: OrderElement; found: Found; hand: HandSet[] }) {
  if (isHand(el, hand) || (found.kind === "row" && found.row.control === "hand")) {
    return <span className="inst-control" data-control="hand">{BY_HAND_LABEL}</span>;
  }
  if (found.kind === "row" && found.row.control === "draft") {
    return (
      <>
        <span className="inst-control" data-control="draft">drafted</span>
        {" "}
        <RunRefuses aura={found.row.draft === "aura"} />
      </>
    );
  }
  return <span className="inst-control" data-control="none">{NO_CONTROL}</span>;
}

function Item({ el, run, hand, join, hole }: { el: OrderElement; run: LatestRun; hand: HandSet[]; join: boolean; hole: string | null }) {
  const found = lookup(el, run);
  return (
    <li data-drawn={el.element} data-hole={hole ?? undefined}>
      <span className="inst-name">{el.element}</span>
      {" · "}
      {found.kind === "row" ? (
        <>
          <span className="inst-state" data-state={found.row.state}>{STATE_LABEL[found.row.state]}</span>
          {" · "}
          <Reading e={found.row} />
        </>
      ) : (
        <>
          <span className="inst-state" data-state={found.state}>{NONE_LABEL[found.state]}</span>
          {" · "}
          {found.reason}
        </>
      )}
      {" · "}
      <Control el={el} found={found} hand={hand} />
      {hole !== null && <> · <span className="inst-hole">place not recorded</span></>}
      {" · "}
      <span className="inst-entry">
        entry{" "}
        {el.entry_ref.map((id, i) => <span key={id}>{i > 0 && ", "}<span className="inst-entry-id">{id}</span></span>)}
      </span>
      {join && <span className="inst-join" data-join="next" aria-hidden="true" />}
    </li>
  );
}

function Branch({ b, run, hand }: { b: OrderBranch; run: LatestRun; hand: HandSet[] }) {
  return (
    <section aria-label={`Branch ${b.branch}`} data-branch={b.branch} className="inst-branch">
      <h4>{b.branch}</h4>
      <ol aria-label={`${b.branch} elements`}>
        {b.elements.map((el, i) => <Item key={`${el.element}/${el.channel}`} el={el} run={run} hand={hand} join={i < b.elements.length - 1} hole={null} />)}
      </ol>
      {b.place_not_recorded.length > 0 && (
        <div role="group" aria-label={`${b.branch}: place not recorded`} className="inst-holes">
          <ul>
            {b.place_not_recorded.map((el) => <Item key={`${el.element}/${el.channel}`} el={el} run={run} hand={hand} join={false} hole={b.branch} />)}
          </ul>
        </div>
      )}
    </section>
  );
}

/** How many read-back elements the order names nowhere: counted, never listed, never drawn. */
function unnamed(order: ReadOrder, run: LatestRun): number {
  const named = order.branches.flatMap((b) => [...b.elements, ...b.place_not_recorded]);
  return run.path.elements.filter((r) => !named.some((n) => n.element === r.name && n.channel === r.channel)).length;
}

export function Drawing({ order, run, kinds }: { order: ReadOrder; run: LatestRun; kinds?: KindTable }) {
  const banner = bannerOf(order, kinds);
  const left = unnamed(order, run);
  return (
    <div role="group" aria-label="Light path drawing" className="inst-drawing">
      <p className="inst-banner" data-banner={banner.how}>{banner.text}</p>
      <p className="console-muted">Order {order.entry_ref} · grade {order.grade} · source: {order.source}</p>
      <p className="console-muted">Lines show the order light travels through the elements, and nothing else.</p>
      {order.branches.map((b) => <Branch key={b.branch} b={b} run={run} hand={order.hand_set} />)}
      {left > 0 && <p className="console-muted">{left} read-back {left === 1 ? "element is" : "elements are"} not named in this order, so {left === 1 ? "it is" : "they are"} not drawn.</p>}
    </div>
  );
}
