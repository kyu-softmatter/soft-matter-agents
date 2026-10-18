import { act, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { fakeTransport, type Route } from "../../test/fakes";
import TweezersScreen from "./index";

configure({ asyncUtilTimeout: 8000 });

const TRAPS = [
  { index: 0, on: true, x_um: 0, y_um: 0, z_um: 0, power_pct: 25 },
  { index: 1, on: false, x_um: 8, y_um: 0, z_um: 0, power_pct: 25 },
];

const META = {
  type: "frame",
  seq: 1,
  t: 1759300000,
  width: 800,
  height: 600,
  binning: 1,
  source_width: 800,
  source_height: 600,
  display_min: 0,
  display_max: 100,
  jpeg_bytes: 4,
  camera: "Kinetix_red",
  meta: { pixel_um: 0.1 },
};

function show({ tweezers = { kind: "mock", n_traps: 2, bench: false, traps: TRAPS, error: null } as unknown, allowed = true } = {}) {
  const commands: Record<string, unknown>[] = [];
  const routes: Record<string, Route> = {
    "/api/state": () => ({ status: 200, body: { tweezers } }),
    "/api/permissions?ops=trap_move,trap_set": () => ({
      status: 200,
      body: Object.fromEntries(
        ["trap_move", "trap_set"].map((op) => [op, allowed ? { allowed: true, reason: null } : { allowed: false, reason: "take control first" }]),
      ),
    }),
    "/api/commands": (init) => {
      commands.push(JSON.parse(String(init?.body)));
      return { status: 200, body: { op_id: `op${commands.length}`, accepted: true } };
    },
  };
  const t = fakeTransport(routes);
  render(
    <ClientProvider client={new Client(t.transport, "127.0.0.1")}>
      <TweezersScreen />
    </ClientProvider>,
  );
  return { commands, sockets: t.sockets };
}

describe("tweezers screen", () => {
  beforeEach(() => {
    let n = 0;
    URL.createObjectURL = vi.fn(() => `blob:frame-${++n}`);
    URL.revokeObjectURL = vi.fn();
  });

  it("lists the mock traps and sends trap_move and trap_set", async () => {
    const { commands } = show();
    expect((await screen.findByTestId("tweezers-kind")).textContent).toContain("Mock tweezers");
    const table = screen.getByRole("table", { name: "Traps" });
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    await waitFor(() => expect((screen.getAllByRole("button", { name: "Move" })[1] as HTMLButtonElement).disabled).toBe(false));
    fireEvent.change(screen.getByLabelText(/Trap 1 x/), { target: { value: "5.25" } });
    fireEvent.change(screen.getByLabelText(/Trap 1 y/), { target: { value: "-3" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Move" })[1]);
    await waitFor(() => expect(commands).toHaveLength(1));
    expect(commands[0]).toMatchObject({ kind: "start", op: "trap_move", args: { trap: 1, x_um: 5.25, y_um: -3, z_um: 0 } });
    fireEvent.click(screen.getByRole("button", { name: "Off" }));
    await waitFor(() => expect(commands).toHaveLength(2));
    expect(commands[1]).toMatchObject({ op: "trap_set", args: { trap: 1, on: true } });
  });

  it("keeps moves disabled with the reason when the operator may not move", async () => {
    show({ allowed: false });
    expect(await screen.findByText(/take control first/)).toBeTruthy();
    expect((screen.getAllByRole("button", { name: "Move" })[0] as HTMLButtonElement).disabled).toBe(true);
  });

  it("says so when the setup has no tweezers", async () => {
    show({ tweezers: null });
    expect(await screen.findByText(/No tweezers on this setup/)).toBeTruthy();
  });

  it("moves the chosen trap to a click on the live frame", async () => {
    const { commands, sockets } = show();
    await screen.findByTestId("tweezers-kind");
    await waitFor(() => expect((screen.getAllByRole("button", { name: "Move" })[0] as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByLabelText("Choose trap 1"));
    const ws = sockets.find((s) => s.path === "/ws/frames")!;
    act(() => {
      ws.open();
      ws.send(META);
      ws.onmessage?.(new MessageEvent("message", { data: new Blob([new Uint8Array([1, 2, 3, 4])]) }));
    });
    const stack = await screen.findByTestId("live-stack");
    stack.getBoundingClientRect = () => ({ left: 0, top: 0, width: 400, height: 300, right: 400, bottom: 300, x: 0, y: 0, toJSON: () => ({}) });
    // 400x300 on screen for an 800x600 frame at 0.1 um/px: (300, 75) on screen is (600, 150) px
    fireEvent.click(stack, { clientX: 300, clientY: 75 });
    await waitFor(() => expect(commands).toHaveLength(1));
    expect(commands[0]).toMatchObject({ op: "trap_move", args: { trap: 1, x_um: 20, y_um: -15 } });
    expect(screen.getByRole("img", { name: "Traps over the frame" })).toBeTruthy();
  });

  it("will not move real tweezers on a click when the frame has no pixel size", async () => {
    const { commands, sockets } = show({ tweezers: { kind: "tweez300", n_traps: 2, bench: true, traps: TRAPS, error: null } });
    await screen.findByTestId("tweezers-kind");
    await waitFor(() => expect((screen.getAllByRole("button", { name: "Move" })[0] as HTMLButtonElement).disabled).toBe(false));
    const ws = sockets.find((s) => s.path === "/ws/frames")!;
    act(() => {
      ws.open();
      ws.send({ ...META, meta: {} });
      ws.onmessage?.(new MessageEvent("message", { data: new Blob([new Uint8Array([1, 2, 3, 4])]) }));
    });
    const stack = await screen.findByTestId("live-stack");
    stack.getBoundingClientRect = () => ({ left: 0, top: 0, width: 400, height: 300, right: 400, bottom: 300, x: 0, y: 0, toJSON: () => ({}) });
    fireEvent.click(stack, { clientX: 210, clientY: 155 });
    expect((await screen.findByRole("alert")).textContent).toContain("does not say its pixel size");
    expect(commands).toHaveLength(0);
  });
});
