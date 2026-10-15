import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { fmt, HistogramChart, LineChart, linePath, scaleOf } from "./Charts";

describe("chart geometry", () => {
  it("takes the range of the finite values", () => {
    expect(scaleOf([3, null, 1, Number.NaN, 2], false)).toEqual({ lo: 1, hi: 3, log: false });
    expect(scaleOf([0, -1, 10, 1000], true)).toEqual({ lo: 1, hi: 3, log: true });
    expect(scaleOf([null], false)).toBeNull();
    const flat = scaleOf([5, 5], false)!;
    expect(flat.lo).toBeLessThan(5);
    expect(flat.hi).toBeGreaterThan(5);
  });

  it("breaks the line at a missing value", () => {
    const sx = scaleOf([0, 1, 2, 3], false)!;
    const sy = scaleOf([0, 1], false)!;
    const d = linePath([0, 1, 2, 3], [0, 1, null, 0], sx, sy);
    expect(d.match(/M/g)).toHaveLength(2);
    expect(d.match(/L/g)).toHaveLength(1);
  });

  it("formats numbers for labels", () => {
    expect(fmt(2.1e-13)).toBe("2.100e-13");
    expect(fmt(293.04567)).toBe("293");
    expect(fmt(0)).toBe("0");
    expect(fmt(null)).toBe("–");
  });
});

describe("charts", () => {
  it("draws a line chart with its title and ranges", () => {
    render(<LineChart title="temperature" x={[0, 10, 20]} y={[293, 294, 292]} xLabel="steps_taken" />);
    expect(screen.getByRole("img", { name: "temperature" }).querySelector("path")?.getAttribute("d")).toMatch(/^M/);
    expect(screen.getByText(/steps_taken 0 … 20/)).toBeTruthy();
  });

  it("says when there is nothing to draw", () => {
    render(<LineChart title="empty" x={[]} y={[]} />);
    expect(screen.getByText("no values to draw")).toBeTruthy();
  });

  it("draws one bar per bin", () => {
    render(<HistogramChart title="hist" edges={[0, 1, 2, 3]} counts={[4, 0, 2]} />);
    expect(screen.getByRole("img", { name: "hist" }).querySelectorAll("rect.sim-chart-bar")).toHaveLength(3);
  });
});
