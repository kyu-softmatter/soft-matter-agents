/**
 * The example drawing the sample shows until a recorded order arrives (console card 025). It is **not an order**: it comes from
 * `path.example`, beside the order and never inside it, and the server gives it only for the sample while the order's state is
 * `none`. So it carries no entry, no grade and no read-back, and nothing here looks for one.
 *
 * What is drawn is each element's label and setting exactly as the file has them, in the file's order, and **nothing else**: no
 * name, state or control of its own is written in this file, and the page adds no word to either. A click opens the element where
 * a real element opens, says its kind of control in the file's words, and says nothing can be done: there is no field, list,
 * selector or button in what opens, nothing it does reaches the changes or [Apply], and nothing it does sends a request.
 */

import { useState } from "react";

import type { LatestRun } from "./api";

export type Example = NonNullable<LatestRun["path"]["example"]>;

export const EXAMPLE_MARK = "Example: not this microscope's path";
export const EXAMPLE_NOTHING = "Example: nothing here can be changed or drafted.";

type ExampleElement = Example["branches"][number]["elements"][number];

function Item({ el, join }: { el: ExampleElement; join: boolean }) {
  const [opened, setOpened] = useState(false);
  return (
    <li data-example-element={el.id}>
      <span className="inst-name">{el.label}</span>
      {" · "}
      <span className="inst-state">{el.setting}</span>
      {" "}
      <button type="button" aria-label={`Open ${el.label}`} aria-expanded={opened} onClick={() => setOpened(!opened)}>{opened ? "close" : "open"}</button>
      {opened && (
        <div role="group" aria-label={`Opened: ${el.label}`} className="inst-opened">
          <p>{el.label}: {el.control}</p>
          <p className="console-muted">{EXAMPLE_NOTHING}</p>
        </div>
      )}
      {join && <span className="inst-join" aria-hidden="true" />}
    </li>
  );
}

export function ExampleDrawing({ example }: { example: Example }) {
  return (
    <section aria-label="Example light path" className="inst-example">
      <h3>{EXAMPLE_MARK}</h3>
      {example.branches.map((b, i) => (
        <section key={i} aria-label="Example branch" className="inst-branch">
          <ol aria-label="Example elements">
            {b.elements.map((el, j) => <Item key={el.id} el={el} join={j < b.elements.length - 1} />)}
          </ol>
        </section>
      ))}
    </section>
  );
}
