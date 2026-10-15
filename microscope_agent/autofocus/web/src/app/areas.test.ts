import { describe, expect, it, vi } from "vitest";

import { AREAS, areaIdOfPath, buildRegistry, registry } from "./areas";
import { areaFromHash, areaHref, hashOfArea, parseHash } from "./route";

const screen = () => Promise.resolve({ default: () => null });

describe("area registry", () => {
  it("lists every area in navigation order, with no screen yet as a placeholder", () => {
    const r = buildRegistry({});
    expect(r.map((e) => e.id)).toEqual(AREAS.map((a) => a.id));
    expect(r.every((e) => e.load === undefined)).toBe(true);
  });

  it("picks up features/<id>/index.tsx for a registered area", () => {
    const r = buildRegistry({ "../features/map/index.tsx": screen });
    expect(r.find((e) => e.id === "map")?.load).toBe(screen);
    expect(r.find((e) => e.id === "sample")?.load).toBeUndefined();
  });

  it("ignores a feature folder that is not an area, and says so", () => {
    const warn = vi.fn();
    const r = buildRegistry({ "../features/extra/index.tsx": screen }, warn);
    expect(r).toHaveLength(AREAS.length);
    expect(warn).toHaveBeenCalledWith(expect.stringContaining("features/extra"));
  });

  it("reads only <id>/index.tsx paths", () => {
    expect(areaIdOfPath("../features/live/index.tsx")).toBe("live");
    expect(areaIdOfPath("../features/live/View.tsx")).toBeNull();
  });

  it("has the six areas of T-010, simulation (PLAN v0.4), results, patterns, tweezers, sessions (T-106) and admin-only accounts", () => {
    expect(registry.map((e) => e.id)).toEqual([
      "console", "hardware", "sample", "map", "objective", "live", "simulation", "results", "patterns", "tweezers", "sessions", "accounts",
    ]);
    expect(registry.filter((e) => e.adminOnly).map((e) => e.id)).toEqual(["accounts"]);
  });
});

describe("hash routing", () => {
  it("maps hashes to areas and falls back to the console", () => {
    expect(areaFromHash("#/map")).toBe("map");
    expect(areaFromHash("#/map/flags?x=1")).toBe("map");
    expect(areaFromHash("")).toBe("console");
    expect(areaFromHash("#/nowhere")).toBe("console");
    expect(hashOfArea("live")).toBe("#/live");
  });

  it("passes everything after the area through as rest", () => {
    expect(parseHash("#/simulation/runs/run-20260924-001")).toEqual({
      area: "simulation",
      rest: "runs/run-20260924-001",
    });
    expect(parseHash("#/map?sample_id=20260930_1849_1")).toEqual({
      area: "map",
      rest: "?sample_id=20260930_1849_1",
    });
    expect(parseHash("#/map")).toEqual({ area: "map", rest: "" });
    expect(parseHash("#/nowhere/x")).toEqual({ area: "console", rest: "" });
  });

  it("builds hrefs that parse back to the same route", () => {
    for (const [area, rest] of [["simulation", "runs/r1"], ["map", "?x=1"], ["live", ""]] as const) {
      expect(parseHash(areaHref(area, rest))).toEqual({ area, rest });
    }
    expect(areaHref("console", "/questions/q1")).toBe("#/console/questions/q1");
  });
});
