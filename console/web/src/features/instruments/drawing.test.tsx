import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { ScreenContextProvider } from "../../app/screenContext";
import { fakeTransport } from "../../test/fakes";
import { PATHS as QPATHS } from "../questions/api";
import schema from "../../../../../contracts/schemas/idle_status.schema.json";
import { PATHS } from "./api";
import { ChangesProvider } from "./changes";
import type { LatestRun } from "./api";
import InstrumentsScreen from "./index";
import { type KindTable, DESCRIPTION_WORDS } from "./order";
import { NO_ORDER, PathPanel } from "./path";
import { AURA_REFUSED_LONGER, RUN_REFUSES } from "./parts";

/**
 * The light path drawn in the order light travels (console card 023, part 2). Every order used here is the schema file's own
 * `examples` or `x_refused`, read from `contracts/schemas/idle_status.schema.json` and not from a copy, and then changed by the
 * test where it needs a different order. What a source says is the fixture's: no element, branch or place is named by the page.
 */

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const DEF = (schema as Json).$defs.light_path_order as Json;
const EXAMPLES: Json[] = DEF.examples;
const REFUSED: Json[] = DEF.x_refused;
const READ = EXAMPLES.find((e) => e.status === "read") as Json;
const NOT_IN = EXAMPLES.find((e) => e.status === "not_in_snapshot") as Json;
const copy = <T,>(v: T): T => JSON.parse(JSON.stringify(v)) as T;

const RUN_ID = "run-20261026-001";
const T1 = "2026-10-26T09:00:01Z";
const KNOWN_DESCRIPTION: KindTable = { [READ.source_kind]: { kind: "description" } };
const KNOWN_OBSERVED: KindTable = { [READ.source_kind]: { kind: "observed" } };

interface Row {
  key: string; name: string; channel: string; state: string; value: string | null; t_wall: string | null; reason: string | null;
  backend: string | null; sent: string | null; sent_at: string | null; control: string | null; draft: string | null;
}
const row = (name: string, channel: string, state: string, extra: Partial<Row> = {}): Row => ({
  key: `${channel}/${name}`, name, channel, state, value: null, t_wall: null, reason: null, backend: null, sent: null, sent_at: null,
  control: "hand", draft: null, ...extra,
});
const read = (name: string, channel: string, value: string, extra: Partial<Row> = {}) =>
  row(name, channel, "read_back", { value, t_wall: T1, backend: "mock", ...extra });

/** The read-back rows that match the example order by exact name and channel, and two that the order does not name. */
const ROWS: Row[] = [
  read("dia_lamp", "stand_ti2e", "1", { control: "draft", draft: "dialamp" }),
  read("Aura", "stand_ti2e", "0", { control: "draft", draft: "aura" }),
  read("Nosepiece", "stand_ti2e", "3"),
];

const CHANNELS = {
  t_s: 2, t_wall: "2026-10-26T09:00:02Z", label: "after",
  rows: [
    { channel: "stand_ti2e", opened: true, detail: null, backend: "mock" },
    { channel: "camera_red", opened: false, detail: "camera_red did not open", backend: null },
  ],
};

function order(state: string, data: unknown = null, problems: string[] = []) {
  return { state, data, problems };
}

function runWith(ord: ReturnType<typeof order>, rows: Row[] = ROWS, extra: Json = {}): LatestRun {
  return {
    state: "ok", message: null, run_id: RUN_ID, started_at: "2026-10-26T09:00:00Z", running: true, ended_how: null, ended_at: null,
    plan_id: "p", frame_tap: false, channels: CHANNELS, events_seen: 3, traps: [], trap_series: [], strength_last_sent: null, piezo: [],
    path: { source: "run", run_id: RUN_ID, kind: null, t_wall: T1, written_at: null, ended_at: null, ended_how: null, detail: null, elements: rows, order: ord },
    ...extra,
  } as unknown as LatestRun;
}
const readRun = (data: unknown = READ, rows: Row[] = ROWS) => runWith(order("read", data), rows);

const clients: Client[] = [];
afterEach(() => {
  clients.splice(0).forEach((c) => c.events.stop());
  vi.useRealTimers();
});

function panelOf(run: LatestRun, kinds?: KindTable) {
  const fake = fakeTransport({});
  const client = new Client(fake.transport, "127.0.0.1");
  clients.push(client);
  const ui = (r: LatestRun) => (
    <ClientProvider client={client}>
      <ChangesProvider><PathPanel run={r} onDraft={() => undefined} kinds={kinds} /></ChangesProvider>
    </ClientProvider>
  );
  const out = render(ui(run));
  const panel = () => screen.getByRole("region", { name: "Live optical path" });
  const drawing = () => screen.queryByRole("group", { name: "Light path drawing" });
  return { ...out, fake, panel, drawing, again: (r: LatestRun) => out.rerender(ui(r)) };
}

const branchNames = () => screen.queryAllByRole("region", { name: /^Branch / }).map((r) => r.getAttribute("data-branch"));
const drawnNames = (branch: string) => {
  const b = screen.getByRole("region", { name: `Branch ${branch}` });
  return within(within(b).getByRole("list", { name: `${branch} elements` })).queryAllByRole("listitem").map((l) => l.querySelector(".inst-name")?.textContent);
};
const item = (name: string) => {
  const li = document.querySelector(`[data-drawn="${name}"]`);
  if (li === null) throw new Error(`nothing drawn for ${name}`);
  return li as HTMLElement;
};
const stateOf = (li: HTMLElement) => Array.from(li.querySelectorAll("[data-state]")).map((n) => n.textContent);
const controlOf = (li: HTMLElement) => Array.from(li.querySelectorAll("[data-control]")).map((n) => n.textContent);

describe("the schema's examples are what these tests read", () => {
  it("holds a read order and a not_in_snapshot order and refused instances", () => {
    expect(READ).toBeTruthy();
    expect(NOT_IN).toBeTruthy();
    expect(REFUSED.length).toBeGreaterThan(1);
  });
});

describe("the drawing follows the order", () => {
  it("draws each branch the order names, with its elements in the order's own order", () => {
    panelOf(readRun());
    expect(branchNames()).toEqual(READ.branches.map((b: Json) => b.branch));
    for (const b of READ.branches as Json[]) expect(drawnNames(b.branch)).toEqual(b.elements.map((e: Json) => e.element));
  });

  it("says nothing of read-back elements when the order names every one of them", () => {
    panelOf(readRun(READ, ROWS.filter((r) => r.name === "dia_lamp")));
    expect(screen.queryByText(/not named in this order/)).toBeNull();
  });

  it("counts the read-back elements the order does not name, and names none of them", () => {
    panelOf(readRun());
    expect(screen.getByText(/2 read-back elements are not named in this order, so they are not drawn\./)).toBeTruthy();
    expect(screen.queryByText("Nosepiece")).toBeNull();
    expect(screen.queryByText("Aura")).toBeNull();
  });

  it("follows a reorder, a rename and a removal in the order", () => {
    const o = copy(READ);
    o.branches[0].elements.reverse();
    const first = o.branches[0].elements[0].element;
    const view = panelOf(readRun(o));
    expect(drawnNames(o.branches[0].branch)).toEqual(o.branches[0].elements.map((e: Json) => e.element));
    expect(drawnNames(o.branches[0].branch)[0]).toBe(first);

    const renamed = copy(READ);
    renamed.branches[0].elements[0].element = "renamed_element";
    view.again(readRun(renamed));
    expect(drawnNames(renamed.branches[0].branch)[0]).toBe("renamed_element");
    expect(screen.queryByText("dia_lamp")).toBeNull();

    const removed = copy(READ);
    removed.branches[0].elements.splice(1, 1);
    view.again(readRun(removed));
    expect(drawnNames(removed.branches[0].branch)).toEqual([READ.branches[0].elements[0].element]);
    expect(screen.queryByText("polarizer")).toBeNull();
  });

  it("draws no branch the order does not name, and none of its own", () => {
    const o = copy(READ);
    o.branches = [o.branches[0]];
    panelOf(readRun(o, [...ROWS, read("Objective", "stand_ti2e", "2")]));
    expect(branchNames()).toEqual([o.branches[0].branch]);
    for (const n of ["Aura", "Nosepiece", "Objective"]) expect(document.querySelector(`[data-drawn="${n}"]`)).toBeNull();
  });

  it("an order with two branches draws both, in the order's sequence, and one with none draws no branch", () => {
    const o = copy(READ);
    o.branches = [{ ...copy(READ.branches[0]), branch: "second_branch" }, { ...copy(READ.branches[0]), branch: "first_branch" }];
    const view = panelOf(readRun(o));
    expect(branchNames()).toEqual(["second_branch", "first_branch"]);
    const none = copy(READ);
    none.branches = [];
    view.again(readRun(none));
    expect(branchNames()).toEqual([]);
    expect(view.drawing()).not.toBeNull();
  });

  it("the stand picture is gone: no picture of the stand and no part named only by the old rows", () => {
    panelOf(readRun());
    expect(screen.queryByRole("figure", { name: "Picture of the stand" })).toBeNull();
    expect(screen.queryByText(/Condenser turret/)).toBeNull();
    expect(screen.queryByText(/Spectra III via DMD/)).toBeNull();
  });
});

describe("a source with no order is 017's list, and nothing is drawn", () => {
  const listed = () => within(screen.getByRole("list", { name: "Path elements" })).getAllByRole("listitem");

  it("no order key", () => {
    const view = panelOf(runWith(order("none")));
    expect(view.drawing()).toBeNull();
    expect(branchNames()).toEqual([]);
    expect(within(view.panel()).getByText(NO_ORDER)).toBeTruthy();
    expect(listed()).toHaveLength(ROWS.length);
  });

  it("a status file written before the order existed has no order key at all", () => {
    const run = readRun();
    delete (run.path as Json).order;
    const view = panelOf(run);
    expect(view.drawing()).toBeNull();
    expect(within(view.panel()).getByText(NO_ORDER)).toBeTruthy();
    expect(listed()).toHaveLength(ROWS.length);
  });

  it("not_in_snapshot: the list, the file's reason, and no drawing", () => {
    const view = panelOf(runWith(order("not_in_snapshot", NOT_IN)));
    expect(view.drawing()).toBeNull();
    expect(branchNames()).toEqual([]);
    expect(within(view.panel()).getByText(NO_ORDER)).toBeTruthy();
    expect(within(view.panel()).getByText(new RegExp(NOT_IN.reason))).toBeTruthy();
    expect(listed()).toHaveLength(ROWS.length);
    expect(view.panel().textContent).not.toContain("from a description");
  });

  it.each(REFUSED.map((_, i) => i))("x_refused[%i], as the server judged it, is an order not understood: the list, its problems, nothing drawn", (i) => {
    const why = [`$.light_path_order: refused instance ${i}`];
    const view = panelOf(runWith(order("not_understood", null, why)));
    expect(view.drawing()).toBeNull();
    expect(branchNames()).toEqual([]);
    expect(within(view.panel()).getByText(/not understood/i)).toBeTruthy();
    expect(within(view.panel()).getByText(NO_ORDER)).toBeTruthy();
    expect(view.panel().textContent).toContain(why[0]);
    expect(listed()).toHaveLength(ROWS.length);
  });

  it("a read order whose pieces do not narrow is not drawn in part, however much of it is sound", () => {
    const o = copy(READ);
    o.branches[0].elements[1] = { element: 7, channel: null, entry_ref: ["x"] };
    const view = panelOf(readRun(o));
    expect(view.drawing()).toBeNull();
    expect(branchNames()).toEqual([]);
    expect(within(view.panel()).getByText(/not understood/i)).toBeTruthy();
    expect(listed()).toHaveLength(ROWS.length);
  });

  it("a read order with no data is not understood", () => {
    const view = panelOf(runWith(order("read", null)));
    expect(view.drawing()).toBeNull();
    expect(within(view.panel()).getByText(/not understood/i)).toBeTruthy();
  });
});

describe("the banner", () => {
  it("an order from a description reads exactly the words, in an element that holds nothing else", () => {
    panelOf(readRun(), KNOWN_DESCRIPTION);
    const banner = screen.getByText(DESCRIPTION_WORDS);
    expect(banner.textContent).toBe("from a description, not checked on this microscope");
    expect(banner.getAttribute("data-banner")).toBe("description");
  });

  it("a source kind the page has no words for shows the grade as given, never observed, and never the description's words", () => {
    panelOf(readRun(), {});
    const banner = document.querySelector("[data-banner]") as HTMLElement;
    expect(banner.getAttribute("data-banner")).toBe("unknown");
    expect(banner.textContent).toContain(READ.grade);
    expect(banner.textContent).toContain(READ.source_kind);
    expect(screen.getByRole("region", { name: "Live optical path" }).textContent).not.toMatch(/observed/i);
    expect(screen.queryByText(DESCRIPTION_WORDS)).toBeNull();
  });

  it("the page's own table starts empty, so an order straight from the schema's example reads as unknown", () => {
    panelOf(readRun());
    expect((document.querySelector("[data-banner]") as HTMLElement).getAttribute("data-banner")).toBe("unknown");
  });

  it.each(["constructor", "__proto__", "toString", "hasOwnProperty"])("a source kind that is a name every object has (%s) is not in the table", (kind) => {
    const o = copy(READ);
    o.source_kind = kind;
    panelOf(readRun(o));
    expect((document.querySelector("[data-banner]") as HTMLElement).getAttribute("data-banner")).toBe("unknown");
  });

  it("an observed order replaces the drawing whole, and the banner names its grade", () => {
    const view = panelOf(readRun(), KNOWN_DESCRIPTION);
    expect(screen.getByText(DESCRIPTION_WORDS)).toBeTruthy();
    const seen = copy(READ);
    seen.grade = "E2";
    seen.entry_ref = "light_path_order_observed_20261101";
    seen.source = "an observation at the stand";
    seen.branches = [{ branch: "observed_branch", elements: [{ element: "only_observed", channel: null, entry_ref: ["an_entry"] }], place_not_recorded: [] }];
    view.rerender(<ClientProvider client={clients[0]}><ChangesProvider><PathPanel run={readRun(seen)} onDraft={() => undefined} kinds={KNOWN_OBSERVED} /></ChangesProvider></ClientProvider>);
    expect(screen.queryByText(DESCRIPTION_WORDS)).toBeNull();
    const banner = document.querySelector("[data-banner]") as HTMLElement;
    expect(banner.getAttribute("data-banner")).toBe("observed");
    expect(banner.textContent).toContain("E2");
    expect(branchNames()).toEqual(["observed_branch"]);
    const text = screen.getByRole("region", { name: "Live optical path" }).textContent as string;
    for (const gone of ["dia_lamp", "polarizer", "intermediate_magnification", READ.entry_ref, "transmitted"]) expect(text).not.toContain(gone);
  });
});

describe("holes", () => {
  it("a branch with a hole is drawn only as far as its order goes, with no line after its last element", () => {
    panelOf(readRun(), KNOWN_DESCRIPTION);
    const b = READ.branches[0];
    const region = screen.getByRole("region", { name: `Branch ${b.branch}` });
    const drawn = within(region).getByRole("list", { name: `${b.branch} elements` });
    expect(within(drawn).getAllByRole("listitem")).toHaveLength(b.elements.length);
    expect(drawn.querySelectorAll("[data-join]")).toHaveLength(b.elements.length - 1);
    const last = within(drawn).getAllByRole("listitem").at(-1) as HTMLElement;
    expect(last.querySelector("[data-join]")).toBeNull();
  });

  it("an element with no recorded place reads 'place not recorded' beside its branch, never in the drawn list and never joined", () => {
    panelOf(readRun(), KNOWN_DESCRIPTION);
    const b = READ.branches[0];
    const hole = b.place_not_recorded[0].element;
    expect(drawnNames(b.branch)).not.toContain(hole);
    const region = screen.getByRole("region", { name: `Branch ${b.branch}` });
    const beside = within(region).getByRole("group", { name: `${b.branch}: place not recorded` });
    const li = within(beside).getByText(hole).closest("li") as HTMLElement;
    expect(li.textContent).toContain("place not recorded");
    expect(li.querySelector("[data-join]")).toBeNull();
    expect(li.getAttribute("data-hole")).toBe(b.branch);
  });

  it("a hole's live value is shown when the read-back has it, and not invented when it has not", () => {
    const o = copy(READ);
    const hole = o.branches[0].place_not_recorded[0];
    const view = panelOf(readRun(o, [...ROWS, read(hole.element, hole.channel, "4")]));
    const li = item(hole.element);
    expect(li.textContent).toContain("4");
    expect(stateOf(li)).toEqual(["read back"]);
    view.again(readRun(o, ROWS));
    expect(stateOf(item(hole.element))).toEqual(["not read"]);
    expect(item(hole.element).textContent).not.toMatch(/read 2026/);
  });

  it("a branch whose elements are all holes is drawn as no element, with every hole beside it", () => {
    const o = copy(READ);
    o.branches[0].place_not_recorded = o.branches[0].elements;
    o.branches[0].elements = [];
    panelOf(readRun(o));
    expect(drawnNames(o.branches[0].branch)).toEqual([]);
    const beside = screen.getByRole("group", { name: `${o.branches[0].branch}: place not recorded` });
    expect(within(beside).getAllByRole("listitem")).toHaveLength(2);
  });
});

describe("values", () => {
  it("an element the read-back omits, on a channel the run did not open, reads not open with the run's reason and no value", () => {
    const o = copy(READ);
    o.branches[0].elements.push({ element: "red_arm", channel: "camera_red", entry_ref: ["camera_red_entry"] });
    panelOf(readRun(o));
    const li = item("red_arm");
    expect(stateOf(li)).toEqual(["not open"]);
    expect(li.textContent).toContain("camera_red did not open");
    expect(li.textContent).not.toMatch(/read 2026|=|assumed/);
  });

  it("an element with no channel reads 'no channel', with no value and no state it could not have", () => {
    panelOf(readRun());
    const li = item("polarizer");
    expect(stateOf(li)).toEqual(["no channel"]);
    expect(li.textContent).not.toMatch(/read 2026|read back|not open/);
  });

  it("an element on an open channel that the read-back does not name reads not read and says the read-back names no such element", () => {
    const o = copy(READ);
    o.branches[0].elements.push({ element: "unnamed_turret", channel: "stand_ti2e", entry_ref: ["e"] });
    panelOf(readRun(o));
    const li = item("unnamed_turret");
    expect(stateOf(li)).toEqual(["not read"]);
    expect(li.textContent).toMatch(/names no element called unnamed_turret/);
  });

  it("a channel the page knows nothing of (no channels row) is not claimed open or closed", () => {
    const o = copy(READ);
    o.branches[0].elements.push({ element: "far_element", channel: "no_such_channel", entry_ref: ["e"] });
    panelOf(readRun(o));
    expect(stateOf(item("far_element"))).toEqual(["not read"]);
  });

  it("names are matched exactly: the read-back's DiaLamp is not the order's dia_lamp", () => {
    panelOf(readRun(READ, [read("DiaLamp", "stand_ti2e", "1")]));
    const li = item("dia_lamp");
    expect(stateOf(li)).toEqual(["not read"]);
    expect(li.textContent).not.toContain("read 2026");
  });

  it("a read-back row of the same name on another channel is not the order's element", () => {
    panelOf(readRun(READ, [read("dia_lamp", "another_channel", "1")]));
    const li = item("dia_lamp");
    expect(stateOf(li)).toEqual(["not read"]);
    expect(li.textContent).not.toContain("read 2026");
  });

  it("an element matched in the order and the read-back shows 017's state with its time, and the mock's label", () => {
    panelOf(readRun());
    const li = item("dia_lamp");
    expect(stateOf(li)).toEqual(["read back"]);
    expect(li.textContent).toContain("read 2026-10-26 09:00:01");
    expect(li.textContent).toContain("the mock's state");
  });

  it("a sent state is shown as sent, with what was sent, and a not-read state with its reason and no value", () => {
    const rows = [
      row("dia_lamp", "stand_ti2e", "sent", { sent: '{"state": "on"}', sent_at: "2026-10-26T09:00:05Z", control: "draft", draft: "dialamp" }),
      row("polarizer", "stand_ti2e", "not_read", { reason: "busy at the read" }),
    ];
    const o = copy(READ);
    o.branches[0].elements[1].channel = "stand_ti2e";
    panelOf(readRun(o, rows));
    expect(stateOf(item("dia_lamp"))).toEqual(["sent"]);
    expect(item("dia_lamp").textContent).toContain('sent {"state": "on"} at 2026-10-26 09:00:05');
    expect(stateOf(item("polarizer"))).toEqual(["not read"]);
    expect(item("polarizer").textContent).toContain("busy at the read");
  });
});

describe("controls and the notice", () => {
  it("a drafted element says drafted and carries 017's refusal notice word for word, the Aura's longer one included", () => {
    const o = copy(READ);
    o.branches[0].elements.push({ element: "Aura", channel: "stand_ti2e", entry_ref: ["e"] });
    panelOf(readRun(o));
    expect(controlOf(item("dia_lamp"))).toEqual(["drafted"]);
    expect(item("dia_lamp").textContent).toContain(RUN_REFUSES);
    expect(item("dia_lamp").textContent).not.toContain(AURA_REFUSED_LONGER);
    expect(controlOf(item("Aura"))).toEqual(["drafted"]);
    expect(item("Aura").textContent).toContain(RUN_REFUSES);
    expect(item("Aura").textContent).toContain(AURA_REFUSED_LONGER);
  });

  it("an element in the order's hand_set reads moved by hand, and so does a matched element the read-back says is by hand", () => {
    const o = copy(READ);
    const hand = o.hand_set[0];
    o.branches[0].elements.push({ element: hand.element, channel: hand.channel, entry_ref: ["e"] }, { element: "Nosepiece", channel: "stand_ti2e", entry_ref: ["e"] });
    panelOf(readRun(o));
    expect(controlOf(item(hand.element))).toEqual(["moved by hand"]);
    expect(controlOf(item("Nosepiece"))).toEqual(["moved by hand"]);
  });

  it("a hand_set entry for the same element on another channel does not make this one moved by hand", () => {
    const o = copy(READ);
    const hand = o.hand_set[0];
    o.branches[0].elements.push({ element: hand.element, channel: `${hand.channel}_other`, entry_ref: ["e"] });
    panelOf(readRun(o, []));
    expect(controlOf(item(hand.element))).toEqual(["control not given"]);
  });

  it("an element whose control nothing names says so, and is not given a label it was not given", () => {
    panelOf(readRun());
    expect(controlOf(item("polarizer"))).toEqual(["control not given"]);
  });

  it("every drawn element carries its entry id as text", () => {
    panelOf(readRun());
    for (const e of [...READ.branches[0].elements, ...READ.branches[0].place_not_recorded] as Json[]) {
      const li = item(e.element);
      for (const id of e.entry_ref) expect(li.querySelector(".inst-entry")?.textContent).toContain(id);
    }
    expect(screen.getByRole("region", { name: "Live optical path" }).textContent).toContain(READ.entry_ref);
  });

  it("an entry id is text and nothing follows it: no link anywhere in the drawing, and pressing it sends nothing", async () => {
    const view = panelOf(readRun());
    const drawing = view.drawing() as HTMLElement;
    expect(drawing.querySelectorAll("a")).toHaveLength(0);
    expect(drawing.querySelectorAll("[href]")).toHaveLength(0);
    const id = within(drawing).getAllByText(READ.branches[0].elements[0].entry_ref[0])[0];
    fireEvent.click(id);
    fireEvent.doubleClick(id);
    await act(async () => { await Promise.resolve(); });
    expect(view.fake.calls).toEqual([]);
    expect(window.location.hash).toBe("");
  });
});

describe("lines show order, never light", () => {
  it("turning a source on changes that source's label and nothing on any line", () => {
    const off = [read("dia_lamp", "stand_ti2e", "0", { control: "draft", draft: "dialamp" }), ...ROWS.slice(1)];
    const on = [read("dia_lamp", "stand_ti2e", "1", { control: "draft", draft: "dialamp" }), ...ROWS.slice(1)];
    const view = panelOf(readRun(READ, off));
    const marks = () => {
      const d = view.drawing() as HTMLElement;
      return {
        joins: Array.from(d.querySelectorAll("[data-join]")).map((n) => n.outerHTML),
        classes: Array.from(d.querySelectorAll("*")).map((n) => `${n.tagName}.${n.className}`),
        styles: Array.from(d.querySelectorAll("[style]")).map((n) => n.getAttribute("style")),
        others: Array.from(d.querySelectorAll("li")).filter((n) => n.getAttribute("data-drawn") !== "dia_lamp").map((n) => n.textContent),
        lamp: item("dia_lamp").querySelector("[data-state]")?.outerHTML,
        lampText: item("dia_lamp").textContent,
      };
    };
    const a = marks();
    view.again(readRun(READ, on));
    const b = marks();
    expect(b.joins).toEqual(a.joins);
    expect(b.classes).toEqual(a.classes);
    expect(b.styles).toEqual(a.styles);
    expect(b.others).toEqual(a.others);
    expect(b.lamp).toEqual(a.lamp);
    expect(b.lampText).not.toEqual(a.lampText);
  });

  it("no line is lit or coloured, ends in a detector, or says which camera a state reaches", () => {
    const view = panelOf(readRun());
    const d = view.drawing() as HTMLElement;
    for (const j of Array.from(d.querySelectorAll("[data-join]"))) {
      expect(j.getAttribute("aria-hidden")).toBe("true");
      expect(j.textContent).toBe("");
      expect(j.getAttribute("style")).toBeNull();
      expect(j.className).toBe("inst-join");
    }
    expect(d.textContent).not.toMatch(/camera|detector|lit\b|beam reaches/i);
    expect(screen.getByText(/Lines show the order light travels/)).toBeTruthy();
  });
});

describe("the whole screen, with nothing sent", () => {
  function showScreen(run: LatestRun) {
    window.location.hash = "#/instruments/optics";
    const fake = fakeTransport({
      [PATHS.status]: () => ({ status: 200, body: { state: "none", data: null, problems: [] } }),
      [PATHS.limits]: () => ({ status: 200, body: { state: "none", piezo: {}, tweezers: {}, problems: [] } }),
      [PATHS.latestRun]: () => ({ status: 200, body: run }),
      [QPATHS.signing]: () => ({ status: 200, body: { person_named: true, is_person: true, practice: false, approvals_folder: true } }),
    });
    const client = new Client(fake.transport, "127.0.0.1");
    clients.push(client);
    render(
      <ClientProvider client={client}>
        <ScreenContextProvider area="instruments"><InstrumentsScreen /></ScreenContextProvider>
      </ClientProvider>,
    );
    return fake;
  }

  it("shows the drawing for a read order, and each of the schema's examples as its status says", async () => {
    showScreen(readRun());
    expect(await screen.findByRole("group", { name: "Light path drawing" })).toBeTruthy();
    expect(branchNames()).toEqual(READ.branches.map((b: Json) => b.branch));
  });

  it("shows 017's list for the not_in_snapshot example", async () => {
    showScreen(runWith(order("not_in_snapshot", NOT_IN)));
    expect(await screen.findByText(NO_ORDER)).toBeTruthy();
    expect(screen.queryByRole("group", { name: "Light path drawing" })).toBeNull();
  });

  it("no request but the reads of files leaves the page while it renders or refreshes", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    const fake = showScreen(readRun());
    await screen.findByRole("group", { name: "Light path drawing" });
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(fake.calls.filter((c) => c.init?.method !== undefined && c.init.method !== "GET")).toEqual([]);
    const allowed = new Set<string>([PATHS.status, PATHS.limits, PATHS.latestRun, QPATHS.signing]);
    expect(fake.calls.map((c) => c.path).filter((p) => !allowed.has(p))).toEqual([]);
  });
});
