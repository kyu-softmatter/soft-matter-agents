import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { fakeTransport, type Route } from "../../test/fakes";
import { PATHS, type RunStream, type StopResult } from "./api";
import { ABORT_LABEL, CLOSE_NOTE, FollowedRun } from "./runs";

const RUN = "run-20261005-001";

function stream(over: Partial<RunStream> = {}): RunStream {
  return {
    run_id: RUN, agent: "microscope", followed: true, state: "running", ended_how: null,
    plan_id: "plan_microscope_mic-20261005-001", revision: 1, t0_wall: "2026-10-05T10:00:00-07:00",
    can_stop: true, stop_unavailable: null, frame_tap: true,
    events: [{ event: "dispatch", element: "Shutter", t_mono: 0.1 }], total: 1, partial_tail: false, bad_lines: 0,
    ...over,
  };
}

const clients: Client[] = [];
afterEach(() => {
  clients.splice(0).forEach((c) => c.events.stop());
});

function renderRun(first: RunStream, extra: Record<string, Route> = {}) {
  const ok = (body: unknown) => ({ status: 200, body });
  const stops: unknown[] = [];
  const routes: Record<string, Route> = {
    [PATHS.runStream("microscope", RUN)]: () => ok(first),
    [PATHS.runStop("microscope", RUN)]: (init) => {
      stops.push(JSON.parse(String(init?.body)));
      const r: StopResult = { run_id: RUN, outcome: "begun", message: `run ${RUN} began to abort` };
      return ok(r);
    },
    ...extra,
  };
  const fake = fakeTransport(routes);
  const client = new Client(fake.transport, "127.0.0.1");
  clients.push(client);
  render(
    <ClientProvider client={client}>
      <FollowedRun agent="microscope" runId={RUN} />
    </ClientProvider>,
  );
  return { ...fake, stops };
}

describe("a run soft-matter-agents executes", () => {
  it("shows its events, its frame, and an Abort that goes to the run's stop route", async () => {
    const t = renderRun(stream(), {
      [PATHS.runStream("microscope", RUN, 1)]: () => ({ status: 200, body: stream({ events: [], total: 1 }) }),
    });
    expect(await screen.findByText("running")).toBeTruthy();
    expect(screen.getByRole("table", { name: "Run events (events.jsonl)" })).toBeTruthy();
    expect(screen.getByRole("img", { name: `Latest frame of ${RUN}` }).getAttribute("src")).toMatch(
      new RegExp(`^${PATHS.runFrame("microscope", RUN)}\\?t=\\d+$`),
    );
    expect(screen.getByText(new RegExp(CLOSE_NOTE))).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "wrong well" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: ABORT_LABEL }));
    });
    expect(await screen.findByText(`run ${RUN} began to abort`)).toBeTruthy();
    expect(t.stops).toEqual([{ reason: "wrong well" }]);
  });

  it("shows a refusal next to the button", async () => {
    renderRun(stream(), {
      [PATHS.runStop("microscope", RUN)]: () => ({
        status: 409, body: { detail: { code: "run_ended", message: "run has ended (completed)" } },
      }),
    });
    await screen.findByText("running");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: ABORT_LABEL }));
    });
    expect((await screen.findByRole("alert")).textContent).toMatch(/has ended/);
  });

  it("an ended run cannot be aborted, says how it ended, and is not read again", async () => {
    const t = renderRun(stream({ state: "ended", ended_how: "stopped_from_outside", can_stop: false,
      stop_unavailable: "the run has ended (stopped_from_outside)", frame_tap: false }));
    expect(await screen.findByText("ended: stopped_from_outside")).toBeTruthy();
    expect((screen.getByRole("button", { name: ABORT_LABEL }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole("img")).toBeNull();
    await new Promise((r) => setTimeout(r, 1200));
    expect(t.calls.filter((c) => c.path.includes("/stream")).length).toBe(1);
  });

  it("a run that is not followed says why the console cannot stop it", async () => {
    renderRun(stream({ followed: false, state: "not_followed", can_stop: false, frame_tap: false, events: [], total: 0,
      stop_unavailable: "this run is not followed (no events.jsonl), so the console has no stop channel for it; " +
        "stop it at the instrument or in the operator terminal" }));
    expect(await screen.findByText(/operator terminal/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: ABORT_LABEL })).toBeNull();
  });

  it("a failed read is said, not hidden", async () => {
    renderRun(stream(), { [PATHS.runStream("microscope", RUN)]: () => ({ status: 500, body: { detail: "boom" } }) });
    await waitFor(() => expect(screen.getByText(/Run events unavailable/)).toBeTruthy());
  });
});
