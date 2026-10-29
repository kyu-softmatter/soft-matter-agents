import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { ScreenContextProvider } from "../../app/screenContext";
import { fakeTransport, type Route } from "../../test/fakes";
import { PATHS as QPATHS } from "../questions/api";
import { PATHS } from "./api";
import InstrumentsScreen from "./index";
import { DRAFT_LINK } from "./path";

/** The Instruments screens on a followed run (console card 015): the run's own files, nothing started or sent. */

const RUN_ID = "run-20261026-001";
const PERSON = { person_named: true, is_person: true, practice: false, approvals_folder: true };
const VIEWER = { person_named: true, is_person: false, practice: false, approvals_folder: true };
const NOT_BUILT = "not built yet";

const clients: Client[] = [];
afterEach(() => {
  clients.splice(0).forEach((c) => c.events.stop());
  vi.useRealTimers();
});

const NO_STATUS = { state: "none", data: null, problems: [] };
const LIMITS = {
  state: "present", policy_version: "v1", written_by: "kyuhwan", written_at: "2026-10-01T00:00:00Z",
  piezo: { x: { min: { value: 11, unit: "um" }, max: { value: 555, unit: "um" } }, y: null, z: null },
  tweezers: { positions: { "40x": null, "60x": null, "100x": null }, step_max: null, strength: null }, problems: [],
};
const NO_RUN = { state: "no_run", message: null, run_id: null, started_at: null, running: false, ended_how: null, ended_at: null,
  plan_id: null, frame_tap: false, channels: null, events_seen: 0, traps: [], trap_series: [], strength_last_sent: null, piezo: [],
  path: { source: "none", elements: [] } };
const CHANNELS = {
  t_s: 2, t_wall: "2026-10-26T09:00:02Z", label: "after",
  rows: [
    { channel: "piezo_stage", opened: true, detail: null, backend: "mock" },
    { channel: "camera_red", opened: false, detail: "not opened", backend: null },
  ],
};
const RUNNING = {
  ...NO_RUN, state: "ok", run_id: RUN_ID, started_at: "2026-10-26T09:00:00Z", running: true, plan_id: "plan-mic-20261026-900-r1",
  frame_tap: true, channels: CHANNELS, events_seen: 12,
  traps: [{ trap: "trap_1", x_um: 2, y_um: 0, strength: 0.3, on: true }],
  trap_series: [{ t_s: 1, trap: "trap_1", x_um: 2, y_um: 0 }, { t_s: 2, trap: "trap_1", x_um: 3, y_um: 1 }],
  strength_last_sent: 0.3,
  piezo: [
    { t_s: 1, t_wall: "2026-10-26T09:00:01Z", x_um: 100, y_um: 110, z_um: 120, label: "before" },
    { t_s: 2, t_wall: "2026-10-26T09:00:02Z", x_um: 101, y_um: 111, z_um: 121, label: "after" },
    { t_s: 3, t_wall: "2026-10-26T09:00:03Z", x_um: 102, y_um: 112, z_um: 122, label: "after" },
  ],
};
const ENDED = { ...RUNNING, running: false, ended_how: "completed", ended_at: "2026-10-26T09:05:00Z", frame_tap: false };
const STREAM = {
  run_id: RUN_ID, agent: "microscope", followed: true, state: "running", ended_how: null, plan_id: "p", revision: 1,
  t0_wall: "2026-10-26T09:00:00Z", can_stop: true, stop_unavailable: null, frame_tap: true, events: [], total: 0,
  partial_tail: false, bad_lines: 0,
};

interface Opts {
  status?: unknown;
  run?: unknown;
  signing?: Record<string, unknown>;
  draft?: Route;
  hash?: string;
  runs?: () => unknown;
  latest?: Route;
}

function show(opts: Opts = {}) {
  window.location.hash = opts.hash ?? "#/instruments";
  const fake = fakeTransport({
    [PATHS.status]: () => ({ status: 200, body: opts.status ?? NO_STATUS }),
    [PATHS.limits]: () => ({ status: 200, body: LIMITS }),
    [PATHS.latestRun]: opts.latest ?? (() => ({ status: 200, body: opts.runs ? opts.runs() : (opts.run ?? NO_RUN) })),
    [QPATHS.signing]: () => ({ status: 200, body: opts.signing ?? PERSON }),
    [PATHS.draft]: opts.draft ?? ((init) => ({ status: 200, body: { kind: JSON.parse(String(init?.body)).kind, card: { card: "plan" }, valid: true, problems: [], range_problems: [], refused_today: ["r"], saved: false, note: "n" } })),
    [QPATHS.runStream("microscope" as never, RUN_ID) as string]: () => ({ status: 200, body: STREAM }),
    [QPATHS.runStream("microscope" as never, RUN_ID, 0) as string]: () => ({ status: 200, body: STREAM }),
  });
  const client = new Client(fake.transport, "127.0.0.1");
  clients.push(client);
  render(
    <ClientProvider client={client}>
      <ScreenContextProvider area="instruments">
        <InstrumentsScreen />
      </ScreenContextProvider>
    </ClientProvider>,
  );
  return { ...fake, client };
}

const LIVE_TABS: [string, string][] = [
  ["status", "Instrument status"], ["cameras", "Cameras"], ["tweezers", "Tweezers"], ["confocal", "Confocal"], ["piezo", "Piezo stage"],
];

describe("which run the screens follow", () => {
  it.each(LIVE_TABS)("%s says it is following the run while one is running", async (hash) => {
    show({ hash: `#/instruments/${hash}`, run: RUNNING });
    expect(await screen.findByText(`Following ${RUN_ID} (running)`)).toBeTruthy();
  });

  it.each(LIVE_TABS)("%s says no run is running, and shows no value, when there is none", async (hash) => {
    show({ hash: `#/instruments/${hash}` });
    expect(await screen.findByText(/^No run is running/)).toBeTruthy();
    expect(screen.queryByRole("table", { name: "Traps (sent)" })).toBeNull();
    expect(screen.queryByRole("table", { name: "Piezo positions" })).toBeNull();
    expect(screen.queryByRole("table", { name: "Devices" })).toBeNull();
  });

  it("a run that has ended says no run is running, and its values stay as of when it ended", async () => {
    show({ hash: "#/instruments/tweezers", run: ENDED });
    expect(await screen.findByText(/^No run is running/)).toBeTruthy();
    expect(screen.getByText(`Last run: ${RUN_ID}, completed.`)).toBeTruthy();
    expect(screen.getByText(`as of 2026-10-26 09:05:00, from ${RUN_ID}`)).toBeTruthy();
    expect(within(screen.getByRole("table", { name: "Traps (sent)" })).getByText("trap_1")).toBeTruthy();
  });

  it("an ended run's piezo position is as of the time it was read, from that run", async () => {
    show({ hash: "#/instruments/piezo", run: ENDED });
    expect(await screen.findByText(`as of 2026-10-26 09:00:03, from ${RUN_ID}`)).toBeTruthy();
  });

  it("the runs folder missing is said, and is not 'no run'", async () => {
    show({ run: { ...NO_RUN, state: "runs_not_found", message: "the runs folder was not found" } });
    expect(await screen.findByText(/the runs folder was not found/)).toBeTruthy();
  });
});

describe("following reads again only while a run is running", () => {
  it("re-reads the run on a timer while it runs, and stops once it has ended", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let n = 0;
    const t = show({ run: undefined, runs: () => (n++ < 3 ? RUNNING : ENDED) });
    await screen.findByText(`Following ${RUN_ID} (running)`);
    const reads = () => t.calls.filter((c) => c.path === PATHS.latestRun).length;
    const first = reads();
    await act(async () => { await vi.advanceTimersByTimeAsync(2100); });
    await waitFor(() => expect(reads()).toBeGreaterThan(first));
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    await waitFor(() => expect(screen.getByText(/^No run is running/)).toBeTruthy());
    const settled = reads();
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(reads()).toBe(settled);
  });

  it("a read that fails while following keeps what was shown, and does not go back to loading", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let n = 0;
    const t = show({ latest: () => (n++ === 0 ? { status: 200, body: RUNNING } : { status: 500, body: { detail: "gone" } }) });
    await screen.findByText(`Following ${RUN_ID} (running)`);
    const reads = () => t.calls.filter((c) => c.path === PATHS.latestRun).length;
    await act(async () => { await vi.advanceTimersByTimeAsync(2100); });
    await waitFor(() => expect(reads()).toBeGreaterThan(1));
    expect(screen.getByText(`Following ${RUN_ID} (running)`)).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("does not read again by itself when no run is running", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const t = show();
    await screen.findByText(/^No run is running/);
    const before = t.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(20_000); });
    expect(t.calls.length).toBe(before);
  });
});

describe("the connection state", () => {
  it("lists each channel the run's last snapshot tried: opened with where it came from, or not opened and why", async () => {
    show({ run: RUNNING });
    const table = await screen.findByRole("table", { name: "Devices" });
    const rows = within(table).getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell").map((c) => c.textContent));
    expect(rows).toEqual([["piezo_stage", "opened", "mock"], ["camera_red", "not opened", "not opened"]]);
    expect(screen.getByText(`From the last snapshot of ${RUN_ID}, as of 2026-10-26 09:00:02.`)).toBeTruthy();
  });

  it("an opened channel shows where it came from, a channel not opened shows why, and neither shows the other's field", async () => {
    const channels = {
      ...CHANNELS,
      rows: [
        { channel: "piezo_stage", opened: true, detail: "firmware 3", backend: "mock" },
        { channel: "camera_red", opened: false, detail: "port busy", backend: "micromanager" },
      ],
    };
    show({ run: { ...RUNNING, channels } });
    const table = await screen.findByRole("table", { name: "Devices" });
    const rows = within(table).getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell").map((c) => c.textContent));
    expect(rows).toEqual([["piezo_stage", "opened", "mock"], ["camera_red", "not opened", "port busy"]]);
  });

  it("a screen with no run shows no connection state, whatever its payload carries", async () => {
    show({ run: { ...NO_RUN, channels: CHANNELS } });
    expect(await screen.findByText("There is no run to read a connection state from.")).toBeTruthy();
    expect(screen.queryByRole("table", { name: "Devices" })).toBeNull();
  });

  it("a run with no snapshot has no connection state to show", async () => {
    show({ run: { ...RUNNING, channels: { t_s: null, t_wall: null, label: null, rows: [] } } });
    expect(await screen.findByText("No snapshot yet, so no connection state.")).toBeTruthy();
  });
});

describe("runtime pieces not built yet", () => {
  const PIECES = [
    "Idle status file writer", "Check now", "Latest frames per camera", "Second camera (mock)",
    "Piezo trace that moves (mock)", "Trap commands echoed back (mock)", "Confocal elements (mock)",
  ];
  const piece = (name: string) => within(screen.getByRole("list", { name: "Runtime pieces" })).getByText(new RegExp(`^${name.replace(/[()]/g, "\\$&")}:`));

  it("with nothing on disk every piece reads 'not built yet'", async () => {
    show();
    await screen.findByRole("list", { name: "Runtime pieces" });
    for (const p of PIECES) expect(piece(p).textContent).toBe(`${p}: ${NOT_BUILT}`);
  });

  it("a piece shows as there only when the files show it", async () => {
    const status = {
      state: "present", problems: [],
      data: { artifact: "idle_status", schema_version: "0.1", written_at: "2026-10-26T09:00:00Z", written_by_run: RUN_ID, last_run: null, check_now: null,
              ownership: { status: "not_built" }, registry: { path: "p", sha256: "a".repeat(64) } },
    };
    const run = { ...RUNNING, channels: { ...CHANNELS, rows: [...CHANNELS.rows, { channel: "camera_blue", opened: true, detail: null, backend: "mock" }, { channel: "confocal_csuw1", opened: true, detail: null, backend: "mock" }] } };
    show({ status, run });
    await screen.findByRole("list", { name: "Runtime pieces" });
    expect(piece("Idle status file writer").textContent).toContain("a status file was found");
    expect(piece("Second camera (mock)").textContent).toContain("in the last snapshot");
    expect(piece("Confocal elements (mock)").textContent).toContain("in the last snapshot");
    expect(piece("Piezo trace that moves (mock)").textContent).toContain("positions differ");
    expect(piece("Check now").textContent).toContain(NOT_BUILT);
    expect(piece("Latest frames per camera").textContent).toContain(NOT_BUILT);
    expect(piece("Trap commands echoed back (mock)").textContent).toContain(NOT_BUILT);
  });
});

describe("the piezo plot reads the run's snapshots", () => {
  it("draws one point per snapshot on each axis, labelled as read back", async () => {
    show({ hash: "#/instruments/piezo", run: RUNNING });
    for (const name of ["t-x (read back)", "t-y (read back)", "t-z (read back)"]) {
      const plot = await screen.findByRole("img", { name });
      expect(plot.querySelectorAll("circle")).toHaveLength(3);
    }
  });

  it("with no snapshot there is no plot", async () => {
    show({ hash: "#/instruments/piezo", run: { ...RUNNING, piezo: [] } });
    await screen.findByText("no position read yet");
    expect(screen.queryByRole("img", { name: /read back/ })).toBeNull();
  });
});

describe("the camera frame is asked for the person only", () => {
  const frame = () => screen.queryByRole("img", { name: `Latest frame of ${RUN_ID}` });

  it("shows the frame tap's frame to the person while the run acquires", async () => {
    const t = show({ hash: "#/instruments/cameras", run: RUNNING });
    expect(await screen.findByRole("img", { name: `Latest frame of ${RUN_ID}` })).toBeTruthy();
    expect(t.calls.some((c) => c.path.includes("/stream"))).toBe(true);
  });

  it("asks neither the stream nor the frame for any other login, and says why", async () => {
    const t = show({ hash: "#/instruments/cameras", run: RUNNING, signing: VIEWER });
    expect(await screen.findByText("Frames are shown to the person's login only.")).toBeTruthy();
    await new Promise((r) => setTimeout(r, 30));
    expect(frame()).toBeNull();
    expect(t.calls.some((c) => c.path.includes("/stream") || c.path.includes("/frame"))).toBe(false);
  });

  it("asks for no frame while no run is running", async () => {
    const t = show({ hash: "#/instruments/cameras", run: ENDED });
    await screen.findByText(/^No run is running/);
    expect(frame()).toBeNull();
    expect(t.calls.some((c) => c.path.includes("/stream") || c.path.includes("/frame"))).toBe(false);
  });

  it("keeps the other panels' wording", async () => {
    show({ hash: "#/instruments/cameras", run: RUNNING });
    expect((await screen.findByRole("region", { name: "Camera 2, blue" })).textContent).toContain("not opened by software yet");
  });
});

describe("the piezo draft is an operation plan, shown and saved nowhere", () => {
  const open = async (opts: Opts = {}) => {
    const t = show({ hash: "#/instruments/piezo", ...opts });
    await screen.findByRole("group", { name: "Draft a piezo move" });
    return { ...t, form: screen.getByRole("group", { name: "Draft a piezo move" }), posts: () => t.calls.filter((c) => c.init?.method === "POST") };
  };

  it("sends a step as the person wrote it, with its return, and shows the card in full", async () => {
    const t = await open();
    fireEvent.change(within(t.form).getByLabelText("Axis"), { target: { value: "y" } });
    fireEvent.change(within(t.form).getByLabelText("Target (µm)"), { target: { value: "120" } });
    fireEvent.change(within(t.form).getByLabelText("Return to (µm)"), { target: { value: "100" } });
    fireEvent.change(within(t.form).getByLabelText("Read-back tolerance (µm)"), { target: { value: "1" } });
    fireEvent.click(within(t.form).getByRole("button", { name: "Draft piezo move" }));
    expect(await screen.findByRole("region", { name: "Plan draft" })).toBeTruthy();
    expect(t.posts().map((c) => [c.path, JSON.parse(String(c.init?.body))])).toEqual([
      [PATHS.draft, { kind: "piezo", axis: "y", move: "step", target_um: 120, role: "verify_mapping", return_um: 100, tolerance_um: 1 }],
    ]);
  });

  it("sends a sine with its fields and no target", async () => {
    const t = await open();
    fireEvent.change(within(t.form).getByLabelText("Move"), { target: { value: "sine" } });
    for (const [label, v] of [["Centre (µm)", "100"], ["Amplitude (µm)", "5"], ["Period (s)", "10"], ["Cycles", "2"], ["Points per period", "16"], ["Read-back tolerance (µm)", "0.5"]]) {
      fireEvent.change(within(t.form).getByLabelText(label), { target: { value: v } });
    }
    fireEvent.change(within(t.form).getByLabelText("Starts at"), { target: { value: "minimum" } });
    fireEvent.click(within(t.form).getByRole("button", { name: "Draft piezo move" }));
    await screen.findByRole("region", { name: "Plan draft" });
    expect(JSON.parse(String(t.posts()[0].init?.body))).toEqual({
      kind: "piezo", axis: "x", move: "sine", centre_um: 100, amplitude_um: 5, period_s: 10, cycles: 2, points_per_period: 16, start: "minimum", tolerance_um: 0.5,
    });
  });

  it("shows the server's refusal in words and no card as valid", async () => {
    const t = await open({
      draft: () => ({ status: 422, body: { detail: { code: "invalid", message: "the read-back tolerance is a number of micrometres above zero, and it is yours to say" } } }),
    });
    fireEvent.click(within(t.form).getByRole("button", { name: "Draft piezo move" }));
    expect((await screen.findByRole("alert")).textContent).toContain("yours to say");
    expect("tolerance_um" in JSON.parse(String(t.posts()[0].init?.body))).toBe(false);
  });

  it("sends nothing else: a tour that drafts is the only thing that posts", async () => {
    const t = await open({ run: RUNNING });
    fireEvent.change(within(t.form).getByLabelText("Read-back tolerance (µm)"), { target: { value: "1" } });
    fireEvent.click(within(t.form).getByRole("button", { name: "Draft piezo move" }));
    await screen.findByRole("region", { name: "Plan draft" });
    expect(t.calls.filter((c) => c.init?.method !== undefined && c.init.method !== "GET").map((c) => c.path)).toEqual([PATHS.draft]);
    expect(t.calls.some((c) => c.path.includes("/stop") || c.path.includes("/live/on") || c.path.includes("/command"))).toBe(false);
  });

  it("says what is moved by hand and offers no draft for it", async () => {
    show({ hash: "#/instruments/optics" });
    expect(await screen.findByText(/^Moved by hand:/)).toBeTruthy();
    expect(screen.getByText(/filters, the objectives, the light path, the spinning disk, the large XY stage and the trap laser/)).toBeTruthy();
  });
});


describe("the live optical path on Optics and control", () => {
  interface El {
    key: string; name: string; channel: string; state: string; value: string | null; t_wall: string | null; reason: string | null;
    backend: string | null; sent: string | null; sent_at: string | null; control: string | null; draft: string | null;
  }
  const el = (name: string, channel: string, state: string, extra: Partial<El> = {}): El => ({
    key: `${channel}/${name}`, name, channel, state, value: null, t_wall: null, reason: null, backend: null, sent: null, sent_at: null,
    control: "hand", draft: null, ...extra,
  });
  const T1 = "2026-10-26T09:00:01Z";
  const read = (name: string, channel: string, value: string, extra: Partial<El> = {}) =>
    el(name, channel, "read_back", { value, t_wall: T1, backend: "mock", ...extra });
  const ELEMENTS: El[] = [
    read("FilterTurret1", "stand_ti2e", "2"),
    read("Nosepiece", "stand_ti2e", "3"),
    read("CSUW1-Dichroic", "confocal_csuw1", "1"),
    el("LightPath", "stand_ti2e", "not_read", { reason: "the read returned no position for it" }),
    read("DiaLamp", "stand_ti2e", "1", { control: "draft", draft: "dialamp" }),
    read("Aura", "stand_ti2e", "0", { control: "draft", draft: "aura" }),
    el("laser_combiner", "laser_combiner", "sent", {
      value: "assumed on", reason: "It reports nothing back, so it is shown at the most dangerous state its commands allow.",
      sent: '{"state": "off"}', sent_at: "2026-10-26T09:00:02Z", control: null,
    }),
  ];
  const PATH = { source: "run", run_id: RUN_ID, kind: null, t_wall: T1, written_at: null, ended_at: null, ended_how: null, detail: null, elements: ELEMENTS };
  const PATH_RUN = { ...RUNNING, path: PATH };

  async function open(run: unknown, hash = "#/instruments/optics") {
    const t = show({ hash, run });
    const panel = await screen.findByRole("region", { name: "Live optical path" });
    const item = (name: string) => {
      const li = within(panel).getAllByRole("listitem").find((l) => l.getAttribute("data-element")?.endsWith(`/${name}`));
      if (li === undefined) throw new Error(`no item for ${name}`);
      return li;
    };
    const names = () => within(panel).getAllByRole("listitem").map((l) => l.querySelector(".inst-name")?.textContent);
    return { t, panel, item, names };
  }
  const stateOf = (li: HTMLElement) => Array.from(li.querySelectorAll("[data-state]")).map((n) => n.textContent);
  const handOf = (li: HTMLElement) => Array.from(li.querySelectorAll("[data-control]")).map((n) => n.textContent);

  it("shows exactly one state per element, and a filter turret shows read back and moved by hand together", async () => {
    const { item, names } = await open(PATH_RUN);
    for (const n of names()) expect(["read back", "sent", "not open", "not read"]).toContain(stateOf(item(n as string))[0]);
    for (const n of names()) expect(stateOf(item(n as string))).toHaveLength(1);
    expect(stateOf(item("FilterTurret1"))).toEqual(["read back"]);
    expect(handOf(item("FilterTurret1"))).toEqual(["moved by hand"]);
  });

  it("each element with a control shows exactly one of moved by hand or drafted, and the laser has neither", async () => {
    const { item } = await open(PATH_RUN);
    for (const n of ["FilterTurret1", "Nosepiece", "CSUW1-Dichroic", "LightPath"]) expect(handOf(item(n))).toEqual(["moved by hand"]);
    for (const n of ["DiaLamp", "Aura"]) expect(handOf(item(n))).toEqual([DRAFT_LINK]);
    expect(handOf(item("laser_combiner"))).toEqual([]);
  });

  it("names follow the fixture: a name nobody coded here appears, and one the read-back omits does not", async () => {
    const odd = { ...PATH, elements: [read("Widget-7", "stand_ti2e", "4"), read("Nosepiece", "stand_ti2e", "3")] };
    const { names, panel } = await open({ ...RUNNING, path: odd });
    expect(names()).toEqual(["Widget-7", "Nosepiece"]);
    expect(within(panel).queryByText("FilterTurret1")).toBeNull();
    expect(within(panel).queryByText("Aura")).toBeNull();
  });

  it("an element the read-back names without a position reads not read, with its reason and no value", async () => {
    const { item } = await open(PATH_RUN);
    const li = item("LightPath");
    expect(stateOf(li)).toEqual(["not read"]);
    expect(li.textContent).toContain("the read returned no position for it");
    expect(li.textContent).not.toContain("=");
    expect(li.textContent).not.toContain("read 2026");
  });

  it("a channel the run did not open reads not open with its reason, never off", async () => {
    const els = [el("laser_combiner", "laser_combiner", "not_open", { reason: "the run did not open it", control: null })];
    const { item } = await open({ ...RUNNING, path: { ...PATH, elements: els } });
    expect(stateOf(item("laser_combiner"))).toEqual(["not open"]);
    expect(item("laser_combiner").textContent).toContain("the run did not open it");
    expect(item("laser_combiner").textContent).not.toMatch(/\boff\b/);
  });

  it("a busy channel reads not read with the reason and no value", async () => {
    const els = [el("FilterTurret1", "stand_ti2e", "not_read", { reason: "busy at the read" })];
    const { item } = await open({ ...RUNNING, path: { ...PATH, elements: els } });
    expect(stateOf(item("FilterTurret1"))).toEqual(["not read"]);
    expect(item("FilterTurret1").textContent).toContain("busy at the read");
    expect(item("FilterTurret1").textContent).not.toContain("read 2026");
  });

  it("a blind laser whose sent commands end in off is shown at the dangerous state, not off", async () => {
    const { item } = await open(PATH_RUN);
    const li = item("laser_combiner");
    expect(stateOf(li)).toEqual(["sent"]);
    expect(li.textContent).toContain("assumed on");
    expect(li.textContent).toContain('sent {"state": "off"} at 2026-10-26 09:00:02');
    expect(li.textContent).not.toContain("read back");
    expect(li.textContent).not.toContain("shown off");
  });

  it("an apply later than the latest snapshot shows sent, with what was sent and when, not read back", async () => {
    const els = [read("FilterTurret1", "stand_ti2e", "2")].map((e) => ({ ...e, state: "sent", sent: '{"State": 4}', sent_at: "2026-10-26T09:00:05Z" }));
    const { item } = await open({ ...RUNNING, path: { ...PATH, elements: els } });
    const li = item("FilterTurret1");
    expect(stateOf(li)).toEqual(["sent"]);
    expect(li.textContent).toContain('sent {"State": 4} at 2026-10-26 09:00:05');
    expect(li.textContent).not.toContain("read back");
  });

  it("on the mock every state is labelled the mock's, and on the instrument it is not", async () => {
    const { item } = await open(PATH_RUN);
    for (const n of ["FilterTurret1", "Nosepiece", "DiaLamp"]) expect(item(n).textContent).toContain("the mock's state");
    expect(item("LightPath").textContent).not.toContain("the mock's");
  });

  it("on the instrument a read is not labelled the mock's", async () => {
    const els = [read("FilterTurret1", "stand_ti2e", "2", { backend: "micromanager" })];
    const { item } = await open({ ...RUNNING, path: { ...PATH, elements: els } });
    expect(stateOf(item("FilterTurret1"))).toEqual(["read back"]);
    expect(item("FilterTurret1").textContent).not.toContain("the mock's");
  });

  it("every read value carries its read time", async () => {
    const { item } = await open(PATH_RUN);
    for (const n of ["FilterTurret1", "Nosepiece", "CSUW1-Dichroic", "DiaLamp", "Aura"]) expect(item(n).textContent).toContain("read 2026-10-26 09:00:01");
  });

  it("no element moved by hand offers a control", async () => {
    const { item } = await open(PATH_RUN);
    for (const n of ["FilterTurret1", "Nosepiece", "CSUW1-Dichroic", "LightPath"]) {
      expect(within(item(n)).queryAllByRole("button")).toEqual([]);
      expect(within(item(n)).queryAllByRole("link")).toEqual([]);
      expect(within(item(n)).queryAllByRole("textbox")).toEqual([]);
    }
    expect(within(item("laser_combiner")).queryAllByRole("button")).toEqual([]);
  });

  it("the lamp and the LED carry the draft link, which moves focus to the drafts", async () => {
    const t = await open(PATH_RUN);
    for (const n of ["DiaLamp", "Aura"]) expect(within(t.item(n)).getAllByRole("button").map((b) => b.textContent)).toEqual([DRAFT_LINK]);
    fireEvent.click(within(t.item("DiaLamp")).getByRole("button"));
    expect(document.activeElement).toBe(screen.getByRole("group", { name: "Drafts" }));
  });

  it("beside the draft links it says the run will refuse the draft, and the Aura for longer", async () => {
    const { item } = await open(PATH_RUN);
    const refuse = /The run will refuse this draft even when it is made and signed: the runtime cannot yet match this element to what software may command/;
    expect(item("DiaLamp").textContent).toMatch(refuse);
    expect(item("Aura").textContent).toMatch(refuse);
    expect(item("Aura").textContent).toContain("stays refused longer than the lamp and the camera, until which light engine feeds which channel is settled");
    expect(item("DiaLamp").textContent).not.toContain("stays refused longer");
  });

  it("the Light source drafts say the run will refuse them, the Aura for longer", async () => {
    show({ hash: "#/instruments/optics" });
    const aura = await screen.findByRole("group", { name: "Aura III LED" });
    const lamp = screen.getByRole("group", { name: "Transmitted lamp" });
    for (const g of [aura, lamp]) expect(g.textContent).toContain("The run will refuse this draft even when it is made and signed");
    expect(aura.textContent).toContain("stays refused longer than the lamp and the camera");
    expect(lamp.textContent).not.toContain("stays refused longer");
  });

  it("the red camera's draft on the Cameras page says the run will refuse it", async () => {
    show({ hash: "#/instruments/cameras" });
    const cam = await screen.findByRole("group", { name: "Camera red arm" });
    expect(cam.textContent).toContain("The run will refuse this draft even when it is made and signed");
    expect(cam.textContent).not.toContain("stays refused longer");
  });

  it("the piezo draft is not told the run will refuse it", async () => {
    show({ hash: "#/instruments/piezo" });
    await screen.findByText(/^No run is running/);
    expect(screen.queryByText(/The run will refuse this draft/)).toBeNull();
  });

  it("a made draft shows the server's reasons, the run's refusal among them", async () => {
    const reasons = ["Refused until you write a limit: your safety file has none for this part yet.", "The run will refuse this draft even when it is made and signed: the runtime cannot yet match this element to what software may command."];
    show({
      hash: "#/instruments/optics",
      draft: () => ({ status: 200, body: { kind: "dialamp", card: { card: "plan" }, valid: true, problems: [], range_problems: [], refused_today: reasons, saved: false, note: "n" } }),
    });
    const lamp = await screen.findByRole("group", { name: "Transmitted lamp" });
    fireEvent.click(within(lamp).getByRole("button", { name: /^Draft/ }));
    await waitFor(() => expect(within(lamp).getAllByText(/The run will refuse this draft/).length).toBeGreaterThan(1));
  });

  it("outside a run it says where the path was read: the status file, with its write time and the run's outcome", async () => {
    const path = { ...PATH, source: "status_file", run_id: RUN_ID, kind: "operation", written_at: "2026-10-26T09:10:00Z", ended_at: "2026-10-26T09:05:00Z", ended_how: "completed" };
    const { panel } = await open({ ...ENDED, path });
    expect(within(panel).getByText(new RegExp(`^From the runtime's status file, written 2026-10-26 09:10:00: run ${RUN_ID}, ended 2026-10-26 09:05:00: completed\\.`))).toBeTruthy();
    expect(within(panel).getByText(/^No run is running/)).toBeTruthy();
  });

  it("a live view leaves no snapshot: the file's run, end time and outcome text are shown as they stand, with no element", async () => {
    const path = { source: "status_file", run_id: RUN_ID, kind: "live_view", t_wall: null, written_at: "2026-10-26T09:10:00Z", ended_at: "2026-10-26T09:05:00Z",
      ended_how: "ended: camera_red did not open", detail: "That run took no snapshot (a live view takes none), so no element was read.", elements: [] };
    const { panel } = await open({ ...ENDED, path });
    expect(within(panel).getByText(/ended 2026-10-26 09:05:00: ended: camera_red did not open\./)).toBeTruthy();
    expect(within(panel).getByText(/took no snapshot/)).toBeTruthy();
    expect(within(panel).queryAllByRole("listitem")).toEqual([]);
  });

  it("a run's last snapshot, with no status file, is marked as of its time, from that run", async () => {
    const path = { ...PATH, source: "last_snapshot", ended_at: "2026-10-26T09:05:00Z", ended_how: "completed" };
    const { panel } = await open({ ...ENDED, path });
    expect(within(panel).getByText(`as of 2026-10-26 09:00:01, from ${RUN_ID}`)).toBeTruthy();
  });

  it("with no snapshot and no status file anywhere it says not built yet and lists nothing", async () => {
    const { panel } = await open(NO_RUN);
    expect(within(panel).getByText(/^No run is running/)).toBeTruthy();
    expect(within(panel).getByText(/nothing to show: not built yet/)).toBeTruthy();
    expect(within(panel).queryAllByRole("listitem")).toEqual([]);
  });

  it("a running run that has taken no snapshot says so, and does not say not built yet", async () => {
    const { panel } = await open({ ...RUNNING, path: { ...PATH, t_wall: null, elements: [] } });
    expect(within(panel).getByText(/has taken no snapshot yet/)).toBeTruthy();
    expect(within(panel).queryByText(/not built yet/)).toBeNull();
  });

  it("says that a position read back is the stand's report and not proof of which element is in the beam, and names the two traps", async () => {
    const { panel } = await open(PATH_RUN);
    expect(within(panel).getByText(/not proof of which element is in the beam/)).toBeTruthy();
    expect(within(panel).getByText(/turret label that names the wrong position/)).toBeTruthy();
    expect(within(panel).getByText(/send no light to one camera/)).toBeTruthy();
  });

  it("says no order is given, and invents none", async () => {
    const { panel } = await open(PATH_RUN);
    expect(within(panel).getByText(/No order is given/)).toBeTruthy();
  });

  it("no request leaves the page while it renders, refreshes or its draft link is pressed, except the reads of files", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    const { t, panel } = await open(PATH_RUN);
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    fireEvent.click(within(panel).getAllByRole("button", { name: DRAFT_LINK })[0]);
    await act(async () => { await vi.advanceTimersByTimeAsync(100); });
    expect(t.calls.filter((c) => c.init?.method !== undefined && c.init.method !== "GET")).toEqual([]);
    const allowed = new Set<string>([PATHS.status, PATHS.limits, PATHS.latestRun, QPATHS.signing]);
    expect(t.calls.map((c) => c.path).filter((p) => !allowed.has(p))).toEqual([]);
    expect(t.calls.filter((c) => c.path === PATHS.latestRun).length).toBeGreaterThan(1);
  });
});
