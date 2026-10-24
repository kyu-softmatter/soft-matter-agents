import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { ScreenContextProvider, useCurrentScreenContext } from "../../app/screenContext";
import { fakeTransport } from "../../test/fakes";
import ConsoleScreen, { parseRest } from "./index";
import { changedKeys } from "./questions";
import { consoleRoutes, FAKE_DATA, type FakeData } from "./testData";

function ContextProbe() {
  return <output data-testid="ctx">{JSON.stringify(useCurrentScreenContext())}</output>;
}

// stop every client's event stream so no reconnect timer outlives its test
const clients: Client[] = [];
afterEach(() => {
  clients.splice(0).forEach((c) => c.events.stop());
});

function renderConsole(data: FakeData = FAKE_DATA, hash = "#/questions", hostname = "127.0.0.1") {
  window.location.hash = hash;
  const { routes, submitted } = consoleRoutes(data);
  const fake = fakeTransport(routes);
  const client = new Client(fake.transport, hostname);
  clients.push(client);
  const view = render(
    <ClientProvider client={client}>
      <ScreenContextProvider area="questions">
        <ConsoleScreen />
        <ContextProbe />
      </ScreenContextProvider>
    </ClientProvider>,
  );
  const gets = (path: string) => fake.calls.filter((c) => c.path === path && c.init?.method !== "POST").length;
  return { ...fake, client, submitted, gets, view };
}

const ctx = () => JSON.parse(screen.getByTestId("ctx").textContent ?? "{}");

describe("parseRest", () => {
  it("reads the documented forms and falls back to the first screen", () => {
    expect(parseRest("")).toEqual({ tab: "questions" });
    expect(parseRest("questions/sim-20260923-001")).toEqual({ tab: "questions", qid: "sim-20260923-001" });
    expect(parseRest("runs/simulation/run-1")).toEqual({ tab: "runs", agent: "simulation", runId: "run-1" });
    expect(parseRest("runs/nobody/run-1")).toEqual({ tab: "runs" });
    expect(parseRest("inbox")).toEqual({ tab: "inbox" });
    expect(parseRest("whatever")).toEqual({ tab: "questions" });
    expect(parseRest("ask")).toEqual({ tab: "questions" }); // the Ask tab is gone: the field is on the first screen
  });
});

describe("question detail", () => {
  it("shows card tabs of the latest version and switches between them", async () => {
    renderConsole(FAKE_DATA, "#/questions/questions/sim-20260923-001");
    const tabs = await screen.findByRole("tablist", { name: "Cards" });
    expect(within(tabs).getAllByRole("tab").map((t) => t.textContent)).toEqual(["goal", "axis a1", "axis a7"]);
    expect(screen.getByRole("article", { name: "Card v5_goal.json" })).toBeTruthy();

    fireEvent.click(within(tabs).getByRole("tab", { name: "axis a7" }));
    const card = screen.getByRole("article", { name: "Card v5_axis_bd_pairwise_a7.json" });
    expect(within(card).getByText("infeasible")).toBeTruthy();
    await waitFor(() =>
      expect(ctx()).toMatchObject({ area: "questions", qid: "sim-20260923-001", version: 5, card_kind: "axis" }),
    );
  });

  it("lists every version the store returns, past v3", async () => {
    const t = renderConsole(FAKE_DATA, "#/questions/questions/sim-20260923-001");
    const picker = (await screen.findByLabelText("Version")) as HTMLSelectElement;
    expect([...picker.options].map((o) => o.textContent)).toEqual(["v1", "v2", "v5 (latest)"]);

    fireEvent.change(picker, { target: { value: "1" } });
    expect(await screen.findByRole("article", { name: "Card goal.json" })).toBeTruthy();
    expect(t.gets("/api/console/questions/sim-20260923-001?version=1")).toBe(1);
    expect(screen.getByRole("tab", { name: "refusal" })).toBeTruthy();
  });

  it("shows grades exactly as the card has them, and the degraded banner", async () => {
    renderConsole(FAKE_DATA, "#/questions/questions/sim-20260923-001");
    const table = await screen.findByRole("table", { name: "Numbers" });
    const grades = within(table).getAllByTitle("grade as written on the card").map((g) => g.textContent);
    expect(grades).toEqual(["E2", "E4", "E9"]);
    expect(within(table).getByText("0.09")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("librarian unreachable");
  });

  it("compares two versions by card and field", async () => {
    renderConsole(FAKE_DATA, "#/questions/questions/sim-20260923-001");
    fireEvent.change(await screen.findByLabelText("Compare with"), { target: { value: "2" } });
    const diff = await screen.findByRole("table", { name: "Changes v5 to v2" });
    expect(within(diff).getByText("axis_bd_pairwise_a7.json").nextSibling?.textContent).toBe("changed: verdict");
    expect(within(diff).getByText("goal.json").nextSibling?.textContent).toBe("only in v5");
    expect(changedKeys({ a: 1, b: 2 }, { a: 1, b: 3, c: 0 })).toEqual(["b", "c"]);
  });
});

describe("runs and inbox", () => {
  it("links a simulation run to the simulation area", async () => {
    renderConsole(FAKE_DATA, "#/questions/runs/simulation/run-20260924-001-smoke-g2k2");
    const link = await screen.findByRole("link", { name: "Open in Simulation" });
    expect(link.getAttribute("href")).toBe("#/simulation/runs/run-20260924-001-smoke-g2k2");
    expect(screen.getByText(/Not opened: trajectory.gsd/)).toBeTruthy();
    expect(within(screen.getByRole("table", { name: "Events" })).getByText("complete")).toBeTruthy();
    await waitFor(() => expect(ctx()).toMatchObject({ run_id: "run-20260924-001-smoke-g2k2", agent: "simulation" }));
  });

  it("shows a microscope run's explanation fields and no simulation link", async () => {
    renderConsole(FAKE_DATA, "#/questions/runs/microscope/run-20260924-003");
    expect(await screen.findByText("No plan fits this run.")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Open in Simulation" })).toBeNull();
  });

  it("opens a run from the list, which shows the approval kind", async () => {
    renderConsole(FAKE_DATA, "#/questions/runs");
    expect(await screen.findByText("smoke_auto")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "run-20260924-003" }));
    expect(await screen.findByRole("region", { name: "Run run-20260924-003" })).toBeTruthy();
    expect(window.location.hash).toBe("#/questions/runs/microscope/run-20260924-003");
  });

  it("lists inbox threads with their rounds", async () => {
    renderConsole(FAKE_DATA, "#/questions/inbox");
    const inbox = await screen.findByRole("region", { name: "Inbox" });
    expect(within(inbox).getByText("thr-tracer-diffusivity-001")).toBeTruthy();
    expect(within(inbox).getByText("Round two.")).toBeTruthy();
  });
});

describe("the runs folder was not found (console card 005)", () => {
  it("says so in words, and does not show an empty list of runs", async () => {
    const why =
      "this project's microscope runs folder was not found in soft-matter-agents: neither " +
      "microscope_runtime/runs/ nor microscope_agent/runs/ is there. The console cannot see the runs, " +
      "which is not the same as there being none.";
    window.location.hash = "#/questions/runs";
    const { routes } = consoleRoutes(FAKE_DATA);
    const fake = fakeTransport({
      ...routes,
      "/api/console/runs": () => ({ status: 404, body: { detail: { code: "runs_not_found", message: why } } }),
    });
    const client = new Client(fake.transport, "127.0.0.1");
    clients.push(client);
    render(
      <ClientProvider client={client}>
        <ScreenContextProvider area="questions">
          <ConsoleScreen />
        </ScreenContextProvider>
      </ClientProvider>,
    );
    const alert = await screen.findByText(/runs folder was not found/);
    expect(alert.textContent).toBe(why);
    expect(alert.getAttribute("role")).toBe("alert");
    expect(screen.queryByText(/no runs/i)).toBeNull();
  });
});
