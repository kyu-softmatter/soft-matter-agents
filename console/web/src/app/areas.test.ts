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
    const r = buildRegistry({ "../features/experiments/index.tsx": screen });
    expect(r.find((e) => e.id === "experiments")?.load).toBe(screen);
    expect(r.find((e) => e.id === "instruments")?.load).toBeUndefined();
  });

  it("ignores a feature folder that is not an area, and says so", () => {
    const warn = vi.fn();
    const r = buildRegistry({ "../features/extra/index.tsx": screen }, warn);
    expect(r).toHaveLength(AREAS.length);
    expect(warn).toHaveBeenCalledWith(expect.stringContaining("features/extra"));
  });

  it("keeps a screen folder that is in no navigation out of the registry without a warning", () => {
    const warn = vi.fn();
    const r = buildRegistry({ "../features/live/index.tsx": screen }, warn);
    expect(r.map((e) => e.id)).not.toContain("live");
    expect(warn).not.toHaveBeenCalled();
  });

  it("reads only <id>/index.tsx paths", () => {
    expect(areaIdOfPath("../features/live/index.tsx")).toBe("live");
    expect(areaIdOfPath("../features/live/View.tsx")).toBeNull();
  });

  it("has the six areas and, for an administrator only, Admin (console card 008)", () => {
    expect(registry.map((e) => e.id)).toEqual([
      "questions", "instruments", "experiments", "simulation", "library", "results", "admin",
    ]);
    expect(registry.filter((e) => e.adminOnly).map((e) => e.id)).toEqual(["admin"]);
  });
});

describe("hash routing", () => {
  it("maps hashes to areas and falls back to Questions", () => {
    expect(areaFromHash("#/library")).toBe("library");
    expect(areaFromHash("#/library/flags?x=1")).toBe("library");
    expect(areaFromHash("")).toBe("questions");
    expect(areaFromHash("#/nowhere")).toBe("questions");
    expect(hashOfArea("instruments")).toBe("#/instruments");
  });

  it("passes everything after the area through as rest", () => {
    expect(parseHash("#/simulation/runs/run-20260924-001")).toEqual({
      area: "simulation",
      rest: "runs/run-20260924-001",
    });
    expect(parseHash("#/experiments?sample_id=20260930_1849_1")).toEqual({
      area: "experiments",
      rest: "?sample_id=20260930_1849_1",
    });
    expect(parseHash("#/experiments")).toEqual({ area: "experiments", rest: "" });
    expect(parseHash("#/nowhere/x")).toEqual({ area: "questions", rest: "" });
  });

  it("builds hrefs that parse back to the same route", () => {
    for (const [area, rest] of [["simulation", "runs/r1"], ["experiments", "?x=1"], ["instruments", ""]] as const) {
      expect(parseHash(areaHref(area, rest))).toEqual({ area, rest });
    }
    expect(areaHref("questions", "/questions/q1")).toBe("#/questions/questions/q1");
  });
});
