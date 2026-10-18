import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { ScreenContextProvider, useCurrentScreenContext } from "../../app/screenContext";
import { fakeTransport, type Route } from "../../test/fakes";
import {
  type CurrentSample,
  type Geometry,
  type GeometryField,
  type LoadingState,
  PATHS,
  type Permission,
  PROVISIONAL_FIELDS,
  SAMPLE_OPS,
  type SampleAccess,
  type SampleDetail,
  type SampleOp,
} from "./api";
import SampleScreen from "./index";

const ID = "20261001_0930_1";
const OTHER = "20260930_1849_1";

const step = () => ({ done: false, by: null, t: null });
function emptyLoading(session_id: string | null = "s-1"): LoadingState {
  return { session_id, geometry: step(), person: step(), image: { ...step(), ok: null, why: null, result_ref: null }, confirmed: false };
}

function detail(id: string, over: Partial<SampleDetail> = {}): SampleDetail {
  return {
    sample_id: id,
    created: "2026-10-01T10:00:00",
    fitted_at: null,
    closed_loop: false,
    objectives_used: [],
    last_session: null,
    awaiting_return: false,
    reserved: false,
    dir: `D:\\AutoFocus\\samples\\${id}`,
    hole: null,
    counts: { flags: 0, candidates: 0, visits: 0, boundary_points: 0 },
    ...over,
  };
}

const GEOMETRY: Geometry = {
  values: {
    sample_size_mm: { value: [24, 50], source: { kind: "default", by: null, t: null } },
    chamber_shape: { value: "hole", source: { kind: "default", by: null, t: null } },
    hole_diameter_mm: { value: 6, source: { kind: "entered", by: "kyu", t: "2026-10-01T09:40" } },
    coverslip_thickness_um: { value: 170, source: { kind: "default", by: null, t: null } },
    sample_thickness_um: { value: null, source: { kind: "not_set", by: null, t: null } },
    orientation: { value: "upright", source: { kind: "entered", by: "kyu", t: "2026-10-01T09:41" } },
  },
};

const allowed = (): Record<SampleOp, Permission> =>
  Object.fromEntries(SAMPLE_OPS.map((op) => [op, { allowed: true, reason: null }])) as Record<SampleOp, Permission>;

/** what the fake server answers; tests change it, then send an event to make the screen re-read */
interface World {
  samples: Map<string, { detail: SampleDetail; geometry: Geometry; loading: LoadingState }>;
  fields: GeometryField[];
  current: CurrentSample | null;
  access: SampleAccess;
  permissions: Route;
  commands: Route;
  openFolder: Route;
}

function world(): World {
  const w: World = {
    samples: new Map(),
    fields: PROVISIONAL_FIELDS,
    current: { sample_id: ID, reserved: false, session_id: "s-1" },
    access: { can_open_folder: true, open_reason: null },
    permissions: () => ({ status: 200, body: allowed() }),
    commands: () => ({ status: 200, body: { op_id: "op-1" } }),
    openFolder: () => ({ status: 204 }),
  };
  w.samples.set(ID, { detail: detail(ID), geometry: GEOMETRY, loading: emptyLoading() });
  w.samples.set(OTHER, {
    detail: detail(OTHER, { created: "2026-09-30T18:49:00", fitted_at: "2026-09-30T19:10:00" }),
    geometry: GEOMETRY,
    loading: emptyLoading(null),
  });
  return w;
}

/** Route table that looks paths up when called, so samples added during a test are served. */
function routesOf(w: World): Record<string, Route> {
  const fixed: Record<string, Route> = {
    [PATHS.state]: () => ({ status: 200, body: { sample: w.current } }),
    [PATHS.list]: () => ({
      status: 200,
      body: [...w.samples.values()].map((s) => s.detail).sort((a, b) => (b.created ?? "").localeCompare(a.created ?? "")),
    }),
    [PATHS.fields]: () => ({ status: 200, body: w.fields }),
    [PATHS.permissions(SAMPLE_OPS)]: (init) => w.permissions(init),
    "/api/commands": (init) => w.commands(init),
  };
  const lookup = (path: string): Route | undefined => {
    if (path in fixed) return fixed[path];
    if (path.startsWith("/api/sample/access")) return () => ({ status: 200, body: w.access });
    for (const [id, s] of w.samples) {
      if (path === PATHS.detail(id)) return () => ({ status: 200, body: s.detail });
      if (path === PATHS.geometry(id)) return () => ({ status: 200, body: s.geometry });
      if (path === PATHS.loading(id)) return () => ({ status: 200, body: s.loading });
      if (path === PATHS.openFolder(id)) return (init) => w.openFolder(init);
    }
    return undefined;
  };
  return new Proxy(fixed, { get: (_t, path) => (typeof path === "string" ? lookup(path) : undefined) });
}

function ContextProbe() {
  return <output data-testid="ctx">{JSON.stringify(useCurrentScreenContext())}</output>;
}

/** The screen on the shell's client over a fake transport: no network, no socket, no window. */
function setup(w: World = world(), hostname = "127.0.0.1") {
  const t = fakeTransport(routesOf(w));
  const client = new Client(t.transport, hostname);
  window.location.hash = "#/sample"; // as the shell would have it
  render(
    <ClientProvider client={client}>
      <ScreenContextProvider area="sample">
        <SampleScreen />
        <ContextProbe />
      </ScreenContextProvider>
    </ClientProvider>,
  );
  const socket = () => t.sockets[t.sockets.length - 1];
  const sent = () =>
    t.calls
      .filter((c) => c.path === "/api/commands")
      .map((c) => JSON.parse(String(c.init?.body)) as { kind: string; op: string; args: unknown });
  return { ...t, socket, sent, client };
}

const geometryPanel = () => screen.getByRole("region", { name: "Geometry" });
const loadingPanel = () => screen.getByRole("region", { name: "Loading check" });
const button = (name: string) => screen.getByRole("button", { name }) as HTMLButtonElement;
const ready = () => waitFor(() => expect(button("Sample is on the stage").disabled).toBe(false));

describe("sample screen", () => {
  it("shows the geometry with the source of every value and marks the safety fields", async () => {
    setup();
    await waitFor(() => expect(screen.getByTestId("source-orientation").textContent).toBe("entered by kyu 2026-10-01T09:41"));
    expect(screen.getByTestId("source-coverslip_thickness_um").textContent).toBe("default");
    expect(screen.getByTestId("source-sample_thickness_um").textContent).toBe("not set");
    const marked = [...geometryPanel().querySelectorAll("tr[data-field]")]
      .filter((tr) => within(tr as HTMLElement).queryByText("safety limit"))
      .map((tr) => tr.getAttribute("data-field"));
    expect(marked).toEqual(["coverslip_thickness_um", "sample_thickness_um", "orientation"]);
  });

  it("renders the field list the server serves, with no field names of its own", async () => {
    const w = world();
    w.fields = [{ key: "new_field_um", label: "New field", kind: "number", unit: "µm", choices: null, default: null, safety: true }];
    setup(w);
    await waitFor(() => expect(screen.getByLabelText("New field")).toBeTruthy());
    expect(screen.queryByLabelText("Coverslip thickness")).toBeNull();
  });

  it("saves only the changed keys through sample_geometry_set", async () => {
    const t = setup();
    await ready();
    fireEvent.change(screen.getByLabelText("Sample thickness"), { target: { value: "120" } });
    fireEvent.click(button("Save geometry"));
    await waitFor(() => expect(t.sent()).toHaveLength(1));
    expect(t.sent()[0]).toMatchObject({
      kind: "start",
      op: "sample_geometry_set",
      args: { sample_id: ID, values: { sample_thickness_um: 120 } },
    });
  });

  it("does not save a pair with one half empty", async () => {
    setup();
    await ready();
    fireEvent.change(screen.getByLabelText("Sample size (second)"), { target: { value: "" } });
    expect(screen.getByText("Enter both values: Sample size")).toBeTruthy();
    expect(button("Save geometry").disabled).toBe(true);
  });

  it("shows 'Loading confirmed' only when the engine says so, never from the steps alone", async () => {
    const w = world();
    const all = emptyLoading();
    all.geometry = { done: true, by: "kyu", t: "t1" };
    all.person = { done: true, by: "kyu", t: "t2" };
    all.image = { done: true, ok: true, by: "kyu", t: "t3", why: null, result_ref: "r" };
    w.samples.get(ID)!.loading = { ...all, confirmed: false };
    const t = setup(w);
    await waitFor(() => expect(within(loadingPanel()).getByRole("status").textContent).toBe("Loading not confirmed"));
    expect(screen.queryByText("Loading confirmed (person + image)")).toBeNull();
    expect(within(loadingPanel()).getByText(/hole edge seen, grade computed/)).toBeTruthy();

    w.samples.get(ID)!.loading = { ...all, confirmed: true };
    act(() => t.socket().event("finished", { op: "loading_check_image", summary: {} }, "op-1"));
    await waitFor(() => expect(screen.getByText("Loading confirmed (person + image)")).toBeTruthy());
  });

  it("lists the missing steps and sends the person and image steps", async () => {
    const t = setup();
    await waitFor(() =>
      expect(within(loadingPanel()).getByRole("status").textContent).toBe("Loading not confirmed: missing geometry, person, image"),
    );
    await ready();
    fireEvent.click(button("Sample is on the stage"));
    fireEvent.click(button("Check with an image"));
    await waitFor(() => expect(t.sent().map((c) => c.op)).toEqual(["loading_confirm_person", "loading_check_image"]));
    expect(t.sent()[1].args).toEqual({ sample_id: ID });
  });

  it("shows the image check failure reason from the engine with the computed grade", async () => {
    const w = world();
    w.samples.get(ID)!.loading.image = { done: true, ok: false, by: "kyu", t: "t", why: "no hole edge in the frame", result_ref: null };
    setup(w);
    expect(await screen.findByText("image check failed (grade computed): no hole edge in the frame")).toBeTruthy();
  });

  it("remote view (the shell's read-only flag): every command is off, the folder is a path only", async () => {
    const w = world();
    w.access = { can_open_folder: false, open_reason: null };
    setup(w, "192.168.0.20");
    await screen.findByLabelText("Sample thickness");
    await waitFor(() => expect(screen.getAllByText("Read-only: remote view").length).toBeGreaterThan(0));
    for (const name of ["New sample", "Save geometry", "Sample is on the stage", "Check with an image", `Open ${OTHER}`]) {
      expect(button(name).disabled).toBe(true);
    }
    expect((screen.getByLabelText("Sample thickness") as HTMLInputElement).disabled).toBe(true);
    expect(screen.queryByRole("button", { name: "Open folder" })).toBeNull();
    expect(screen.getByText(`D:\\AutoFocus\\samples\\${ID}`)).toBeTruthy();
  });

  it("a remote_view 403 on a command turns the screen read-only (the shell's flag)", async () => {
    const w = world();
    w.commands = () => ({ status: 403, body: { detail: { code: "remote_view", message: "remote view" } } });
    setup(w);
    await ready();
    fireEvent.click(button("Sample is on the stage"));
    await waitFor(() => expect(button("Check with an image").disabled).toBe(true));
    expect(button("New sample").disabled).toBe(true);
  });

  it("a non-remote 403 on Open folder is that action's reason only, no read-only", async () => {
    const w = world();
    w.openFolder = () => ({ status: 403, body: { detail: { code: "role", message: "Needs the operator role" } } });
    setup(w);
    await ready();
    fireEvent.click(button("Open folder"));
    const region = () => screen.getByRole("region", { name: "Opened sample" });
    await waitFor(() => expect(within(region()).getByText("Needs the operator role")).toBeTruthy());
    expect(button("Sample is on the stage").disabled).toBe(false);
    expect(button("New sample").disabled).toBe(false);
    expect(screen.queryByText(/^Read-only/)).toBeNull();
  });

  it("a remote_view 403 on Open folder switches the app to read-only", async () => {
    const w = world();
    w.openFolder = () => ({ status: 403, body: { detail: { code: "remote_view", message: "remote view" } } });
    setup(w);
    await ready();
    fireEvent.click(button("Open folder"));
    await waitFor(() => expect(button("Sample is on the stage").disabled).toBe(true));
    expect(screen.getAllByText("Read-only: remote view").length).toBeGreaterThan(0);
  });

  it("session open for this sample: other samples cannot be opened, with the router's reason", async () => {
    const w = world();
    w.access = { can_open_folder: true, open_reason: `Session s-1 is open for sample ${ID}` };
    setup(w);
    await ready();
    await waitFor(() => expect(button("New sample").disabled).toBe(true));
    expect(button(`Open ${OTHER}`).disabled).toBe(true);
    expect(screen.getAllByText(`Session s-1 is open for sample ${ID}`).length).toBeGreaterThan(0);
  });

  it("no session for the sample: geometry and loading steps are off with the shared reason", async () => {
    const w = world();
    w.current = { sample_id: ID, reserved: false, session_id: null };
    w.permissions = () => ({
      status: 200,
      body: Object.fromEntries(
        SAMPLE_OPS.map((op) => [
          op,
          op === "sample_open" || op === "sample_new"
            ? { allowed: true, reason: null }
            : { allowed: false, reason: "Open an experiment session first" },
        ]),
      ),
    });
    setup(w);
    await screen.findByLabelText("Sample thickness");
    await waitFor(() => expect(screen.getAllByText("Open an experiment session first")).toHaveLength(3));
    for (const name of ["Save geometry", "Sample is on the stage", "Check with an image"]) expect(button(name).disabled).toBe(true);
    expect(button("New sample").disabled).toBe(false);
  });

  it("permissions unreadable: every sample control is off with the shared fallback reason", async () => {
    const w = world();
    w.permissions = () => ({ status: 404, body: { detail: "Not Found" } });
    setup(w);
    await screen.findByLabelText("Sample thickness");
    await waitFor(() => expect(screen.getAllByText("Permission check unavailable").length).toBeGreaterThanOrEqual(4));
    for (const name of ["New sample", "Save geometry", "Sample is on the stage", "Check with an image", `Open ${OTHER}`]) {
      expect(button(name).disabled).toBe(true);
    }
  });

  it("an op left out of the permissions answer is off, never allowed", async () => {
    const w = world();
    w.permissions = () => {
      const p: Partial<Record<SampleOp, Permission>> = allowed();
      delete p.loading_check_image;
      return { status: 200, body: p };
    };
    setup(w);
    await ready();
    expect(button("Check with an image").disabled).toBe(true);
    expect(screen.getByText("Permission check unavailable")).toBeTruthy();
  });

  it("shows a server refusal and an engine preflight_failed next to the control", async () => {
    const w = world();
    w.commands = (init) => {
      const cmd = JSON.parse(String(init?.body)) as { op: string };
      return cmd.op === "loading_confirm_person"
        ? { status: 409, body: { detail: "anna has control of the microscope" } }
        : { status: 200, body: { op_id: "op-7" } };
    };
    const t = setup(w);
    await ready();
    fireEvent.click(button("Sample is on the stage"));
    expect(await screen.findByText("anna has control of the microscope")).toBeTruthy();

    fireEvent.click(button("Check with an image"));
    await waitFor(() => expect(t.sent().at(-1)?.op).toBe("loading_check_image"));
    await act(async () => {}); // let the op_id register
    act(() =>
      t.socket().event(
        "preflight_failed",
        { op: "loading_check_image", checks: [{ name: "objective", ok: false, why: "4x is not in place" }] },
        "op-7",
      ),
    );
    expect(await screen.findByText("4x is not in place")).toBeTruthy();
  });

  it("New sample selects the reserved sample the engine reports", async () => {
    const w = world();
    w.current = null;
    const t = setup(w);
    await waitFor(() => expect(button("New sample").disabled).toBe(false));
    fireEvent.click(button("New sample"));
    await waitFor(() => expect(t.sent().at(-1)?.op).toBe("sample_new"));
    const NEW = "20261001_1200_1";
    w.samples.set(NEW, {
      detail: detail(NEW, { created: "2026-10-01T12:00:00", reserved: true }),
      geometry: GEOMETRY,
      loading: emptyLoading(null),
    });
    act(() => t.socket().event("finished", { op: "sample_new", summary: { sample_id: NEW } }, "op-1"));
    await waitFor(() => expect(window.location.hash).toBe(`#/sample?sample_id=${NEW}`));
    expect(await screen.findByText("reserved, no session yet")).toBeTruthy();
    await waitFor(() => expect(screen.getByRole("region", { name: "Opened sample" }).textContent).toContain(NEW));
  });

  it("re-reads its state when the event socket opens again", async () => {
    const w = world();
    const t = setup(w);
    await ready();
    act(() => t.socket().open());
    w.samples.get(ID)!.loading = { ...emptyLoading(), confirmed: true };
    act(() => t.socket().close()); // the shell reconnects with backoff
    await waitFor(() => expect(t.sockets.length).toBeGreaterThan(1), { timeout: 3000 });
    act(() => t.socket().open());
    await waitFor(() => expect(screen.getByText("Loading confirmed (person + image)")).toBeTruthy());
    t.client.events.stop();
  });

  it("shows brightfield from a light_changed event in the one light shape", async () => {
    const t = setup();
    await ready();
    const lights = (state: string) => ({
      dialamp: { state, intensity: 12 },
      aura: { state: "off", lines: {} },
      verified: true,
      records: [],
    });
    act(() => t.socket().event("light_changed", lights("on")));
    expect(await screen.findByText("Brightfield: on")).toBeTruthy();
    act(() => t.socket().event("light_changed", lights("off")));
    expect(await screen.findByText("Brightfield: off")).toBeTruthy();
  });

  it("shows the engine's hole fit status text as is", async () => {
    const w = world();
    w.samples.get(ID)!.detail.hole = {
      centre_um: [100, 200],
      diameter_mm: 6.1,
      fit_rms_um: 4,
      n_points: 40,
      arc_deg: 140,
      fitted_at: "2026-10-01T09:50",
      status: "partial trace",
    };
    setup(w);
    await waitFor(() => expect(screen.getByRole("region", { name: "Opened sample" }).textContent).toContain("140° arc"));
    expect(screen.getByRole("region", { name: "Opened sample" }).textContent).toContain("(partial trace)");
  });

  it("Open folder posts to the router and never opens anything itself", async () => {
    const t = setup();
    fireEvent.click(await screen.findByRole("button", { name: "Open folder" }));
    await waitFor(() => expect(t.calls.some((c) => c.path === PATHS.openFolder(ID) && c.init?.method === "POST")).toBe(true));
    expect(t.sent()).toHaveLength(0);
  });

  it("opening another sample sends sample_open", async () => {
    const t = setup();
    await waitFor(() => expect(button(`Open ${OTHER}`).disabled).toBe(false));
    fireEvent.click(button(`Open ${OTHER}`));
    await waitFor(() => expect(t.sent().at(-1)).toMatchObject({ kind: "start", op: "sample_open", args: { sample_id: OTHER } }));
  });

  it("puts the sample id, geometry sources and loading state in the prompt context, no images", async () => {
    setup();
    await waitFor(() => expect(JSON.parse(screen.getByTestId("ctx").textContent ?? "{}").sample_id).toBe(ID));
    const ctx = JSON.parse(screen.getByTestId("ctx").textContent ?? "{}");
    expect(ctx.area).toBe("sample");
    expect(ctx.geometry.orientation).toEqual({ value: "upright", source: "entered" });
    expect(ctx.loading).toEqual({ geometry: false, person: false, image: false, confirmed: false });
  });
});
