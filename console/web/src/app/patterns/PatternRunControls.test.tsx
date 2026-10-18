import { act, configure, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { fakeTransport, type Route } from "../../test/fakes";
import { Client, ClientProvider } from "../client";
import { PatternRunControls } from "./PatternRunControls";

configure({ asyncUtilTimeout: 8000 });

function show(allowed = true) {
  const commands: Record<string, unknown>[] = [];
  const times: number[] = [];
  const routes: Record<string, Route> = {
    "/api/permissions?ops=pattern_run": () => ({
      status: 200,
      body: { pattern_run: allowed ? { allowed: true, reason: null } : { allowed: false, reason: "open a session first" } },
    }),
    "/api/state": () => ({ status: 200, body: { running: [] } }),
    "/api/commands": (init) => {
      commands.push(JSON.parse(String(init?.body)));
      return { status: 200, body: { op_id: "pattern_run_7", accepted: true } };
    },
  };
  const t = fakeTransport(routes);
  render(
    <ClientProvider client={new Client(t.transport, "127.0.0.1")}>
      <PatternRunControls patternId="sq" onTime={(v) => times.push(v)} />
    </ClientProvider>,
  );
  const events = () => t.sockets.find((s) => s.path === "/ws/events")!;
  return { commands, times, events };
}

describe("pattern run controls", () => {
  it("runs, follows progress, aborts and sees the end", async () => {
    const { commands, times, events } = show();
    const run = await screen.findByRole("button", { name: "Run on piezo / traps" });
    await waitFor(() => expect((run as HTMLButtonElement).disabled).toBe(false));
    fireEvent.change(screen.getByLabelText("Repeats"), { target: { value: "3" } });
    fireEvent.click(run);
    await waitFor(() => expect(commands).toHaveLength(1));
    expect(commands[0]).toMatchObject({ kind: "start", op: "pattern_run", args: { pattern_id: "sq", repeats: 3 } });
    const ws = events();
    act(() => {
      ws.open();
      ws.event("progress", { op: "pattern_run", status: "running", data: { pattern_id: "sq", t_s: 1.25, elapsed_s: 4, of_s: 9 } }, "pattern_run_7");
    });
    expect(times).toContain(1.25);
    expect(screen.getByTestId("pattern-run-status").textContent).toContain("4.0 / 9.0 s");
    fireEvent.click(screen.getByRole("button", { name: "Abort run" }));
    await waitFor(() => expect(commands).toHaveLength(2));
    expect(commands[1]).toMatchObject({ kind: "abort", op_id: "pattern_run_7" });
    act(() => ws.event("aborted", {}, "pattern_run_7"));
    await waitFor(() => expect(screen.getByTestId("pattern-run-status").textContent).toBe("aborted"));
    expect((screen.getByRole("button", { name: "Abort run" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("ignores another pattern's progress", async () => {
    const { times, events } = show();
    await screen.findByRole("button", { name: "Run on piezo / traps" });
    const ws = events();
    act(() => {
      ws.open();
      ws.event("progress", { op: "pattern_run", data: { pattern_id: "other", t_s: 2 } }, "pattern_run_9");
    });
    expect(times).toEqual([]);
  });

  it("keeps Run disabled with the engine's reason", async () => {
    show(false);
    expect(await screen.findByText("open a session first")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Run on piezo / traps" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
