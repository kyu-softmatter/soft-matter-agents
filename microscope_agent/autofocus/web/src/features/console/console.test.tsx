import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Client, ClientProvider, type ReadOnlyState } from "../../app/client";
import { ScreenContextProvider, useCurrentScreenContext } from "../../app/screenContext";
import { fakeTransport } from "../../test/fakes";
import { CHECKING_PERMISSIONS, PERMISSION_CHECK_UNAVAILABLE, READ_ONLY_REMOTE, READ_ONLY_STORE_REASON } from "./api";
import ConsoleScreen, { parseRest } from "./index";
import { changedKeys } from "./questions";
import { submitReason } from "./submit";
import { consoleRoutes, FAKE_DATA, type FakeData, MOCK_STORE, READ_ONLY_STORE } from "./testData";

function ContextProbe() {
  return <output data-testid="ctx">{JSON.stringify(useCurrentScreenContext())}</output>;
}

// stop every client's event stream so no reconnect timer outlives its test
const clients: Client[] = [];
afterEach(() => {
  clients.splice(0).forEach((c) => c.events.stop());
});

function renderConsole(data: FakeData = FAKE_DATA, hash = "#/console", hostname = "127.0.0.1") {
  window.location.hash = hash;
  const { routes, submitted } = consoleRoutes(data);
  const fake = fakeTransport(routes);
  const client = new Client(fake.transport, hostname);
  clients.push(client);
  const view = render(
    <ClientProvider client={client}>
      <ScreenContextProvider area="console">
        <ConsoleScreen />
        <ContextProbe />
      </ScreenContextProvider>
    </ClientProvider>,
  );
  const gets = (path: string) => fake.calls.filter((c) => c.path === path && c.init?.method !== "POST").length;
  return { ...fake, client, submitted, gets, view };
}

const ctx = () => JSON.parse(screen.getByTestId("ctx").textContent ?? "{}");
const submitButton = () => screen.getByRole("button", { name: "Submit question" }) as HTMLButtonElement;
const LOCAL: ReadOnlyState = { readOnly: false, why: null };

describe("parseRest", () => {
  it("reads the documented forms and falls back to the question list", () => {
    expect(parseRest("")).toEqual({ tab: "questions" });
    expect(parseRest("questions/sim-20260923-001")).toEqual({ tab: "questions", qid: "sim-20260923-001" });
    expect(parseRest("runs/simulation/run-1")).toEqual({ tab: "runs", agent: "simulation", runId: "run-1" });
    expect(parseRest("runs/nobody/run-1")).toEqual({ tab: "runs" });
    expect(parseRest("inbox")).toEqual({ tab: "inbox" });
    expect(parseRest("whatever")).toEqual({ tab: "questions" });
  });
});

describe("question list", () => {
  it("filters by agent, status and date, and shows the summary fields", async () => {
    renderConsole();
    const list = await screen.findByRole("region", { name: "Questions" });
    expect(within(list).getByText("sim-20260923-001")).toBeTruthy();
    expect(within(list).getByText("tracer_diffusivity")).toBeTruthy();
    expect(within(list).getByText("verify")).toBeTruthy();

    fireEvent.change(within(list).getByLabelText("Agent"), { target: { value: "simulation" } });
    expect(within(list).queryByText("mic-20260925-001")).toBeNull();
    expect(within(list).getByText("sim-20260923-001")).toBeTruthy();

    fireEvent.change(within(list).getByLabelText("Agent"), { target: { value: "" } });
    fireEvent.change(within(list).getByLabelText("Status"), { target: { value: "VALIDATED" } });
    expect(within(list).queryByText("sim-20260923-001")).toBeNull();
    expect(within(list).getByText("mic-20260925-001")).toBeTruthy();

    fireEvent.change(within(list).getByLabelText("Status"), { target: { value: "" } });
    fireEvent.change(within(list).getByLabelText("Created from"), { target: { value: "2026-09-24" } });
    expect(within(list).queryByText("sim-20260923-001")).toBeNull();
    expect(within(list).getByText("mic-20260925-001")).toBeTruthy();
  });

  it("reads once on open, again on Refresh and after the event socket reconnects; no polling", async () => {
    const t = renderConsole();
    await screen.findByRole("region", { name: "Questions" });
    expect(t.gets("/api/console/questions")).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(t.gets("/api/console/questions")).toBe(2));

    act(() => t.sockets[0].open());
    act(() => t.sockets[0].event("position", { x_um: 1 }));
    expect(t.gets("/api/console/questions")).toBe(2); // first connect and events: no re-read

    act(() => t.sockets[0].close());
    await waitFor(() => expect(t.sockets).toHaveLength(2), { timeout: 3000 }); // the shell's backoff
    act(() => t.sockets[1].open());
    await waitFor(() => expect(t.gets("/api/console/questions")).toBe(3));
  });
});

describe("question detail", () => {
  it("shows card tabs of the latest version and switches between them", async () => {
    renderConsole(FAKE_DATA, "#/console/questions/sim-20260923-001");
    const tabs = await screen.findByRole("tablist", { name: "Cards" });
    expect(within(tabs).getAllByRole("tab").map((t) => t.textContent)).toEqual(["goal", "axis a1", "axis a7"]);
    expect(screen.getByRole("article", { name: "Card v5_goal.json" })).toBeTruthy();

    fireEvent.click(within(tabs).getByRole("tab", { name: "axis a7" }));
    const card = screen.getByRole("article", { name: "Card v5_axis_bd_pairwise_a7.json" });
    expect(within(card).getByText("infeasible")).toBeTruthy();
    await waitFor(() =>
      expect(ctx()).toMatchObject({ area: "console", qid: "sim-20260923-001", version: 5, card_kind: "axis" }),
    );
  });

  it("lists every version the store returns, past v3", async () => {
    const t = renderConsole(FAKE_DATA, "#/console/questions/sim-20260923-001");
    const picker = (await screen.findByLabelText("Version")) as HTMLSelectElement;
    expect([...picker.options].map((o) => o.textContent)).toEqual(["v1", "v2", "v5 (latest)"]);

    fireEvent.change(picker, { target: { value: "1" } });
    expect(await screen.findByRole("article", { name: "Card goal.json" })).toBeTruthy();
    expect(t.gets("/api/console/questions/sim-20260923-001?version=1")).toBe(1);
    expect(screen.getByRole("tab", { name: "refusal" })).toBeTruthy();
  });

  it("shows grades exactly as the card has them, and the degraded banner", async () => {
    renderConsole(FAKE_DATA, "#/console/questions/sim-20260923-001");
    const table = await screen.findByRole("table", { name: "Numbers" });
    const grades = within(table).getAllByTitle("grade as written on the card").map((g) => g.textContent);
    expect(grades).toEqual(["E2", "E4", "E9"]);
    expect(within(table).getByText("0.09")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("librarian unreachable");
  });

  it("compares two versions by card and field", async () => {
    renderConsole(FAKE_DATA, "#/console/questions/sim-20260923-001");
    fireEvent.change(await screen.findByLabelText("Compare with"), { target: { value: "2" } });
    const diff = await screen.findByRole("table", { name: "Changes v5 to v2" });
    expect(within(diff).getByText("axis_bd_pairwise_a7.json").nextSibling?.textContent).toBe("changed: verdict");
    expect(within(diff).getByText("goal.json").nextSibling?.textContent).toBe("only in v5");
    expect(changedKeys({ a: 1, b: 2 }, { a: 1, b: 3, c: 0 })).toEqual(["b", "c"]);
  });
});

describe("runs and inbox", () => {
  it("links a simulation run to the simulation area", async () => {
    renderConsole(FAKE_DATA, "#/console/runs/simulation/run-20260924-001-smoke-g2k2");
    const link = await screen.findByRole("link", { name: "Open in Simulation" });
    expect(link.getAttribute("href")).toBe("#/simulation/runs/run-20260924-001-smoke-g2k2");
    expect(screen.getByText(/Not opened: trajectory.gsd/)).toBeTruthy();
    expect(within(screen.getByRole("table", { name: "Events" })).getByText("complete")).toBeTruthy();
    await waitFor(() => expect(ctx()).toMatchObject({ run_id: "run-20260924-001-smoke-g2k2", agent: "simulation" }));
  });

  it("shows a microscope run's explanation fields and no simulation link", async () => {
    renderConsole(FAKE_DATA, "#/console/runs/microscope/run-20260924-003");
    expect(await screen.findByText("No plan fits this run.")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Open in Simulation" })).toBeNull();
  });

  it("opens a run from the list, which shows the approval kind", async () => {
    renderConsole(FAKE_DATA, "#/console/runs");
    expect(await screen.findByText("smoke_auto")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "run-20260924-003" }));
    expect(await screen.findByRole("region", { name: "Run run-20260924-003" })).toBeTruthy();
    expect(window.location.hash).toBe("#/console/runs/microscope/run-20260924-003");
  });

  it("lists inbox threads with their rounds", async () => {
    renderConsole(FAKE_DATA, "#/console/inbox");
    const inbox = await screen.findByRole("region", { name: "Inbox" });
    expect(within(inbox).getByText("thr-tracer-diffusivity-001")).toBeTruthy();
    expect(within(inbox).getByText("Round two.")).toBeTruthy();
  });
});

describe("ask a question", () => {
  it("orders the reasons: remote view, permission, then read-only store", () => {
    const ok = { data: { submit_question: { allowed: true, reason: null } } };
    const viewer = { data: { submit_question: { allowed: false, reason: "Needs the operator role" } } };
    const remote = { readOnly: true, why: "remote view" };
    expect(submitReason(LOCAL, ok, { data: MOCK_STORE })).toBeUndefined();
    expect(submitReason(LOCAL, ok, { data: READ_ONLY_STORE })).toBe(READ_ONLY_STORE_REASON);
    expect(submitReason(LOCAL, viewer, { data: READ_ONLY_STORE })).toBe("Needs the operator role");
    expect(submitReason(remote, ok, { data: MOCK_STORE })).toBe(READ_ONLY_REMOTE);
    expect(submitReason(LOCAL, {}, { data: MOCK_STORE })).toBe(CHECKING_PERMISSIONS);
    expect(submitReason(LOCAL, { data: {} }, { data: MOCK_STORE })).toBe(PERMISSION_CHECK_UNAVAILABLE);
    expect(submitReason(LOCAL, { error: "HTTP 502" }, { data: MOCK_STORE })).toBe(PERMISSION_CHECK_UNAVAILABLE);
  });

  it("is disabled with the read-only reason when the store is not the mock store", async () => {
    const t = renderConsole({ ...FAKE_DATA, store: READ_ONLY_STORE }, "#/console/ask");
    expect(await screen.findByText(READ_ONLY_STORE_REASON)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "How fast?" } });
    expect(submitButton().disabled).toBe(true);
    fireEvent.submit(screen.getByRole("form", { name: "Ask a question" }));
    expect(t.submitted).toHaveLength(0);
    expect(screen.getByText("Store: soft-matter-agents (read-only)")).toBeTruthy();
  });

  it("shows the shared permission reason for a viewer", async () => {
    renderConsole(
      { ...FAKE_DATA, permissions: { submit_question: { allowed: false, reason: "Needs the operator role" } } },
      "#/console/ask",
    );
    expect(await screen.findByText("Needs the operator role")).toBeTruthy();
    expect(submitButton().disabled).toBe(true);
  });

  it("is greyed out on a remote screen, with the read-only badge", async () => {
    renderConsole(FAKE_DATA, "#/console/ask", "lab-pc.example.test");
    expect(await screen.findAllByText(READ_ONLY_REMOTE)).toHaveLength(2); // badge and reason
    expect(submitButton().disabled).toBe(true);
  });

  it("disables submit when the permission check cannot be read, and keeps the reads", async () => {
    renderConsole({ ...FAKE_DATA, permissions: null }, "#/console/ask");
    expect(await screen.findByText(PERMISSION_CHECK_UNAVAILABLE)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "How fast?" } });
    expect(submitButton().disabled).toBe(true);

    fireEvent.click(screen.getByRole("tab", { name: "Questions" }));
    expect(await screen.findByText("sim-20260923-001")).toBeTruthy();
  });

  it("shows a non-remote 403 next to the form and leaves the app writable (D16 viewer)", async () => {
    const t = renderConsole(
      {
        ...FAKE_DATA,
        postRefusal: { status: 403, body: { detail: { code: "role", message: "role viewer may not submit_question" } } },
      },
      "#/console/ask",
    );
    await screen.findByText("Store: mock");
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "How fast?" } });
    await waitFor(() => expect(submitButton().disabled).toBe(false));
    await act(async () => {
      fireEvent.click(submitButton());
    });
    const form = screen.getByRole("form", { name: "Ask a question" });
    expect((await within(form).findByRole("alert")).textContent).toBe("role viewer may not submit_question");
    expect(t.client.readOnly.get()).toEqual({ readOnly: false, why: null });
    expect(screen.queryByText(READ_ONLY_REMOTE)).toBeNull();
    expect(submitButton().disabled).toBe(false);
  });

  it("a 403 remote_view on submit switches the app to read-only (the shell's rule)", async () => {
    const t = renderConsole(
      {
        ...FAKE_DATA,
        postRefusal: { status: 403, body: { detail: { code: "remote_view", message: "remote view: no" } } },
      },
      "#/console/ask",
    );
    await screen.findByText("Store: mock");
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "How fast?" } });
    await waitFor(() => expect(submitButton().disabled).toBe(false));
    await act(async () => {
      fireEvent.click(submitButton());
    });
    await waitFor(() => expect(t.client.readOnly.get().readOnly).toBe(true));
    expect(submitButton().disabled).toBe(true);
    expect(screen.getAllByText(READ_ONLY_REMOTE).length).toBeGreaterThan(0);
  });

  it("submits to the mock store and re-reads the list", async () => {
    const t = renderConsole(FAKE_DATA, "#/console/ask");
    await screen.findByText("Store: mock");
    expect(submitButton().disabled).toBe(true); // no text yet
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "How fast do tracers move?" } });
    fireEvent.change(screen.getByLabelText("Agent"), { target: { value: "simulation" } });
    await waitFor(() => expect(submitButton().disabled).toBe(false));
    await act(async () => {
      fireEvent.click(submitButton());
    });
    expect(await screen.findByText("Submitted as sim-20261001-901")).toBeTruthy();
    expect(t.submitted).toEqual([{ text: "How fast do tracers move?", target: "simulation" }]);
    await waitFor(() => expect(t.gets("/api/console/questions")).toBe(2));

    fireEvent.click(screen.getByRole("tab", { name: "Questions" }));
    expect(await screen.findByText("sim-20261001-901")).toBeTruthy();
  });
});
