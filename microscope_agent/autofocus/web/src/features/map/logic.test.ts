import { describe, expect, it } from "vitest";

import type { EngineEvent } from "./clickMove";
import { IDLE, clickMoveReducer, clickMoveText, type Action, type ClickMove } from "./clickMove";
import { fixture, SAMPLE } from "./fixture";
import { diameterOff, fitView, holeFitStatus, toCanvas, toStage, visibleCandidates, visibleFlags } from "./geometry";
import { ALL_LAYERS_ON, buildScene, candidateMark, type SceneInput } from "./scene";

const data = fixture();
const state = data.maps[SAMPLE];

describe("display transform", () => {
  const v = { cx: 0, cy: 0, pxPerUm: 0.1, width: 200, height: 200 };

  it("draws +stage x to the left and +stage y downwards (joystick direction)", () => {
    const [u0, w0] = toCanvas(v, 0, 0);
    const [ux, wx] = toCanvas(v, 100, 0);
    const [uy, wy] = toCanvas(v, 0, 100);
    expect([u0, w0]).toEqual([100, 100]);
    expect(ux).toBeLessThan(u0);
    expect(wx).toBe(w0);
    expect(wy).toBeGreaterThan(w0);
    expect(uy).toBe(u0);
  });

  it("inverts exactly", () => {
    const [u, w] = toCanvas(v, 1234.5, -678.9);
    const [x, y] = toStage(v, u, w);
    expect(x).toBeCloseTo(1234.5, 6);
    expect(y).toBeCloseTo(-678.9, 6);
  });

  it("fits a box into the canvas", () => {
    const f = fitView({ x0: 0, x1: 1000, y0: 0, y1: 500 }, 400, 400);
    expect(f.cx).toBe(500);
    expect(f.cy).toBe(250);
    expect(1000 * f.pxPerUm).toBeLessThanOrEqual(400);
  });
});

describe("hole fit and records", () => {
  it("tells this session's fit from an older one", () => {
    expect(holeFitStatus(state)).toBe("this_session");
    expect(holeFitStatus({ ...state, session_started_at: (state.hole!.fitted_at ?? 0) + 1 })).toBe("previous_session");
    expect(holeFitStatus({ ...state, hole: null })).toBe("none");
  });

  it("warns when the diameter is more than 20 % off", () => {
    expect(diameterOff(state.hole, 6.0)).toBe(false);
    expect(diameterOff(state.hole, 4.5)).toBe(true);
  });

  it("hides decided candidates and, by default, rejected ones", () => {
    const c = data.candidates[SAMPLE];
    expect(visibleCandidates(c, false).map((x) => x.candidate_id)).toEqual(["c1", "c3"]);
    expect(visibleCandidates(c, true).map((x) => x.candidate_id)).toEqual(["c1", "c3", "c4"]);
  });

  it("hides retired and replaced flags", () => {
    const f = data.flags[SAMPLE];
    expect(visibleFlags(f, false).map((x) => x.flag_id)).toEqual(["f1"]);
    const edited = [...f, { ...f[0], flag_id: "f2", note: "denser", replaces: "f1" }];
    expect(visibleFlags(edited, false).map((x) => x.flag_id)).toEqual(["f2"]);
  });
});

describe("scene layers", () => {
  const input: SceneInput = {
    state,
    mosaic: { url: "m.png", extent: data.details["sample_map_20260930-200100"].mosaic! },
    scanBox: state.allowed_box_um,
    flags: data.flags[SAMPLE],
    candidates: data.candidates[SAMPLE],
    showRetired: false,
    showRejected: false,
    field: { x_um: 8026, y_um: 571.6, fov_um: 3900 },
    pin: null,
    staleFit: false,
  };

  it("draws every layer when all are on", () => {
    const layers = new Set(buildScene(input, ALL_LAYERS_ON).map((i) => i.layer));
    expect(layers).toEqual(new Set(["mosaic", "scanBox", "visits", "boundary", "candidates", "flags", "field"]));
  });

  it("drops a layer that is toggled off", () => {
    for (const l of ["mosaic", "candidates", "flags", "boundary"] as const) {
      const items = buildScene(input, { ...ALL_LAYERS_ON, [l]: false });
      expect(items.some((i) => i.layer === l)).toBe(false);
    }
  });

  it("marks candidates by source: hollow classical, filled confirmed, cross rejected", () => {
    const marks = (show: boolean) =>
      buildScene({ ...input, showRejected: show }, ALL_LAYERS_ON).flatMap((i) => (i.kind === "candidate" ? [[i.id, i.mark]] : []));
    expect(marks(false)).toEqual([
      ["c1", "hollow"],
      ["c3", "filled"],
    ]);
    expect(marks(true)).toContainEqual(["c4", "cross"]);
    expect(candidateMark({ ...data.candidates[SAMPLE][0], source: "person_rejected" })).toBe("cross");
  });

  it("draws a retired flag only on the toggle, and then as retired, never as active", () => {
    const flagsOf = (show: boolean) =>
      buildScene({ ...input, showRetired: show }, ALL_LAYERS_ON).flatMap((i) => (i.kind === "flag" ? [[i.id, i.retired]] : []));
    expect(flagsOf(false)).toEqual([["f1", false]]);
    expect(flagsOf(true)).toEqual([
      ["f1", false],
      ["f0", true],
    ]);
  });

  it("colours visits by verdict only", () => {
    const visits = buildScene(input, ALL_LAYERS_ON).filter((i) => i.layer === "visits");
    expect(visits.map((v) => (v.kind === "rect" ? v.style : null))).toEqual(["visit_in_focus"]);
  });
});

describe("click-to-move steps", () => {
  const ev = (kind: string, data: Record<string, unknown> = {}, op_id = "op-1"): EngineEvent => ({ kind, op_id, data });
  const run = (actions: Action[]): ClickMove => actions.reduce(clickMoveReducer, IDLE);

  it("goes plan -> retract confirm -> retract -> move -> arrived, Z left retracted", () => {
    const steps: [Action, string][] = [
      [{ type: "click", x_um: 7000, y_um: 1000 }, "submitting"],
      [{ type: "submitted", op_id: "op-1" }, "submitting"],
      [{ type: "event", ev: ev("planned", { distance_um: 1100, large_move: true, retract_needed: true, z_safe_um: 0 }) }, "planned"],
      [{ type: "event", ev: ev("confirm_required", { key: "retract_then_move", z_um: 3048.7, z_safe_um: 0 }) }, "confirm"],
      [{ type: "answered" }, "planned"],
      [{ type: "event", ev: ev("progress", { step: "retract" }) }, "retracting"],
      [{ type: "event", ev: ev("progress", { step: "move_xy" }) }, "moving"],
      [{ type: "event", ev: ev("finished", { x_um: 7000.2, y_um: 999.8, z_um: 0, retracted: true }) }, "arrived"],
    ];
    let s = IDLE;
    for (const [a, phase] of steps) {
      s = clickMoveReducer(s, a);
      // "submitted" with nothing buffered leaves the phase; it gains the op id
      expect(a.type === "submitted" ? s.op_id : s.phase).toBe(a.type === "submitted" ? "op-1" : phase);
    }
    expect(s.arrived).toEqual({ x_um: 7000.2, y_um: 999.8, z_um: 0, retracted: true });
    expect(clickMoveText(s)).toBe("Arrived (7000.2, 999.8 read back).");
  });

  it("shows the preflight reason when the target is outside the box", () => {
    const s = run([
      { type: "click", x_um: 20000, y_um: 0 },
      { type: "submitted", op_id: "op-1" },
      { type: "event", ev: ev("preflight_failed", { why: "outside the scan box + 1 mm" }) },
    ]);
    expect(s.phase).toBe("refused");
    expect(clickMoveText(s)).toBe("outside the scan box + 1 mm");
  });

  it("replays events that arrive before the POST returns", () => {
    const s = run([
      { type: "click", x_um: 1, y_um: 2 },
      { type: "event", ev: ev("planned", {}, "op-9") },
      { type: "event", ev: ev("preflight_failed", { why: "goto_xy is running" }, "op-9") },
      { type: "event", ev: ev("planned", {}, "op-other") },
      { type: "submitted", op_id: "op-9" },
    ]);
    expect(s.phase).toBe("refused");
    expect(s.why).toBe("goto_xy is running");
  });

  it("ignores other operations and a second click while moving", () => {
    let s = run([
      { type: "click", x_um: 1, y_um: 2 },
      { type: "submitted", op_id: "op-1" },
      { type: "event", ev: ev("planned") },
    ]);
    s = clickMoveReducer(s, { type: "event", ev: ev("finished", {}, "op-2") });
    expect(s.phase).toBe("planned");
    s = clickMoveReducer(s, { type: "click", x_um: 5, y_um: 5 });
    expect(s.target).toEqual([1, 2]);
  });

  it("ends with the reason on abort", () => {
    const s = run([
      { type: "click", x_um: 1, y_um: 2 },
      { type: "submitted", op_id: "op-1" },
      { type: "event", ev: ev("planned") },
      { type: "event", ev: ev("aborted", { why: "abort requested" }) },
    ]);
    expect(s.phase).toBe("ended");
    expect(clickMoveText(s)).toBe("Move stopped: abort requested");
  });
});
