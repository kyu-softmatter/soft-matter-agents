import { act, fireEvent, render as rtlRender, screen, waitFor, within } from "@testing-library/react";
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

function ExperimentsScreen() {
  const details = useMemo(() => ({ sample_id: "20260930_1849_1" }), []);
  useScreenContext(details);
  return <p>experiments screen</p>;
}

function ContextProbe() {
  const ctx = useCurrentScreenContext();
  return <output data-testid="ctx">{JSON.stringify(ctx)}</output>;
}

function withProbe(entries: AreaEntry[]): AreaEntry[] {
  // the probe stands in for the prompt box: it reads the context of the screen in view
  return entries.map((e) =>
    e.id === "experiments"
      ? { ...e, load: () => Promise.resolve({ default: () => (<><ExperimentsScreen /><ContextProbe /></>) }) }
      : e.id === "instruments"
        ? { ...e, load: () => Promise.resolve({ default: ContextProbe }) }
        : e,
  );
}

describe("Shell", () => {
  it("shows every area in the navigation and a placeholder for one with no screen", () => {
    render(<Shell registry={buildRegistry({})} />);
    const nav = screen.getByRole("navigation", { name: "Areas" });
    expect(nav.querySelectorAll("a")).toHaveLength(AREAS.filter((a) => !("adminOnly" in a)).length);
    expect(screen.queryByRole("link", { name: "Admin" })).toBeNull();
    expect(screen.getByText("Questions: not implemented yet")).toBeTruthy();
    expect(screen.getByText("Soft-matter agents")).toBeTruthy();
  });

  it("shows the admin-only areas to an admin", () => {
    render(<Shell registry={buildRegistry({})} admin />);
    const nav = screen.getByRole("navigation", { name: "Areas" });
    expect(nav.querySelectorAll("a")).toHaveLength(AREAS.length);
    expect(screen.getByRole("link", { name: "Admin" })).toBeTruthy();
  });

  it("switches area from the navigation and updates the hash", () => {
    render(<Shell registry={buildRegistry({})} />);
    fireEvent.click(screen.getByRole("link", { name: "Library" }));
    expect(window.location.hash).toBe("#/library");
    expect(screen.getByText("Library: not implemented yet")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Library" }).getAttribute("aria-current")).toBe("page");
  });

  it("follows a hash change from outside (back button, link)", () => {
    render(<Shell registry={buildRegistry({})} />);
    act(() => {
      window.location.hash = "#/results";
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(screen.getByText("Results: not implemented yet")).toBeTruthy();
  });

  it("lazy-loads a registered screen and passes its context on with the area", async () => {
    window.location.hash = "#/experiments";
    render(<Shell registry={withProbe(buildRegistry({}))} />);
    expect(await screen.findByText("experiments screen")).toBeTruthy();
    await waitFor(() =>
      expect(JSON.parse(screen.getByTestId("ctx").textContent ?? "{}")).toEqual({
        area: "experiments",
        sample_id: "20260930_1849_1",
      }),
    );
  });

  it("drops the previous screen's context when the area changes", async () => {
    window.location.hash = "#/experiments";
    render(<Shell registry={withProbe(buildRegistry({}))} />);
    await screen.findByText("experiments screen");
    fireEvent.click(screen.getByRole("link", { name: "Instruments" }));
    await waitFor(() =>
      expect(JSON.parse(screen.getByTestId("ctx").textContent ?? "{}")).toEqual({ area: "instruments" }),
    );
  });

  it("shows a load failure inside the area, not a blank app", async () => {
    window.location.hash = "#/library";
    const broken = buildRegistry({}).map((e) =>
      e.id === "library" ? { ...e, load: () => Promise.reject(new Error("chunk missing")) } : e,
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

  it("has a footer on every screen, with what the app puts in it, and no prompt box or side panel", () => {
    render(<Shell registry={buildRegistry({})} footer={<span>footer here</span>} />);
    expect(within(screen.getByTestId("shell-footer")).getByText("footer here")).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Prompt" })).toBeNull();
    expect(document.querySelector("aside")).toBeNull();
  });

  it("does not open an administrator-only area for anyone else", () => {
    window.location.hash = "#/admin";
    render(<Shell registry={buildRegistry({})} />);
    expect(screen.getByText("Questions: not implemented yet")).toBeTruthy();
    expect(screen.queryByText("Admin: not implemented yet")).toBeNull();
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
