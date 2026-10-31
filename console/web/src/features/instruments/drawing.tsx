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
 *
 * **The look is the person's page's, rebuilt here** (console card 026): a branch is a labelled area, an element is one box that is one
 * button, and a click opens the element in a panel beside the areas, one at a time. Only the layout is drawn; the words, entry ids and
 * click contents are what they were, and a join is the same plain line whatever any element reads.
 */

import { useId, useState } from "react";

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

const keyOf = (el: OrderElement) => `${el.element}/${el.channel}`;

/**
 * An element is a box and the box is one button: its name first, bold, and beneath it what 023 shows, in the same order. What a
 * click opens is not under the box but in the panel beside the areas, so nothing interactive is nested in the box. The button's
 * name is `Open <element>` and the lines beneath it are its description, so a screen reader still reads the state.
 */
function Item({ el, run, hand, join, hole, opened, onToggle }: {
  el: OrderElement; run: LatestRun; hand: HandSet[]; join: boolean; hole: string | null; opened: boolean; onToggle: () => void;
}) {
  const found = lookup(el, run);
  const control = controlOf(el, found, hand);
  const lines = useId();
  return (
    <li data-drawn={el.element} data-hole={hole ?? undefined}>
      <button type="button" className="inst-box" aria-label={`Open ${el.element}`} aria-expanded={opened} aria-describedby={lines} onClick={onToggle}>
        <span className="inst-name">{el.element}</span>
        <span className="inst-lines" id={lines}>
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
        </span>
      </button>
      {join && <span className="inst-join" data-join="next" aria-hidden="true" />}
    </li>
  );
}

type Opening = { openKey: string | null; toggle: (key: string) => void };

function Branch({ b, run, hand, o }: { b: OrderBranch; run: LatestRun; hand: HandSet[]; o: Opening }) {
  const item = (el: OrderElement, join: boolean, hole: string | null) => (
    <Item key={keyOf(el)} el={el} run={run} hand={hand} join={join} hole={hole} opened={o.openKey === keyOf(el)} onToggle={() => o.toggle(keyOf(el))} />
  );
  return (
    <section aria-label={`Branch ${b.branch}`} data-branch={b.branch} className="inst-branch">
      <h4>{b.branch}</h4>
      <ol aria-label={`${b.branch} elements`}>
        {b.elements.map((el, i) => item(el, i < b.elements.length - 1, null))}
      </ol>
      {b.place_not_recorded.length > 0 && (
        <div role="group" aria-label={`${b.branch}: place not recorded`} className="inst-holes">
          <ul>
            {b.place_not_recorded.map((el) => item(el, false, b.branch))}
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
  // One element is open at a time: a click on another box moves the panel to it, a click on the open box closes it.
  const [openKey, setOpenKey] = useState<string | null>(null);
  const o: Opening = { openKey, toggle: (key) => setOpenKey(openKey === key ? null : key) };
  const open = openKey === null ? undefined : order.branches.flatMap((b) => [...b.elements, ...b.place_not_recorded]).find((e) => keyOf(e) === openKey);
  const found = open === undefined ? undefined : lookup(open, run);
  return (
    <div role="group" aria-label="Light path drawing" className="inst-drawing">
      <p className="inst-banner" data-banner={banner.how}>{banner.text}</p>
      <p className="console-muted">Order {order.entry_ref} · grade {order.grade} · source: {order.source}</p>
      <p className="console-muted">Lines show the order light travels through the elements, and nothing else.</p>
      <div className="inst-stage">
        <div className="inst-areas">
          {order.branches.map((b) => <Branch key={b.branch} b={b} run={run} hand={order.hand_set} o={o} />)}
        </div>
        {open !== undefined && found !== undefined && (
          <div className="inst-side" key={keyOf(open)}>
            <ClickPanel el={open} found={found} control={controlOf(open, found, order.hand_set)} hand={handSetOf(open, order.hand_set)} run={run} />
          </div>
        )}
      </div>
      {left > 0 && <p className="console-muted">{left} read-back {left === 1 ? "element is" : "elements are"} not named in this order, so {left === 1 ? "it is" : "they are"} not drawn.</p>}
    </div>
  );
}
