import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { ScreenContextProvider } from "../../app/screenContext";
import { fakeTransport, type Route } from "../../test/fakes";
import { PATHS } from "./api";
import LibraryScreen from "./index";

/** The Library screen (console card 016): the librarian's generated pages and four request forms with Send inert. */

const clients: Client[] = [];
afterEach(() => {
  clients.splice(0).forEach((c) => c.events.stop());
});

const V = "kbv-0123456789ab";
const OLD = "kbv-ba9876543210";
const NOT_SENT = "Not sent: the librarian's inbox is not open yet.";
const EXAMPLE =
  "This is example data: a copy of recorded files kept with the console, not from this microscope's librarian. " +
  "Where each file came from is written in mock_data/SOURCE.md.";
const footer = (v = V) => `Generated from the knowledge store at ${v}. Do not edit by hand: correct the store and regenerate.`;
const BEHIND = "This page was built from an older version of the store. Correct the store and regenerate the pages.";

const span = (text: string, page: string | null = null, code = false) => ({ text, code, page });

const INDEX = (over: Record<string, unknown> = {}) => ({
  example: false, example_note: null, state: "shown", message: null, title: "The knowledge store",
  facts: [{ label: "Entries", value: "12" }],
  groups: [
    { key: "devices", title: "Devices", links: [{ label: "dia_lamp", page: "device_dia_lamp", kind: "device", entries: 3 }] },
    { key: "quantities", title: "Quantities", links: [{ label: "na", page: "quantity_na", kind: "quantity", entries: 1 }] },
  ],
  registered_unused: ["lamp_power"], footer: footer(), footer_version: V, current_version: V, behind: false, note: null, ...over,
});

const PAGE = (over: Record<string, unknown> = {}) => ({
  example: false, example_note: null, page_id: "device_dia_lamp", title: "Device: dia_lamp",
  blocks: [
    { type: "paragraph", spans: [span("See "), span("the NA page", "quantity_na"), span(" and "), span("entry x", null), span(" and "), span("guide y", null)] },
  ],
  footer: footer(), footer_version: V, current_version: V, behind: false, note: null, ...over,
});

const MAP = (over: Record<string, unknown> = {}) => ({
  example: false, example_note: null, state: "not_built", message: "The librarian has not built the data map yet.",
  kb_version: null, current_version: V, behind: false, note: null, footer: null, subjects: [], relations: [], evidence_page: false, ...over,
});

const answer = (outcome: string, over: Record<string, unknown> = {}) => ({
  answer_id: `ca-20261020-${outcome}`, item_id: "ci-20261020-100000-abcd", answered_by: "librarian",
  answered_at: "2026-10-20T10:00:00Z", outcome, reason: `reason of ${outcome}`, kb_version: V, answer: null,
  entries_cited: [], numbers: [], gaps: [], entries_marked: [], other_side: [], quantity_name: null, entries_made: [],
  example: true, ...over,
});

const OUTCOMES = ["entered", "waiting_for_a_name", "refuted", "in_conflict", "superseded", "kept", "no_entry_of_that_name"];
const ANSWERS = (over: Record<string, unknown> = {}) => ({
  example: true, example_note: EXAMPLE, message: null,
  answers: [
    ...OUTCOMES.map((o) => answer(o)),
    answer("answered", {
      answer: "The lamp is 12 V.",
      numbers: [{ name: "lamp_voltage", value: 12, unit: "V", entry_id: "dia_lamp_voltage", grade: "E2", source: "maker's sheet", covers_conditions: "not_stated" }],
      gaps: [{ asked_for: "the lamp's power", looked_in: "devices" }],
    }),
    answer("not_in_the_store", { gaps: [{ asked_for: "something", looked_in: "everywhere" }] }),
  ],
  ...over,
});

interface Opts {
  index?: unknown;
  pages?: Record<string, unknown>;
  map?: unknown;
  answers?: unknown;
  hash?: string;
}

function show(opts: Opts = {}) {
  window.location.hash = opts.hash ?? "#/library";
  const routes: Record<string, Route> = {
    [PATHS.index]: () => ({ status: 200, body: opts.index ?? INDEX() }),
    [PATHS.map]: () => ({ status: 200, body: opts.map ?? MAP() }),
    [PATHS.answers]: () => ({
      status: 200,
      body: opts.answers ?? { example: false, example_note: null, answers: [], message: "No answers yet." },
    }),
  };
  for (const [id, body] of Object.entries({ device_dia_lamp: PAGE(), ...(opts.pages ?? {}) })) {
    routes[PATHS.page(id)] = () => ({ status: 200, body });
  }
  const fake = fakeTransport(routes);
  const client = new Client(fake.transport, "127.0.0.1");
  clients.push(client);
  render(
    <ClientProvider client={client}>
      <ScreenContextProvider area="library">
        <LibraryScreen />
      </ScreenContextProvider>
    </ClientProvider>,
  );
  const nonGets = () => fake.calls.filter((c) => c.init?.method !== undefined && c.init.method !== "GET");
  return { ...fake, client, nonGets };
}

const type = (label: string | RegExp, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

describe("the tabs", () => {
  it("offers pages, the data map and the four forms, Pages first", async () => {
    show();
    const bar = await screen.findByRole("tablist", { name: "Library" });
    expect(within(bar).getAllByRole("tab").map((t) => t.textContent)).toEqual([
      "Pages", "Data map", "Ask the librarian", "Add a document or value", "Withdraw a value", "Offer a result",
    ]);
    expect((await screen.findByRole("tab", { name: "Pages" })).getAttribute("aria-selected")).toBe("true");
  });
});

describe("Pages: grouped by the kind of data, as generated", () => {
  it("groups the pages and shows the front page's footer", async () => {
    show();
    const devices = await screen.findByRole("region", { name: "Devices" });
    expect(within(devices).getByRole("link", { name: "dia_lamp" }).getAttribute("href")).toBe("#/library/pages/device_dia_lamp");
    expect(screen.getByRole("region", { name: "Quantities" })).toBeTruthy();
    expect(screen.getByText(footer())).toBeTruthy();
  });

  it("says plainly when the front page was built from an older version of the store", async () => {
    show({ index: INDEX({ behind: true, note: BEHIND, footer_version: OLD, footer: footer(OLD) }) });
    expect(await screen.findByText(BEHIND)).toBeTruthy();
  });

  it("follows a link to another wiki page and shows a link to an entry or a guide as text", async () => {
    show({ hash: "#/library/pages/device_dia_lamp" });
    const link = await screen.findByRole("link", { name: "the NA page" });
    expect(link.getAttribute("href")).toBe("#/library/pages/quantity_na");
    expect(screen.getByText(/entry x/)).toBeTruthy();
    expect(screen.queryByRole("link", { name: /entry x|guide y/ })).toBeNull();
  });

  it("says a page built from an older version is older", async () => {
    show({
      hash: "#/library/pages/device_dia_lamp",
      pages: { device_dia_lamp: PAGE({ behind: true, note: BEHIND, footer_version: OLD, footer: footer(OLD) }) },
    });
    expect(await screen.findByText(BEHIND)).toBeTruthy();
  });
});

describe("Data map: counts only", () => {
  it("says not built yet until the files exist", async () => {
    show({ hash: "#/library/map" });
    expect(await screen.findByText(/Not built yet\./)).toBeTruthy();
  });

  it("shows coverage as counts and never a score or rank", async () => {
    show({
      hash: "#/library/map",
      map: MAP({
        state: "built", message: null, kb_version: V, footer: footer(),
        subjects: [{ id: "page:device_dia_lamp", kind: "device", page: "device_dia_lamp", coverage: { E1: 1, E2: 2, E3: 0, E4: 0, E5: 0 }, disputed: 0 }],
      }),
    });
    const table = await screen.findByRole("table", { name: "Coverage by subject" });
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "Subject", "Kind", "E1", "E2", "E3", "E4", "E5", "Disputed",
    ]);
    expect(within(table).getAllByRole("cell").map((c) => c.textContent)).toEqual([
      "device_dia_lamp", "device", "1", "2", "0", "0", "0", "0",
    ]);
    expect(document.body.textContent).not.toMatch(/score|rank|total|overall/i);
  });

  it("says when the map was built from an older version of the store", async () => {
    show({
      hash: "#/library/map",
      map: MAP({ state: "built", message: null, kb_version: OLD, behind: true, note: BEHIND, footer: footer(OLD) }),
    });
    expect(await screen.findByText(BEHIND)).toBeTruthy();
  });
});

describe("the forms", () => {
  it("Send on an empty form says what is missing and sends nothing", async () => {
    const { nonGets, calls } = show({ hash: "#/library/add" });
    await screen.findByRole("form", { name: "Add a document or value" });
    await screen.findByText("No answers yet.");
    const before = calls.length;
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText(/the form needs fixing first/)).toBeTruthy();
    expect(nonGets()).toEqual([]);
    expect(calls.length).toBe(before);
  });

  it("Send on a good form answers not sent, writes nothing and asks the server nothing", async () => {
    const { nonGets, calls } = show({ hash: "#/library/ask" });
    await screen.findByRole("form", { name: "Ask the librarian" });
    await screen.findByText("No answers yet.");
    const before = calls.length;
    type("Your question", "what is the lamp power?");
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText(NOT_SENT)).toBeTruthy();
    expect(nonGets()).toEqual([]);
    expect(calls.length).toBe(before);
  });

  it("the offer form answers not sent too", async () => {
    const { nonGets } = show({ hash: "#/library/offer" });
    await screen.findByRole("form", { name: "Offer a result" });
    type("Path of the result card", "microscope_agent/questions/mic-1/result_a.json");
    type("The fact, in words", "the pixel pitch is 6.5 um");
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText(NOT_SENT)).toBeTruthy();
    expect(nonGets()).toEqual([]);
  });

  it("a remembered value is labelled as entering at the lowest grade", async () => {
    show({ hash: "#/library/add" });
    await screen.findByRole("form", { name: "Add a document or value" });
    expect(screen.queryByText(/lowest grade/)).toBeNull();
    fireEvent.change(screen.getByLabelText("What kind of source"), { target: { value: "operator_recall" } });
    expect(screen.getByText(/enters at the lowest grade/)).toBeTruthy();
    expect(screen.getByText(/never chosen here/)).toBeTruthy();
  });

  it("the withdraw form says words alone cannot refute a value", async () => {
    show({ hash: "#/library/withdraw" });
    expect(await screen.findByText(/Words alone cannot refute a value/)).toBeTruthy();
  });

  it("a form edit clears the last answer", async () => {
    show({ hash: "#/library/ask" });
    await screen.findByRole("form", { name: "Ask the librarian" });
    type("Your question", "x");
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByText(NOT_SENT);
    type("Your question", "xy");
    expect(screen.queryByText(NOT_SENT)).toBeNull();
  });
});

describe("the answers list", () => {
  it("shows all seven outcomes, each labelled example data, from the mock store", async () => {
    show({ hash: "#/library/ask", answers: ANSWERS() });
    const list = await screen.findByRole("region", { name: "Answers" });
    await waitFor(() => expect(within(list).getAllByText("example data").length).toBeGreaterThanOrEqual(10));
    for (const w of ["Entered", "Waiting for a name", "Refuted", "In conflict", "Superseded", "Kept", "No entry of that name"]) {
      expect(within(list).getByText(w)).toBeTruthy();
    }
  });

  it("gives every number with its entry, grade, source and whether it covers the conditions", async () => {
    show({ hash: "#/library/ask", answers: ANSWERS() });
    const table = await screen.findByRole("table", { name: "Numbers" });
    expect(within(table).getAllByRole("cell").map((c) => c.textContent)).toEqual([
      "lamp_voltage", "12 V", "dia_lamp_voltage", "E2", "maker's sheet", "conditions not stated",
    ]);
    expect(screen.getByText(/Asked for: the lamp's power\. Looked in: devices\./)).toBeTruthy();
  });

  it("from the real store says no answers yet", async () => {
    show({ hash: "#/library/add" });
    expect(await screen.findByText("No answers yet.")).toBeTruthy();
    expect(screen.queryByText("example data")).toBeNull();
  });
});

describe("the notes and the answers on each tab", () => {
  const FORMS: [string, string][] = [
    ["ask", "Ask the librarian"], ["add", "Add a document or value"], ["withdraw", "Withdraw a value"], ["offer", "Offer a result"],
  ];
  for (const [tab, title] of FORMS) {
    it(`the ${tab} form says the inbox is not open and Send only checks`, async () => {
      show({ hash: `#/library/${tab}` });
      const form = await screen.findByRole("form", { name: title });
      expect(within(form).getByText(/inbox is not open yet, so Send only checks the form/)).toBeTruthy();
      expect(within(form).getByText(/Nothing you type here is kept or sent/)).toBeTruthy();
    });
  }

  it("lists the answers under the forms", async () => {
    show({ hash: "#/library/ask", answers: ANSWERS() });
    expect(await screen.findByRole("region", { name: "Answers" })).toBeTruthy();
  });

  for (const [name, hash] of [["pages", "#/library"], ["data map", "#/library/map"]]) {
    it(`does not list the answers under the ${name}`, async () => {
      show({ hash, answers: ANSWERS() });
      await screen.findByRole("tablist", { name: "Library" });
      await waitFor(() => expect(screen.getByRole("tab", { name: "Pages" })).toBeTruthy());
      expect(screen.queryByRole("region", { name: "Answers" })).toBeNull();
      expect(screen.queryByText("example data")).toBeNull();
    });
  }
});
