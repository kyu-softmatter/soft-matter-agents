import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { fakeTransport } from "../../test/fakes";
import schema from "../../../../../contracts/schemas/idle_status.schema.json";
import type { LatestRun } from "./api";
import { ChangesList, ChangesProvider, NOT_SAVED_WORDS, useChanges } from "./changes";
import { HAND_SELECTOR_SAYS, NOT_OFFERED, NO_SLOTS_GIVEN, SLOT_NOT_GIVEN } from "./click";
import { CHANNEL_DRAFT, CHANNEL_TAB, NO_CONTROL_CHANNELS } from "./join";
import { Optics } from "./optics";
import { PathPanel } from "./path";
import { COMBINER_SENTENCE, NO_DRAFT_LABEL, RUN_REFUSES } from "./parts";
import capabilities from "../../../../../contracts/capabilities/microscope.json";

/**
 * What a click opens in the drawing (console card 023, part 3). The order is the schema file's own read example, changed by the
 * test to name the elements it needs. No element, slot or word is named by the page: each is the fixture's.
 */

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const DEF = (schema as Json).$defs.light_path_order as Json;
const READ = (DEF.examples as Json[]).find((e) => e.status === "read") as Json;
const copy = <T,>(v: T): T => JSON.parse(JSON.stringify(v)) as T;

const RUN_ID = "run-20261026-001";
const T1 = "2026-10-26T09:00:01Z";
const REF = ["light_path_order_from_description_20261016"];
/** An element of the order. Its read-back pair is the fixture's own choice: the channel and the element's name, or none for an element with no channel. */
const place = (element: string, channel: string | null, read_back: { channel: string; name: string } | null | undefined = undefined) => ({
  element, channel, entry_ref: REF, read_back: read_back === undefined ? (channel === null ? null : { channel, name: element }) : read_back,
});
const pairOf = (element: string, channel: string) => ({ channel, name: element });

interface Row {
  key: string; name: string; channel: string; state: string; value: string | null; t_wall: string | null; reason: string | null;
  backend: string | null; sent: string | null; sent_at: string | null; control: string | null; draft: string | null; words: string | null;
}
const row = (name: string, channel: string, state: string, extra: Partial<Row> = {}): Row => ({
  key: `${channel}/${name}`, name, channel, state, value: null, t_wall: null, reason: null, backend: null, sent: null, sent_at: null,
  control: "hand", draft: null, words: null, ...extra,
});
const read = (name: string, channel: string, value: string, extra: Partial<Row> = {}) =>
  row(name, channel, "read_back", { value, t_wall: T1, backend: "mock", ...extra });

/** The two sentences card 024 gives, word for word; the server pins the same ones, so a change on either side fails a test here. */
const AURA_WORDS = "No draft is offered for the Aura yet. A plan will name the light engine by its model, and the console has nowhere to read that model from yet, so it guesses none.";
const LAMP_WORDS = "No draft is offered for the transmitted lamp yet. The run has no recorded quantity for its brightness, and no table of its on and off states.";

const ROWS: Row[] = [
  read("dia_lamp", "stand_ti2e", "1", { control: "no_draft", words: LAMP_WORDS }),
  read("filter_turret_1", "stand_ti2e", "five_band"),
  read("nosepiece", "stand_ti2e", "3"),
  row("laser_shutter", "laser_combiner", "sent", { control: null, sent: '{"shutter":"closed"}', sent_at: T1 }),
  read("kinetix_exposure", "camera_red", "10"),
  read("stage_z", "piezo_stage", "100"),
  read("trap_laser", "optical_tweezers", "on"),
  read("disk_position", "confocal_csuw1", "1"),
  read("blue_gain", "camera_blue", "2"),
];

/** An order that names every kind of element a click can open, and a hand_set that gives two slots for one of them. */
function orderWithElements() {
  const o = copy(READ);
  o.branches[0].elements = [
    place("dia_lamp", "stand_ti2e"), place("filter_turret_1", "stand_ti2e"), place("nosepiece", "stand_ti2e"),
    place("polarizer", null), place("laser_shutter", "laser_combiner"), place("kinetix_exposure", "camera_red"),
    place("stage_z", "piezo_stage"), place("trap_laser", "optical_tweezers"),
    place("objective_turret", "stand_ti2e"), place("disk_position", "confocal_csuw1"), place("blue_gain", "camera_blue"),
  ];
  o.branches[0].place_not_recorded = [];
  return o;
}

function runWith(rows: Row[] = ROWS, order: unknown = orderWithElements(), extra: Json = {}): LatestRun {
  return {
    state: "ok", message: null, run_id: RUN_ID, started_at: "2026-10-26T09:00:00Z", running: true, ended_how: null, ended_at: null,
    plan_id: "p", frame_tap: false, events_seen: 3, traps: [], trap_series: [], strength_last_sent: 0.25, piezo: [],
    channels: {
      t_s: 2, t_wall: "2026-10-26T09:00:02Z", label: "after",
      rows: [
        { channel: "stand_ti2e", opened: true, detail: null, backend: "mock" },
        { channel: "camera_red", opened: true, detail: null, backend: "mock" },
      ],
    },
    path: { source: "run", run_id: RUN_ID, kind: null, t_wall: T1, written_at: null, ended_at: null, ended_how: null, detail: null,
      elements: rows, order: { state: "read", data: order, problems: [] } },
    ...extra,
  } as unknown as LatestRun;
}

const clients: Client[] = [];
afterEach(() => {
  clients.splice(0).forEach((c) => c.events.stop());
  vi.useRealTimers();
});

function show(run: LatestRun = runWith(), onTab: (rest: string) => void = () => undefined) {
  const fake = fakeTransport({});
  const client = new Client(fake.transport, "127.0.0.1");
  clients.push(client);
  const out = render(
    <ClientProvider client={client}>
      <ChangesProvider onTab={onTab}>
        <PathPanel run={run} />
        <ChangesList />
      </ChangesProvider>
    </ClientProvider>,
  );
  return { ...out, fake };
}

const opener = (name: string) => screen.getByRole("button", { name: `Open ${name}` });
const open = (name: string) => {
  fireEvent.click(opener(name));
  return screen.getByRole("group", { name: `Opened: ${name}` });
};
const changes = () => screen.getByRole("region", { name: "Changes" });
const changeWords = () => within(changes()).queryAllByRole("listitem").map((l) => l.querySelector("[data-words]")?.textContent);

describe("a click opens an element and nothing else", () => {
  it("opens nothing until an element is clicked, and closes it on a second click", () => {
    show();
    expect(screen.queryByRole("group", { name: /^Opened: / })).toBeNull();
    open("dia_lamp");
    expect(opener("dia_lamp").getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(opener("dia_lamp"));
    expect(screen.queryByRole("group", { name: "Opened: dia_lamp" })).toBeNull();
    expect(opener("dia_lamp").getAttribute("aria-expanded")).toBe("false");
  });

  it("makes no request while it renders, opens an element, chooses a slot or refreshes", () => {
    const view = show();
    open("filter_turret_1");
    fireEvent.click(screen.getByRole("button", { name: "Choose slot 0" }));
    open("dia_lamp");
    expect(view.fake.calls).toEqual([]);
  });
});

describe("the red camera's exposure opens its fields in place; the Aura and the lamp open words and no fields", () => {
  it("opens the lamp with the server's words, no fields, no draft button and no refusal notice", () => {
    show();
    const box = open("dia_lamp");
    expect(within(box).getByText(LAMP_WORDS)).toBeTruthy();
    expect(within(box).queryAllByRole("textbox").length + within(box).queryAllByRole("combobox").length + within(box).queryAllByRole("spinbutton").length).toBe(0);
    expect(within(box).queryByRole("button", { name: /draft|add to the changes/i })).toBeNull();
    expect(within(box).queryByRole("group", { name: "Transmitted lamp" })).toBeNull();
    expect(box.textContent).not.toContain(RUN_REFUSES);
    expect(within(box).queryByRole("button", { name: /Light source tab/ })).toBeNull();
  });

  it("opens the Aura the same way, with its own words", () => {
    const o = orderWithElements();
    o.branches[0].elements.push(place("aura", "stand_ti2e"));
    show(runWith([...ROWS, read("aura", "stand_ti2e", "off", { control: "no_draft", words: AURA_WORDS })], o));
    const box = open("aura");
    expect(within(box).getByText(AURA_WORDS)).toBeTruthy();
    expect(within(box).queryAllByRole("textbox").length + within(box).queryAllByRole("combobox").length).toBe(0);
    expect(within(box).queryByRole("button", { name: /draft|add to the changes/i })).toBeNull();
    expect(within(box).queryByRole("group", { name: "Aura III LED" })).toBeNull();
  });

  it("says in the drawing, beside the element, that no draft is offered yet, and not that it is drafted", () => {
    show();
    const li = document.querySelector('[data-drawn="dia_lamp"]') as HTMLElement;
    expect(Array.from(li.querySelectorAll("[data-control]")).map((n) => [n.getAttribute("data-control"), n.textContent])).toEqual([["no_draft", NO_DRAFT_LABEL]]);
    expect(NO_DRAFT_LABEL).toBe("no draft is offered yet");
    expect(li.textContent).not.toContain("drafted");
    expect(li.textContent).not.toContain(RUN_REFUSES);
  });

  it("takes no words of its own: a no-draft row that carries none is shown with no control given", () => {
    show(runWith(ROWS.map((r) => (r.name === "dia_lamp" ? { ...r, words: null } : r))));
    const box = open("dia_lamp");
    expect(box.textContent).not.toContain("No draft is offered");
    expect(within(box).getByText("This page is given no control for this element.")).toBeTruthy();
  });

  it("opens the red camera's exposure field for an element on the red camera's channel, though the read-back calls it moved by hand", () => {
    show();
    const box = open("kinetix_exposure");
    expect(within(box).getByRole("group", { name: "Camera red arm exposure" })).toBeTruthy();
    expect(within(box).getByLabelText("Exposure (ms)")).toBeTruthy();
    expect(within(box).getAllByText(RUN_REFUSES).length).toBeGreaterThan(0);
  });

  it("labels the red camera's exposure as drafted in the drawing too, not as moved by hand", () => {
    show();
    const li = document.querySelector('[data-drawn="kinetix_exposure"]') as HTMLElement;
    expect(Array.from(li.querySelectorAll("[data-control]")).map((n) => n.getAttribute("data-control"))).toEqual(["draft"]);
  });

  it("adds a filled draft to the changes, in words, and refuses an empty one without adding it", () => {
    show();
    const box = open("kinetix_exposure");
    fireEvent.click(within(box).getByRole("button", { name: "Add to the changes" }));
    expect(within(box).getByRole("alert").textContent).toMatch(/exposure/i);
    expect(changeWords()).toEqual([]);
    fireEvent.change(within(box).getByLabelText("Exposure (ms)"), { target: { value: "40" } });
    fireEvent.click(within(box).getByRole("button", { name: "Add to the changes" }));
    expect(changeWords()).toEqual(["Camera red arm exposure: 40 ms"]);
  });

  it("refuses a second draft of the same part until the first is removed", () => {
    show();
    const box = open("kinetix_exposure");
    fireEvent.change(within(box).getByLabelText("Exposure (ms)"), { target: { value: "40" } });
    fireEvent.click(within(box).getByRole("button", { name: "Add to the changes" }));
    fireEvent.click(within(box).getByRole("button", { name: "Add to the changes" }));
    expect(within(box).getByRole("alert").textContent).toMatch(/already/);
    expect(changeWords()).toHaveLength(1);
  });
});

describe("a part moved by hand opens its slot list", () => {
  const hand = (slots: Json[]) => {
    const o = orderWithElements();
    o.hand_set = [{ element: "filter_turret_1", channel: "stand_ti2e", slots, read_back: pairOf("filter_turret_1", "stand_ti2e") }];
    return runWith(ROWS, o);
  };
  const SLOTS = [
    { slot: 0, name: "five_band", resolves: true, entry_ref: "filter_turret_1_slot_0" },
    { slot: 1, name: "dapi", resolves: true, entry_ref: "filter_turret_1_slot_1" },
    { slot: 5, name: null, resolves: false, why: "the registry gives slot 5 no name" },
  ];

  it("lists the slots by the fixture's names, shows the row's value with its source, and marks no slot", () => {
    show(hand(SLOTS));
    const box = open("filter_turret_1");
    const slots = within(within(box).getByRole("list", { name: "Slots of filter_turret_1" })).getAllByRole("listitem");
    expect(slots.map((s) => s.getAttribute("data-slot"))).toEqual(["0", "1", "5"]);
    expect(slots[0].textContent).toContain("five_band");
    expect(slots[1].textContent).toContain("dapi");
    expect(slots.map((s) => s.getAttribute("data-current"))).toEqual([null, null, null]);
    expect(within(box).queryByText(/current slot, as read/)).toBeNull();
    const value = within(box).getByTestId("read-value").textContent ?? "";
    expect(value).toContain("five_band");
    expect(value).toMatch(/read /);
    expect(value).toContain("the mock's state");
    expect(value).toContain(SLOT_NOT_GIVEN);
  });

  it("follows a renamed slot", () => {
    const s: Json[] = copy(SLOTS);
    s[1].name = "renamed_slot";
    show(hand(s));
    const box = open("filter_turret_1");
    expect(within(box).getByText(/renamed_slot/)).toBeTruthy();
    expect(within(box).queryByText("dapi")).toBeNull();
  });

  it("marks no slot, and says no value was read, when the element was not read back", () => {
    const rows = ROWS.map((r) => (r.name === "filter_turret_1" ? row("filter_turret_1", "stand_ti2e", "not_read", { reason: "busy at the read" }) : r));
    const o = orderWithElements();
    o.hand_set = [{ element: "filter_turret_1", channel: "stand_ti2e", slots: SLOTS, read_back: pairOf("filter_turret_1", "stand_ti2e") }];
    show(runWith(rows, o));
    const box = open("filter_turret_1");
    expect(within(box).queryByText(/current slot, as read/)).toBeNull();
    const value = within(box).getByTestId("read-value").textContent ?? "";
    expect(value).toContain("No value was read back");
    expect(value).toContain("busy at the read");
    expect(value).toContain(SLOT_NOT_GIVEN);
  });

  it("adds a selector for a chosen slot, and says software never writes it", () => {
    show(hand(SLOTS));
    const box = open("filter_turret_1");
    expect(within(box).getByText(HAND_SELECTOR_SAYS)).toBeTruthy();
    fireEvent.click(within(box).getByRole("button", { name: "Choose slot 1" }));
    expect(changeWords()).toEqual(["filter_turret_1 set by hand to dapi (slot 1)"]);
    expect(changes().querySelector("[data-change-kind]")?.getAttribute("data-change-kind")).toBe("selector");
  });

  it("refuses an unresolved slot, naming it, and adds nothing", () => {
    show(hand(SLOTS));
    const box = open("filter_turret_1");
    fireEvent.click(within(box).getByRole("button", { name: "Choose slot 5" }));
    const alert = within(box).getByRole("alert").textContent ?? "";
    expect(alert).toContain("slot 5");
    expect(alert).toContain("the registry gives slot 5 no name");
    expect(changeWords()).toEqual([]);
  });

  it("names the word of an unresolved slot that has one", () => {
    const s: Json[] = copy(SLOTS);
    s[2] = { slot: 2, name: "dichroic_x", resolves: false, why: "the store holds no entry for dichroic_x" };
    show(hand(s));
    const box = open("filter_turret_1");
    fireEvent.click(within(box).getByRole("button", { name: "Choose slot 2" }));
    expect(within(box).getByRole("alert").textContent).toContain("dichroic_x");
    expect(changeWords()).toEqual([]);
  });

  it("refuses a second slot of the same element until the first is removed", () => {
    show(hand(SLOTS));
    const box = open("filter_turret_1");
    fireEvent.click(within(box).getByRole("button", { name: "Choose slot 0" }));
    fireEvent.click(within(box).getByRole("button", { name: "Choose slot 1" }));
    expect(within(box).getByRole("alert").textContent).toMatch(/already/);
    expect(changeWords()).toEqual(["filter_turret_1 set by hand to five_band (slot 0)"]);
  });

  it("opens the slot list of an element the order's hand_set names even when the read-back holds no row for it", () => {
    const o = orderWithElements();
    o.hand_set = [{ element: "objective_turret", channel: "stand_ti2e", slots: SLOTS, read_back: pairOf("objective_turret", "stand_ti2e") }];
    show(runWith(ROWS, o));
    const box = open("objective_turret");
    expect(within(box).getByRole("list", { name: "Slots of objective_turret" })).toBeTruthy();
    expect(within(box).getByTestId("read-value").textContent).toContain("read-back names no element called objective_turret on channel stand_ti2e");
    const li = document.querySelector('[data-drawn="objective_turret"]') as HTMLElement;
    expect(li.querySelector("[data-control]")?.getAttribute("data-control")).toBe("hand");
  });

  it("marks no slot when the value read back is a slot's number", () => {
    const rows = ROWS.map((r) => (r.name === "filter_turret_1" ? read("filter_turret_1", "stand_ti2e", "1") : r));
    const o = orderWithElements();
    o.hand_set = [{ element: "filter_turret_1", channel: "stand_ti2e", slots: SLOTS, read_back: pairOf("filter_turret_1", "stand_ti2e") }];
    show(runWith(rows, o));
    const box = open("filter_turret_1");
    const slots = within(within(box).getByRole("list", { name: "Slots of filter_turret_1" })).getAllByRole("listitem");
    expect(slots.map((s) => s.getAttribute("data-current"))).toEqual([null, null, null]);
    expect(within(box).queryByText(/current slot, as read/)).toBeNull();
    expect(within(box).getByTestId("read-value").textContent).toContain("Read back: 1");
  });

  it("marks no slot when the value read back is a slot's name, and when it is none of them", () => {
    const rows = ROWS.map((r) => (r.name === "filter_turret_1" ? read("filter_turret_1", "stand_ti2e", "mystery") : r));
    const o = orderWithElements();
    o.hand_set = [{ element: "filter_turret_1", channel: "stand_ti2e", slots: SLOTS, read_back: pairOf("filter_turret_1", "stand_ti2e") }];
    show(runWith(rows, o));
    const box = open("filter_turret_1");
    expect(within(box).getByTestId("read-value").textContent).toContain("Read back: mystery");
    expect(within(box).queryByText(/current slot, as read/)).toBeNull();
    expect(within(box).queryByText(/matches none of these slots/)).toBeNull();
  });

  it("joins the slot list to the element by the hand_set's pair, not its id", () => {
    const o = orderWithElements();
    o.hand_set = [{ element: "some_other_id", channel: "stand_ti2e", slots: SLOTS, read_back: pairOf("filter_turret_1", "stand_ti2e") }];
    show(runWith(ROWS, o));
    expect(within(open("filter_turret_1")).getByRole("list", { name: "Slots of filter_turret_1" })).toBeTruthy();
  });

  it("says the slot list is not given, and offers nothing, for a hand element the order gives no slots for", () => {
    show(hand(SLOTS));
    const box = open("nosepiece");
    expect(within(box).getByText(NO_SLOTS_GIVEN)).toBeTruthy();
    expect(within(box).queryAllByRole("button")).toEqual([]);
    expect(within(box).queryByRole("list")).toBeNull();
  });
});

describe("the laser combiner and the trap say why there is no control", () => {
  it("opens the combiner to its reason and what was last sent, and offers no field or button", () => {
    show();
    const box = open("laser_shutter");
    expect(within(box).getByText(/No control is offered/)).toBeTruthy();
    expect(within(box).getByText(/last sent/i).parentElement?.textContent).toContain('{"shutter":"closed"}');
    expect(within(box).queryAllByRole("textbox")).toEqual([]);
    expect(within(box).queryAllByRole("button")).toEqual([]);
  });

  it("opens the trap to its reason and the strength last sent, and offers no field", () => {
    show();
    const box = open("trap_laser");
    expect(within(box).getByText(/No control is offered/)).toBeTruthy();
    expect(within(box).getByText(/last sent/i).parentElement?.textContent).toContain("0.25");
    expect(within(box).queryAllByRole("textbox")).toEqual([]);
  });

  it("says nothing was sent when the run's events hold none", () => {
    show(runWith(ROWS.map((r) => (r.name === "laser_shutter" ? { ...r, sent: null, sent_at: null } : r))));
    const box = open("laser_shutter");
    expect(within(box).getByText(/nothing sent in this run's events/)).toBeTruthy();
  });

  it("opens an element the order names with no channel to say no control is given for it", () => {
    show();
    const box = open("polarizer");
    expect(within(box).getByText(/This page is given no control for this element/)).toBeTruthy();
    expect(within(box).queryAllByRole("button")).toEqual([]);
  });
});

describe("no click offers a laser line, a power or a software move", () => {
  const ELEMENTS = ["dia_lamp", "filter_turret_1", "nosepiece", "polarizer", "laser_shutter", "kinetix_exposure", "stage_z", "trap_laser"];

  it("says in every opened element what is not offered and why", () => {
    show();
    for (const name of ELEMENTS) {
      const box = open(name);
      expect(within(box).getByText(NOT_OFFERED)).toBeTruthy();
      fireEvent.click(opener(name));
    }
  });

  it("offers no control whose name is a laser line, a software move or a goto, on any element", () => {
    show();
    for (const name of ELEMENTS) {
      const box = open(name);
      const names = within(box).queryAllByRole("button").map((b) => b.textContent ?? "").concat(within(box).queryAllByRole("textbox").map((t) => t.getAttribute("aria-label") ?? ""));
      expect(names.filter((n) => /laser|line|move|goto|go to|set position/i.test(n))).toEqual([]);
      fireEvent.click(opener(name));
    }
  });

  it("offers the one draft's own field, the red camera's exposure, and none on the lamp, the trap, the combiner or the hand parts", () => {
    show();
    const fields = (name: string) => {
      const box = open(name);
      const n = within(box).queryAllByRole("textbox").length + within(box).queryAllByRole("combobox").length;
      fireEvent.click(opener(name));
      return n;
    };
    expect(fields("trap_laser")).toBe(0);
    expect(fields("laser_shutter")).toBe(0);
    expect(fields("filter_turret_1")).toBe(0);
    expect(fields("nosepiece")).toBe(0);
    expect(fields("dia_lamp")).toBe(0);
    expect(fields("kinetix_exposure")).toBe(1);
  });
});

describe("an element with a section tab links to it", () => {
  it("links the piezo stage, the red camera and the trap to their tabs, and the link only goes there", () => {
    const go = vi.fn();
    show(runWith(), go);
    fireEvent.click(within(open("stage_z")).getByRole("button", { name: "Open the Piezo stage tab" }));
    expect(go).toHaveBeenLastCalledWith("piezo");
    fireEvent.click(opener("stage_z"));
    fireEvent.click(within(open("kinetix_exposure")).getByRole("button", { name: "Open the Cameras tab" }));
    expect(go).toHaveBeenLastCalledWith("cameras");
    fireEvent.click(opener("kinetix_exposure"));
    fireEvent.click(within(open("trap_laser")).getByRole("button", { name: "Open the Tweezers tab" }));
    expect(go).toHaveBeenLastCalledWith("tweezers");
    expect(go).toHaveBeenCalledTimes(3);
  });

  it("links the spinning disk and the blue camera to theirs", () => {
    const go = vi.fn();
    show(runWith(), go);
    fireEvent.click(within(open("disk_position")).getByRole("button", { name: "Open the Confocal tab" }));
    expect(go).toHaveBeenLastCalledWith("confocal");
    fireEvent.click(opener("disk_position"));
    fireEvent.click(within(open("blue_gain")).getByRole("button", { name: "Open the Cameras tab" }));
    expect(go).toHaveBeenLastCalledWith("cameras");
  });

  it("links no tab for an element that has no section", () => {
    show();
    expect(within(open("nosepiece")).queryByRole("button", { name: /tab$/ })).toBeNull();
    expect(within(open("dia_lamp")).queryByRole("button", { name: /tab$/ })).toBeNull();
  });
});

describe("the changes list", () => {
  const withSlots = () => {
    const o = orderWithElements();
    o.hand_set = [{ element: "filter_turret_1", channel: "stand_ti2e", slots: [{ slot: 0, name: "five_band", resolves: true, entry_ref: "e0" }], read_back: pairOf("filter_turret_1", "stand_ti2e") }];
    return runWith(ROWS, o);
  };

  it("says nothing has been added when it is empty, and carries the not-saved words", () => {
    show();
    expect(within(changes()).getByText(/Nothing has been added/)).toBeTruthy();
    expect(within(changes()).getByText(NOT_SAVED_WORDS)).toBeTruthy();
  });

  it("shows 'These changes will be made:' with each change in the order added, as a setting or a required state", () => {
    show(withSlots());
    fireEvent.click(within(open("filter_turret_1")).getByRole("button", { name: "Choose slot 0" }));
    const lamp = open("kinetix_exposure");
    fireEvent.change(within(lamp).getByLabelText("Exposure (ms)"), { target: { value: "40" } });
    fireEvent.click(within(lamp).getByRole("button", { name: "Add to the changes" }));
    expect(within(changes()).getByText("These changes will be made:")).toBeTruthy();
    expect(changeWords()).toEqual(["filter_turret_1 set by hand to five_band (slot 0)", "Camera red arm exposure: 40 ms"]);
    expect(Array.from(changes().querySelectorAll("[data-change-kind]")).map((n) => n.getAttribute("data-change-kind"))).toEqual(["selector", "part"]);
    expect(within(changes()).getAllByText(/^required state$|^setting$/).map((n) => n.textContent)).toEqual(["required state", "setting"]);
  });

  it("removes one change and leaves the rest in their order", () => {
    show(withSlots());
    fireEvent.click(within(open("filter_turret_1")).getByRole("button", { name: "Choose slot 0" }));
    const lamp = open("kinetix_exposure");
    fireEvent.change(within(lamp).getByLabelText("Exposure (ms)"), { target: { value: "40" } });
    fireEvent.click(within(lamp).getByRole("button", { name: "Add to the changes" }));
    fireEvent.click(within(changes()).getByRole("button", { name: "Remove filter_turret_1 set by hand to five_band (slot 0)" }));
    expect(changeWords()).toEqual(["Camera red arm exposure: 40 ms"]);
  });

  it("states the selector's words: set by the person's hand, then read and compared", () => {
    show(withSlots());
    fireEvent.click(within(open("filter_turret_1")).getByRole("button", { name: "Choose slot 0" }));
    expect(within(changes()).getByText(/set by your hand at the bench hand-over/)).toBeTruthy();
  });
});

describe("what the clicks leave out and refuse, said in the click's own words", () => {
  const handWith = (slots: Json[]) => {
    const o = orderWithElements();
    o.hand_set = [{ element: "filter_turret_1", channel: "stand_ti2e", slots, read_back: pairOf("filter_turret_1", "stand_ti2e") }];
    return runWith(ROWS, o);
  };
  const slotsOf = () => within(within(open("filter_turret_1")).getByRole("list", { name: "Slots of filter_turret_1" })).getAllByRole("listitem");

  it("says a slot a plan cannot name cannot be named, with the reason, next to that slot", () => {
    show(handWith([{ slot: 5, name: null, resolves: false, why: "the registry gives slot 5 no name" }, { slot: 0, name: "five_band", resolves: true, entry_ref: "e" }]));
    const slots = slotsOf();
    expect(slots[0].textContent).toContain("a plan cannot name it: the registry gives slot 5 no name");
    expect(slots[1].textContent).not.toContain("a plan cannot name it");
  });

  it("marks no slot on any slot, even one whose name is the value read back", () => {
    show(handWith([{ slot: 0, name: "five_band", resolves: true, entry_ref: "e" }, { slot: 1, name: "dapi", resolves: true, entry_ref: "f" }]));
    expect(slotsOf().map((s) => s.getAttribute("data-current"))).toEqual([null, null]);
  });

  it("says the slot list is not given when the order's hand_set names the element with no slots", () => {
    show(handWith([]));
    const box = open("filter_turret_1");
    expect(within(box).getByText(NO_SLOTS_GIVEN)).toBeTruthy();
    expect(within(box).queryByRole("list")).toBeNull();
    expect(within(box).queryAllByRole("button")).toEqual([]);
  });

  it("gives the laser combiner's own sentence and not the trap's", () => {
    show();
    expect(within(open("laser_shutter")).getByText(COMBINER_SENTENCE)).toBeTruthy();
    expect(within(open("trap_laser")).queryByText(COMBINER_SENTENCE)).toBeNull();
  });

  it("says nothing was sent to the trap when the run's events hold no strength", () => {
    show(runWith(ROWS, orderWithElements(), { strength_last_sent: null }));
    expect(within(open("trap_laser")).getByText(/nothing sent in this run's events/)).toBeTruthy();
  });

  it("says what is missing from an empty exposure draft, by the field's own name", () => {
    show();
    const box = open("kinetix_exposure");
    fireEvent.click(within(box).getByRole("button", { name: "Add to the changes" }));
    expect(within(box).getByRole("alert").textContent).toBe("Not added: fill in the exposure first.");
  });
});

describe("the camera's draft names what is missing", () => {
  it("asks for the exposure by name and adds nothing", () => {
    show();
    const box = open("kinetix_exposure");
    fireEvent.click(within(box).getByRole("button", { name: "Add to the changes" }));
    expect(within(box).getByRole("alert").textContent).toBe("Not added: fill in the exposure first.");
    expect(changeWords()).toEqual([]);
  });
});

describe("the page around the drawing", () => {
  const optics = (run: LatestRun) => {
    const fake = fakeTransport({});
    const client = new Client(fake.transport, "127.0.0.1");
    clients.push(client);
    return render(<ClientProvider client={client}><Optics run={run} /></ClientProvider>);
  };

  it("shows the changes list under a drawn order and keeps the separate drafts away", () => {
    optics(runWith());
    expect(screen.getByRole("region", { name: "Changes" })).toBeTruthy();
    expect(screen.queryByRole("group", { name: "Drafts" })).toBeNull();
  });

  it("offers no draft of the Aura or the lamp below the list either, where the source gives no order to click", () => {
    const run = runWith();
    optics({ ...run, path: { ...run.path, order: { state: "none", data: null, problems: [] } } } as LatestRun);
    expect(screen.getByRole("region", { name: "Changes" })).toBeTruthy();
    expect(screen.queryByRole("group", { name: "Drafts" })).toBeNull();
    expect(screen.queryByRole("group", { name: "Aura III LED" })).toBeNull();
    expect(screen.queryByRole("group", { name: "Transmitted lamp" })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Draft / })).toBeNull();
  });
});

describe("the channel table names only what a click may offer", () => {
  const devices = new Set<string>(((capabilities as Json).configurations as Json[]).flatMap((c) => c.devices as string[]));
  /** The piezo stage is the one key the capabilities file does not hold: the server's piezo draft names the stage as `piezo_stage`
   * (`PIEZO_DEVICE` in `drafts.py`), and the file lists the configurations' devices, which the stage is not one of. */
  const NOT_IN_CAPABILITIES = ["piezo_stage"];
  const keys = () => [...Object.keys(CHANNEL_DRAFT), ...NO_CONTROL_CHANNELS, ...Object.keys(CHANNEL_TAB)];

  it("holds only device ids the capabilities file names, the piezo stage excepted and named", () => {
    expect(devices.size).toBeGreaterThan(0);
    expect(keys().filter((k) => !devices.has(k) && !NOT_IN_CAPABILITIES.includes(k))).toEqual([]);
    expect(keys().filter((k) => NOT_IN_CAPABILITIES.includes(k))).toEqual(["piezo_stage"]);
    expect(devices.has("piezo_stage")).toBe(false);
  });

  it("names, for a draft form, only a kind the server's draft list holds, read from the generated types", () => {
    const sources = import.meta.glob("../../api/schema.ts", { query: "?raw", import: "default", eager: true }) as Record<string, string>;
    const text = Object.values(sources)[0];
    expect(text).toBeTruthy();
    const kinds = /\n\s+DraftIn: \{[\s\S]*?\n\s+kind: ([^;]+);/.exec(text)?.[1] ?? "";
    expect(kinds).not.toBe("");
    expect(Object.values(CHANNEL_DRAFT).length).toBeGreaterThan(0);
    for (const kind of Object.values(CHANNEL_DRAFT)) expect(kinds).toContain(`"${kind}"`);
  });

  it("is keyed by channels only: no key of any table is an element of the fixture's order", () => {
    const elements = orderWithElements().branches[0].elements.map((e: Json) => e.element as string);
    expect(keys().filter((k) => elements.includes(k))).toEqual([]);
  });

  it("gives an element on a channel the table does not hold no tab link and the plain words for its control", () => {
    const o = orderWithElements();
    o.branches[0].elements.push(place("mystery_part", "mystery_channel"));
    show(runWith(ROWS, o));
    const box = open("mystery_part");
    expect(within(box).queryByRole("button", { name: /tab$/ })).toBeNull();
    expect(within(box).getByText(/This page is given no control for this element/)).toBeTruthy();
  });
});

describe("one required state per element, whatever channel the second try names", () => {
  it("refuses a second selector for the same element on another channel, as the server's draft does", () => {
    let result: string | undefined;
    function Probe() {
      const { addSelector } = useChanges();
      return (
        <>
          <button type="button" onClick={() => addSelector("filter_turret_1", "stand_ti2e", { slot: 0, name: "five_band", resolves: true })}>first</button>
          <button type="button" onClick={() => { result = addSelector("filter_turret_1", "another_channel", { slot: 1, name: "dapi", resolves: true }); }}>second</button>
        </>
      );
    }
    const client = new Client(fakeTransport({}).transport, "127.0.0.1");
    clients.push(client);
    render(<ClientProvider client={client}><ChangesProvider onTab={() => undefined}><Probe /><ChangesList /></ChangesProvider></ClientProvider>);
    fireEvent.click(screen.getByRole("button", { name: "first" }));
    fireEvent.click(screen.getByRole("button", { name: "second" }));
    expect(result).toMatch(/already/);
    expect(changeWords()).toEqual(["filter_turret_1 set by hand to five_band (slot 0)"]);
  });
});
