import { act, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { fakeTransport, type Route } from "../test/fakes";
import { App } from "./App";
import { Client, ClientProvider } from "./client";
import { lightIsOn, readAssistantStatus, readLights, useEngineStatus } from "./status";
import { ShutdownNoticeView } from "./StatusBar";

describe("useEngineStatus after an unlock", () => {
  function Probe({ resumed }: { resumed?: number }) {
    const s = useEngineStatus(resumed);
    return <p data-testid="loaded">{String(s.loaded)}</p>;
  }

  it("re-reads /api/state when useAuth().resumed changes, and only then", async () => {
    const t = fakeTransport({ "/api/state": () => ({ status: 200, body: { running: [] } }) });
    const client = new Client(t.transport, "127.0.0.1");
    const reads = () => t.calls.filter((c) => c.path === "/api/state").length;
    const { rerender } = render(
      <ClientProvider client={client}>
        <Probe resumed={0} />
      </ClientProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("loaded").textContent).toBe("true"));
    const before = reads();
    rerender(
      <ClientProvider client={client}>
        <Probe resumed={0} />
      </ClientProvider>,
    );
    expect(reads()).toBe(before);
    rerender(
      <ClientProvider client={client}>
        <Probe resumed={1} />
      </ClientProvider>,
    );
    await waitFor(() => expect(reads()).toBe(before + 1));
  });
});

const SNAPSHOT = {
  positions: { x_um: 8026.0, y_um: 571.6, z_um: 3048.7, errors: {} },
  lights: {
    dialamp: { state: "off", intensity: 608 },
    aura: { state: "off", lines: { GREEN: null } },
    verified: true,
    records: [],
  },
  running: [],
  last_shutdown_lights: { t: 1759300000, all_off: true },
};

function setup(routes: Record<string, Route> = {}, hostname = "127.0.0.1") {
  const t = fakeTransport({ "/api/state": () => ({ status: 200, body: SNAPSHOT }), ...routes });
  const client = new Client(t.transport, hostname);
  render(<App client={client} />);
  // the event socket is open unless a test closes it: values show as current
  act(() => t.sockets.find((s) => s.path === "/ws/events")?.open());
  return { ...t, client };
}

describe("status readers", () => {
  it("reads light values without guessing", () => {
    expect(lightIsOn("0")).toBe(false);
    expect(lightIsOn("1")).toBe(true);
    expect(lightIsOn("on")).toBe(true);
    expect(lightIsOn({ state: "1", line: "GREEN" })).toBe(true);
    expect(lightIsOn("2100")).toBeNull();
    expect(lightIsOn(undefined)).toBeNull();
  });

  it("reads a light as unknown unless its state is on or off, and skips a missing lamp", () => {
    const v = readLights({ dialamp: { state: "unknown" }, verified: false });
    expect(v).toMatchObject({ lights: [{ name: "DiaLamp", on: null }], verified: false });
    expect(v?.lights).toHaveLength(1);
    expect(readLights(null)).toBeNull();
  });

  it("reads the one light shape {dialamp: {state, intensity}, aura: {state, lines}}", () => {
    const v = readLights({
      dialamp: { state: "0", intensity: 608 },
      aura: { state: "1", lines: { GREEN: 1 } },
      verified: true,
      records: [],
    });
    expect(v?.lights.map((l) => [l.name, l.on])).toEqual([
      ["DiaLamp", false],
      ["Aura", true],
    ]);
    expect(v?.verified).toBe(true);
  });

  it("reads the assistant status, D7 data stage included", () => {
    expect(readAssistantStatus({ provider: "fake", connected: true, data_stage: "text" })).toEqual({
      available: true,
      provider: "fake",
      connected: true,
      data_stage: "text",
    });
    expect(readAssistantStatus(null).available).toBe(false);
  });
});

describe("StatusBar", () => {
  it("shows lights, position, idle and the assistant as unavailable before T-013", async () => {
    setup();
    await waitFor(() => expect(screen.getByTestId("sb-position").textContent).toContain("Z 3048.70 µm"));
    expect(screen.getByTestId("sb-position").textContent).toContain("XY 8026.0, 571.6 µm");
    expect(screen.getByTestId("sb-lights").textContent).toContain("DiaLamp off");
    expect(screen.getByTestId("sb-running").textContent).toBe("idle");
    expect(screen.getByTestId("sb-assistant").textContent).toBe("assistant: unavailable");
    expect(screen.queryByTestId("sb-readonly")).toBeNull();
  });

  it("follows position and light_changed events from /ws/events", async () => {
    const { sockets } = setup();
    await screen.findByText(/Z 3048.70/);
    act(() => {
      sockets[0].open();
      sockets[0].event("position", { x_um: 1, y_um: 2, z_um: 2989.42 });
      sockets[0].event("light_changed", {
        dialamp: { state: "on", intensity: 608 },
        aura: { state: "off", lines: {} },
        verified: true,
      });
    });
    expect(screen.getByTestId("sb-position").textContent).toContain("Z 2989.42 µm");
    expect(screen.getByTestId("sb-lights").textContent).toContain("DiaLamp ON");
    expect(screen.getByTestId("sb-server").textContent).toBe("server: connected");
  });

  it("re-reads the state after a lifecycle event to show the running operation", async () => {
    let running: unknown[] = [];
    const { sockets } = setup({ "/api/state": () => ({ status: 200, body: { ...SNAPSHOT, running } }) });
    await screen.findByText(/Z 3048.70/);
    running = [{ op_id: "op-7", op: "scan_4x", state: "running" }];
    act(() => sockets[0].event("started", {}, "op-7"));
    await waitFor(() => expect(screen.getByTestId("sb-running").textContent).toBe("running: scan_4x"));
  });

  it("shows the assistant provider and data stage when T-013 answers", async () => {
    setup({ "/api/assistant/status": () => ({ status: 200, body: { provider: "fake", connected: true, data_stage: "prompt_only" } }) });
    await waitFor(() =>
      expect(screen.getByTestId("sb-assistant").textContent).toBe("assistant: fake · data prompt_only"),
    );
  });

  it("marks a remote viewer read-only", async () => {
    setup({}, "192.168.1.20");
    expect(await screen.findByTestId("sb-readonly")).toBeTruthy();
    expect(screen.getByTestId("sb-readonly").textContent).toBe("remote · read only");
  });

  it("says when the server cannot be reached", async () => {
    const { sockets } = setup({ "/api/state": () => ({ status: 503, body: { detail: "engine not ready" } }) });
    expect(await screen.findByText("state: engine not ready")).toBeTruthy();
    act(() => sockets[0].close());
    expect(screen.getByTestId("sb-server").textContent).toBe("server: disconnected");
    expect(screen.getByTestId("sb-lights-stale").textContent).toContain("lights: unknown");
  });

  it("treats a locked login like a dropped socket: no live values until the unlock", async () => {
    const { sockets } = setup();
    await screen.findByText(/Z 3048.70/);
    const events = sockets.find((s) => s.path === "/ws/events")!;
    act(() => events.send({ type: "lock", locked: true }));
    expect(screen.getByTestId("sb-server").textContent).toBe("server: connected · login locked");
    expect(screen.getByTestId("sb-lights-stale").textContent).toContain("lights: unknown");
    expect(screen.getByTestId("sb-position").textContent?.startsWith("position: unknown")).toBe(true);
    expect(screen.getByTestId("sb-running").textContent).toBe("operation: unknown");
    act(() => events.send({ type: "lock", locked: false }));
    expect(screen.getByTestId("sb-server").textContent).toBe("server: connected");
    expect(screen.getByTestId("sb-lights").textContent).toContain("DiaLamp off");
    expect(screen.getByTestId("sb-position").textContent).toContain("Z 3048.70 µm");
  });
});

describe("last-shutdown notice (ui-spec 5.2)", () => {
  it("shows nothing when the engine reports no last shutdown", () => {
    const { container } = render(<ShutdownNoticeView last={null} />);
    expect(container.textContent).toBe("");
  });

  it("says all lights read off, quietly", () => {
    render(<ShutdownNoticeView last={{ t: 1759300000, all_off: true }} />);
    expect(screen.getByRole("status").textContent).toContain("all lights read back off");
  });

  it("warns when a light did not read back off", () => {
    render(<ShutdownNoticeView last={{ t: 1759300000, all_off: false }} />);
    expect(screen.getByRole("alert").textContent).toContain("did not read back off");
  });

  it("appears on the first screen from GET /api/state", async () => {
    setup({ "/api/state": () => ({ status: 200, body: { ...SNAPSHOT, last_shutdown_lights: { t: 1, all_off: false } } }) });
    expect((await screen.findByTestId("shutdown-notice")).getAttribute("role")).toBe("alert");
  });
});
