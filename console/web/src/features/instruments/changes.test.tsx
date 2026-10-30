import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { fakeTransport, type Route } from "../../test/fakes";
import type { DraftOut } from "./api";
import { ApplyPanel, CANNOT_SIGN_YET, ChangesList, ChangesProvider, NOT_SAVED_WORDS, RUN_SENDS_NOTHING, useChanges } from "./changes";
import type { DraftKind } from "./parts";

/**
 * The changes list, its check and [Apply] (console card 023, part 4). The server's answers are fixtures here; whether the card it
 * builds passes plan.schema.json is tested where the card is built (tests/server/test_instruments.py), never against a copy.
 */

const CHANGES = "/api/instruments/changes";
const SLOT = { slot: 3, name: "five_band", resolves: true };
const LAMP = { kind: "dialamp", state: "on", intensity_percent: 12 } as const;

const draft = (over: Partial<DraftOut> = {}): DraftOut => ({
  kind: "changes", card: { card: "plan", status: "DRAFT" }, valid: true, problems: [], range_problems: [], refused_today: [],
  saved: false, note: "A draft.", ...over,
});

const clients: Client[] = [];
afterEach(() => clients.splice(0).forEach((c) => c.events.stop()));

function Adder({ part = "dialamp" as DraftKind, words = "Transmitted lamp: on, 12 %" }) {
  const c = useChanges();
  return (
    <>
      <button type="button" onClick={() => c.addPart(part, LAMP, words)}>add lamp</button>
      <button type="button" onClick={() => c.addSelector("filter_turret_1", "stand_ti2e", SLOT)}>add slot</button>
      <button type="button" onClick={() => c.addSelector("polarizer", null, { ...SLOT, name: "x" })}>add second slot</button>
    </>
  );
}

function show(routes: Record<string, Route> = {}, extra?: { signed?: boolean }) {
  const fake = fakeTransport(routes);
  const client = new Client(fake.transport, "127.0.0.1");
  clients.push(client);
  const out = render(
    <ClientProvider client={client}>
      <ChangesProvider>
        <Adder />
        <ChangesList signed={extra?.signed} />
      </ChangesProvider>
    </ClientProvider>,
  );
  return { ...out, fake };
}

const click = (name: string | RegExp) => fireEvent.click(screen.getByRole("button", { name }));
const asked = (fake: { calls: { path: string; init?: RequestInit }[] }) => fake.calls.filter((c) => c.path === CHANGES);

describe("the changes list sends nothing until a button is pressed", () => {
  it("makes no request while it renders, collects, removes or re-renders", () => {
    const view = show();
    click("add lamp");
    click("add slot");
    click(/^Remove Transmitted lamp/);
    view.rerender(<></>);
    expect(asked(view.fake)).toEqual([]);
    expect(view.fake.calls.filter((c) => c.path.startsWith("/api/instruments"))).toEqual([]);
  });
});

describe("Check the draft", () => {
  it("sends the settings and the required states in the order they were added, and nothing else", async () => {
    const view = show({ [CHANGES]: () => ({ status: 200, body: draft() }) });
    click("add lamp");
    click("add slot");
    click("Check the draft");
    await screen.findByLabelText("Plan draft");
    expect(screen.queryByTestId("apply-refused")).toBeNull(); // a check is not an application: it carries no signing refusal
    const sent = asked(view.fake);
    expect(sent).toHaveLength(1);
    expect(JSON.parse(String(sent[0].init?.body))).toEqual({
      parts: [{ kind: "dialamp", state: "on", intensity_percent: 12 }],
      selectors: [{ element: "filter_turret_1", value: "five_band" }],
    });
  });

  it("shows the schema's refusal in the schema's words and offers no signing", async () => {
    show({ [CHANGES]: () => ({ status: 200, body: draft({ valid: false, problems: ["$.devices: [] is too short"] }) }) });
    click("add lamp");
    click("Check the draft");
    const box = await screen.findByLabelText("Plan draft");
    expect(within(box).getByText("$.devices: [] is too short")).toBeTruthy();
    expect(within(box).getByText("This draft is not offered for signing.")).toBeTruthy();
  });

  it("says a quantity with no limit named yet is refused before signing, in the server's words", async () => {
    const why = "No limit has been named for the transmitted lamp's intensity yet, so this draft cannot be signed.";
    show({ [CHANGES]: () => ({ status: 200, body: draft({ valid: false, range_problems: [why] }) }) });
    click("add lamp");
    click("Check the draft");
    const box = await screen.findByLabelText("Plan draft");
    expect(within(box).getByText(why)).toBeTruthy();
    expect(within(box).getByRole("alert").textContent).toContain("not offered for signing");
  });

  it("forgets a check when the list changes, so an answer is never shown for a list it was not asked of", async () => {
    show({ [CHANGES]: () => ({ status: 200, body: draft() }) });
    click("add lamp");
    click("Check the draft");
    await screen.findByLabelText("Plan draft");
    click("add slot");
    expect(screen.queryByLabelText("Plan draft")).toBeNull();
    click(/^Remove filter_turret_1/);
    expect(screen.queryByLabelText("Plan draft")).toBeNull();
  });

  it("is not offered with nothing in the list, and says why", () => {
    show();
    const button = screen.getByRole("button", { name: "Check the draft" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Apply" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("says what went wrong when the server refuses to build the draft", async () => {
    show({ [CHANGES]: () => ({ status: 422, body: { detail: "this part is already in the draft" } }) });
    click("add lamp");
    click("Check the draft");
    expect((await screen.findByRole("alert")).textContent).toContain("this part is already in the draft");
  });

  it("keeps the words 'Not saved. This draft exists only on this screen.'", async () => {
    show({ [CHANGES]: () => ({ status: 200, body: draft() }) });
    expect(screen.getByText(NOT_SAVED_WORDS)).toBeTruthy();
    click("add lamp");
    expect(screen.getByText(NOT_SAVED_WORDS)).toBeTruthy();
  });
});

describe("[Apply] is shown and refused while a draft is saved nowhere", () => {
  it("checks the draft on the press, then says it cannot be signed yet because it is saved nowhere, and opens no password field", async () => {
    const view = show({ [CHANGES]: () => ({ status: 200, body: draft() }) });
    click("add lamp");
    expect(asked(view.fake)).toEqual([]);
    click("Apply");
    const refusal = await screen.findByTestId("apply-refused");
    expect(refusal.textContent).toContain(CANNOT_SIGN_YET);
    expect(CANNOT_SIGN_YET).toBe("This draft cannot be signed yet, because it is saved nowhere.");
    expect(asked(view.fake)).toHaveLength(1);
    expect(screen.queryByLabelText(/password/i)).toBeNull();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByRole("button", { name: /^Run/ })).toBeNull();
  });

  it("gives the limit's refusal first when a quantity has no limit named, and still says it is saved nowhere", async () => {
    const why = "No limit has been named for the Aura LED's power yet, so this draft cannot be signed.";
    show({ [CHANGES]: () => ({ status: 200, body: draft({ valid: false, range_problems: [why] }) }) });
    click("add lamp");
    click("Apply");
    const refusal = await screen.findByTestId("apply-refused");
    expect(refusal.textContent).toContain("cannot be signed");
    expect(refusal.textContent).toContain(CANNOT_SIGN_YET);
    expect(screen.getByLabelText("Plan draft")).toBeTruthy();
  });

  it("writes nothing and sends nothing but the one check", async () => {
    const view = show({ [CHANGES]: () => ({ status: 200, body: draft() }) });
    click("add lamp");
    click("Apply");
    await screen.findByTestId("apply-refused");
    const other = view.fake.calls.filter((c) => c.path !== CHANGES && !c.path.startsWith("/api/auth"));
    expect(other).toEqual([]);
    expect(view.fake.calls.filter((c) => c.init?.method === "POST" && c.path !== CHANGES)).toEqual([]);
  });
});

describe("the run button, after signing, sends nothing", () => {
  it("is not there before a draft is signed", () => {
    show();
    expect(screen.queryByRole("button", { name: "Run" })).toBeNull();
  });

  it("says nothing is sent and why, and sends no request", async () => {
    const view = show({}, { signed: true });
    click("add lamp"); // a list to ask about, so a press that wrongly asked would be heard
    const before = view.fake.calls.length;
    click("Run");
    expect((await screen.findByTestId("run-says")).textContent).toBe(RUN_SENDS_NOTHING);
    expect(RUN_SENDS_NOTHING).toContain("bench hand-over");
    await waitFor(() => expect(view.fake.calls.length).toBe(before));
    expect(view.fake.calls.filter((c) => c.init?.method === "POST")).toEqual([]);
  });
});

describe("the apply panel needs the list it belongs to", () => {
  it("cannot be rendered outside it", () => {
    const err = console.error;
    console.error = () => undefined;
    try {
      expect(() => render(<ApplyPanel />)).toThrow(/ChangesProvider/);
    } finally {
      console.error = err;
    }
  });
});
