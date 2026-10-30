/**
 * What a click opens in the drawing (console card 023, part 3): the element's own controls, and only those the rules already
 * allow. A drafted element opens its draft fields in place; a part moved by hand opens its slot list, and choosing a slot adds a
 * required state that software never writes; the laser combiner and the trap say why they have no control. **No click offers a
 * laser line, a power, a level beyond the three drafts, or a software move of a hand-moved part.** Nothing here sends anything.
 */

import { useState } from "react";

import { shortTime } from "../questions/ui";
import type { LatestRun } from "./api";
import { useChanges } from "./changes";
import { type Control, type Found, NO_CONTROL_CHANNELS, tabOf } from "./join";
import type { HandSet, OrderElement } from "./order";
import { COMBINER_SENTENCE } from "./parts";
import { DRAFT_LABEL, PartDraft } from "./partdraft";
import { RunRefuses } from "./readout";

export const NOT_OFFERED =
  "Not offered here, and refused until its own limit exists: a laser line, a laser power, any level beyond the lamp, the Aura and the red camera's exposure, and a software move of a part that is moved by hand.";
export const HAND_SELECTOR_SAYS =
  "Choosing a slot adds a required state, not a command. Software never writes it: it is shown at the bench hand-over, set by your hand, then read and compared.";
export const NO_SLOTS_GIVEN = "The slot list is not given for this element, so no slot can be chosen here.";
const NO_CONTROL_HERE = "This page is given no control for this element.";

export const SLOT_NOT_GIVEN = "Which of these slots that is has not been given, so no slot is marked.";

/**
 * **No slot is marked as the current one.** Nothing gives the page which slot a position read back means, so a value equal to a
 * slot's number or name marks nothing: the row's own value is shown with where it came from, and the page says it cannot tell
 * which slot that is.
 */
function ReadBackValue({ found }: { found: Found }) {
  if (found.kind !== "row") return <p className="console-muted" data-testid="read-value">{`No value was read back for this element: ${found.reason}. ${SLOT_NOT_GIVEN}`}</p>;
  if (found.row.state !== "read_back") {
    return <p className="console-muted" data-testid="read-value">{`No value was read back for this element: ${found.row.reason ?? "the read-back gives no position"}. ${SLOT_NOT_GIVEN}`}</p>;
  }
  return (
    <p className="console-muted" data-testid="read-value">
      Read back: <span className="inst-name">{found.row.value}</span> · read {shortTime(found.row.t_wall)}
      {found.row.backend === "mock" && <> · <span className="inst-backend">the mock&apos;s state</span></>}. {SLOT_NOT_GIVEN}
    </p>
  );
}

function SlotList({ el, found, set }: { el: OrderElement; found: Found; set: HandSet }) {
  const { addSelector } = useChanges();
  const [refused, setRefused] = useState<string | undefined>(undefined);
  return (
    <>
      <p className="console-muted">{HAND_SELECTOR_SAYS}</p>
      <ul aria-label={`Slots of ${el.element}`}>
        {set.slots.map((s) => (
          <li key={s.slot} data-slot={s.slot}>
            <span className="inst-name">{s.name ?? "no name given"}</span> (slot {s.slot})
            {!s.resolves && <> · <span className="console-muted">a plan cannot name it: {s.why}</span></>}
            {" "}
            <button type="button" onClick={() => setRefused(addSelector(el.element, el.channel, s))}>{`Choose slot ${s.slot}`}</button>
          </li>
        ))}
      </ul>
      <ReadBackValue found={found} />
      {refused !== undefined && <p role="alert" className="console-error">{refused}</p>}
    </>
  );
}

/** What was last sent to an element with no control, in the run's own words. */
function LastSent({ el, found, run }: { el: OrderElement; found: Found; run: LatestRun }) {
  if (el.channel === "optical_tweezers") {
    const s = run.strength_last_sent;
    return <p><span>Last sent:</span> {s === null || s === undefined ? "nothing sent in this run's events" : `strength ${s}`}</p>;
  }
  if (found.kind !== "row") return <p><span>Last sent:</span> nothing this page can show: the read-back holds no such element</p>;
  const r = found.row;
  return (
    <p>
      <span>Last sent:</span>{" "}
      {r.sent ? `${r.sent}${r.sent_at ? ` at ${shortTime(r.sent_at)}` : ""}` : "nothing sent in this run's events"}
    </p>
  );
}

export function ClickPanel({ el, found, control, hand, run }: { el: OrderElement; found: Found; control: Control; hand: HandSet | undefined; run: LatestRun }) {
  const { addPart, go } = useChanges();
  const tab = tabOf(el.channel);
  return (
    <div role="group" aria-label={`Opened: ${el.element}`} className="inst-opened">
      {control.kind === "draft" && control.part !== null && (
        <PartDraft kind={control.part} label={DRAFT_LABEL[control.part]} onAdd={addPart} />
      )}
      {control.kind === "draft" && control.part === null && (
        <p className="console-muted">This element is drafted, but this page has no draft form for it. <RunRefuses /></p>
      )}
      {control.kind === "hand" && (hand === undefined || hand.slots.length === 0 ? (
        <p className="console-muted">{NO_SLOTS_GIVEN}</p>
      ) : (
        <SlotList el={el} found={found} set={hand} />
      ))}
      {control.kind === "none" && (
        el.channel !== null && NO_CONTROL_CHANNELS.includes(el.channel) ? (
          <>
            <p>No control is offered for the {el.channel === "laser_combiner" ? "laser combiner" : "trap"} here: it is not one of the three things a draft may set.</p>
            {el.channel === "laser_combiner" && <p className="console-muted">{COMBINER_SENTENCE}</p>}
            <LastSent el={el} found={found} run={run} />
          </>
        ) : (
          <p className="console-muted">{NO_CONTROL_HERE}</p>
        )
      )}
      {tab !== undefined && <button type="button" onClick={() => go(tab.tab)}>{`Open the ${tab.label} tab`}</button>}
      <p className="console-muted">{NOT_OFFERED}</p>
    </div>
  );
}
