import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { fakeTransport, type Route } from "../../test/fakes";
import schema from "../../../../../contracts/schemas/run_interface.schema.json";
import { PATHS } from "./api";
import { ALSO_STOPS_THE_PLAN, LightsOff, NOTHING_KNOWN, USE_THE_SWITCH } from "./lightsoff";

/**
 * [Lights off] (console card 023, part 5). The server's answers are fixtures built from `lights_off_reply`'s own `examples` and
 * `x_refused`, read from `contracts/schemas/run_interface.schema.json` and not from a copy. What the server does with the host's
 * reply is tested where it is done (tests/server/test_lights_off.py); here the page shows what the server says, and nothing else.
 */

const REPLY = schema.$defs.lights_off_reply;
const EXAMPLES = REPLY.examples as Record<string, unknown>[];
const SOURCE_ROWS = EXAMPLES[0].sources as { source: string; channel: string; result: string; read_back: string | null; reason?: string }[];

/** The server's answer for a host reply: what `LightsOffOut` carries. */
function served(example: Record<string, unknown>) {
  const answer = example.lights_off as string;
  return {
    answer,
    how: (example.as as string | undefined) ?? null,
    run_id: (example.run_id as string | undefined) ?? null,
    reason: (example.reason as string | undefined) ?? null,
    sources: ((example.sources as { reason?: string }[] | undefined) ?? []).map((s) => ({ reason: null, ...s })),
  };
}

const clients: Client[] = [];
afterEach(() => {
  clients.splice(0).forEach((c) => c.events.stop());
  cleanup();
});

function show(route: Route | undefined, running = false) {
  const fake = fakeTransport(route ? { [PATHS.lightsOff]: route } : {});
  const client = new Client(fake.transport, "127.0.0.1");
  clients.push(client);
  render(
    <ClientProvider client={client}>
      <LightsOff running={running} />
    </ClientProvider>,
  );
  return { ...fake, client, presses: () => fake.calls.filter((c) => c.path === PATHS.lightsOff) };
}

const press = async () => {
  fireEvent.click(screen.getByRole("button", { name: "Lights off" }));
};

describe("the button", () => {
  it("makes no request while it renders", () => {
    const v = show(() => ({ status: 200, body: served(EXAMPLES[0]) }));
    expect(screen.getByRole("button", { name: "Lights off" })).toBeTruthy();
    expect(v.calls.filter((c) => c.path.startsWith("/api/instruments"))).toEqual([]);
  });

  it("one press is one POST with no body and no query", async () => {
    const v = show(() => ({ status: 200, body: served(EXAMPLES[0]) }));
    await press();
    await screen.findByTestId("lights-off-result");
    expect(v.presses().length).toBe(1);
    expect(v.presses()[0].path).toBe("/api/instruments/lights-off");
    expect(v.presses()[0].init?.method).toBe("POST");
    expect(v.presses()[0].init?.body ?? undefined).toBeUndefined();
  });

  it("asks for no confirmation, no password and no draft", async () => {
    const v = show(() => ({ status: 200, body: served(EXAMPLES[0]) }));
    await press();
    await screen.findByTestId("lights-off-result");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByLabelText(/password/i)).toBeNull();
    expect(v.calls.filter((c) => c.init?.method === "POST").map((c) => c.path)).toEqual([PATHS.lightsOff]);
  });

  it("a second press while the first is waiting sends nothing more", async () => {
    const v = show(() => ({ status: 200, body: served(EXAMPLES[0]) }));
    const button = screen.getByRole("button", { name: "Lights off" });
    act(() => { button.click(); button.click(); }); // both before anything re-renders: only the page's own guard can stop the second
    await screen.findByTestId("lights-off-result");
    expect(v.presses().length).toBe(1);
  });

  it("says that it also stops the running plan only while a plan runs", () => {
    show(undefined, false);
    expect(screen.queryByText(ALSO_STOPS_THE_PLAN)).toBeNull();
    cleanup();
    show(undefined, true);
    expect(screen.getByText(ALSO_STOPS_THE_PLAN)).toBeTruthy();
  });
});

describe("what a reply the schema gives as an example is shown as", () => {
  it("done: one row per source in the reply's order, and the run that turned the lights off", async () => {
    show(() => ({ status: 200, body: served(EXAMPLES[0]) }));
    await press();
    const result = await screen.findByTestId("lights-off-result");
    expect(within(result).getByText(/run-20261029-901/)).toBeTruthy();
    const rows = within(within(result).getByRole("table", { name: "Light sources" })).getAllByRole("row").slice(1);
    expect(rows.map((r) => within(r).getAllByRole("cell")[0].textContent)).toEqual(SOURCE_ROWS.map((s) => s.source));
  });

  it("an off row shows what was read back", async () => {
    show(() => ({ status: 200, body: served(EXAMPLES[0]) }));
    await press();
    const row = (await screen.findByText("Aura III")).closest("tr") as HTMLElement;
    expect(within(row).getByText(/Off/)).toBeTruthy();
    expect(row.textContent).toContain("0");
    expect(row.textContent).toContain("widefield_source_a");
  });

  it("a sent row is never shown as off", async () => {
    show(() => ({ status: 200, body: served(EXAMPLES[0]) }));
    await press();
    const row = (await screen.findByText("DiaLamp")).closest("tr") as HTMLElement;
    expect(row.textContent).toMatch(/Sent/);
    expect(row.textContent).toMatch(/cannot be read back/);
    expect(row.textContent).not.toMatch(/\bOff\b/);
  });

  it("a not-turned-off row gives its reason and says to use the switch on the device", async () => {
    show(() => ({ status: 200, body: served(EXAMPLES[0]) }));
    await press();
    const row = (await screen.findByText("optical tweezers")).closest("tr") as HTMLElement;
    expect(row.textContent).toContain("not software-controllable");
    expect(row.textContent).toContain(USE_THE_SWITCH);
    expect(row.textContent).not.toMatch(/\bOff\b/);
  });

  it("done as the stop of a running plan says the plan was stopped; a run of its own does not", async () => {
    show(() => ({ status: 200, body: served(EXAMPLES[1]) }));
    await press();
    const result = await screen.findByTestId("lights-off-result");
    expect(result.textContent).toMatch(/running plan was stopped/);
    expect(result.textContent).toContain("run-20261029-902");
    expect(within(result).getByText("Aura III").closest("tr")?.textContent).toContain("read back 1 after 0 was written");
    cleanup();
    show(() => ({ status: 200, body: served(EXAMPLES[0]) }));
    await press();
    expect((await screen.findByTestId("lights-off-result")).textContent).not.toMatch(/plan was stopped/);
  });

  it("stop sent: names the run, gives the reason, shows no row and no source as off, and says to check each switch", async () => {
    show(() => ({ status: 200, body: served(EXAMPLES[2]) }));
    await press();
    const result = await screen.findByTestId("lights-off-result");
    expect(result.textContent).toContain("run-20261029-903");
    expect(result.textContent).toContain(EXAMPLES[2].reason as string);
    expect(result.textContent).toMatch(/check each light at its switch/i);
    expect(within(result).queryByRole("table")).toBeNull();
    expect(result.textContent).not.toMatch(/\bOff\b/);
  });

  it("refused: gives the reason, says nothing was sent to any light and to use the switches, and shows no row", async () => {
    for (const ex of [EXAMPLES[3], EXAMPLES[4]]) {
      show(() => ({ status: 200, body: served(ex) }));
      await press();
      const result = await screen.findByTestId("lights-off-result");
      expect(result.textContent).toContain(ex.reason as string);
      expect(result.textContent).toMatch(/nothing was sent to any light/i);
      expect(result.textContent).toMatch(/use the switches/i);
      expect(within(result).queryByRole("table")).toBeNull();
      cleanup();
    }
  });
});

describe("no answer", () => {
  const NO_ANSWER = { answer: "no_answer", how: null, run_id: null, reason: "the host did not answer", sources: [] };
  const NO_HOST = { answer: "no_host", how: null, run_id: null, reason: "no live-view host was given to this console", sources: [] };

  it.each([["no answer", NO_ANSWER], ["no host", NO_HOST]])("%s: nothing is known about the lights, and no light is shown off", async (_n, body) => {
    show(() => ({ status: 200, body }));
    await press();
    const result = await screen.findByTestId("lights-off-result");
    expect(result.textContent).toContain(NOTHING_KNOWN);
    expect(result.textContent).toContain(body.reason);
    expect(result.textContent).toMatch(/use the switches/i);
    expect(within(result).queryByRole("table")).toBeNull();
    expect(result.textContent).not.toMatch(/\bOff\b/);
  });

  it("a refused request or a failed one is the same: nothing is known, and nothing is resent", async () => {
    const v = show(() => ({ status: 500, body: { detail: "boom" } }));
    await press();
    const result = await screen.findByTestId("lights-off-result");
    expect(result.textContent).toContain(NOTHING_KNOWN);
    await waitFor(() => expect(v.presses().length).toBe(1));
  });

  it("an answer the page does not know is shown as no answer, with nothing taken from it", async () => {
    show(() => ({ status: 200, body: { answer: "off_everywhere", sources: [{ source: "x", channel: "x", result: "off", read_back: "0" }] } }));
    await press();
    const result = await screen.findByTestId("lights-off-result");
    expect(result.textContent).toContain(NOTHING_KNOWN);
    expect(within(result).queryByRole("table")).toBeNull();
  });

  it("a done answer with no rows, or a row whose result the page does not know, shows no light as off", async () => {
    for (const body of [
      { ...served(EXAMPLES[0]), sources: [] },
      { ...served(EXAMPLES[0]), sources: [{ source: "x", channel: "x", result: "fine", read_back: "0", reason: null }] },
      { ...served(EXAMPLES[0]), run_id: null },
      { ...served(EXAMPLES[0]), sources: [{ source: "x", channel: "x", result: "off", read_back: null, reason: null }] },
      { ...served(EXAMPLES[0]), sources: [{ source: "x", channel: "x", result: "sent", read_back: "0", reason: null }] },
      { ...served(EXAMPLES[0]), sources: [{ source: "x", channel: "x", result: "not_turned_off", read_back: null, reason: null }] },
    ]) {
      show(() => ({ status: 200, body }));
      await press();
      const result = await screen.findByTestId("lights-off-result");
      expect(result.textContent).toContain(NOTHING_KNOWN);
      expect(within(result).queryByRole("table")).toBeNull();
      cleanup();
    }
  });
});

describe("a stop-sent or refused answer missing what the schema requires", () => {
  it("is shown as no answer, with no run named and no row", async () => {
    for (const body of [
      { ...served(EXAMPLES[2]), run_id: null },
      { ...served(EXAMPLES[2]), reason: null },
      { ...served(EXAMPLES[3]), reason: null },
    ]) {
      show(() => ({ status: 200, body }));
      await press();
      const result = await screen.findByTestId("lights-off-result");
      expect(result.textContent).toContain(NOTHING_KNOWN);
      expect(result.textContent).not.toMatch(/run-2026/);
      expect(within(result).queryByRole("table")).toBeNull();
      cleanup();
    }
  });
});

describe("what a new press clears", () => {
  it("the earlier answer is gone while the next is waited for", async () => {
    let n = 0;
    show(() => ({ status: 200, body: served(n++ === 0 ? EXAMPLES[0] : EXAMPLES[3]) }));
    await press();
    await screen.findByText("Aura III");
    await press();
    await waitFor(() => expect(screen.queryByText("Aura III")).toBeNull());
    expect((await screen.findByTestId("lights-off-result")).textContent).toContain(EXAMPLES[3].reason as string);
  });
});
