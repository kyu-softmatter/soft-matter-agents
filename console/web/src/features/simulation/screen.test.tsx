import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { type ReactNode, useMemo } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { ScreenContextProvider, useCurrentScreenContext } from "../../app/screenContext";
import { fakeTransport } from "../../test/fakes";
import { SimulationClientContext } from "./client";
import { fakeClient } from "./fakeClient";
import { type Frame, frameFromJson } from "./frame";
import SimulationScreen from "./index";
import { usePlayback } from "./playback";
import { Viewers, type Viewer3DProps } from "./Viewers";

const T = 1_000_000_000_000;

beforeEach(() => {
  // jsdom has no canvas; the viewer skips drawing without a context
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
});
afterEach(() => {
  vi.restoreAllMocks();
});

function ContextProbe() {
  return <output data-testid="ctx">{JSON.stringify(useCurrentScreenContext())}</output>;
}

function App({ children }: { children?: ReactNode }) {
  const client = useMemo(() => fakeClient(() => T), []);
  return (
    <ScreenContextProvider area="simulation">
      <SimulationClientContext.Provider value={client}>
        <SimulationScreen />
        <ContextProbe />
        {children}
      </SimulationClientContext.Provider>
    </ScreenContextProvider>
  );
}

describe("simulation screen", () => {
  it("lists the runs and opens one into the hash and the prompt context", async () => {
    window.location.hash = "#/simulation";
    render(<App />);
    const table = await screen.findByRole("table", { name: "Simulation runs" });
    expect(within(table).getAllByRole("row")).toHaveLength(4);
    expect(screen.getByText("mock data")).toBeTruthy();
    expect(screen.getByTestId("ctx").textContent).toBe('{"area":"simulation"}');

    fireEvent.click(screen.getByRole("link", { name: "mock-sim-2d-done" }));
    expect(window.location.hash).toBe("#/simulation/runs/mock-sim-2d-done");
    expect(await screen.findByRole("heading", { name: "mock-sim-2d-done" })).toBeTruthy();
    await waitFor(() => expect(screen.getByTestId("ctx").textContent).toContain('"run_id":"mock-sim-2d-done"'));

    fireEvent.click(screen.getByRole("link", { name: "← all runs" }));
    expect(window.location.hash).toBe("#/simulation");
    expect(await screen.findByRole("table", { name: "Simulation runs" })).toBeTruthy();
  });

  it("shows progress, frames, playback and graphs of a run linked to directly", async () => {
    window.location.hash = "#/simulation/runs/mock-sim-2d-done";
    render(<App />);
    const progress = await screen.findByRole("region", { name: "Progress" });
    expect(within(progress).getByText("complete")).toBeTruthy();
    expect(within(progress).getByText("10000 / 10000")).toBeTruthy();
    expect(within(progress).getByText("planned_duration_reached")).toBeTruthy();

    expect(await screen.findByRole("img", { name: "Frame 0, 64 particles, xy plane" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Next frame" }));
    expect(await screen.findByRole("img", { name: "Frame 1, 64 particles, xy plane" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Last frame" }));
    expect(await screen.findByRole("img", { name: "Frame 200, 64 particles, xy plane" })).toBeTruthy();

    const graphs = await screen.findByRole("region", { name: "Graphs" });
    expect(within(graphs).getByRole("img", { name: "temperature" })).toBeTruthy();
    expect(within(graphs).getByRole("img", { name: "msd_curve" })).toBeTruthy();
    expect(within(graphs).getByRole("table", { name: "Observable values" })).toBeTruthy();

    const dl = screen.getByRole("region", { name: "Download" });
    expect(within(dl).getByRole("button", { name: "Download mock-sim-2d-done.zip" })).toHaveProperty("disabled", true);
    expect(await within(dl).findByText(/include trajectory\.npz/)).toBeTruthy();
  });

  it("says when a run faulted, and when the 3D viewer is not there", async () => {
    window.location.hash = "#/simulation/runs/mock-sim-3d-fault";
    render(<App />);
    const progress = await screen.findByRole("region", { name: "Progress" });
    expect(within(progress).getByText("fault")).toBeTruthy();
    expect(within(progress).getByText("step_displacement_diverged")).toBeTruthy();
    expect(await screen.findByRole("img", { name: "Frame 0, 128 particles, xy plane" })).toBeTruthy();
    fireEvent.change(screen.getByRole("combobox", { name: "Plane" }), { target: { value: "xz" } });
    expect(screen.getByRole("img", { name: "Frame 0, 128 particles, xz plane" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "3D" }));
    expect(screen.getByText(/3D viewer: not available yet|Loading 3D viewer/)).toBeTruthy();
  });

  it("updates a running run from its pushed progress", async () => {
    let t = T;
    const client = fakeClient(() => t);
    window.location.hash = "#/simulation/runs/mock-sim-2d-running";
    render(
      <ScreenContextProvider area="simulation">
        <SimulationClientContext.Provider value={client}>
          <SimulationScreen />
        </SimulationClientContext.Provider>
      </ScreenContextProvider>,
    );
    const progress = await screen.findByRole("region", { name: "Progress" });
    expect(within(progress).getByText("3000 / 60000")).toBeTruthy(); // 30 s at 100 steps/s
    expect(within(progress).getByText(/expected end/)).toBeTruthy();
    t += 10_000;
    expect(await within(progress).findByText("4000 / 60000", undefined, { timeout: 3000 })).toBeTruthy();
  });

  it("reports a run that does not exist", async () => {
    window.location.hash = "#/simulation/runs/nope";
    render(<App />);
    expect((await screen.findByRole("alert")).textContent).toContain("no simulation run nope");
  });
});

describe("simulation screen on the server", () => {
  it("reads the runs through the app's shared client when there is one", async () => {
    const runs = (await fakeClient(() => T).listRuns()).map((r) => ({ ...r, source: "soft-matter-agents" }));
    const { transport, calls } = fakeTransport({ "/api/simulation/runs": () => ({ status: 200, body: runs }) });
    window.location.hash = "#/simulation";
    render(
      <ScreenContextProvider area="simulation">
        <ClientProvider client={new Client(transport, "127.0.0.1")}>
          <SimulationScreen />
        </ClientProvider>
      </ScreenContextProvider>,
    );
    const table = await screen.findByRole("table", { name: "Simulation runs" });
    expect(within(table).getAllByRole("row")).toHaveLength(4);
    expect(screen.queryByText("mock data")).toBeNull();
    expect(calls.map((c) => c.path)).toContain("/api/simulation/runs");
  });
});

describe("Viewers 2D/3D switch", () => {
  const frames: Frame[] = [0, 1].map((i) =>
    frameFromJson({ index: i, step: i * 10, n: 1, dimensions: 3, units: "m", box: [1, 1, 1, 0, 0, 0], types: ["A"], typeid: [0], positions: [i, 0, 0], fields: {} }),
  );

  it("hands the 3D viewer the frame the shared controls choose", () => {
    const seen: (Frame | null)[] = [];
    function Fake3D(props: Viewer3DProps) {
      seen.push(props.frame);
      return <p>3d frame {props.frame?.index}</p>;
    }
    function Harness() {
      const p = usePlayback(frames.length);
      return <Viewers frame={frames[p.index]} nFrames={frames.length} playback={p} error={null} viewer3d={Fake3D} />;
    }
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "3D" }));
    expect(screen.getByText("3d frame 0")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Next frame" }));
    expect(screen.getByText("3d frame 1")).toBeTruthy();
    expect(seen.at(-1)).toBe(frames[1]);
    fireEvent.click(screen.getByRole("button", { name: "2D" }));
    expect(screen.getByRole("img", { name: "Frame 1, 1 particles, xy plane" })).toBeTruthy();
  });
});
