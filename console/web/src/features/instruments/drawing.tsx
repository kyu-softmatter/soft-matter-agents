/**
 * The light path drawn in the order light travels (console card 023, part 2).
 *
 * **Everything drawn comes from the order the run's source gave**: which branches there are, which elements each holds and in
 * what sequence, and which have no recorded place. No element, branch or place is named in this file, and nothing is drawn that
 * the order does not name. **Lines show order only**: a join between two neighbours carries no state, so no source being on or off
 * changes one, none ends in a detector, and none says which camera a state reaches. A branch with a hole is drawn only as far as
 * its order goes; an element with no recorded place is listed beside the branch, with its live value, and never drawn into one.
 *
 * An element's state is the read-back's, found by **exact match of the pair the order gives it** (`read_back`) against a row's
 * channel and name, never by the element's id; no normalisation and no table of names live here. An element no row answers reads
 * "not open" (the run did not open the channel), "no channel" (it has none and no pair) or "not read", with the reason, and
 * **never a value**.
 */

import { useState } from "react";

import type { LatestRun } from "./api";
import { ClickPanel } from "./click";
import { type Control, controlOf, handSetOf, lookup } from "./join";
import {
  type HandSet, type KindTable, type OrderBranch, type OrderElement, type ReadOrder, bannerOf,
} from "./order";
import { NO_DRAFT_LABEL } from "./parts";
import { BY_HAND_LABEL, Reading, RunRefuses, STATE_LABEL } from "./readout";

export const NO_CONTROL = "control not given";

const NONE_LABEL: Record<"no_channel" | "not_open" | "not_read", string> = {
  no_channel: "no channel", not_open: "not open", not_read: "not read",
};

function ControlLabel({ control }: { control: Control }) {
  if (control.kind === "hand") return <span className="inst-control" data-control="hand">{BY_HAND_LABEL}</span>;
  if (control.kind === "draft") {
    return (
      <>
        <span className="inst-control" data-control="draft">drafted</span>
        {" "}
        <RunRefuses />
      </>
    );
  }
  if (control.kind === "no_draft") return <span className="inst-control" data-control="no_draft">{NO_DRAFT_LABEL}</span>;
  return <span className="inst-control" data-control="none">{NO_CONTROL}</span>;
}

function Item({ el, run, hand, join, hole }: { el: OrderElement; run: LatestRun; hand: HandSet[]; join: boolean; hole: string | null }) {
  const found = lookup(el, run);
  const control = controlOf(el, found, hand);
  const [opened, setOpened] = useState(false);
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
      <ControlLabel control={control} />
      {hole !== null && <> · <span className="inst-hole">place not recorded</span></>}
      {" · "}
      <span className="inst-entry">
        entry{" "}
        {el.entry_ref.map((id, i) => <span key={id}>{i > 0 && ", "}<span className="inst-entry-id">{id}</span></span>)}
      </span>
      {" "}
      <button type="button" aria-label={`Open ${el.element}`} aria-expanded={opened} onClick={() => setOpened(!opened)}>{opened ? "close" : "open"}</button>
      {opened && <ClickPanel el={el} found={found} control={control} hand={handSetOf(el, hand)} run={run} />}
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

/** How many read-back rows no pair of the order names: counted, never listed, never drawn. An element's id names no row. */
function unnamed(order: ReadOrder, run: LatestRun): number {
  const named = order.branches.flatMap((b) => [...b.elements, ...b.place_not_recorded]);
  return run.path.elements.filter((r) => !named.some((n) => n.read_back !== null && n.read_back.name === r.name && n.read_back.channel === r.channel)).length;
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
