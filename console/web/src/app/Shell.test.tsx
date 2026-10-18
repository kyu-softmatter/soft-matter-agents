import { act, fireEvent, render as rtlRender, screen, waitFor } from "@testing-library/react";
import { type ReactNode, useEffect, useMemo } from "react";
import { describe, expect, it } from "vitest";

import { AREAS, type AreaEntry, buildRegistry } from "./areas";
import { useAreaPath } from "./route";
import { useCurrentScreenContext, useScreenContext } from "./screenContext";
import { fakeTransport } from "../test/fakes";
import { assistantLoaderFrom, AssistantSlotView } from "./AssistantSlot";
import { Client, ClientProvider } from "./client";
import { Shell } from "./Shell";

// The shell runs inside the client provider in the app (the prompt box and screens use it).
function render(ui: ReactNode) {
  const client = new Client(fakeTransport({}).transport, "127.0.0.1");
  return rtlRender(<ClientProvider client={client}>{ui}</ClientProvider>);
}

let simulationMounts = 0;

function SimulationScreen() {
  const [rest, setRest] = useAreaPath();
  useEffect(() => {
    simulationMounts += 1; // counted at commit: a remount would add one
  }, []);
  return (
    <div>
      <p data-testid="rest">{rest}</p>
      <button onClick={() => setRest("runs/r2")}>open r2</button>
    </div>
  );
}

function MapScreen() {
  const details = useMemo(() => ({ sample_id: "20260930_1849_1" }), []);
  useScreenContext(details);
  return <p>map screen</p>;
}

function ContextProbe() {
  const ctx = useCurrentScreenContext();
  return <output data-testid="ctx">{JSON.stringify(ctx)}</output>;
}

function withProbe(entries: AreaEntry[]): AreaEntry[] {
  // the probe stands in for the prompt box: it reads the context of the screen in view
  return entries.map((e) =>
    e.id === "map"
      ? { ...e, load: () => Promise.resolve({ default: () => (<><MapScreen /><ContextProbe /></>) }) }
      : e.id === "sample"
        ? { ...e, load: () => Promise.resolve({ default: ContextProbe }) }
        : e,
  );
}

describe("Shell", () => {
  it("shows every area in the navigation and a placeholder for one with no screen", () => {
    render(<Shell registry={buildRegistry({})} />);
    const nav = screen.getByRole("navigation", { name: "Areas" });
    expect(nav.querySelectorAll("a")).toHaveLength(AREAS.filter((a) => !("adminOnly" in a)).length);
    expect(screen.queryByRole("link", { name: "Accounts" })).toBeNull();
    expect(screen.getByText("Console: not implemented yet")).toBeTruthy();
    expect(screen.getByText("Takatori Lab Console")).toBeTruthy();
  });

  it("shows the admin-only areas to an admin", () => {
    render(<Shell registry={buildRegistry({})} admin />);
    const nav = screen.getByRole("navigation", { name: "Areas" });
    expect(nav.querySelectorAll("a")).toHaveLength(AREAS.length);
    expect(screen.getByRole("link", { name: "Accounts" })).toBeTruthy();
  });

  it("switches area from the navigation and updates the hash", () => {
    render(<Shell registry={buildRegistry({})} />);
    fireEvent.click(screen.getByRole("link", { name: "Objective" }));
    expect(window.location.hash).toBe("#/objective");
    expect(screen.getByText("Objective: not implemented yet")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Objective" }).getAttribute("aria-current")).toBe("page");
  });

  it("follows a hash change from outside (back button, link)", () => {
    render(<Shell registry={buildRegistry({})} />);
    act(() => {
      window.location.hash = "#/hardware";
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(screen.getByText("Hardware: not implemented yet")).toBeTruthy();
  });

  it("lazy-loads a registered screen and passes its context on with the area", async () => {
    window.location.hash = "#/map";
    render(<Shell registry={withProbe(buildRegistry({}))} />);
    expect(await screen.findByText("map screen")).toBeTruthy();
    await waitFor(() =>
      expect(JSON.parse(screen.getByTestId("ctx").textContent ?? "{}")).toEqual({
        area: "map",
        sample_id: "20260930_1849_1",
      }),
    );
  });

  it("drops the previous screen's context when the area changes", async () => {
    window.location.hash = "#/map";
    render(<Shell registry={withProbe(buildRegistry({}))} />);
    await screen.findByText("map screen");
    fireEvent.click(screen.getByRole("link", { name: "Sample" }));
    await waitFor(() =>
      expect(JSON.parse(screen.getByTestId("ctx").textContent ?? "{}")).toEqual({ area: "sample" }),
    );
  });

  it("shows a load failure inside the area, not a blank app", async () => {
    window.location.hash = "#/live";
    const broken = buildRegistry({}).map((e) =>
      e.id === "live" ? { ...e, load: () => Promise.reject(new Error("chunk missing")) } : e,
    );
    const quiet = console.error;
    console.error = () => {};
    try {
      render(<Shell registry={broken} />);
      expect(await screen.findByRole("alert")).toBeTruthy();
      expect(screen.getByText(/chunk missing/)).toBeTruthy();
      expect(screen.getByRole("navigation", { name: "Areas" })).toBeTruthy();
    } finally {
      console.error = quiet;
    }
  });

  it("keeps a slot for the prompt box and the status bar", () => {
    // whatever T-014 puts in the slot, the region is there
    render(<Shell registry={buildRegistry({})} statusBar={<span>status here</span>} />);
    expect(screen.getByRole("region", { name: "Prompt" })).toBeTruthy();
    expect(screen.getByText("status here")).toBeTruthy();
  });

  it("shows a placeholder in the prompt slot while there is no prompt box", () => {
    render(<AssistantSlotView load={assistantLoaderFrom({})} />);
    expect(screen.getByText("Prompt box: not implemented yet")).toBeTruthy();
  });

  it("loads the prompt box into the slot when it exists", async () => {
    render(<AssistantSlotView load={() => Promise.resolve({ default: () => <p>prompt box</p> })} />);
    expect(await screen.findByText("prompt box")).toBeTruthy();
  });

  it("hands the rest of the hash to the area and keeps the screen mounted when it changes", async () => {
    simulationMounts = 0;
    window.location.hash = "#/simulation/runs/r1";
    const reg = buildRegistry({}).map((e) =>
      e.id === "simulation"
        ? { ...e, load: () => Promise.resolve({ default: SimulationScreen }) }
        : e,
    );
    render(<Shell registry={reg} />);
    expect((await screen.findByTestId("rest")).textContent).toBe("runs/r1");
    fireEvent.click(screen.getByRole("button", { name: "open r2" }));
    await waitFor(() => expect(screen.getByTestId("rest").textContent).toBe("runs/r2"));
    expect(window.location.hash).toBe("#/simulation/runs/r2");
    expect(simulationMounts).toBe(1);
    expect(screen.getByRole("link", { name: "Simulation" }).getAttribute("aria-current")).toBe("page");
  });
});
