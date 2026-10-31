/**
 * The example drawing the sample shows until a recorded order arrives (console card 025). It is **not an order**: it comes from
 * `path.example`, beside the order and never inside it, and the server gives it only for the sample while the order's state is
 * `none`. So it carries no entry, no grade and no read-back, and nothing here looks for one.
 *
 * What is drawn is each element's label and setting exactly as the file has them, in the file's order, and **nothing else**: no
 * name, state or control of its own is written in this file, and the page adds no word to either. A click opens the element in a panel beside
 * the areas, as a real element does, says its kind of control in the file's words, and says nothing can be done: there is no field,
 * list, selector or button in what opens, nothing it does reaches the changes or [Apply], and nothing it does sends a request.
 */

import { useId, useState } from "react";

import type { LatestRun } from "./api";

export type Example = NonNullable<LatestRun["path"]["example"]>;

export const EXAMPLE_MARK = "Example: not this microscope's path";
export const EXAMPLE_NOTHING = "Example: nothing here can be changed or drafted.";

type ExampleElement = Example["branches"][number]["elements"][number];

/** A box, as the real drawing's (card 026): the label first, the setting beneath it, and nothing else. The box is one button. */
function Item({ el, join, opened, onToggle }: { el: ExampleElement; join: boolean; opened: boolean; onToggle: () => void }) {
  const lines = useId();
  return (
    <li data-example-element={el.id}>
      <button type="button" className="inst-box" aria-label={`Open ${el.label}`} aria-expanded={opened} aria-describedby={lines} onClick={onToggle}>
        <span className="inst-name">{el.label}</span>
        <span className="inst-lines" id={lines}>{el.setting}</span>
      </button>
      {join && <span className="inst-join" aria-hidden="true" />}
    </li>
  );
}

export function ExampleDrawing({ example }: { example: Example }) {
  // One box is open at a time; its panel stands beside the areas and inside this frame, and holds no button, so it has no close button.
  const [openId, setOpenId] = useState<string | null>(null);
  const open = openId === null ? undefined : example.branches.flatMap((b) => b.elements).find((e) => e.id === openId);
  return (
    <section aria-label="Example light path" className="inst-example">
      <h3>{EXAMPLE_MARK}</h3>
      <div className="inst-stage">
        <div className="inst-areas">
          {example.branches.map((b, i) => (
            <section key={i} aria-label="Example branch" className="inst-branch">
              <ol aria-label="Example elements">
                {b.elements.map((el, j) => (
                  <Item key={el.id} el={el} join={j < b.elements.length - 1} opened={openId === el.id} onToggle={() => setOpenId(openId === el.id ? null : el.id)} />
                ))}
              </ol>
            </section>
          ))}
        </div>
        {open !== undefined && (
          <div className="inst-side" key={open.id}>
            <div role="group" aria-label={`Opened: ${open.label}`} className="inst-opened">
              <h4 className="inst-opened-title">{open.label}</h4>
              <p>{open.label}: {open.control}</p>
              <p className="console-muted">{EXAMPLE_NOTHING}</p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
