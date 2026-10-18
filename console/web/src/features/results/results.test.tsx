import { configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { ScreenContextProvider } from "../../app/screenContext";
import { fakeTransport } from "../../test/fakes";
import { basicPanels, datasetsIn, targetsIn, theoryOf } from "./extract";
import ResultsScreen, { PATHS, seriesDatasets } from "./index";
import { scaleOf, ticks } from "./Plot";

configure({ asyncUtilTimeout: 8000 });

const RESULT = {
  card: "result",
  datasets: {
    msd: {
      x_name: "lag_s",
      units: { lag_s: "s", msd_um2: "um^2" },
      lag_s: [1, 2, 4],
      msd_um2: [0.9, 1.7, 3.5],
      msd_um2_theory: [0.84, 1.68, 3.36],
      label: "not a column",
    },
  },
  scalars: { D: 0.21 },
};

describe("extract", () => {
  it("finds same-length numeric arrays as one dataset, x from x_name, units", () => {
    const [d, ...more] = datasetsIn(RESULT, "result_x.json");
    expect(more).toEqual([]);
    expect(d.path).toBe("datasets.msd");
    expect(d.x).toBe("lag_s");
    expect(d.columns.map((c) => c.name)).toEqual(["lag_s", "msd_um2", "msd_um2_theory"]);
    expect(d.columns[1].unit).toBe("um^2");
  });

  it("ignores lone arrays, short arrays and arrays with text", () => {
    expect(datasetsIn({ a: [1, 2, 3], b: [1], c: ["x", 2] }, "s")).toEqual([]);
    expect(datasetsIn({ a: [1, 2], b: [3, 4] }, "s")).toHaveLength(1);
  });

  it("pairs theory columns with their measured column", () => {
    const cols = ["t", "y", "y_theory", "theory_z", "z"].map((name) => ({ name, values: [1, 2] }));
    expect(theoryOf("y_theory", cols)).toBe("y");
    expect(theoryOf("theory_z", cols)).toBe("z");
    expect(theoryOf("w_theory", cols)).toBeNull();
    const bare = ["t", "m", "theory"].map((name) => ({ name, values: [1, 2] }));
    expect(theoryOf("theory", bare)).toBe("m");
  });

  it("draws value-kind targets only", () => {
    const t = targetsIn({ targets: [
      { metric: "msd_um2", kind: "value", value: 2, unit: "um^2" },
      { metric: "msd_um2", kind: "decade_resolution", value: 1, unit: "count" },
      { metric: "x", value: "high" },
    ] });
    expect(t.map((e) => [e.kind, e.drawn])).toEqual([["value", true], ["decade_resolution", false]]);
    const [p] = basicPanels(datasetsIn(RESULT, "r"), t);
    expect(p.y.name).toBe("msd_um2");
    expect(p.theory?.name).toBe("msd_um2_theory");
    expect(p.targets.map((e) => e.value)).toEqual([2]);
  });

  it("makes round ticks and log decades", () => {
    expect(ticks({ lo: 0, hi: 10, log: false })).toEqual([0, 2, 4, 6, 8, 10]);
    expect(ticks(scaleOf([1, 1000], true)!)).toEqual([1, 10, 100, 1000]);
  });
});

function renderScreen(hash: string) {
  const q = { qid: "sim-1", agent: "simulation", title: "relaxation", status: "VALIDATED", created_at: null,
    updated_at: null, latest_version: 1, versions: [1], source: "mock" };
  const card = (name: string, data: unknown) => ({ name, kind: "result", version: 1, status: null, created_at: null, data });
  const t = fakeTransport({
    [PATHS.questions]: () => ({ status: 200, body: [q] }),
    [PATHS.runs]: () => ({ status: 200, body: [{ run_id: "run-1", agent: "simulation", qid: "sim-1", plan_id: null,
      status: null, created_at: null, finished_at: null, backend: null, source: "mock" }] }),
    [PATHS.question("sim-1")]: () => ({ status: 200, body: {
      summary: q, version: 1, goal: card("goal.json", { targets: [{ metric: "msd_um2", kind: "value", value: 2, unit: "um^2" }] }),
      axes: [], plan: null, synthesis: null, refusals: [], results: [card("result_msd.json", RESULT)], others: [],
      documents: [], files: [] } }),
    [PATHS.simRuns]: () => ({ status: 200, body: [{ run_id: "run-1", qid: "sim-1" }, { run_id: "local-7", qid: "sim-1" }] }),
    [PATHS.simSeries("local-7")]: () => ({ status: 200, body: { run_id: "local-7", observable: null, scalars: {},
      observables: null, log: {}, curves: [{ path: "energy", x_name: "step", x: [0, 1, 2], y: [5, 4, 3], kind: "line" }] } }),
    [PATHS.run("simulation", "run-1")]: () => ({ status: 200, body: { summary: {}, records: {
      "observables.json": { curve: { time_si: [0, 100], psi6: [0.3, 0.8] } } }, files: [], not_opened: [] } }),
  });
  window.location.hash = hash;
  render(
    <ClientProvider client={new Client(t.transport, "localhost")}>
      <ScreenContextProvider area="results">
        <ResultsScreen />
      </ScreenContextProvider>
    </ClientProvider>,
  );
  return t;
}

describe("simulation series", () => {
  it("turns log columns and curves into datasets named by x_name and path", () => {
    const ds = seriesDatasets({ run_id: "s1", observable: null, scalars: {}, observables: null,
      log: { step: [0, 1, 2], energy: [3, 2, 1] },
      curves: [{ path: "psi6_curve.psi6_global", x_name: "time_si", x: [0, 1], y: [0.1, 0.2], kind: "line" }] }, "s1");
    expect(ds.map((d) => [d.source, d.x, d.columns.map((c) => c.name)])).toEqual([
      ["s1/log", "step", ["step", "energy"]],
      ["s1/psi6_curve.psi6_global", "time_si", ["time_si", "psi6_curve.psi6_global"]],
    ]);
  });
});

describe("results screen", () => {
  it("lists qids and opens one on click", async () => {
    renderScreen("#/results");
    fireEvent.click(await screen.findByRole("button", { name: /sim-1/ }));
    expect(window.location.hash).toBe("#/results/sim-1");
    expect(await screen.findByRole("heading", { name: "sim-1" })).toBeTruthy();
  });

  it("draws basic plots with dashed theory and a target line, from cards and runs", async () => {
    const t = renderScreen("#/results/sim-1");
    const msd = await screen.findByRole("img", { name: /msd_um2 · result_msd.json/ });
    expect(within(msd.closest("figure")!).getAllByTestId("theory-line")).toHaveLength(1);
    expect(within(msd.closest("figure")!).getAllByTestId("target-line")).toHaveLength(1);
    expect(screen.getByRole("img", { name: /psi6 · run-1\/observables.json/ })).toBeTruthy();
    // the run's dataset has no theory column, so no dashed line there
    const psi = screen.getByRole("img", { name: /psi6 · run-1/ }).closest("figure")!;
    expect(within(psi).queryAllByTestId("theory-line")).toHaveLength(0);
    // a local simulation run of the qid; run-1 is the console's and is not read twice
    expect(screen.getByRole("img", { name: /energy · local-7\/energy/ })).toBeTruthy();
    expect(t.calls.some((c) => c.path === PATHS.simSeries("run-1"))).toBe(false);
  });

  it("takes a malformed escape in the route as written", async () => {
    renderScreen("#/results/sim-1%");
    expect(await screen.findByText(/Loading sim-1%|sim-1%:/)).toBeTruthy();
  });

  it("explorer: picks x and y columns and redraws", async () => {
    renderScreen("#/results/sim-1");
    const ex = await screen.findByRole("region", { name: "Explore" });
    expect(within(ex).getByRole("img", { name: "msd_um2 vs lag_s" })).toBeTruthy();
    expect(within(ex).getAllByTestId("theory-line")).toHaveLength(1);
    fireEvent.click(within(ex).getByRole("checkbox", { name: /theory \(dashed\)/ }));
    expect(within(ex).queryAllByTestId("theory-line")).toHaveLength(0);
    fireEvent.change(within(ex).getByRole("combobox", { name: /X axis/ }), { target: { value: "msd_um2_theory" } });
    const yPick = ex.querySelector("details.res-ypick") as HTMLDetailsElement;
    expect(yPick.open).toBe(false);
    expect(yPick.querySelector("summary")?.textContent).toBe("Y axis msd_um2");
    fireEvent.click(yPick.querySelector("summary")!);
    expect(yPick.open).toBe(true);
    fireEvent.click(within(ex).getByRole("checkbox", { name: /^lag_s/ }));
    expect(yPick.querySelector("summary")?.textContent).toBe("Y axis msd_um2, lag_s");
    fireEvent.mouseDown(document.body);
    expect(yPick.open).toBe(false);
    await waitFor(() => expect(within(ex).getByRole("img", { name: "msd_um2, lag_s vs msd_um2_theory" })).toBeTruthy());
    fireEvent.change(within(ex).getByRole("combobox", { name: /Dataset/ }), { target: { value: "run-1/observables.json:curve" } });
    expect(within(ex).getByRole("img", { name: "psi6 vs time_si" })).toBeTruthy();
  });
});
