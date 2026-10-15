import { describe, expect, it } from "vitest";

import { firstProblem, patternDuration, patternTime, sampleTrack, timeColor, type Track } from "./model";
import { DEFAULT_SHAPE, fromCsv, generate, toCsv } from "./shapes";

const track: Track = { target: "piezo", points: [[0, 0, 0, 0], [2, 10, 0, 4], [4, 10, 10, 4]] };

describe("pattern model", () => {
  it("interpolates between points and holds at the ends", () => {
    expect(sampleTrack(track, 1)).toEqual([1, 5, 0, 2]);
    expect(sampleTrack(track, -1)).toEqual([0, 0, 0, 0]);
    expect(sampleTrack(track, 9)).toEqual([4, 10, 10, 4]);
  });

  it("wraps a looping pattern and clamps one that does not", () => {
    expect(patternDuration({ tracks: [track] })).toBe(4);
    expect(patternTime({ tracks: [track], loop: true }, 5)).toBe(1);
    expect(patternTime({ tracks: [track], loop: false }, 5)).toBe(4);
  });

  it("colours time from gray to dark green", () => {
    expect(timeColor(0)).toBe("rgb(158, 158, 158)");
    expect(timeColor(1)).toBe("rgb(27, 94, 32)");
    expect(timeColor(2)).toBe(timeColor(1));
  });

  it("names the first problem the server would refuse", () => {
    expect(firstProblem({ tracks: [track] })).toBeNull();
    expect(firstProblem({ tracks: [] })).toContain("at least one track");
    expect(firstProblem({ tracks: [track, track] })).toContain("one track only");
    expect(firstProblem({ tracks: [{ target: "trap:0", points: [[0, 0, 0, 0], [1, 61, 0, 0]] }] })).toContain(
      "outside -60..60",
    );
    expect(firstProblem({ tracks: [{ target: "piezo", points: [[0], [0]] }] })).toContain("time must go up");
    expect(firstProblem({ tracks: [{ target: "piezo", points: [[0, 0, 0, 0], [4000, 0, 0, 0]] }] })).toContain("at most 3600 s");
  });
});

describe("shapes", () => {
  it("makes a circle that starts at 0 s, ends at its duration and closes", () => {
    const pts = generate({ ...DEFAULT_SHAPE, kind: "circle", r: 5, n: 1, duration_s: 2, rate_hz: 10 });
    expect(pts).toHaveLength(21);
    expect(pts[0]).toEqual([0, 5, 0, 0]);
    expect(pts[20][0]).toBe(2);
    expect(pts[20][1]).toBeCloseTo(5);
    expect(pts[20][2]).toBeCloseTo(0);
  });

  it("ramps z over the shape (a helix for the piezo)", () => {
    const pts = generate({ ...DEFAULT_SHAPE, z0: -2, z1: 2, duration_s: 1, rate_hz: 4 });
    expect(pts.map((p) => p[3])).toEqual([-2, -1, 0, 1, 2]);
  });

  it("rasters back and forth across the box", () => {
    const pts = generate({ ...DEFAULT_SHAPE, kind: "raster", r: 10, h: 10, n: 2, duration_s: 4, rate_hz: 1 });
    expect(pts.map((p) => [p[1], p[2]])).toEqual([[-5, -5], [0, -5], [5, 5], [0, 5], [-5, 5]]);
  });

  it("round-trips points through CSV and skips comments", () => {
    const pts = generate({ ...DEFAULT_SHAPE, kind: "line", duration_s: 1, rate_hz: 2 });
    expect(fromCsv(toCsv(pts))).toEqual(pts);
    expect(fromCsv("# t x y z\n0, 1, 2\n1 3 4 5\n")).toEqual([[0, 1, 2, 0], [1, 3, 4, 5]]);
  });
});
