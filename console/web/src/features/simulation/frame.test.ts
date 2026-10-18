import { describe, expect, it } from "vitest";

import { type FrameJson, FrameFormatError, frameFromJson } from "./frame";

// The shape of Python agents.simulation.Frame.to_dict() for a 2-particle 2D frame.
function json(over: Partial<FrameJson> = {}): FrameJson {
  return {
    index: 3,
    step: 300,
    n: 2,
    dimensions: 2,
    units: "m",
    box: [5e-5, 5e-5, 0, 0, 0, 0],
    types: ["A", "B"],
    typeid: [0, 1],
    positions: [1e-6, 2e-6, 0, -3e-6, 4e-6, 0],
    fields: {},
    ...over,
  };
}

describe("frameFromJson", () => {
  it("turns the server frame into typed arrays", () => {
    const f = frameFromJson(json());
    expect(f.n).toBe(2);
    expect(f.dimensions).toBe(2);
    expect(f.step).toBe(300);
    expect(f.box).toEqual([5e-5, 5e-5, 0, 0, 0, 0]);
    expect(f.positions).toBeInstanceOf(Float32Array);
    expect(f.positions).toHaveLength(6);
    expect(f.positions[3]).toBeCloseTo(-3e-6);
    expect(f.typeid).toBeInstanceOf(Int32Array);
    expect(Array.from(f.typeid)).toEqual([0, 1]);
    expect(f.types).toEqual(["A", "B"]);
  });

  it("flattens per-particle field rows", () => {
    const f = frameFromJson(json({ fields: { orientation: [[1, 0, 0, 0], [0, 1, 0, 0]], diameter: [1, 2] } }));
    expect(f.fields.orientation).toEqual([1, 0, 0, 0, 0, 1, 0, 0]);
    expect(f.fields.orientation.length / f.n).toBe(4);
    expect(f.fields.diameter).toEqual([1, 2]);
  });

  it("keeps a null step and an empty frame", () => {
    const f = frameFromJson(json({ step: null, n: 0, positions: [], typeid: [] }));
    expect(f.step).toBeNull();
    expect(f.n).toBe(0);
  });

  it.each([
    ["positions", { positions: [1, 2, 3] }],
    ["typeid", { typeid: [0] }],
    ["box", { box: [1, 1, 1] }],
    ["dimensions", { dimensions: 4 }],
    ["field", { fields: { diameter: [1, 2, 3] } }],
    ["field values", { fields: { diameter: ["x", 2] } }],
  ])("rejects a bad %s", (_name, over) => {
    expect(() => frameFromJson(json(over as Partial<FrameJson>))).toThrow(FrameFormatError);
  });
});
