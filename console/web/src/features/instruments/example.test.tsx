import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { fakeTransport } from "../../test/fakes";
import schema from "../../../../../contracts/schemas/idle_status.schema.json";
import example from "../../../../src/sma_console/agents/mock_data/console/example/light_path.json";
import type { LatestRun } from "./api";
import { ChangesList, ChangesProvider, useChanges } from "./changes";
import { NO_ORDER, PathPanel } from "./path";

/**
 * The example drawing the sample shows until a recorded order arrives (console card 025, parts 3 to 5). The example is the sample's
 * own file, read from it here and not copied, and what the page may show of it is that file's labels and settings and nothing more.
 * An order is the schema file's own `examples` or `x_refused`, as in the drawing's tests.
 */

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const DEF = (schema as Json).$defs.light_path_order as Json;
const READ = (DEF.examples as Json[]).find((e) => e.status === "read") as Json;
const NOT_IN = (DEF.examples as Json[]).find((e) => e.status === "not_in_snapshot") as Json;
const REFUSED = (DEF.x_refused as Json[])[0];

const MARK = "Example: not this microscope's path";
const NOTHING = "Example: nothing here can be changed or drafted.";
const FILE_ELEMENTS: Json[] = (example as Json).branches.flatMap((b: Json) => b.elements);

const none = { state: "none", data: null, problems: [] };
function runWith(order: Json, ex: Json | null = example as Json): LatestRun {
  return {
    state: "ok", message: null, run_id: "run-20261026-001", started_at: "2026-10-26T09:00:00Z", running: false, ended_how: "completed",
    ended_at: "2026-10-26T09:05:00Z", plan_id: "p", frame_tap: false, channels: null, events_seen: 3, traps: [], trap_series: [],
    strength_last_sent: null, piezo: [],
    path: { source: "last_snapshot", run_id: "run-20261026-001", kind: null, t_wall: "2026-10-26T09:00:01Z", written_at: null, ended_at: null, ended_how: null, detail: null,
      elements: [], order, example: ex },
  } as unknown as LatestRun;
}

const clients: Client[] = [];
afterEach(() => clients.splice(0).forEach((c) => c.events.stop()));

/** What the changes hold, written out as text, so a test can compare it before and after. */
function Probe() {
  const { items, addPart } = useChanges();
  return (
    <>
      <pre data-testid="items">{JSON.stringify(items)}</pre>
      <button type="button" onClick={() => addPart("camera_exposure", { kind: "camera_exposure" } as never, "a camera exposure")}>seed a change</button>
    </>
  );
}

function view(run: LatestRun) {
  const fake = fakeTransport({});
  const client = new Client(fake.transport, "127.0.0.1");
  clients.push(client);
  render(
    <ClientProvider client={client}>
      <ChangesProvider>
        <PathPanel run={run} />
        <Probe />
        <ChangesList />
      </ChangesProvider>
    </ClientProvider>,
  );
  return { fake, section: () => screen.queryByRole("region", { name: "Example light path" }) };
}

const names = (section: HTMLElement) => Array.from(section.querySelectorAll(".inst-name")).map((n) => n.textContent);

describe("the example above 017's list", () => {
  it("is a section headed by the mark, at a heading level no lower than the panel's own, with the file's labels in its order", () => {
    const v = view(runWith(none));
    const section = v.section() as HTMLElement;
    expect(section).toBeTruthy();
    const heading = within(section).getByRole("heading", { name: MARK });
    const panel = screen.getByRole("heading", { name: "The light path, now" });
    expect(Number(heading.tagName.slice(1))).toBeLessThanOrEqual(Number(panel.tagName.slice(1)));
    expect(names(section)).toEqual(FILE_ELEMENTS.map((e) => e.label));
  });

  it("stands above 017's list, which and whose words are unchanged below it", () => {
    const v = view(runWith(none));
    const section = v.section() as HTMLElement;
    const words = screen.getByText(NO_ORDER);
    expect(section.compareDocumentPosition(words) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByRole("list", { name: "Path elements" })).toBeTruthy();
  });

  it("draws each element as its label and its setting from the file, and the page adds no word of its own to either", () => {
    const section = view(runWith(none)).section() as HTMLElement;
    const items = Array.from(section.querySelectorAll("li"));
    expect(items).toHaveLength(FILE_ELEMENTS.length);
    items.forEach((li, i) => {
      const clone = li.cloneNode(true) as HTMLElement;
      clone.querySelectorAll("button, .inst-join").forEach((n) => n.remove());
      expect((clone.textContent ?? "").trim()).toBe(`${FILE_ELEMENTS[i].label} · ${FILE_ELEMENTS[i].setting}`);
    });
  });

  it("shows no entry id, no grade, no link, no read-back and none of 017's states", () => {
    const section = view(runWith(none)).section() as HTMLElement;
    expect(section.querySelector(".inst-entry, .inst-entry-id, .inst-state[data-state], a, [href]")).toBeNull();
    expect(section.textContent).not.toMatch(/\bentry\b|grade|not open|not read|read back|read-back|no channel|place not recorded|lights off/i);
    expect(within(section).queryByRole("button", { name: /lights off/i })).toBeNull();
  });
});

describe("the example gives way", () => {
  it("to a read order, drawn as card 023 has it, with no example", () => {
    const v = view(runWith({ state: "read", data: READ, problems: [] }));
    expect(screen.getByRole("group", { name: "Light path drawing" })).toBeTruthy();
    expect(v.section()).toBeNull();
    expect(screen.queryByRole("heading", { name: MARK })).toBeNull();
    for (const e of FILE_ELEMENTS) expect(screen.queryByText(e.label)).toBeNull();
  });

  it("to a not_in_snapshot order, which shows 017's list with its reason and no example", () => {
    const v = view(runWith({ state: "not_in_snapshot", data: NOT_IN, problems: [] }));
    expect(screen.getByText(NO_ORDER)).toBeTruthy();
    expect(screen.getByText(`Why: ${NOT_IN.reason}`)).toBeTruthy();
    expect(v.section()).toBeNull();
  });

  it("to a not_understood order, which shows 017's list with its reasons and no example", () => {
    const v = view(runWith({ state: "not_understood", data: null, problems: ["a reason it is refused"] }));
    expect(screen.getByText("a reason it is refused")).toBeTruthy();
    expect(screen.getByText(NO_ORDER)).toBeTruthy();
    expect(v.section()).toBeNull();
    expect(REFUSED).toBeTruthy();
  });

  it("when the server gives none, which is every store but the sample, and shows 017's list alone", () => {
    const v = view(runWith(none, null));
    expect(v.section()).toBeNull();
    expect(screen.getByText(NO_ORDER)).toBeTruthy();
  });
});

describe("a click on an example element", () => {
  const open = (label: string) => fireEvent.click(screen.getByRole("button", { name: `Open ${label}` }));

  it("opens where a real element opens, names its kind of control in the file's words, and says nothing can be done", () => {
    view(runWith(none));
    for (const e of FILE_ELEMENTS) {
      open(e.label);
      const opened = screen.getByRole("group", { name: `Opened: ${e.label}` });
      expect(opened.textContent).toContain(e.control);
      expect(within(opened).getByText(NOTHING)).toBeTruthy();
      expect(opened.querySelector("input, select, textarea, button, a, [href], [role=button], [role=combobox], [role=listbox]")).toBeNull();
    }
  });

  it("changes neither the changes list nor [Apply]", async () => {
    view(runWith(none));
    fireEvent.click(screen.getByRole("button", { name: "seed a change" }));
    await act(async () => { await Promise.resolve(); });
    const state = () => ({
      items: screen.getByTestId("items").textContent,
      list: screen.getByRole("region", { name: "Changes" }).textContent,
      apply: (screen.getByRole("button", { name: "Apply" }) as HTMLButtonElement).disabled,
    });
    const before = state();
    expect(before.items).not.toBe("[]");
    for (const e of FILE_ELEMENTS) { open(e.label); open(e.label); open(e.label); }
    await act(async () => { await Promise.resolve(); });
    expect(state()).toEqual(before);
  });

  it("sends no request, however it is pressed", async () => {
    const v = view(runWith(none));
    for (const e of FILE_ELEMENTS) {
      open(e.label);
      const label = screen.getAllByText(e.label)[0];
      fireEvent.click(label);
      fireEvent.doubleClick(label);
    }
    await act(async () => { await Promise.resolve(); });
    expect(v.fake.calls).toEqual([]);
  });
});
