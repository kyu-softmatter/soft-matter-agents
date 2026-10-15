import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Client, ClientProvider, type Transport } from "../../app/client";
import { ScreenContextProvider } from "../../app/screenContext";
import { fakeTransport, type Route } from "../../test/fakes";
import {
  type Focus100xDefaults,
  type LensRow,
  type ObjectivePlan,
  type ObjectiveState,
  PATHS,
  type Permissions,
  SCREEN_OPS,
} from "./api";
import ObjectiveScreen from "./index";

// ---------- a fake engine world behind the shell's client ----------

const LENSES: LensRow[] = [
  { nosepiece_state: 0, label: "1-Plan Apo LmbdD20 4x", registry_key: "4x", magnification: 4, na: 0.2,
    immersion: "dry", working_distance_um: 20000, selectable: false, disabled_reason: "already on that objective" },
  { nosepiece_state: 3, label: "4-Plan Apo 40x WI", registry_key: "40x-WI", magnification: 40, na: 1.15,
    immersion: "water", working_distance_um: null, selectable: false, disabled_reason: "no working distance value" },
  { nosepiece_state: 5, label: "6-Plan Apo LmbdD0.13 100x Oil", registry_key: "100x-Oil", magnification: 100,
    na: 1.45, immersion: "oil", working_distance_um: 130, selectable: true, disabled_reason: null },
];

const STATE: ObjectiveState = {
  nosepiece_state: 0,
  label: "1-Plan Apo LmbdD20 4x",
  pixel_um: 1.625,
  z_um: 3048.7,
  pfs: { enabled: false, locked: false, in_range: "Out of Range" },
  immersion_loaded_this_session: null,
  awaiting_return: null,
  running: null,
};

interface Opts {
  hostname?: string;
  lenses?: LensRow[];
  z4x?: number | null;
  /** answer for /api/permissions; default all allowed */
  permissions?: Route;
  /** /api/permissions never answers */
  permissionsPending?: boolean;
  escapeRefusal?: string;
  commands?: Route;
}

function plan(lenses: LensRow[], target: number, escape: boolean, refusal?: string): ObjectivePlan {
  const lens = lenses.find((l) => l.nosepiece_state === target);
  return {
    steps: [
      { step: 1, name: "Record XY, Z, objective; lights off", target: "" },
      { step: 2, name: "PFS off, retract Z", target: "Z -> 0 µm" },
      ...(escape ? [{ step: 3, name: "Step out in Y", target: "Y -> y + 15000 µm" }] : []),
      { step: 4, name: "Rotate", target: lens?.label ?? "" },
      { step: 5, name: "Load immersion", target: lens?.immersion ?? "" },
      ...(escape ? [{ step: 6, name: "Return XY", target: "XY -> start" }] : []),
      { step: 7, name: "Approach Z", target: "Z -> 2800 µm" },
    ],
    escape: { allowed: refusal === undefined, reason: refusal ?? null, sign: "+Y", dy_um: 15000,
      mark: "unmeasured provisional", default: (lens?.immersion ?? "dry") !== "dry" },
    immersion: lens?.immersion ?? "dry",
    approach_target_um: 2800,
    approach_step_um: 10,
    approach_step_mark: "unmeasured provisional",
    refusal: lens?.disabled_reason ?? null,
  };
}

function focusDefaults(z4x: number | null, centre?: number): Focus100xDefaults {
  const c = centre ?? (z4x === null ? null : z4x - 60);
  return { z_4x_focus_um: z4x, lab_offset_um: -60, centre_um: c, half_um: 40, step_um: 2, fine_half_um: 3,
    fine_step_um: 0.2, exposure_ms: 20, metric: "peak", ceiling_um: c === null ? null : Math.min(3200, c + 52),
    above_4x_focus: c !== null && z4x !== null && c > z4x, immersion_loaded_this_session: false };
}

const ALLOWED: Permissions = Object.fromEntries(SCREEN_OPS.map((op) => [op, { allowed: true, reason: null }]));

type Ev = { kind: string; op_id: string; data: Record<string, unknown> };

/** The screen on the shell's client over a fake transport: no network, no socket, no window. */
function setup(o: Opts = {}) {
  const lenses = o.lenses ?? LENSES;
  const z4x = o.z4x === undefined ? 3048.7 : o.z4x;
  const sent: Record<string, unknown>[] = [];
  const fixed: Record<string, Route> = {
    [PATHS.state]: () => ({ status: 200, body: STATE }),
    [PATHS.lenses]: () => ({ status: 200, body: lenses }),
    [PATHS.permissions(SCREEN_OPS)]: o.permissions ?? (() => ({ status: 200, body: ALLOWED })),
    [PATHS.focusDefaults()]: () => ({ status: 200, body: focusDefaults(z4x) }),
    "/api/commands": (init) => {
      sent.push(JSON.parse(String(init?.body)) as Record<string, unknown>);
      return o.commands ? o.commands(init) : { status: 200, body: { op_id: "op-1" } };
    },
  };
  const t = fakeTransport(fixed);
  // query-string paths (plan, focus defaults for a typed centre) are answered here: the shared
  // fakeTransport looks paths up in a plain table, so they cannot be routes there
  const dynamic = (path: string): Route | undefined => {
    const u = new URL(path, "http://x");
    if (u.pathname === "/api/objective/plan") {
      return () => ({ status: 200, body: plan(lenses, Number(u.searchParams.get("target_state")),
        u.searchParams.get("escape") === "true", o.escapeRefusal) });
    }
    if (u.pathname === "/api/objective/focus100x/defaults" && u.searchParams.has("centre_um")) {
      return () => ({ status: 200, body: focusDefaults(z4x, Number(u.searchParams.get("centre_um"))) });
    }
    return undefined;
  };
  const transport: Transport = {
    ...t.transport,
    fetch: async (path, init) => {
      if (o.permissionsPending && path.startsWith("/api/permissions")) return new Promise<Response>(() => {});
      const route = dynamic(path);
      if (route === undefined) return t.transport.fetch(path, init);
      t.calls.push({ path, init });
      const { status, body } = route(init);
      return new Response(body === undefined ? null : JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    },
  };
  const client = new Client(transport, o.hostname ?? "127.0.0.1");
  render(
    <ClientProvider client={client}>
      <ScreenContextProvider area="objective">
        <ObjectiveScreen />
      </ScreenContextProvider>
    </ClientProvider>,
  );
  const socket = () => t.sockets[t.sockets.length - 1];
  const emit = (evs: Ev[]) =>
    act(() => {
      for (const e of evs) socket().event(e.kind, e.data, e.op_id);
    });
  return { sent, socket, sockets: t.sockets, emit, calls: t.calls };
}

async function ready(o: Opts = {}) {
  const w = setup(o);
  act(() => w.socket().open());
  await screen.findByTestId("current-label");
  return w;
}

// ---------- scripted engine events (a 4x -> 100x Oil change, ops-spec 4.2) ----------

function toLoading(opId: string, escape = true): Ev[] {
  return [
    { kind: "started", op_id: opId, data: { op: "objective_change",
      start_state: { return_xy: [8026.0, 571.6], z_before: 3048.7, objective_before: "1-Plan Apo LmbdD20 4x" } } },
    { kind: "progress", op_id: opId, data: { step: 1, detail: "recorded" } },
    // the one light shape the shell reads (T-010-6)
    { kind: "light_changed", op_id: opId, data: { dialamp: { state: 0, intensity: 608 }, aura: { state: 0, lines: {} }, verified: true, records: [] } },
    { kind: "progress", op_id: opId, data: { step: 2, axis: "z", commanded: 0, readback: 0.0, pfs_in_range: "Out of Range" } },
    { kind: "position", op_id: opId, data: { z_um: 0.0, x_um: 8026.0, y_um: 571.6 } },
    ...(escape ? [{ kind: "progress", op_id: opId, data: { step: 3, axis: "y", commanded: 15571.6, readback: 15571.6 } }] : []),
    { kind: "progress", op_id: opId, data: { step: 4, axis: "nosepiece", commanded: 5, label_read: "6-Plan Apo LmbdD0.13 100x Oil" } },
    { kind: "confirm_required", op_id: opId, data: { key: "load_immersion", kind: "manual_step",
      prompt: "Load oil on 6-Plan Apo LmbdD0.13 100x Oil, then press Loading done", options: ["done"], context: { immersion: "oil" } } },
  ];
}

function afterLoading(opId: string, nSteps = 3, escape = true): Ev[] {
  const evs: Ev[] = [{ kind: "confirmed", op_id: opId, data: { key: "load_immersion", by: "operator@example.test", at: "17:50" } }];
  if (escape) evs.push({ kind: "progress", op_id: opId, data: { step: 6, axis: "xy", commanded: "8026.0, 571.6", readback: "8026.0, 571.6" } });
  for (let i = 1; i <= nSteps; i += 1) {
    const z = (2800 * i) / nSteps;
    evs.push({ kind: "progress", op_id: opId, data: { step: 7, z_um: z, target_um: 2800, step_index: i, n_steps: nSteps } });
    evs.push({ kind: "position", op_id: opId, data: { z_um: z } });
  }
  evs.push({ kind: "finished", op_id: opId, data: { state: "done", end_state: { lights: { dialamp: { state: 0, intensity: 608 }, aura: { state: 0, lines: {} }, verified: true, records: [] } } } });
  return evs;
}

// ---------- tests ----------

describe("objective change", () => {
  it("rotates with the +Y step-out and drives the seven steps from events", async () => {
    const w = await ready();
    await screen.findByLabelText("Plan");
    await waitFor(() => expect(screen.getByRole("button", { name: "Rotate" })).toHaveProperty("disabled", false));
    fireEvent.click(screen.getByRole("button", { name: "Rotate" }));
    await waitFor(() => expect(w.sent).toHaveLength(1));
    expect(w.sent[0]).toMatchObject({ kind: "start", op: "objective_change",
      args: { target_state: 5, escape: true } });

    w.emit(toLoading("op-1"));
    expect(screen.getByTestId("step-1").dataset.status).toBe("done");
    expect(screen.getByTestId("step-2").textContent).toContain("read 0.0");
    expect(screen.getByTestId("step-2").textContent).toContain("PFS Out of Range");
    expect(screen.getByTestId("step-3").textContent).toContain("read 15571.6");
    expect(screen.getByTestId("step-4").textContent).toContain("6-Plan Apo LmbdD0.13 100x Oil");
    expect(screen.getByTestId("step-5").dataset.status).toBe("running");

    const card = screen.getByRole("dialog", { name: "Load immersion" });
    fireEvent.click(await within(card).findByRole("button", { name: "Loading done" }));
    await waitFor(() => expect(w.sent).toHaveLength(2));
    expect(w.sent[1]).toMatchObject({ kind: "confirm", op_id: "op-1", args: { key: "load_immersion", ok: true } });

    w.emit(afterLoading("op-1", 3));
    expect(screen.queryByRole("dialog", { name: "Load immersion" })).toBeNull();
    expect(screen.getByTestId("step-5").textContent).toContain("operator@example.test");
    expect(screen.getByTestId("step-6").dataset.status).toBe("done");
    expect(screen.getByTestId("change-ended").textContent).toBe("Done");
  });

  it("moves the Z approach bar one event at a time, never jumping to the target", async () => {
    const w = await ready();
    w.emit(toLoading("op-9", false));
    const after = afterLoading("op-9", 4, false);
    const bar = () => screen.getByLabelText("Z approach").querySelector("progress") as HTMLProgressElement;
    w.emit(after.slice(0, 3)); // confirmed, first progress, first position
    expect(bar().value).toBe(1);
    expect(screen.getByLabelText("Z approach").textContent).toContain("Z 700.00 µm");
    w.emit(after.slice(3, 5));
    expect(bar().value).toBe(2);
    expect(screen.getByLabelText("Z approach").textContent).toContain("Z 1400.00 µm");
  });

  it("shows the return action after an interrupted change and sends resume", async () => {
    const w = await ready();
    await screen.findByLabelText("Plan");
    w.emit(toLoading("op-2"));
    w.emit([{ kind: "aborted", op_id: "op-2", data: { state: "awaiting_return", why: "stopped by the operator" } }]);
    expect(screen.getByTestId("step-5").dataset.status).toBe("failed");
    const banner = screen.getByRole("alert", { name: "Awaiting return" });
    expect(screen.getByRole("button", { name: "Rotate" })).toHaveProperty("disabled", true);
    const back = within(banner).getByRole("button", { name: "Return to sample position" });
    await waitFor(() => expect(back).toHaveProperty("disabled", false));
    fireEvent.click(back);
    await waitFor(() => expect(w.sent.at(-1)).toMatchObject({ kind: "start", op: "objective_change", args: { resume: true } }));
  });

  it("shows the step-out read-only with its provisional mark, and each lens reason", async () => {
    await ready();
    await screen.findByLabelText("Plan");
    const esc = screen.getByTestId("escape");
    expect(esc.textContent).toContain("Step out +Y 15 mm");
    expect(esc.textContent).toContain("unmeasured provisional");
    expect(within(esc).queryByRole("textbox")).toBeNull(); // never typed
    expect(screen.getByRole("checkbox")).toHaveProperty("checked", true);
    expect(screen.queryByTestId("escape-reason")).toBeNull();
    expect(screen.getByLabelText(/40x WI/)).toHaveProperty("disabled", true);
    expect(screen.getByText("no working distance value")).toBeTruthy();
    expect(screen.getByText("already on that objective")).toBeTruthy();
    expect(screen.getAllByText(/unmeasured provisional/)).toHaveLength(2); // step-out and approach step
  });

  it("shows the engine's refusal of the step-out and rotates without it", async () => {
    const w = await ready({ escapeRefusal: "Y step-out exceeds the stage Y limit" });
    await waitFor(() => expect(screen.getByTestId("escape-reason").textContent).toContain("Y step-out exceeds the stage Y limit"));
    expect(screen.getByRole("checkbox")).toHaveProperty("disabled", true);
    expect(screen.getByRole("checkbox")).toHaveProperty("checked", false);
    await waitFor(() => expect(screen.getByRole("button", { name: "Rotate" })).toHaveProperty("disabled", false));
    fireEvent.click(screen.getByRole("button", { name: "Rotate" }));
    await waitFor(() => expect(w.sent).toHaveLength(1));
    expect(w.sent[0].args).toEqual({ target_state: 5, escape: false });
  });

  it("defaults the step-out off between dry lenses and on for an immersion lens", async () => {
    const dry10x: LensRow = { nosepiece_state: 1, label: "2-Plan Apo 10x", registry_key: "10x", magnification: 10,
      na: 0.45, immersion: "dry", working_distance_um: 4000, selectable: true, disabled_reason: null };
    const w = await ready({ lenses: [LENSES[0], dry10x, LENSES[2]] });
    await screen.findByLabelText("Plan");
    expect(screen.getByRole("checkbox")).toHaveProperty("checked", false); // 4x -> 10x, both dry
    fireEvent.click(screen.getByLabelText(/100x Oil/));
    await waitFor(() => expect(screen.getByRole("checkbox")).toHaveProperty("checked", true));
    fireEvent.click(screen.getByLabelText(/10x \(dry/));
    await waitFor(() => expect(screen.getByRole("checkbox")).toHaveProperty("checked", false));
    await waitFor(() => expect(screen.getByRole("button", { name: "Rotate" })).toHaveProperty("disabled", false));
    fireEvent.click(screen.getByRole("button", { name: "Rotate" }));
    await waitFor(() => expect(w.sent).toHaveLength(1));
    expect(w.sent[0].args).toEqual({ target_state: 1, escape: false });
  });

  it("is read-only in remote view: no commands, and Loading done is never offered", async () => {
    const w = await ready({ hostname: "microscope-pc.lab" });
    await screen.findByLabelText("Plan");
    expect(screen.getAllByText(/Read-only: remote view/).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Rotate" })).toHaveProperty("disabled", true);
    w.emit(toLoading("op-3"));
    expect(screen.queryByRole("button", { name: "Loading done" })).toBeNull();
    expect(screen.getByText(/Waiting for the operator at the microscope PC/)).toBeTruthy();
    expect(w.sent).toHaveLength(0);
  });

  it("goes read-only on a 403 marked remote_view", async () => {
    // T-009b marks the remote refusal with detail.code "remote_view" (and a header)
    const w = await ready({ commands: () => ({ status: 403, body: { detail: { code: "remote_view", message: "remote view" } } }) });
    await waitFor(() => expect(screen.getByRole("button", { name: "Rotate" })).toHaveProperty("disabled", false));
    fireEvent.click(screen.getByRole("button", { name: "Rotate" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Rotate" })).toHaveProperty("disabled", true));
    w.emit(toLoading("op-4"));
    expect(screen.queryByRole("button", { name: "Loading done" })).toBeNull();
  });

  it("shows a plain 403 next to the action that caused it", async () => {
    await ready({ commands: () => ({ status: 403, body: { detail: "Open an experiment session first" } }) });
    await waitFor(() => expect(screen.getByRole("button", { name: "Rotate" })).toHaveProperty("disabled", false));
    fireEvent.click(screen.getByRole("button", { name: "Rotate" }));
    const panel = screen.getByRole("region", { name: "Change objective" });
    await waitFor(() => expect(within(panel).getByRole("alert").textContent).toContain("Open an experiment session first"));
    // the reason belongs to Rotate only: the 100x panel shows no refusal
    expect(within(screen.getByRole("region", { name: "100x focus" })).queryByRole("alert")).toBeNull();
  });

  it("keeps the app writable after a plain 403 (only remote_view switches to read-only)", async () => {
    await ready({ commands: () => ({ status: 403, body: { detail: "Open an experiment session first" } }) });
    await waitFor(() => expect(screen.getByRole("button", { name: "Rotate" })).toHaveProperty("disabled", false));
    fireEvent.click(screen.getByRole("button", { name: "Rotate" }));
    await screen.findByText(/Open an experiment session first/);
    expect(screen.getByRole("button", { name: "Rotate" })).toHaveProperty("disabled", false);
    expect(screen.queryByText(/Read-only/)).toBeNull();
  });

  it("says Checking permissions… while the first check loads", async () => {
    await ready({ permissionsPending: true });
    await screen.findByLabelText("Plan");
    expect(screen.getAllByText("Checking permissions…").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Rotate" })).toHaveProperty("disabled", true);
  });

  it("disables every control when the permission check cannot be read, but keeps progress", async () => {
    const w = await ready({ permissions: () => ({ status: 500, body: { detail: "boom" } }) });
    await waitFor(() => expect(screen.getAllByText("Permission check unavailable").length).toBeGreaterThan(0));
    expect(screen.getByRole("button", { name: "Rotate" })).toHaveProperty("disabled", true);
    expect(screen.getByRole("button", { name: "Re-load immersion" })).toHaveProperty("disabled", true);
    expect(await screen.findByRole("button", { name: "Find 100x focus" })).toHaveProperty("disabled", true);
    w.emit(toLoading("op-7"));
    expect(screen.getByTestId("step-2").dataset.status).toBe("done"); // progress still shown
    expect(screen.queryByRole("button", { name: "Loading done" })).toBeNull();
    expect(within(screen.getByRole("dialog", { name: "Load immersion" })).getByText(/Permission check unavailable/)).toBeTruthy();
    expect(w.sent).toHaveLength(0);
  });

  it("counts an op missing from the permissions answer as unavailable", async () => {
    const partial: Permissions = { focus_100x: { allowed: true, reason: null }, confirm: { allowed: true, reason: null } };
    await ready({ permissions: () => ({ status: 200, body: partial }) });
    await screen.findByLabelText("Plan");
    await waitFor(() => expect(screen.getAllByText("Permission check unavailable").length).toBeGreaterThan(0));
    expect(screen.getByRole("button", { name: "Rotate" })).toHaveProperty("disabled", true);
    await waitFor(() => expect(screen.getByRole("button", { name: "Find 100x focus" })).toHaveProperty("disabled", false));
  });

  it("re-reads its state when the event socket reconnects", async () => {
    const w = await ready();
    const reads = () => w.calls.filter((c) => c.path === PATHS.state).length;
    await waitFor(() => expect(reads()).toBeGreaterThanOrEqual(1));
    const before = reads();
    act(() => w.socket().close());
    // the shell reconnects with backoff (500 ms first); events in the gap are lost
    await waitFor(() => expect(w.sockets).toHaveLength(2), { timeout: 2000 });
    act(() => w.socket().open());
    await waitFor(() => expect(reads()).toBeGreaterThan(before));
  });
});

describe("100x focus", () => {
  it("shows the centre as not set without a 4x focus plane", async () => {
    await ready({ z4x: null });
    const centre = (await screen.findByLabelText("Centre")) as HTMLInputElement;
    expect(centre.value).toBe("");
    expect(centre.placeholder).toBe("not set");
    await waitFor(() => expect(screen.getByText("Enter the sweep centre")).toBeTruthy());
    expect(screen.getByRole("button", { name: "Find 100x focus" })).toHaveProperty("disabled", true);
  });

  it("fills the centre from the 4x plane, shows the ceiling, and draws the sweep and result", async () => {
    const w = await ready();
    const centre = (await screen.findByLabelText("Centre")) as HTMLInputElement;
    expect(Number(centre.value)).toBeCloseTo(2988.7, 6);
    await waitFor(() => expect(screen.getByTestId("ceiling").textContent).toContain("3040.7"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Find 100x focus" })).toHaveProperty("disabled", false));
    fireEvent.click(screen.getByRole("button", { name: "Find 100x focus" }));
    await waitFor(() => expect(w.sent).toHaveLength(1));
    expect(w.sent[0].op).toBe("focus_100x");
    expect((w.sent[0].args as Record<string, number>).centre_um).toBeCloseTo(2988.7, 6);

    w.emit([
      { kind: "started", op_id: "op-5", data: { op: "focus_100x" } },
      { kind: "planned", op_id: "op-5", data: { ceiling_um: 3040.7 } },
      { kind: "progress", op_id: "op-5", data: { phase: "coarse", z_readback_um: 2949.0, score: 10, sat: 0 } },
      { kind: "progress", op_id: "op-5", data: { phase: "coarse", z_readback_um: 2989.0, score: 90, sat: 0.01 } },
      { kind: "progress", op_id: "op-5", data: { phase: "coarse", z_readback_um: 3027.0, score: 12, sat: 0 } },
      { kind: "reading", op_id: "op-5", data: { source: "classical", verdict: "in_focus", z_encoder_um: 2989.42,
        warnings: ["reduce exposure"] } },
    ]);
    expect(screen.getByTestId("ceiling-line")).toBeTruthy();
    expect(document.querySelectorAll('circle[data-saturated="true"]')).toHaveLength(1);
    const result = screen.getByTestId("focus-result");
    expect(result.querySelector('[data-source="computed"]')).toBeTruthy();
    expect(result.textContent).toContain("Z 2989.42 µm");
    expect(result.textContent).toContain("reduce exposure");
  });

  it("shows the top-end extension only as the engine's confirm", async () => {
    const w = await ready();
    await screen.findByLabelText("Centre");
    w.emit([
      { kind: "started", op_id: "op-6", data: { op: "focus_100x" } },
      { kind: "confirm_required", op_id: "op-6", data: { key: "extend_upward", kind: "confirm",
        prompt: "peak at the top end of 2949-3029; extend upward to 3040?", options: ["Extend upward", "Stop"] } },
    ]);
    const box = await screen.findByRole("dialog", { name: "Confirm" });
    fireEvent.click(within(box).getByRole("button", { name: "Extend upward" }));
    await waitFor(() => expect(w.sent.at(-1)).toMatchObject({ kind: "confirm", op_id: "op-6", args: { key: "extend_upward", ok: true } }));
  });
});
