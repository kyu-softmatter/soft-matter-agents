import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { ScreenContextProvider } from "../../app/screenContext";
import { fakeTransport, type Route } from "../../test/fakes";
import { PATHS as QPATHS } from "../questions/api";
import { PATHS } from "./api";
import InstrumentsScreen from "./index";

/** The Instruments screens (console card 012): show, draft and stop. Nothing here commands an instrument. */

const SIGNING = QPATHS.signing;
const PERSON = { person_named: true, is_person: true, practice: false, approvals_folder: true };
const VIEWER = { person_named: true, is_person: false, practice: false, approvals_folder: true };
const LASER = "Tweezers laser · set by hand · not known · assumed on";

const clients: Client[] = [];
afterEach(() => {
  clients.splice(0).forEach((c) => c.events.stop());
});

const reading = (channel: string, name: string, how: string, value: unknown, t = "2026-10-24T11:00:00Z") =>
  how === "not_read" ? { channel, name, how, t_wall: null, value: null } : { channel, name, how, t_wall: t, value };

const IDLE = {
  artifact: "idle_status", schema_version: "0.1", written_at: "2026-10-24T11:05:00Z", written_by_run: "run-20261024-001",
  last_run: {
    run_id: "run-20261024-001", kind: "plan", ended_at: "2026-10-24T11:05:00Z", outcome: "completed", preflight: null,
    last_snapshot: {
      t_wall: "2026-10-24T11:04:00Z",
      channels: [
        reading("dmd", "Spectra III via DMD", "read_back", "mirrors parked"),
        reading("optical_tweezers", "Tweez 300 trap strength", "not_readable", 0.02),
        reading("piezo_stage", "Piezo stage", "not_read", null),
        reading("confocal_csuw1", "CSU-W1 spinning disk", "read_back", "disk 1"),
        reading("widefield_source_a", "Widefield source A", "read_back", "lamp-or-led"),
      ],
    },
  },
  check_now: null, ownership: { status: "not_built" }, registry: { path: "contracts/registry.json", sha256: "a".repeat(64) },
};

const bound = (value: number, unit = "um") => ({ value, unit });
const LIMITS = {
  state: "present", policy_version: "v1", written_by: "kyuhwan", written_at: "2026-10-01T00:00:00Z",
  piezo: { x: { min: bound(11), max: bound(555) }, y: { min: bound(12), max: bound(556) }, z: { min: bound(13), max: bound(557) } },
  tweezers: {
    positions: { "40x": { min: bound(-100), max: bound(100) }, "60x": { min: bound(-67), max: bound(67) }, "100x": { min: bound(-4), max: bound(4) } },
    step_max: bound(1), strength: { min: bound(0, "1"), max: bound(1, "1") },
  },
  problems: [],
};

const NO_RUN = { state: "no_run", message: null, run_id: null, started_at: null, traps: [], trap_series: [], strength_last_sent: null, piezo: [], path: { source: "none", elements: [] } };
const RUN = {
  state: "ok", message: null, run_id: "run-20261024-001", started_at: "2026-10-24T11:00:00Z",
  traps: [{ trap: "trap_1", x_um: 2, y_um: 0, strength: 0.3, on: true }],
  trap_series: [{ t_s: 1, trap: "trap_1", x_um: 2, y_um: 0 }, { t_s: 2, trap: "trap_1", x_um: 3, y_um: 1 }],
  strength_last_sent: 0.3,
  piezo: [
    { t_s: 1, t_wall: "2026-10-24T11:00:01Z", x_um: 100, y_um: 110, z_um: 120, label: "before" },
    { t_s: 40, t_wall: "2026-10-24T11:00:40Z", x_um: 101, y_um: 111, z_um: 121, label: "after" },
  ],
};

const DRAFT_OUT = (kind: string, valid: boolean) => ({
  kind, card: { card: "plan", id: `plan-${kind}`, author: "human" }, valid,
  problems: valid ? [] : ["$.operation: required property is missing"], range_problems: [],
  refused_today: ["Refused until you write a limit: your safety file has none for this part yet."],
  saved: false, note: "A draft is shown in full and saved nowhere. Where a console draft goes before the person signs it is still to be designed.",
});

interface Opts {
  status?: { state: string; data?: unknown; problems?: string[] };
  limits?: unknown;
  run?: unknown;
  signing?: Record<string, unknown>;
  draft?: Route;
  hash?: string;
  extra?: Record<string, Route>;
}

function show(opts: Opts = {}) {
  window.location.hash = opts.hash ?? "#/instruments";
  const fake = fakeTransport({
    [PATHS.status]: () => ({ status: 200, body: opts.status ?? { state: "present", data: IDLE, problems: [] } }),
    [PATHS.limits]: () => ({ status: 200, body: opts.limits ?? LIMITS }),
    [PATHS.latestRun]: () => ({ status: 200, body: opts.run ?? NO_RUN }),
    [SIGNING]: () => ({ status: 200, body: opts.signing ?? PERSON }),
    [PATHS.draft]: opts.draft ?? ((init) => ({ status: 200, body: DRAFT_OUT(JSON.parse(String(init?.body)).kind, true) })),
    ...(opts.extra ?? {}),
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
  const posts = () => fake.calls.filter((c) => c.init?.method === "POST");
  return { ...fake, client, posts };
}

const tab = (name: string) => screen.findByRole("tab", { name });

describe("the six sub-tabs", () => {
  it("offers Status, Optics and control, Cameras, Tweezers, Confocal and Piezo stage, Status first", async () => {
    show();
    const bar = await screen.findByRole("tablist", { name: "Instruments" });
    expect(within(bar).getAllByRole("tab").map((t) => t.textContent)).toEqual([
      "Status", "Optics and control", "Cameras", "Tweezers", "Confocal", "Piezo stage",
    ]);
    expect((await tab("Status")).getAttribute("aria-selected")).toBe("true");
  });
});

describe("Status", () => {
  it("says 'No status yet' when the runtime has written no file, and not that nothing is connected", async () => {
    show({ status: { state: "none", data: null, problems: [] } });
    expect(await screen.findByText("No status yet")).toBeTruthy();
    expect(screen.getByText(/does not mean that nothing is connected/)).toBeTruthy();
    expect(screen.queryByText(/As of/)).toBeNull();
  });

  it("shows when the file was written and by which run, then each reading's name, value, how and when", async () => {
    show();
    expect(await screen.findByText("As of 2026-10-24 11:05:00, from run-20261024-001")).toBeTruthy();
    const table = screen.getByRole("table", { name: "Readings" });
    const rows = within(table).getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell").map((c) => c.textContent));
    expect(rows[0]).toEqual(["Spectra III via DMD", "mirrors parked", "read back", "2026-10-24 11:00:00"]);
    expect(rows[1]).toEqual(["Tweez 300 trap strength", "0.02", "sent, cannot be read", "2026-10-24 11:00:00"]);
    expect(rows[2]).toEqual(["Piezo stage", "unknown", "not read", "—"]);
  });

  it("an invalid file is shown as invalid, with why, and no reading from it", async () => {
    show({ status: { state: "invalid", data: null, problems: ["$.written_at: not a date-time"] } });
    expect(await screen.findByText(/not a date-time/)).toBeTruthy();
    expect(screen.queryByRole("table", { name: "Readings" })).toBeNull();
  });

  it("always has the tweezers laser row, 'assumed on', whatever the file says or lacks", async () => {
    const first = show({ status: { state: "none", data: null, problems: [] } });
    expect(await screen.findByText(LASER)).toBeTruthy();
    first.client.events.stop();
  });

  it("keeps the laser row 'assumed on' when the file has a tweezers reading that says off", async () => {
    const data = JSON.parse(JSON.stringify(IDLE));
    data.last_run.last_snapshot.channels.push(reading("optical_tweezers", "Tweezers laser", "read_back", "off"));
    show({ status: { state: "present", data, problems: [] } });
    expect(await screen.findByText(LASER)).toBeTruthy();
  });

  it("labels the trap strength last sent as sent through the tweezers program", async () => {
    show({ run: RUN });
    expect(await screen.findByText("Trap strength last sent: 0.3 (sent through the tweezers program)")).toBeTruthy();
  });

  it("says 'not checked yet' for which program holds which instrument while ownership is not built", async () => {
    show();
    expect(await screen.findByText("Which program holds which instrument: not checked yet")).toBeTruthy();
  });

  it("offers Check now to the person only, and pressing it answers 'not built yet' and sends nothing", async () => {
    const { calls } = show();
    const button = await screen.findByRole("button", { name: "Check now" });
    await screen.findByText("As of 2026-10-24 11:05:00, from run-20261024-001");
    const before = calls.length;
    fireEvent.click(button);
    expect(await screen.findByText(/Check now is not built yet/)).toBeTruthy();
    expect(calls.length).toBe(before);
    expect(calls.filter((c) => c.init?.method === "POST")).toEqual([]);
  });

  it("does not offer Check now to a login that is not the person's", async () => {
    show({ signing: VIEWER });
    await screen.findByText("As of 2026-10-24 11:05:00, from run-20261024-001");
    expect(screen.queryByRole("button", { name: "Check now" })).toBeNull();
  });
});

describe("Optics and control", () => {
  const open = async (opts: Opts = {}) => {
    const t = show({ hash: "#/instruments/optics", ...opts });
    await screen.findByRole("figure", { name: "Picture of the stand" });
    return t;
  };

  it("draws three rows of parts, labelled as a picture of the stand", async () => {
    await open();
    const picture = screen.getByRole("figure", { name: "Picture of the stand" });
    const rows = within(picture).getAllByRole("group");
    expect(rows.map((r) => r.getAttribute("aria-label"))).toEqual(["Transmitted light", "Light from above", "To the cameras"]);
    expect(within(picture).getByRole("button", { name: /Transmitted lamp/ })).toBeTruthy();
    expect(within(picture).getByRole("button", { name: /Objective/ })).toBeTruthy();
    expect(within(picture).getByRole("button", { name: /Camera red arm/ })).toBeTruthy();
    expect(screen.getByText(/picture of the stand, not a measurement/)).toBeTruthy();
  });

  it("shows a part's state from the status file by channel id, and 'unknown' for a part with none", async () => {
    await open();
    const picture = screen.getByRole("figure", { name: "Picture of the stand" });
    expect(within(picture).getByRole("button", { name: /Spectra III via DMD/ }).textContent).toContain("mirrors parked");
    expect(within(picture).getByRole("button", { name: /Polarizer/ }).textContent).toContain("unknown");
    // which of the two widefield channels is the LED and which the lamp is not recorded, so neither part takes it
    expect(within(picture).getByRole("button", { name: /Aura III LED/ }).textContent).toContain("unknown");
    expect(within(picture).getByRole("button", { name: /Transmitted lamp/ }).textContent).toContain("unknown");
  });

  it("a channel that was not read is unknown, never its last value", async () => {
    await open();
    const picture = screen.getByRole("figure", { name: "Picture of the stand" });
    expect(within(picture).getByRole("button", { name: /Piezo stage/ }).textContent).toContain("unknown");
  });

  it("double-clicking a part opens the tab it belongs to", async () => {
    await open();
    const sections = screen.getByRole("tablist", { name: "Optics sections" });
    expect(within(sections).getAllByRole("tab").map((t) => t.textContent)).toEqual(["Light source", "Filters", "Magnification", "Camera"]);
    fireEvent.doubleClick(screen.getByRole("button", { name: /Objective/ }));
    expect(within(sections).getByRole("tab", { name: "Magnification" }).getAttribute("aria-selected")).toBe("true");
    fireEvent.doubleClick(screen.getByRole("button", { name: /Camera red arm/ }));
    expect(within(sections).getByRole("tab", { name: "Camera" }).getAttribute("aria-selected")).toBe("true");
  });

  it("offers a draft for exactly three parts and says 'set by hand; software may not move it' for every other", async () => {
    await open();
    const sections = screen.getByRole("tablist", { name: "Optics sections" });
    const drafts: string[] = [];
    let byHand = 0;
    for (const name of ["Light source", "Filters", "Magnification", "Camera"]) {
      fireEvent.click(within(sections).getByRole("tab", { name }));
      const panel = screen.getByRole("tabpanel");
      drafts.push(...within(panel).queryAllByRole("button", { name: /^Draft / }).map((b) => b.textContent ?? ""));
      byHand += within(panel).queryAllByText("set by hand; software may not move it").length;
    }
    expect(drafts.sort()).toEqual(["Draft Aura III LED", "Draft Camera red arm exposure", "Draft Transmitted lamp"]);
    expect(byHand).toBeGreaterThanOrEqual(10);
  });

  it("each draft carries 'refused until you write a limit'", async () => {
    await open();
    const sections = screen.getByRole("tablist", { name: "Optics sections" });
    for (const [tabName, part] of [["Light source", "Aura III LED"], ["Light source", "Transmitted lamp"], ["Camera", "Camera red arm"]]) {
      fireEvent.click(within(sections).getByRole("tab", { name: tabName }));
      const box = within(screen.getByRole("tabpanel")).getByRole("group", { name: part });
      expect(within(box).getByText(/refused until you write a limit/i)).toBeTruthy();
    }
  });

  it("the laser combiner reads: close was sent; assumed open until a shutter that reads back shows it blocked", async () => {
    await open();
    fireEvent.click(within(screen.getByRole("tablist", { name: "Optics sections" })).getByRole("tab", { name: "Light source" }));
    expect(screen.getByText("close was sent; assumed open until a shutter that reads back shows it blocked")).toBeTruthy();
  });

  it("a draft is requested from the server, shown in full, and saved nowhere", async () => {
    const t = await open();
    fireEvent.click(within(screen.getByRole("tablist", { name: "Optics sections" })).getByRole("tab", { name: "Light source" }));
    const box = within(screen.getByRole("tabpanel")).getByRole("group", { name: "Aura III LED" });
    fireEvent.change(within(box).getByLabelText("Colour"), { target: { value: "Blue" } });
    fireEvent.change(within(box).getByLabelText("Power (mW)"), { target: { value: "5" } });
    fireEvent.click(within(box).getByRole("button", { name: "Draft Aura III LED" }));
    const view = await screen.findByRole("region", { name: "Plan draft" });
    expect(within(view).getByLabelText("Draft plan card").textContent).toContain('"id": "plan-aura"');
    expect(within(view).getByText(/Not saved/)).toBeTruthy();
    expect(within(view).getByText(/still to be designed/)).toBeTruthy();
    expect(t.posts().map((c) => [c.path, JSON.parse(String(c.init?.body))])).toEqual([[PATHS.draft, { kind: "aura", color: "Blue", power_mw: 5 }]]);
  });

  it("a draft the schema refuses is shown with the refusal and not offered for signing", async () => {
    await open({ draft: () => ({ status: 200, body: DRAFT_OUT("dialamp", false) }) });
    fireEvent.click(within(screen.getByRole("tablist", { name: "Optics sections" })).getByRole("tab", { name: "Light source" }));
    const box = within(screen.getByRole("tabpanel")).getByRole("group", { name: "Transmitted lamp" });
    fireEvent.change(within(box).getByLabelText("Intensity (%)"), { target: { value: "30" } });
    fireEvent.click(within(box).getByRole("button", { name: "Draft Transmitted lamp" }));
    const view = await screen.findByRole("region", { name: "Plan draft" });
    expect(within(view).getByText("This draft is not offered for signing.")).toBeTruthy();
    expect(within(view).getByText("$.operation: required property is missing")).toBeTruthy();
  });

  it("shows the server's refusal in words when the login may not draft", async () => {
    await open({
      draft: () => ({ status: 403, body: { detail: { code: "role", message: "This login can only look: it cannot make a plan draft." } } }),
    });
    fireEvent.click(within(screen.getByRole("tablist", { name: "Optics sections" })).getByRole("tab", { name: "Camera" }));
    const box = within(screen.getByRole("tabpanel")).getByRole("group", { name: "Camera red arm" });
    fireEvent.change(within(box).getByLabelText("Exposure (ms)"), { target: { value: "20" } });
    fireEvent.click(within(box).getByRole("button", { name: "Draft Camera red arm exposure" }));
    expect((await screen.findByRole("alert")).textContent).toContain("This login can only look");
  });
});

describe("Cameras", () => {
  const open = async (opts: Opts = {}) => {
    const t = show({ hash: "#/instruments/cameras", ...opts });
    await screen.findByRole("region", { name: "Camera 1, red" });
    return t;
  };

  it("has four panels, the blue camera 'not opened by software yet', and no traps drawn", async () => {
    await open();
    expect(screen.getByRole("region", { name: "Camera 2, blue" }).textContent).toContain("not opened by software yet");
    expect(screen.getByRole("region", { name: "Both cameras" }).textContent).toContain("not opened by software yet");
    expect(screen.getByRole("region", { name: "With traps and stage" }).textContent).toContain(
      "traps not drawn: their mapping onto the camera is not measured",
    );
  });

  it("offers Live view to the person only, and connects to nothing until it is pressed", async () => {
    const t = await open({ extra: { [QPATHS.live]: () => ({ status: 200, body: { available: false, why_not: "no host", lists: [] } }) } });
    await screen.findByRole("button", { name: "Live view" });
    expect(t.calls.some((c) => c.path === QPATHS.live)).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Live view" }));
    await waitFor(() => expect(t.calls.some((c) => c.path === QPATHS.live)).toBe(true));
  });

  it("does not offer Live view to a login that is not the person's", async () => {
    await open({ signing: VIEWER });
    await waitFor(() => expect(screen.queryByRole("button", { name: "Live view" })).toBeNull());
  });

  it("has the exposure draft of the Optics tab", async () => {
    await open();
    expect(screen.getByRole("button", { name: "Draft Camera red arm exposure" })).toBeTruthy();
  });
});

describe("Tweezers", () => {
  const open = async (opts: Opts = {}) => {
    const t = show({ hash: "#/instruments/tweezers", ...opts });
    await screen.findByText(LASER);
    return t;
  };

  it("with no run says 'no trap sent'", async () => {
    await open();
    expect(await screen.findByText("no trap sent")).toBeTruthy();
  });

  it("shows the latest run's traps and the three plots, each labelled sent", async () => {
    await open({ run: RUN });
    const table = await screen.findByRole("table", { name: "Traps (sent)" });
    expect(within(table).getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell").map((c) => c.textContent))).toEqual([
      ["trap_1", "2", "0", "0.3", "on"],
    ]);
    for (const name of ["t-x (sent)", "t-y (sent)", "x-y (sent)"]) expect(screen.getByRole("img", { name })).toBeTruthy();
    expect(screen.getByText(/from run-20261024-001/)).toBeTruthy();
  });

  it("states the ranges from the safety file, not from code", async () => {
    await open();
    const box = screen.getByRole("group", { name: "What a pattern is allowed" });
    expect(box.textContent).toContain("40x: -100 to 100 µm");
    expect(box.textContent).toContain("100x: -4 to 4 µm");
    expect(box.textContent).toContain("at most 1 µm per step");
    expect(box.textContent).toContain("from your safety file");
    expect(box.textContent).toContain("Trap count and flicker rate are refused until a limit exists");
  });

  it("states a missing limit as a refusal", async () => {
    await open({ limits: { ...LIMITS, tweezers: { positions: { "40x": null, "60x": null, "100x": null }, step_max: null, strength: null } } });
    const box = screen.getByRole("group", { name: "What a pattern is allowed" });
    expect(box.textContent).toContain("40x: no limit in your safety file, so refused");
    expect(box.textContent).toContain("per step: no limit in your safety file, so refused");
  });

  it("a pattern is a trap_steps draft, requested from the server and saved nowhere", async () => {
    const t = await open({ draft: (init) => ({ status: 200, body: DRAFT_OUT(JSON.parse(String(init?.body)).kind, true) }) });
    fireEvent.change(screen.getByLabelText("Pattern"), { target: { value: "circle" } });
    fireEvent.change(screen.getByLabelText("Number of traps"), { target: { value: "4" } });
    fireEvent.change(screen.getByLabelText("Spacing (µm)"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Strength (0 to 1)"), { target: { value: "0.2" } });
    fireEvent.change(screen.getByLabelText("Objective"), { target: { value: "60x" } });
    fireEvent.click(screen.getByRole("button", { name: "Draft trap pattern" }));
    expect(await screen.findByRole("region", { name: "Plan draft" })).toBeTruthy();
    expect(t.posts().map((c) => [c.path, JSON.parse(String(c.init?.body))])).toEqual([
      [PATHS.draft, { kind: "trap_steps", pattern: "circle", n: 4, spacing_um: 2, strength: 0.2, objective: "60x" }],
    ]);
  });

  it("has no click-to-hold and no dragging: nothing on a plot or a trap is a control", async () => {
    await open({ run: RUN });
    await screen.findByRole("table", { name: "Traps (sent)" });
    const plots = screen.getAllByRole("img");
    for (const p of plots) expect(within(p).queryAllByRole("button")).toEqual([]);
    expect(screen.queryByRole("button", { name: /hold/i })).toBeNull();
  });
});

describe("Confocal", () => {
  it("shows state only, from the spinning disk channel, and says the shutter's closed value is not recorded", async () => {
    const t = show({ hash: "#/instruments/confocal" });
    expect(await screen.findByText("disk 1")).toBeTruthy();
    expect(screen.getByText("read back; which value means closed is not recorded")).toBeTruthy();
    expect(screen.queryAllByRole("button").filter((b) => b.getAttribute("role") !== "tab")).toEqual([]);
    expect(t.posts()).toEqual([]);
  });

  it("without a status file the disk is unknown", async () => {
    show({ hash: "#/instruments/confocal", status: { state: "none", data: null, problems: [] } });
    expect(await screen.findByText("No status yet")).toBeTruthy();
  });
});

describe("Piezo stage", () => {
  it("shows x, y and z of the last snapshot with when and from which run, in micrometres", async () => {
    show({ hash: "#/instruments/piezo", run: RUN });
    expect(await screen.findByText("as of 2026-10-24 11:00:40, from run-20261024-001")).toBeTruthy();
    const now = screen.getByRole("group", { name: "Position now" });
    expect(now.textContent).toContain("x 101 µm");
    expect(now.textContent).toContain("y 111 µm");
    expect(now.textContent).toContain("z 121 µm");
  });

  it("with no run shows no position", async () => {
    show({ hash: "#/instruments/piezo" });
    expect(await screen.findByText("no position read yet")).toBeTruthy();
  });

  it("reads the range from the safety file, not from code", async () => {
    show({ hash: "#/instruments/piezo" });
    const box = await screen.findByRole("group", { name: "Your range" });
    expect(box.textContent).toContain("x: 11 to 555 µm");
    expect(box.textContent).toContain("y: 12 to 556 µm");
    expect(box.textContent).toContain("z: 13 to 557 µm");
    expect(box.textContent).toContain("from your safety file");
  });

  it("a range the file lacks is said to be missing", async () => {
    show({ hash: "#/instruments/piezo", limits: { ...LIMITS, piezo: { x: null, y: null, z: null } } });
    const box = await screen.findByRole("group", { name: "Your range" });
    expect(box.textContent).toContain("x: no range in your safety file");
  });

  it("the window and refresh are screen-only, and the read rate is a plan field", async () => {
    show({ hash: "#/instruments/piezo", run: RUN });
    expect(await screen.findByText("The window and refresh change only this screen. How often the stage is read is part of the plan you sign.")).toBeTruthy();
    expect(screen.getByLabelText("Time window")).toBeTruthy();
    expect(screen.getByLabelText("Screen refresh")).toBeTruthy();
  });

  it("window 30 s keeps only the points within 30 s of the last, and refresh starts off", async () => {
    show({ hash: "#/instruments/piezo", run: RUN });
    const refresh = (await screen.findByLabelText("Screen refresh")) as HTMLSelectElement;
    expect(refresh.value).toBe("off");
    const table = screen.getByRole("table", { name: "Piezo positions" });
    expect(within(table).getAllByRole("row").slice(1)).toHaveLength(2);
    fireEvent.change(screen.getByLabelText("Time window"), { target: { value: "30" } });
    expect(within(table).getAllByRole("row").slice(1)).toHaveLength(1);
  });

  it("shows 'designed later' for the pattern generator", async () => {
    show({ hash: "#/instruments/piezo" });
    expect(await screen.findByText("designed later")).toBeTruthy();
  });
});

describe("nothing is commanded and nothing is saved", () => {
  it("a tour of every sub-tab sends no request but the draft route, and no write other than a draft", async () => {
    const t = show();
    await screen.findByText("As of 2026-10-24 11:05:00, from run-20261024-001");
    for (const name of ["Optics and control", "Cameras", "Tweezers", "Confocal", "Piezo stage", "Status"]) {
      fireEvent.click(await tab(name));
      await waitFor(() => expect(screen.getByRole("tab", { name }).getAttribute("aria-selected")).toBe("true"));
    }
    expect(t.calls.filter((c) => c.init?.method !== undefined && c.init.method !== "GET")).toEqual([]);
    const allowed = new Set([PATHS.status, PATHS.limits, PATHS.latestRun, SIGNING, "/api/auth/me", "/api/auth/setup", "/api/auth/control", "/api/auth/activity"]);
    expect(t.calls.map((c) => c.path).filter((p) => !allowed.has(p))).toEqual([]);
  });
});
