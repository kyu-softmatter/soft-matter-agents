import { describe, expect, it, vi } from "vitest";

import { CommandRefused } from "../../app/client";
import { type EventSourceLike, serverClient } from "./client";
import { fakeClient } from "./fakeClient";
import type { RunProgressJson } from "./types";
import { frameFromJson } from "./frame";
import { parseSimRest, runRest } from "./simRoute";

describe("serverClient", () => {
  const progress = (state: string, steps: number) => ({ run_id: "r1", state, steps_taken: steps }) as unknown as RunProgressJson;

  it("GETs the simulation routes through the shared client's get", async () => {
    const get = vi.fn(async () => [] as never);
    const c = serverClient(get, { openEvents: null });
    await c.listRuns();
    await c.getRun("run a");
    await c.getSeries("r1");
    await c.getFrame("r1", 3, ["diameter", "orientation"]);
    await c.getFrame("r1", -1);
    await c.zipEntries("r1");
    expect(get.mock.calls.map((call) => (call as unknown[])[0])).toEqual([
      "/api/simulation/runs",
      "/api/simulation/runs/run%20a",
      "/api/simulation/runs/r1/series",
      "/api/simulation/runs/r1/frames/3?fields=diameter,orientation",
      "/api/simulation/runs/r1/frames/-1",
      "/api/simulation/runs/r1/zip/entries",
    ]);
    expect(c.source).toBe("server");
    expect(c.zipUrl("r1", false)).toBe("/api/simulation/runs/r1/zip");
    expect(c.zipUrl("r1", true)).toBe("/api/simulation/runs/r1/zip?trajectory=1");
  });

  it("passes the shared client's refusals through", async () => {
    const refused = new CommandRefused(404, "no simulation run x", "not_found");
    const c = serverClient(async () => Promise.reject(refused), { openEvents: null });
    await expect(c.getRun("x")).rejects.toBe(refused);
  });

  class FakeEvents implements EventSourceLike {
    static opened: FakeEvents[] = [];
    onerror: ((ev: Event) => void) | null = null;
    closed = false;
    listeners: ((ev: MessageEvent) => void)[] = [];
    constructor(readonly url: string) {
      FakeEvents.opened.push(this);
    }
    addEventListener(type: string, l: (ev: MessageEvent) => void) {
      if (type === "progress") this.listeners.push(l);
    }
    close() {
      this.closed = true;
    }
    push(p: RunProgressJson) {
      this.listeners.forEach((l) => l(new MessageEvent("progress", { data: JSON.stringify(p) })));
    }
  }

  it("follows the progress stream and closes it when the run stops", () => {
    FakeEvents.opened = [];
    const seen: RunProgressJson[] = [];
    const c = serverClient(vi.fn(), { openEvents: (url) => new FakeEvents(url) });
    const stop = c.watchProgress("r1", (p) => seen.push(p));
    const es = FakeEvents.opened[0];
    expect(es.url).toBe("/api/simulation/runs/r1/progress/stream");
    es.push(progress("running", 10));
    expect(es.closed).toBe(false);
    es.push(progress("complete", 20));
    expect(es.closed).toBe(true); // no reconnect after the server ended the stream
    expect(seen.map((p) => p.steps_taken)).toEqual([10, 20]);
    stop();
  });

  it("polls through get when the stream fails, or without EventSource", async () => {
    vi.useFakeTimers();
    try {
      FakeEvents.opened = [];
      let steps = 0;
      const get = vi.fn(async () => progress(steps < 2 ? "running" : "complete", steps++) as never);
      const seen: RunProgressJson[] = [];
      const c = serverClient(get, { openEvents: (url) => new FakeEvents(url), pollMs: 100 });
      const stop = c.watchProgress("r1", (p) => seen.push(p));
      FakeEvents.opened[0].onerror?.(new Event("error"));
      expect(FakeEvents.opened[0].closed).toBe(true);
      await vi.advanceTimersByTimeAsync(500);
      expect(get).toHaveBeenCalledWith("/api/simulation/runs/r1/progress");
      expect(seen.map((p) => p.state)).toEqual(["running", "running", "complete"]);
      stop();

      const plain = serverClient(get, { openEvents: null, pollMs: 100 });
      const stop2 = plain.watchProgress("r1", (p) => seen.push(p));
      await vi.advanceTimersByTimeAsync(0);
      expect(seen).toHaveLength(4);
      stop2();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("fakeClient", () => {
  it("has a finished, a faulted and a running run", async () => {
    const c = fakeClient(() => 1_000_000_000_000);
    const runs = await c.listRuns();
    expect(Object.fromEntries(runs.map((r) => [r.run_id, r.progress.state]))).toEqual({
      "mock-sim-2d-running": "running",
      "mock-sim-3d-fault": "fault",
      "mock-sim-2d-done": "complete",
    });
    expect(runs[0].run_id).toBe("mock-sim-2d-running"); // newest first
    expect(c.source).toBe("mock");
    expect(c.zipUrl("mock-sim-2d-done", true)).toBeNull();
  });

  it("moves the running run forward with the clock", async () => {
    let t = 1_000_000_000_000;
    const c = fakeClient(() => t);
    const before = (await c.getRun("mock-sim-2d-running")).progress;
    t += 10_000;
    const after = (await c.getRun("mock-sim-2d-running")).progress;
    expect(after.steps_taken! - before.steps_taken!).toBe(1000); // 100 steps/s
    expect(after.frames_saved).toBeGreaterThan(before.frames_saved!);
    expect(after.eta).toBe(before.eta);
    const s = await c.getSeries("mock-sim-2d-running");
    expect(s.log.steps_taken.at(-1)).toBe(after.steps_taken);
    expect(s.observables).toBeNull();
  });

  it("serves frames that frameFromJson accepts, and only saved ones", async () => {
    const c = fakeClient(() => 1_000_000_000_000);
    const f = frameFromJson(await c.getFrame("mock-sim-3d-fault", 5));
    expect(f.dimensions).toBe(3);
    expect(f.n).toBe(128);
    expect(f.step).toBe(250);
    const info = await c.getRun("mock-sim-3d-fault");
    await expect(c.getFrame("mock-sim-3d-fault", info.progress.frames_saved!)).rejects.toMatchObject({ status: 404 });
    await expect(c.getRun("nope")).rejects.toMatchObject({ status: 404 });
  });

  it("gives a finished run its observables and log columns", async () => {
    const s = await fakeClient(() => 1_000_000_000_000).getSeries("mock-sim-2d-done");
    expect(Object.keys(s.log)).toEqual(expect.arrayContaining(["steps_taken", "temperature", "pressure"]));
    expect(s.curves[0]).toMatchObject({ path: "msd_curve", kind: "line" });
    expect(s.curves[0].y.every((v) => v !== null && v > 0)).toBe(true);
  });
});

describe("simulation routes", () => {
  it("reads runs/<run_id> and nothing else as a run", () => {
    expect(parseSimRest("")).toEqual({ runId: null });
    expect(parseSimRest("runs")).toEqual({ runId: null });
    expect(parseSimRest("runs/run-20260924-001")).toEqual({ runId: "run-20260924-001" });
    expect(parseSimRest("runs/run-20260924-001/")).toEqual({ runId: "run-20260924-001" });
    expect(parseSimRest("runs/a%20b?x=1")).toEqual({ runId: "a b" });
    expect(parseSimRest("runs/a/b")).toEqual({ runId: null });
    expect(parseSimRest("runs/%E0%A4%A")).toEqual({ runId: null });
    expect(parseSimRest(runRest("a b"))).toEqual({ runId: "a b" });
  });
});
