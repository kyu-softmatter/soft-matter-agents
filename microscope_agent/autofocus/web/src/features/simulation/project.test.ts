import { describe, expect, it } from "vitest";

import { type Frame, frameFromJson } from "./frame";
import { projectFrame, typeColor, TYPE_COLORS } from "./project";

function frame(positions: number[], box = [10, 10, 0, 0, 0, 0], dimensions = 2, fields = {}): Frame {
  const n = positions.length / 3;
  return frameFromJson({
    index: 0,
    step: 0,
    n,
    dimensions,
    units: "m",
    box,
    types: ["A", "B"],
    typeid: Array.from({ length: n }, (_, i) => i % 2),
    positions,
    fields,
  });
}

describe("projectFrame", () => {
  it("fits the box into the canvas, y up", () => {
    // corners of a 10 x 10 box centred on 0, on a 120 px canvas with a 10 px margin
    const p = projectFrame(frame([-5, -5, 0, 5, 5, 0, 0, 0, 0]), "xy", 120, false, 10);
    expect(p.box).toEqual({ x: 10, y: 10, w: 100, h: 100 });
    expect([p.xs[0], p.ys[0]]).toEqual([10, 110]); // (-5, -5): bottom left
    expect([p.xs[1], p.ys[1]]).toEqual([110, 10]); // (5, 5): top right
    expect([p.xs[2], p.ys[2]]).toEqual([60, 60]);
  });

  it("folds unwrapped positions back into the box when asked", () => {
    const f = frame([12, -7, 0]); // one box over in x, half a box under in y
    const wrapped = projectFrame(f, "xy", 120, true, 10);
    expect(wrapped.xs[0]).toBeCloseTo(80); // x = 2
    expect(wrapped.ys[0]).toBeCloseTo(30); // y = 3
    const raw = projectFrame(f, "xy", 120, false, 10);
    expect(raw.xs[0]).toBeGreaterThan(wrapped.xs[0]);
  });

  it("uses the data range on an axis the box does not span", () => {
    // a 3D frame seen from xz with Lz = 0 in the box (no extent): z from the data
    const p = projectFrame(frame([0, 0, -2, 0, 0, 2], [10, 10, 0, 0, 0, 0], 3), "xz", 120, true, 10);
    expect(p.box).toBeNull();
    expect(p.ys[0]).toBeGreaterThan(p.ys[1]);
  });

  it("draws diameters to scale when the frame has them", () => {
    const p = projectFrame(frame([0, 0, 0, 1, 1, 0], undefined, 2, { diameter: [2, 1] }), "xy", 120, true, 10);
    expect(p.r[0]).toBeCloseTo(10); // radius 1 of a 10 unit box on 100 px
    expect(p.r[1]).toBeCloseTo(5);
  });

  it("colors by type, cycling", () => {
    expect(typeColor(0)).toBe(TYPE_COLORS[0]);
    expect(typeColor(TYPE_COLORS.length + 1)).toBe(TYPE_COLORS[1]);
    expect(typeColor(-1)).toBe(TYPE_COLORS[TYPE_COLORS.length - 1]);
  });
});
