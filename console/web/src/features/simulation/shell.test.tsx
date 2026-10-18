import { act, fireEvent, render, screen } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { buildRegistry } from "../../app/areas";
import { Shell } from "../../app/Shell";

// The screen inside the real shell and hash routing, as the app runs it (main.tsx: StrictMode).
const registry = buildRegistry({ "../features/simulation/index.tsx": () => import("./index") });

beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
});
afterEach(() => {
  vi.restoreAllMocks();
});

async function openFromList() {
  const link = await screen.findByRole("link", { name: "mock-sim-2d-done" }, { timeout: 5000 });
  fireEvent.click(link);
  expect(window.location.hash).toBe("#/simulation/runs/mock-sim-2d-done");
  expect(await screen.findByRole("heading", { name: "mock-sim-2d-done" })).toBeTruthy();
  expect(await screen.findByRole("region", { name: "Progress" })).toBeTruthy();
  expect(screen.getByRole("link", { name: "Simulation" }).getAttribute("aria-current")).toBe("page");
  expect(window.location.hash).toBe("#/simulation/runs/mock-sim-2d-done");
}

describe("simulation screen in the shell", () => {
  it("keeps #/simulation/runs/<run_id> when a run is clicked, and shows the run", async () => {
    window.location.hash = "#/simulation";
    render(
      <StrictMode>
        <Shell registry={registry} />
      </StrictMode>,
    );
    await openFromList();
  });

  it("does the same after arriving from the navigation", async () => {
    window.location.hash = "";
    render(
      <StrictMode>
        <Shell registry={registry} />
      </StrictMode>,
    );
    fireEvent.click(screen.getByRole("link", { name: "Simulation" }));
    await openFromList();
    // back to the list, then a direct link from another area (the console's form)
    fireEvent.click(screen.getByRole("link", { name: "← all runs" }));
    expect(window.location.hash).toBe("#/simulation");
    await act(async () => {
      window.location.hash = "#/simulation/runs/mock-sim-3d-fault";
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(await screen.findByRole("heading", { name: "mock-sim-3d-fault" })).toBeTruthy();
  });
});
