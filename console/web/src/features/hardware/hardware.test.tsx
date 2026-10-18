import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { ScreenContextProvider, useCurrentScreenContext } from "../../app/screenContext";
import { fakeTransport, type Route } from "../../test/fakes";
import { type ConfigDraftOut, type ConfigMatchOut, type ConfigTreeOut, type GateRow, type HardwareProfileOut, PATHS, type Permissions, SCREEN_OPS } from "./api";
import HardwareScreen from "./index";

const PROFILE: HardwareProfileOut = {
  path: "D:/AutoFocus/hardware/hardware_profile.json",
  sha256: "abcdef0123456789",
  previous: { sha256: "ef".repeat(32), detected_at: "2026-10-01T17:00:00",
              changed: [{ key: "device.XYStage.read_back", before: true, after: false }] },
  profile: {
    detected_at: "2026-10-01T18:00:00",
    backend_kind: "mock",
    bench: false,
    devices: [
      { label: "Kinetix_red", type: "Camera", present: true, read_back: true, write_verified: null },
      { label: "ZDrive", type: "Stage", present: true, read_back: true, write_verified: null },
      { label: "XYStage", type: "XYStage", present: true, read_back: false, write_verified: null, note: "no read-back" },
    ],
    objectives: [{ label: "1-Plan Apo LmbdD20 4x", state: 0, magnification: 4, working_distance_um: null }],
    camera: { bit_depth: 12 },
    human_confirmed: {},
  },
};

const DEV = (label: string, library: string, adapter: string, over: Partial<NonNullable<ConfigTreeOut["devices"]>[number]> = {}) =>
  ({ label, library, adapter, parent: null, link: null, port: null, roles: [], state_labels: {}, preinit: {}, line: 1, ...over });

// as GET /api/hardware/config serves a small dual-camera cfg
const CONFIG: ConfigTreeOut = {
  path: "C:/mm/bench.cfg",
  sha256: "cd".repeat(32),
  source: "scanned",
  available: [
    { path: "C:/mm/bench.cfg", name: "bench.cfg", source: "scanned" },
    { path: "D:/repo/configs/micromanager/DMD_dualcam_LUNF.cfg", name: "DMD_dualcam_LUNF.cfg", source: "repo" },
  ],
  devices: [
    DEV("Ti2-E__0", "NikonTi2", "Ti2-E__0"),
    DEV("ZDrive", "NikonTi2", "ZDrive", { parent: "Ti2-E__0", link: "parent", roles: ["Focus"] }),
    DEV("XYStage", "NikonTi2", "XYStage", { parent: "Ti2-E__0", link: "parent" }),
    DEV("COM10", "SerialManager", "COM10", { preinit: { BaudRate: "115200" } }),
    DEV("CSUW1-Hub", "CSUW1", "CSUW1-Hub", { parent: "COM10", link: "port", port: "COM10" }),
    DEV("CSUW1-Port", "CSUW1", "CSUW1-Port", { parent: "CSUW1-Hub", link: "inferred",
        state_labels: { "0": "blue_only", "1": "blue_red", "2": "red_only" } }),
    DEV("CSUW1-Shutter", "CSUW1", "CSUW1-Shutter", { parent: "CSUW1-Hub", link: "inferred" }),
    DEV("Kinetix_red", "PVCAM", "Camera-2", { roles: ["Camera"] }),
  ],
  startup: [],
  warnings: [],
  error: null,
};

const MATCH: ConfigMatchOut = {
  detected_at: "2026-10-01T18:00:00",
  rows: [
    { path: "C:/mm/bench.cfg", name: "bench.cfg", source: "scanned", score: 1, exact: true,
      matched: ["Kinetix_red", "XYStage", "ZDrive"], differs: [], missing: [], extra: [] },
    { path: CONFIG.available![1].path, name: "DMD_dualcam_LUNF.cfg", source: "repo", score: 0.3, exact: false,
      matched: ["Kinetix_red", "XYStage", "ZDrive"], differs: [], missing: ["COM10", "CSUW1-Hub"], extra: [] },
  ],
  error: null,
};

const DRAFT: ConfigDraftOut = {
  text: ["# Drafted by dino-autofocus", "Device,ZDrive,NikonTi2,ZDrive", ""].join("\n"),
  devices: 3,
  base: { path: "C:/mm/bench.cfg", name: "bench.cfg", source: "scanned" },
  from_base: ["ZDrive: adapter"],
  unknown_adapter: [],
  hub_found: ["Ti2-E__0: Nosepiece"],
  warnings: [],
  load_check: null,
  suggested_name: "from-scan-202610011800",
};

function requires(over: Partial<GateRow["requires"]> = {}): GateRow["requires"] {
  return { devices: [], objectives: [], confirmed: [], checks: [], arg: null, ...over };
}

// as server/api/hardware.py serves T-028 gate_rows: light_set has one row per mode
const GATES: GateRow[] = [
  { op: "status", enabled: true, reasons: [], requires: requires({ devices: ["camera"] }) },
  {
    op: "sample_map",
    enabled: false,
    reasons: ["xy_stage detected but its state did not read back"],
    requires: requires({ devices: ["camera", "xy_stage"], objectives: ["4x"], checks: ["camera_bit_depth"] }),
  },
  { op: "light_set:brightfield", enabled: true, reasons: [],
    requires: requires({ devices: ["dia_lamp"], arg: { mode: "brightfield" } }) },
  { op: "light_set:aura", enabled: true, reasons: [], requires: requires({ devices: ["aura"], arg: { mode: "aura" } }) },
];

const ALLOWED: Permissions = Object.fromEntries(SCREEN_OPS.map((op) => [op, { allowed: true, reason: null }]));

function refused(ops: readonly string[], reason: string): Permissions {
  return Object.fromEntries(ops.map((op) => [op, { allowed: false, reason }]));
}

function ContextProbe() {
  const ctx = useCurrentScreenContext();
  return <pre data-testid="ctx">{JSON.stringify(ctx)}</pre>;
}

interface Opts {
  hostname?: string;
  permissions?: Route;
  gates?: GateRow[];
  profile?: HardwareProfileOut;
  commands?: Route;
  config?: ConfigTreeOut;
  saveDraft?: Route;
}

/** The screen on the shell's client over a fake transport: no network, no socket, no window. */
function setup(o: Opts = {}) {
  const world = {
    permissions: ALLOWED as Permissions,
    snapshot: { positions: { z_um: 3012.5 }, running: [] } as Record<string, unknown>,
  };
  const t = fakeTransport({
    "/api/state": () => ({ status: 200, body: world.snapshot }),
    [PATHS.profile]: () => ({ status: 200, body: o.profile ?? PROFILE }),
    [PATHS.gates]: () => ({ status: 200, body: o.gates ?? GATES }),
    [PATHS.status]: () => ({ status: 200, body: null }),
    [PATHS.config()]: () => ({ status: 200, body: o.config ?? CONFIG }),
    [PATHS.configMatch]: () => ({ status: 200, body: MATCH }),
    [PATHS.configDraft()]: (init) => init?.method === "POST"
      ? (o.saveDraft ?? (() => ({ status: 201, body: { path: "C:/settings/micromanager/mine.cfg", sha256: "ab".repeat(32), load_check: null } })))(init)
      : { status: 200, body: DRAFT },
    [PATHS.config(CONFIG.available![1].path)]: () =>
      ({ status: 200, body: { ...CONFIG, path: CONFIG.available![1].path, source: "repo", devices: [DEV("NIDAQHub", "NIDAQ", "NIDAQHub")] } }),
    [PATHS.permissions(SCREEN_OPS)]: o.permissions ?? (() => ({ status: 200, body: world.permissions })),
    "/api/commands": o.commands ?? (() => ({ status: 200, body: { op_id: "op-1" } })),
  });
  const client = new Client(t.transport, o.hostname ?? "127.0.0.1");
  render(
    <ClientProvider client={client}>
      <ScreenContextProvider area="hardware">
        <HardwareScreen />
        <ContextProbe />
      </ScreenContextProvider>
    </ClientProvider>,
  );
  const socket = () => t.sockets[0];
  const sent = () =>
    t.calls.filter((c) => c.path === "/api/commands").map((c) => JSON.parse(String(c.init?.body)));
  const emit = (kind: string, data: Record<string, unknown> = {}, opId = "") => act(() => socket().event(kind, data, opId));
  return { ...t, client, world, sent, emit };
}

/** Disabled directly or by a disabled fieldset. */
const isDisabled = (el: HTMLElement) => el.matches(":disabled");
const button = (name: string) => screen.getByRole("button", { name });

describe("hardware screen", () => {
  it("shows off gates first, with their reasons", async () => {
    setup();
    const table = within(await screen.findByRole("region", { name: "Gates" }));
    await waitFor(() => expect(table.getAllByRole("row")).toHaveLength(5));
    const rows = table.getAllByRole("row").slice(1);
    expect(rows[0].textContent).toContain("sample_map");
    expect(rows[0].textContent).toContain("Off");
    expect(rows[0].textContent).toContain("xy_stage detected but its state did not read back");
    expect(rows.map((r) => (r as HTMLTableRowElement).cells[0].textContent)).toEqual(
      ["sample_map", "light_set:aura", "light_set:brightfield", "status"]);
  });

  it("sorts problem devices first", async () => {
    setup();
    const table = within(await screen.findByRole("region", { name: "Devices" }));
    await waitFor(() => expect(table.getAllByRole("row")).toHaveLength(4));
    const rows = table.getAllByRole("row").slice(1);
    expect(rows.map((r) => (r as HTMLTableRowElement).cells[0].textContent)).toEqual(["XYStage", "Kinetix_red", "ZDrive"]);
  });

  it("says when nothing has been scanned", async () => {
    setup({ profile: { profile: null, path: null, sha256: null } });
    expect(await screen.findByText(/Not scanned yet/)).toBeTruthy();
  });

  it("says it is checking permissions until the first answer", async () => {
    setup();
    // the fake's answer is a promise away: the first render has not seen it yet
    expect(screen.getAllByText("Checking permissions…").length).toBeGreaterThan(0);
    expect(isDisabled(button("Scan hardware"))).toBe(true);
    await waitFor(() => expect(isDisabled(button("Scan hardware"))).toBe(false));
  });

  it("counts an op missing from the answer as unavailable", async () => {
    setup({ permissions: () => ({ status: 200, body: { lights_off: { allowed: true, reason: null } } }) });
    await waitFor(() => expect(screen.getAllByText("Permission check unavailable").length).toBeGreaterThan(0));
    expect(isDisabled(button("Scan hardware"))).toBe(true);
    expect(isDisabled(button("Lights off"))).toBe(false);
  });

  it("falls back to 'Permission check unavailable' but keeps Lights off on this PC", async () => {
    const t = setup({ permissions: () => ({ status: 404, body: { detail: "Not Found" } }) });
    await waitFor(() => expect(screen.getAllByText("Permission check unavailable").length).toBeGreaterThan(0));
    expect(isDisabled(button("Scan hardware"))).toBe(true);
    expect(isDisabled(button("Brightfield on"))).toBe(true);
    expect(isDisabled(button("Lights off"))).toBe(false);
    fireEvent.click(button("Lights off"));
    await waitFor(() => expect(t.sent()).toHaveLength(1));
    expect(t.sent()[0]).toMatchObject({ kind: "lights_off" });
  });

  it("greys out Lights off on a remote screen even when permissions can't be read (D2)", async () => {
    setup({ hostname: "192.168.1.20", permissions: () => ({ status: 404, body: { detail: "Not Found" } }) });
    await waitFor(() => expect(isDisabled(button("Lights off"))).toBe(true));
    const lights = within(screen.getByRole("region", { name: "Lights" }));
    expect(lights.getAllByText("Read-only: remote view").length).toBeGreaterThan(0);
  });

  it("disables the confirm form on a remote screen", async () => {
    setup({ hostname: "192.168.1.20" });
    const form = within(await screen.findByRole("region", { name: "Human-confirmed items" }));
    expect(isDisabled(form.getByRole("button", { name: "Save" }))).toBe(true);
    expect(form.getByText("Read-only: remote view")).toBeTruthy();
  });

  it("disables operator commands for a viewer but keeps Lights off", async () => {
    const viewer = {
      ...refused(["hardware_scan", "hardware_confirm", "status", "light_set"], "Needs the operator role"),
      lights_off: { allowed: true, reason: null },
    };
    setup({ permissions: () => ({ status: 200, body: viewer }) });
    await waitFor(() => expect(isDisabled(button("Scan hardware"))).toBe(true));
    await waitFor(() => expect(screen.getAllByText("Needs the operator role").length).toBeGreaterThan(0));
    expect(isDisabled(button("Lights off"))).toBe(false);
  });

  it("needs an open experiment session for light_set (D15)", async () => {
    const noSession = { ...ALLOWED, light_set: { allowed: false, reason: "Open an experiment session first" } };
    setup({ permissions: () => ({ status: 200, body: noSession }) });
    expect((await screen.findAllByText("Open an experiment session first")).length).toBe(2); // both modes
    expect(isDisabled(button("Brightfield on"))).toBe(true);
    expect(isDisabled(button("Scan hardware"))).toBe(false);
    expect(isDisabled(button("Aura GREEN 1 % on"))).toBe(true);
  });

  it("scans with the piezo skipped by default", async () => {
    const t = setup();
    await waitFor(() => expect(isDisabled(button("Scan hardware"))).toBe(false));
    fireEvent.click(button("Scan hardware"));
    await waitFor(() => expect(t.sent()).toHaveLength(1));
    expect(t.sent()[0]).toMatchObject({
      kind: "start", op: "hardware_scan", args: { include_properties: true, piezo_port: "" },
    });
  });

  it("shows the light read-back, not the requested value", async () => {
    const t = setup();
    const state = await screen.findByTestId("light-state");
    await waitFor(() => expect(isDisabled(button("Brightfield on"))).toBe(false));
    fireEvent.click(button("Brightfield on"));
    await waitFor(() => expect(t.sent()).toHaveLength(1));
    expect(state.textContent).toContain("no read-back yet");

    // the one light shape (server/schemas/state.py `Lights`, runner._light_payload)
    t.emit("light_changed", {
      dialamp: { state: "unknown", intensity: null },
      aura: { state: "off", lines: {} },
      verified: false,
      records: [{ device: "DiaLamp", prop: "State", wanted: 1, read: 0, verified: false }],
      error: null,
    });
    expect(state.textContent).toContain("Lights not confirmed: DiaLamp read 0, wanted 1");

    const lit = {
      dialamp: { state: "off", intensity: null },
      aura: { state: "on", lines: { GREEN: 1 } },
      verified: true,
      records: [],
      error: null,
    };
    t.world.snapshot = { ...t.world.snapshot, lights: lit };
    t.emit("light_changed", lit);
    expect(state.textContent).toContain("DiaLamp OFF · Aura GREEN 1 %");

    const lamp = { ...lit, dialamp: { state: "on", intensity: 608 }, aura: { state: "off", lines: {} } };
    t.world.snapshot = { ...t.world.snapshot, lights: lamp };
    t.emit("light_changed", lamp);
    expect(state.textContent).toContain("DiaLamp ON (608) · Aura OFF");

    t.world.snapshot = { ...t.world.snapshot, lights: lit };
    t.emit("light_changed", lit);

    // the end of an operation does not mean lights off (T-011): only a read-back changes the panel
    t.emit("finished", { op: "status", summary: {} }, "op-2");
    await waitFor(() => expect(t.calls.filter((c) => c.path === "/api/state").length).toBeGreaterThan(1));
    expect(state.textContent).toContain("DiaLamp OFF · Aura GREEN 1 %");
  });

  it("re-reads permissions when an operation starts and ends, and names it on Lights off", async () => {
    const t = setup();
    await waitFor(() => expect(isDisabled(button("Scan hardware"))).toBe(false));

    t.world.permissions = { ...ALLOWED, hardware_scan: { allowed: false, reason: "status is running" } };
    t.world.snapshot = { ...t.world.snapshot, running: [{ op: "status", op_id: "op-9" }] };
    t.emit("started", { op: "status" }, "op-9");
    await waitFor(() => expect(isDisabled(button("Scan hardware"))).toBe(true));
    expect(screen.getByText("status is running")).toBeTruthy();
    await waitFor(() => expect(screen.getByText("stops status")).toBeTruthy());

    t.world.permissions = ALLOWED;
    t.world.snapshot = { ...t.world.snapshot, running: [] };
    t.emit("finished", { op: "status", summary: { nosepiece_label: "1-Plan Apo LmbdD20 4x", z_um: 3012.5 } }, "op-9");
    await waitFor(() => expect(isDisabled(button("Scan hardware"))).toBe(false));
    const current = within(screen.getByRole("region", { name: "Current state" }));
    expect(current.getByText("1-Plan Apo LmbdD20 4x")).toBeTruthy();
    expect(current.getByText("Z 3012.50 µm")).toBeTruthy();
  });

  it("shows this area's gate reason when the permission allows the op", async () => {
    setup({
      gates: [...GATES, {
        op: "hardware_scan", enabled: false, reasons: ["camera not detected"],
        requires: requires({ devices: ["camera"] }),
      }],
    });
    expect(await screen.findByText("hardware_scan is off: camera not detected")).toBeTruthy();
    expect(isDisabled(button("Scan hardware"))).toBe(true);
  });

  it("takes each light button's gate from its own light_set mode row (T-028)", async () => {
    setup({
      gates: GATES.map((g) => g.op === "light_set:brightfield"
        ? { ...g, enabled: false, reasons: ["dia_lamp not detected"] } : g),
    });
    const bf = within(screen.getByTestId("light-brightfield"));
    expect(await bf.findByText("light_set:brightfield is off: dia_lamp not detected")).toBeTruthy();
    expect(isDisabled(button("Brightfield on"))).toBe(true);
    expect(isDisabled(button("Aura GREEN 1 % on"))).toBe(false);
  });

  it("shows the previous-profile diff and the backend kind", async () => {
    setup();
    const summary = within(await screen.findByRole("region", { name: "Detection summary" }));
    expect(await summary.findByText("changed: device.XYStage.read_back")).toBeTruthy();
    expect(summary.getByText("mock (not the bench)")).toBeTruthy();
  });

  it("shows a server refusal next to the button", async () => {
    setup({ commands: () => ({ status: 400, body: { detail: "Ann has control of the microscope" } }) });
    await waitFor(() => expect(isDisabled(button("Scan hardware"))).toBe(false));
    fireEvent.click(button("Scan hardware"));
    expect(await screen.findByText("refused: Ann has control of the microscope")).toBeTruthy();
  });

  it("shows a non-remote 403 (a viewer's scan) as that action's reason", async () => {
    setup({ commands: () => ({ status: 403, body: { detail: { code: "role", message: "Needs the operator role" } } }) });
    await waitFor(() => expect(isDisabled(button("Scan hardware"))).toBe(false));
    fireEvent.click(button("Scan hardware"));
    const scan = within(screen.getByRole("region", { name: "Scan" }));
    expect(await scan.findByText("refused: Needs the operator role")).toBeTruthy();
  });

  // T-010 stage 4: only a 403 marked remote_view (T-009b) sets read-only.
  it("leaves the rest of the screen writable after a non-remote 403 (T-010 stage 4)", async () => {
    setup({ commands: () => ({ status: 403, body: { detail: { code: "not_operator", message: "Needs the operator role" } } }) });
    await waitFor(() => expect(isDisabled(button("Scan hardware"))).toBe(false));
    fireEvent.click(button("Scan hardware"));
    await screen.findByText(/refused:/);
    expect(screen.queryAllByText("Read-only: remote view")).toHaveLength(0);
    expect(isDisabled(button("Show objective / Z / PFS"))).toBe(false);
  });

  it("puts the selected gate and its reasons in the screen context", async () => {
    setup();
    const table = within(await screen.findByRole("region", { name: "Gates" }));
    fireEvent.click(await table.findByText("sample_map"));
    const ctx = JSON.parse(screen.getByTestId("ctx").textContent ?? "{}");
    expect(ctx).toEqual({
      area: "hardware",
      gate: "sample_map",
      gate_reasons: ["xy_stage detected but its state did not read back"],
    });
  });

  it("lists a long change set short, with show all", async () => {
    const changed = Array.from({ length: 12 }, (_, i) => ({ key: `device.D${i}.read_back`, before: true, after: false }));
    setup({ profile: { ...PROFILE, previous: { ...PROFILE.previous!, changed } } });
    const summary = within(await screen.findByRole("region", { name: "Detection summary" }));
    const text = await summary.findByText(/changed \(12\):/);
    expect(text.textContent).toContain("device.D7.read_back, …");
    expect(text.textContent).not.toContain("device.D8.read_back");
    fireEvent.click(summary.getByRole("button", { name: "show all 12" }));
    expect(summary.getByText(/changed \(12\):/).textContent).toContain("device.D11.read_back");
    fireEvent.click(summary.getByRole("button", { name: "show fewer" }));
    expect(summary.getByText(/changed \(12\):/).textContent).not.toContain("device.D11.read_back");
  });

  describe("configured hardware", () => {
    const tree = async () => within(await screen.findByRole("list", { name: "Config devices" }));
    const SCANNED: HardwareProfileOut = {
      ...PROFILE,
      profile: { ...PROFILE.profile!, config: { path: "C:/mm/bench.cfg", sha256: "cd".repeat(32) } },
    };

    it("lists the config's devices under their hubs, with the scan's state", async () => {
      setup({ profile: SCANNED });
      const t = await tree();
      // Ti2-E__0 has a problem below it (XYStage reads nothing back), so it starts open
      expect(await t.findByRole("button", { name: "Collapse Ti2-E__0" })).toBeTruthy();
      const xy = t.getByRole("button", { name: "XYStage" }).closest(".hw-cfg-row")!;
      expect(xy.textContent).toContain("Loaded, read failed");
      const z = t.getByRole("button", { name: "ZDrive" }).closest(".hw-cfg-row")!;
      expect(z.textContent).toContain("Connected");
      const hub = t.getByRole("button", { name: "Ti2-E__0" }).closest(".hw-cfg-row")!;
      expect(hub.textContent).toContain("Not loaded");
      expect(hub.textContent).toContain("2 parts · 1 with problems");
      const summary = screen.getByLabelText("Connection summary").textContent ?? "";
      expect(summary).toContain("8 devices · 2 connected");
      expect(summary).toContain("1 read failed");
      expect(summary).toContain("5 not loaded");
    });

    it("expands a closed hub on request and shows a device's details", async () => {
      setup({ profile: SCANNED });
      const t = await tree();
      // COM10 has one dependent: shown directly, no fold
      expect(await t.findByRole("button", { name: "CSUW1-Hub" })).toBeTruthy();
      expect(t.queryByRole("button", { name: /(Expand|Collapse) COM10/ })).toBeNull();
      expect(t.getByRole("button", { name: "COM10" }).closest(".hw-cfg-row")!.textContent).not.toContain("part");
      // CSUW1-Port is "not loaded", so CSUW1-Hub starts open; close and reopen it
      fireEvent.click(t.getByRole("button", { name: "Collapse CSUW1-Hub" }));
      expect(t.queryByRole("button", { name: "CSUW1-Port" })).toBeNull();
      fireEvent.click(t.getByRole("button", { name: "Expand CSUW1-Hub" }));
      fireEvent.click(t.getByRole("button", { name: "CSUW1-Port" }));
      const node = t.getByRole("button", { name: "CSUW1-Port" }).closest("li")!;
      expect(node.textContent).toContain("0: blue_only · 1: blue_red · 2: red_only");
      expect(node.textContent).toContain("inferred");
      await waitFor(() => expect(screen.getByTestId("ctx").textContent).toContain("CSUW1-Port"));
    });

    it("says nothing was checked before the first scan, and the check runs the scan", async () => {
      const s = setup({ profile: { profile: null, path: null, sha256: null } });
      const t = await tree();
      expect(t.getAllByText("Not checked")).toHaveLength(4); // 3 roots + COM10's single dependent; with no problems known, hubs start closed
      expect(screen.getByText(/Not checked yet/)).toBeTruthy();
      const check = button("Check connections");
      await waitFor(() => expect(isDisabled(check)).toBe(false));
      fireEvent.click(check);
      await waitFor(() => expect(s.sent()).toHaveLength(1));
      expect(s.sent()[0]).toMatchObject({ kind: "start", op: "hardware_scan", args: { include_properties: true } });
    });

    it("warns when the scan loaded another config", async () => {
      setup(); // PROFILE has no config path
      await tree();
      expect(screen.getByText(/The last scan loaded a different config/)).toBeTruthy();
    });

    it("reads another config when one is picked", async () => {
      const s = setup({ profile: SCANNED });
      await tree();
      fireEvent.change(screen.getByLabelText("Config file"), { target: { value: CONFIG.available![1].path } });
      expect(await screen.findByRole("button", { name: "NIDAQHub" })).toBeTruthy();
      expect(s.calls.some((c) => c.path === PATHS.config(CONFIG.available![1].path))).toBe(true);
    });
  });

  describe("find or make a config", () => {
    const panel = async () => within(await screen.findByRole("region", { name: "Find or make a config" }));

    it("finds the matching config and shows one on request", async () => {
      const s = setup();
      const p = await panel();
      const find = p.getByRole("button", { name: "Find matching config" });
      await waitFor(() => expect(isDisabled(find)).toBe(false));
      fireEvent.click(find);
      expect((await p.findByLabelText("Match verdict")).textContent).toContain("Exact match: bench.cfg");
      const rows = within(p.getByRole("table", { name: "Config matches" })).getAllByRole("row").slice(1);
      expect(rows[1].textContent).toContain("30%");
      expect(rows[1].textContent).toContain("COM10, CSUW1-Hub");
      fireEvent.click(within(rows[1]).getByRole("button", { name: "Show" }));
      await waitFor(() => expect(s.calls.some((c) => c.path === PATHS.config(CONFIG.available![1].path))).toBe(true));
    });

    it("drafts a config from the scan and saves it as a new file", async () => {
      const s = setup();
      const p = await panel();
      fireEvent.click(p.getByRole("button", { name: "Draft config from scan" }));
      expect((await p.findByLabelText("Draft text")).textContent).toContain("Device,ZDrive,NikonTi2,ZDrive");
      const notes = p.getByLabelText("Config draft").textContent ?? "";
      expect(notes).toContain("The bench (mm-real) load check passes");
      expect(notes).toContain("Ti2-E__0: Nosepiece");
      expect((p.getByLabelText("File name") as HTMLInputElement).value).toBe("from-scan-202610011800");
      fireEvent.change(p.getByLabelText("File name"), { target: { value: "mine" } });
      fireEvent.click(p.getByRole("button", { name: "Save as new file" }));
      expect((await p.findByLabelText("Saved")).textContent).toContain("C:/settings/micromanager/mine.cfg");
      const post = s.calls.find((c) => c.path === PATHS.configDraft() && c.init?.method === "POST");
      expect(JSON.parse(String(post?.init?.body))).toEqual({ name: "mine", base: null, no_base: false });
      // the saved file is shown in the tree
      await waitFor(() => expect(s.calls.some((c) => c.path === PATHS.config("C:/settings/micromanager/mine.cfg"))).toBe(true));
    });

    it("shows why a save was refused", async () => {
      setup({ saveDraft: () => ({ status: 409, body: { detail: { code: "exists", message: "mine.cfg already exists; pick another name" } } }) });
      const p = await panel();
      fireEvent.click(p.getByRole("button", { name: "Draft config from scan" }));
      await p.findByLabelText("Draft text");
      fireEvent.click(p.getByRole("button", { name: "Save as new file" }));
      expect(await p.findByText(/not saved: .*already exists/)).toBeTruthy();
    });

    it("waits for a scan", async () => {
      setup({ profile: { profile: null, path: null, sha256: null } });
      const p = await panel();
      expect(isDisabled(p.getByRole("button", { name: "Find matching config" }))).toBe(true);
      expect(isDisabled(p.getByRole("button", { name: "Draft config from scan" }))).toBe(true);
      expect(p.getByText(/Scan first/)).toBeTruthy();
    });
  });
});
