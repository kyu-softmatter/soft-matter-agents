import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Permissions } from "./api";
import { fixture, SAMPLE, type FakeData } from "./fixture";
import { mountMap, type World } from "./testWorld";

async function mount(over: Partial<FakeData> = {}, opts: Parameters<typeof mountMap>[1] = {}): Promise<World> {
  const w = await mountMap(over, opts);
  await screen.findByText(`Sample map · ${SAMPLE}`);
  await screen.findByTestId("hole-fit");
  return w;
}

const deny = (reason: string, ops: string[]): Permissions =>
  Object.fromEntries(ops.map((op) => [op, { allowed: false, reason }]));
const RECORD_OPS = ["map_flag", "map_flag_retire", "candidate_confirm", "candidate_reject"];

const last = (w: World) => w.sent[w.sent.length - 1];
const opOrKind = (w: World) => w.sent.map((s) => (s.body.op as string) || (s.body.kind as string));

describe("map screen", () => {
  it("shows this session's hole fit and enables the scan step", async () => {
    await mount();
    expect(screen.getByTestId("hole-fit").textContent).toMatch(/^Hole fit \d\d:\d\d \(this session\)$/);
    await waitFor(() => expect(screen.getByRole("button", { name: "Start scan" })).toHaveProperty("disabled", false));
    expect(screen.getByTestId("map-scale").textContent).toContain("+stage x ←  +y ↓");
  });

  it("warns about a fit from an earlier session and keeps the scan off", async () => {
    const base = fixture().maps[SAMPLE];
    await mount({ maps: { [SAMPLE]: { ...base, session_started_at: (base.hole!.fitted_at ?? 0) + 3600 } } });
    expect(screen.getByTestId("hole-fit").textContent).toMatch(/previous session: re-trace before scanning$/);
    expect(screen.getByRole("button", { name: "Start scan" })).toHaveProperty("disabled", true);
    await within(screen.getByRole("region", { name: "Scan" })).findByText("Trace the hole edge in brightfield first");
  });

  it("is read-only on a remote page (the shell's flag): map shown, every control off", async () => {
    const w = await mount({}, { hostname: "lab-pc-2" });
    expect(screen.getByTestId("move-reason").textContent).toBe("Click-to-move: Read-only: remote view");
    for (const name of ["Start tracing", "Start scan", "Confirm", "Retire", "Flag current position"]) {
      for (const b of screen.getAllByRole("button", { name })) expect(b).toHaveProperty("disabled", true);
    }
    expect(screen.getByRole("checkbox", { name: "Mosaic" })).toHaveProperty("disabled", false);
    fireEvent.click(screen.getByTestId("map-canvas"), { clientX: 200, clientY: 200 });
    expect(w.sent).toEqual([]);
  });

  it("keeps flag and candidate writes off for a viewer (D16) but leaves the map", async () => {
    await mount({ permissions: deny("Needs the operator role on the microscope PC", RECORD_OPS) });
    await within(screen.getByRole("region", { name: "Flags" })).findByText("Needs the operator role on the microscope PC");
    expect(screen.queryByTestId("move-reason")).toBeNull();
    for (const b of screen.getAllByRole("button", { name: "Confirm" })) expect(b).toHaveProperty("disabled", true);
    expect(screen.getByRole("checkbox", { name: "Mosaic" })).toHaveProperty("disabled", false);
  });

  it("shows a viewer's D16 403 next to the flag action without locking the screen", async () => {
    const w = await mount(
      {},
      {
        postAnswer: (path) =>
          path.endsWith("/flags")
            ? { status: 403, body: { detail: { code: "forbidden", message: "Needs the operator role on the microscope PC" } } }
            : null,
      },
    );
    const panel = screen.getByRole("region", { name: "Flags" });
    await waitFor(() => expect(within(panel).getByLabelText("Flag name")).toHaveProperty("disabled", false));
    fireEvent.change(within(panel).getByLabelText("Flag name"), { target: { value: "edge" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Flag current position" }));
    await within(panel).findByText("Needs the operator role on the microscope PC");
    // no global read-only: other actions stay on, the map still takes clicks
    expect(screen.queryByTestId("move-reason")).toBeNull();
    expect(screen.getByRole("button", { name: "Start tracing" })).toHaveProperty("disabled", false);
    fireEvent.click(screen.getByTestId("map-canvas"), { clientX: 200, clientY: 200 });
    await waitFor(() => expect(w.sent.map((s) => s.body.op)).toEqual(["goto_xy"]));
  });

  it("goes read-only only on a remote_view 403", async () => {
    await mount(
      {},
      {
        postAnswer: (path) =>
          path.endsWith("/flags") ? { status: 403, body: { detail: { code: "remote_view", message: "remote view" } } } : null,
      },
    );
    const panel = screen.getByRole("region", { name: "Flags" });
    await waitFor(() => expect(within(panel).getByLabelText("Flag name")).toHaveProperty("disabled", false));
    fireEvent.change(within(panel).getByLabelText("Flag name"), { target: { value: "edge" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Flag current position" }));
    await waitFor(() => expect(screen.getByTestId("move-reason").textContent).toBe("Click-to-move: Read-only: remote view"));
  });

  it("disables every control when the permission check cannot be read, map stays viewable", async () => {
    const w = await mount({ permissionsFail: true });
    await waitFor(() =>
      expect(screen.getByTestId("move-reason").textContent).toBe("Click-to-move: Permission check unavailable"),
    );
    for (const name of ["Start tracing", "Start scan", "Confirm", "Retire", "Mark edge here"]) {
      for (const b of screen.getAllByRole("button", { name })) expect(b).toHaveProperty("disabled", true);
    }
    within(screen.getByRole("region", { name: "Flags" })).getByText("Permission check unavailable");
    expect(screen.getByRole("checkbox", { name: "Mosaic" })).toHaveProperty("disabled", false);
    fireEvent.click(screen.getAllByRole("radio")[0]);
    expect(screen.getAllByRole("radio")[0]).toHaveProperty("checked", true);
    fireEvent.click(screen.getByTestId("map-canvas"), { clientX: 200, clientY: 200 });
    expect(w.sent).toEqual([]);
  });

  it("says Checking permissions… until the first answer, and treats a missing op as unavailable", async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((r) => (release = r));
    await mount({ permissionsOmit: ["map_flag"] }, { permissionsGate: gate });
    expect(screen.getByTestId("move-reason").textContent).toBe("Click-to-move: Checking permissions\u2026");
    await act(async () => release());
    await within(screen.getByRole("region", { name: "Flags" })).findByText("Permission check unavailable");
    await waitFor(() => expect(screen.queryByTestId("move-reason")).toBeNull());
  });

  it("shows the engine's reason on the scan step for a partial trace", async () => {
    await mount({ permissions: deny("partial trace: the hole fit is not a closed loop", ["scan_4x"]) });
    const seq = screen.getByRole("region", { name: "Sequence" });
    await within(seq).findByText("partial trace: the hole fit is not a closed loop");
    expect(screen.getByRole("button", { name: "Start scan" })).toHaveProperty("disabled", true);
  });

  it("lists candidates by source (computed / confirmed) and sends a decision to the map route", async () => {
    const w = await mount();
    const panel = screen.getByRole("region", { name: "Candidates" });
    await waitFor(() =>
      expect(within(panel).getAllByRole("listitem").map((li) => li.getAttribute("data-source"))).toEqual([
        "classical_candidate",
        "person_confirmed",
      ]),
    );
    within(panel).getByText(/candidate \(computed\)/);
    const confirm = within(panel).getByRole("button", { name: "Confirm" });
    await waitFor(() => expect(confirm).toHaveProperty("disabled", false));
    fireEvent.click(confirm);
    await waitFor(() => expect(last(w)?.route).toBe(`/api/map/${SAMPLE}/candidates/c1/confirm`));
  });

  it("adds a flag at the current position and edits a note as a new flag", async () => {
    const w = await mount();
    const panel = screen.getByRole("region", { name: "Flags" });
    await waitFor(() => expect(within(panel).getByLabelText("Flag name")).toHaveProperty("disabled", false));
    fireEvent.change(within(panel).getByLabelText("Flag name"), { target: { value: "edge" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Flag current position" }));
    await waitFor(() =>
      expect(last(w)).toEqual({
        route: `/api/map/${SAMPLE}/flags`,
        body: { x_um: 8026, y_um: 571.6, name: "edge", note: "" },
      }),
    );
    fireEvent.click(within(panel).getByRole("button", { name: "Edit note" }));
    fireEvent.change(within(panel).getByLabelText("New note"), { target: { value: "denser" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(last(w)?.body.replaces).toBe("f1"));
  });

  it("keeps a retired flag out of play until the toggle, then shows who retired it and when", async () => {
    await mount();
    const panel = screen.getByRole("region", { name: "Flags" });
    await within(panel).findByRole("button", { name: "good field" });
    expect(within(panel).queryByRole("button", { name: "old" })).toBeNull();
    fireEvent.click(screen.getByRole("checkbox", { name: "Show retired flags" }));
    await within(panel).findByRole("button", { name: "old" });
    expect(screen.getByTestId("retired-f0").textContent).toMatch(/retired by op@example\.test at \d\d:\d\d$/);
    const row = screen.getByTestId("retired-f0").closest("li") as HTMLElement;
    expect(within(row).queryByRole("button", { name: "Retire" })).toBeNull();
  });

  it("shows who decided a candidate and when", async () => {
    await mount();
    const panel = screen.getByRole("region", { name: "Candidates" });
    await waitFor(() => expect(panel.textContent).toMatch(/confirmed by op@example\.test at \d\d:\d\d/));
    fireEvent.click(screen.getByRole("checkbox", { name: "Show rejected candidates" }));
    await waitFor(() => expect(panel.textContent).toMatch(/rejected by op@example\.test at \d\d:\d\d/));
  });

  it("toggles layers and the hidden-by-default records", async () => {
    await mount();
    const mosaic = screen.getByRole("checkbox", { name: "Mosaic" });
    expect(mosaic).toHaveProperty("checked", true);
    fireEvent.click(mosaic);
    expect(mosaic).toHaveProperty("checked", false);
    fireEvent.click(screen.getByRole("checkbox", { name: "Show rejected candidates" }));
    await within(screen.getByRole("region", { name: "Candidates" })).findByText(/rejected/);
  });

  it("starts edge tracing with hole_diameter_mm and sends speed changes as update", async () => {
    const w = await mount();
    const panel = screen.getByRole("region", { name: "Edge trace" });
    const startBtn = within(panel).getByRole("button", { name: "Start tracing" });
    await waitFor(() => expect(startBtn).toHaveProperty("disabled", false));
    fireEvent.click(startBtn);
    await waitFor(() =>
      expect(last(w)).toMatchObject({
        route: "/api/commands",
        body: {
          kind: "start",
          op: "edge_trace",
          args: { sample_id: SAMPLE, speed_um_s: 100, hole_diameter_mm: 6.0, light: "bf" },
        },
      }),
    );
    await within(panel).findByRole("button", { name: "Stop" });
    fireEvent.click(within(panel).getByRole("button", { name: "+" }));
    await waitFor(() => expect(last(w)?.body).toMatchObject({ kind: "update", op_id: "op-1", args: { speed_um_s: 200 } }));
  });

  it("walks the click-to-move steps from scripted events and never raises Z", async () => {
    const w = await mount();
    await waitFor(() => expect(screen.queryByTestId("move-reason")).toBeNull());
    fireEvent.click(screen.getByTestId("map-canvas"), { clientX: 180, clientY: 220 });
    await waitFor(() => expect(w.sent.length).toBe(1));
    const sent = w.sent[0].body as { op: string; args: { x_um: number; y_um: number } };
    expect(sent.op).toBe("goto_xy");
    const op = "op-1";
    await w.emit("planned", { distance_um: 900, large_move: true, retract_needed: true, z_safe_um: 0 }, op);
    await w.emit("confirm_required", { key: "retract_then_move", z_um: 3048.7, z_safe_um: 0 }, op);
    const dialog = screen.getByRole("dialog", { name: "Retract Z" });
    expect(dialog.textContent).toContain("Z 3048.70 µm");
    expect(dialog.textContent).toContain("plan Z 0.0 µm");
    fireEvent.click(within(dialog).getByRole("button", { name: "Retract and move" }));
    await waitFor(() =>
      expect(last(w)?.body).toMatchObject({ kind: "confirm", op_id: op, args: { key: "retract_then_move", ok: true } }),
    );

    await w.emit("progress", { step: "retract" }, op);
    await w.emit("position", { x_um: 8026, y_um: 571.6, z_um: 0 });
    expect(screen.getByTestId("click-move").getAttribute("data-phase")).toBe("retracting");
    await w.emit("progress", { step: "move_xy" }, op);
    expect(screen.getByTestId("click-move").textContent).toMatch(/^Moving to \(/);
    await w.emit("finished", { x_um: sent.args.x_um, y_um: sent.args.y_um, z_um: 0, retracted: true }, op);

    const banner = screen.getByTestId("click-move");
    expect(banner.getAttribute("data-phase")).toBe("arrived");
    expect(banner.textContent).toContain("read back");
    expect(banner.textContent).toContain("Z left retracted at Z 0.00 µm: refocus with a scan tile or focus_100x");
    // only goto_xy and its confirm were sent: the screen does not move Z itself
    expect(opOrKind(w)).toEqual(["goto_xy", "confirm"]);
  });

  it("shows the engine's reason when the click is outside the scan box", async () => {
    const w = await mount();
    await waitFor(() => expect(screen.queryByTestId("move-reason")).toBeNull());
    fireEvent.click(screen.getByTestId("map-canvas"), { clientX: 0, clientY: 0 });
    await waitFor(() => expect(w.sent.length).toBe(1));
    await w.emit("preflight_failed", { why: "outside the scan box + 1 mm" }, "op-1");
    const banner = screen.getByTestId("click-move");
    expect(banner.getAttribute("data-phase")).toBe("refused");
    expect(banner.textContent).toContain("outside the scan box + 1 mm");
  });

  it("puts only short ids into the prompt context, never the mosaic", async () => {
    const w = await mount();
    fireEvent.click(screen.getAllByRole("radio")[0]);
    fireEvent.click(await screen.findByRole("button", { name: "good field" }));
    await waitFor(() => expect(w.shown().flag_id).toBe("f1"));
    expect(w.shown().sample_id).toBe(SAMPLE);
    expect(JSON.stringify(w.shown())).not.toMatch(/mosaic|png/i);
  });

  it("re-reads the records on map_changed", async () => {
    const w = await mount();
    w.data.flags[SAMPLE] = [
      ...w.data.flags[SAMPLE],
      { flag_id: "f9", name: "new one", note: "", t: 0, objective: "4x", x_um: 1, y_um: 2, z_um: null, replaces: null, retired: false, retired_at: null },
    ];
    await w.emit("map_changed", { sample_id: SAMPLE });
    await screen.findByRole("button", { name: "new one" });
  });

  it("re-reads state after the event socket reconnects", async () => {
    const w = await mount();
    w.data.flags[SAMPLE] = [
      ...w.data.flags[SAMPLE],
      { flag_id: "f8", name: "missed while offline", note: "", t: 0, objective: "4x", x_um: 1, y_um: 2, z_um: null, replaces: null, retired: false, retired_at: null },
    ];
    const first = w.socket();
    await act(async () => first.close());
    // the client reconnects after its backoff; open the new socket
    await waitFor(() => expect(w.socket()).not.toBe(first), { timeout: 3000 });
    await act(async () => w.socket().open());
    await screen.findByRole("button", { name: "missed while offline" });
  });
});
