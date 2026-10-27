import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { ScreenContextProvider } from "../../app/screenContext";
import { fakeTransport, type Route } from "../../test/fakes";
import { PATHS } from "./api";
import LibraryScreen from "./index";

/** The Library screen (console cards 016 and 020): the librarian's generated pages, four request forms that send, and the requests list. */

const clients: Client[] = [];
afterEach(() => {
  clients.splice(0).forEach((c) => c.events.stop());
});

const V = "kbv-0123456789ab";
const OLD = "kbv-ba9876543210";
const SENT = "Sent to the librarian.";
const EXAMPLE_ANSWERS =
  "These are example answers written for the console's practice data, not answers from any librarian. " +
  "Their names and numbers are made up.";
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

const view = (over: Record<string, unknown> = {}) => ({
  item_id: "ci-20261020-100000-abcd", kind: "ask", kind_words: "A question", words: "What is the lamp power?",
  login: "member-1", asked_at: "2026-10-20T09:55:00Z", file: null, example: false, state: "delivered · not answered yet",
  answers: [], unreadable: [], ...over,
});

const REQUESTS = (over: Record<string, unknown> = {}) => ({
  example: false, example_note: null, requests: [], orphans: [], message: "No requests yet.", ...over,
});

const ITEM = {
  artifact: "console_store_request", schema_version: "0.1", item_id: "ci-20261027-101500-ab12", words: "x",
  asked_by: { login: "otto", console_role: {} }, asked_at: "2026-10-27T10:15:00Z", asker_mark: { kind: "other_login" },
  attachments: [], request: { kind: "ask" },
};

interface Opts {
  index?: unknown;
  pages?: Record<string, unknown>;
  map?: unknown;
  requests?: unknown;
  /** What POST /api/library/requests answers: an item, or a refusal (status and body). */
  post?: { status: number; body: unknown };
  hash?: string;
}

function show(opts: Opts = {}) {
  window.location.hash = opts.hash ?? "#/library";
  const routes: Record<string, Route> = {
    [PATHS.index]: () => ({ status: 200, body: opts.index ?? INDEX() }),
    [PATHS.map]: () => ({ status: 200, body: opts.map ?? MAP() }),
    [PATHS.requests]: (init) =>
      init?.method === "POST"
        ? (opts.post ?? { status: 200, body: ITEM })
        : { status: 200, body: opts.requests ?? REQUESTS() },
  };
  for (const [id, body] of Object.entries({ device_dia_lamp: PAGE(), ...(opts.pages ?? {}) })) {
    routes[PATHS.page(id)] = () => ({ status: 200, body });
  }
  const fake = fakeTransport(routes);
  const client = new Client(fake.transport, "127.0.0.1");
  clients.push(client);
  const rendered = render(
    <ClientProvider client={client}>
      <ScreenContextProvider area="library">
        <LibraryScreen />
      </ScreenContextProvider>
    </ClientProvider>,
  );
  const nonGets = () => fake.calls.filter((c) => c.init?.method !== undefined && c.init.method !== "GET");
  return { ...fake, client, nonGets, unmount: rendered.unmount };
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

const posts = (calls: { path: string; init?: RequestInit }[]) => calls.filter((c) => c.init?.method === "POST");
const body = (c: { init?: RequestInit }) => JSON.parse(String(c.init?.body));
const pick = (label: string, file: File) => fireEvent.change(screen.getByLabelText(label), { target: { files: [file] } });
const send = () => fireEvent.click(screen.getByRole("button", { name: "Send" }));

describe("the forms", () => {
  it("Send on an empty form says what is missing and sends nothing", async () => {
    const { nonGets, calls } = show({ hash: "#/library/add" });
    await screen.findByRole("form", { name: "Add a document or value" });
    await screen.findByText("No requests yet.");
    const before = calls.length;
    send();
    expect(await screen.findByText(/the form needs fixing first/)).toBeTruthy();
    expect(nonGets()).toEqual([]);
    expect(calls.length).toBe(before);
  });

  it("Send on a good form sends the words as typed and the request without them, and says it was sent", async () => {
    const { calls } = show({ hash: "#/library/ask" });
    await screen.findByRole("form", { name: "Ask the librarian" });
    const typed = "  what is the lamp power?\n ";
    type("Your question", typed);
    send();
    expect(await screen.findByText(SENT)).toBeTruthy();
    const sent = posts(calls);
    expect(sent.map((c) => c.path)).toEqual([PATHS.requests]);
    expect(body(sent[0])).toEqual({ words: typed, request: { kind: "ask" } });
  });

  it("the offer form sends too", async () => {
    const { calls } = show({ hash: "#/library/offer" });
    await screen.findByRole("form", { name: "Offer a result" });
    type("Path of the result card", "microscope_agent/questions/mic-1/result_a.json");
    type("The fact, in words", "the pixel pitch is 6.5 um");
    send();
    expect(await screen.findByText(SENT)).toBeTruthy();
    expect(body(posts(calls)[0])).toEqual({
      words: "the pixel pitch is 6.5 um",
      request: { kind: "offer_result", result_card: "microscope_agent/questions/mic-1/result_a.json" },
    });
  });

  it("empties a form that was sent, and reads the requests again", async () => {
    const { calls } = show({ hash: "#/library/ask" });
    await screen.findByRole("form", { name: "Ask the librarian" });
    await screen.findByText("No requests yet.");
    type("Your question", "x");
    send();
    await screen.findByText(SENT);
    expect((screen.getByLabelText("Your question") as HTMLTextAreaElement).value).toBe("");
    await waitFor(() => expect(calls.filter((c) => c.path === PATHS.requests && c.init?.method !== "POST").length).toBe(2));
  });

  it("shows what the server refused in its words and keeps the form", async () => {
    show({ hash: "#/library/ask", post: { status: 422, body: { detail: { code: "refused", message: "The librarian's inbox is not there, so nothing was sent." } } } });
    await screen.findByRole("form", { name: "Ask the librarian" });
    type("Your question", "x");
    send();
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe("The librarian's inbox is not there, so nothing was sent.");
    expect(screen.queryByText(SENT)).toBeNull();
    expect((screen.getByLabelText("Your question") as HTMLTextAreaElement).value).toBe("x");
  });

  it("sends the one file the request names, inside the request as base64, under its cleaned name", async () => {
    const { calls } = show({ hash: "#/library/add" });
    await screen.findByRole("form", { name: "Add a document or value" });
    type("Who read it", "member-1");
    type("What to take, in your words", "the rated power");
    pick("File", new File(["hello"], "sheet 1.pdf", { type: "application/pdf" }));
    send();
    await screen.findByText(SENT);
    const b = body(posts(calls)[0]);
    expect(b.file).toEqual({ name: "sheet_1.pdf", content_base64: "aGVsbG8=" });
    expect(b.request.document).toBe("sheet_1.pdf");
    expect(b.words).toBe("the rated power");
    expect(Object.keys(b).sort()).toEqual(["file", "request", "words"]);
  });

  it("sends no file when the request no longer names one, even if one was picked", async () => {
    const { calls } = show({ hash: "#/library/withdraw" });
    await screen.findByRole("form", { name: "Withdraw a value" });
    type("Entry name (typed or pasted)", "dia_lamp_voltage");
    type("Why, in your words", "it reads wrong");
    fireEvent.change(screen.getByLabelText("Evidence"), { target: { value: "reading" } });
    pick("File (optional)", new File(["hello"], "reading.pdf"));
    fireEvent.change(screen.getByLabelText("Evidence"), { target: { value: "none" } });
    send();
    await screen.findByText(SENT);
    expect(posts(calls)).toHaveLength(1);
    const b = body(posts(calls)[0]);
    expect(b.file).toBeUndefined();
    expect(b.request).toEqual({ kind: "withdraw_value", entry_id: "dia_lamp_voltage", evidence: { kind: "none" } });
    expect(b.words).toBe("it reads wrong");
  });

  it("sends no file on a second send in which none was picked, after a first send that carried one", async () => {
    const { calls } = show({ hash: "#/library/withdraw" });
    await screen.findByRole("form", { name: "Withdraw a value" });
    fireEvent.change(screen.getByLabelText("Evidence"), { target: { value: "document" } });
    type("Entry name (typed or pasted)", "dia_lamp_voltage");
    type("Why, in your words", "it reads wrong");
    pick("File", new File(["hello"], "sheet.pdf"));
    send();
    await screen.findByText(SENT);
    expect(body(posts(calls)[0]).file).toEqual({ name: "sheet.pdf", content_base64: "aGVsbG8=" });
    fireEvent.change(screen.getByLabelText("Evidence"), { target: { value: "reading" } });
    type("Entry name (typed or pasted)", "dia_lamp_voltage");
    type("Why, in your words", "it reads wrong again");
    type("Who took the reading", "member-1");
    type("Reading: value", "12");
    type("Reading: unit", "V");
    send();
    await waitFor(() => expect(posts(calls)).toHaveLength(2));
    expect(body(posts(calls)[1]).file).toBeUndefined();
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
    show({ hash: "#/library/ask", post: { status: 422, body: { detail: { code: "refused", message: "nope" } } } });
    await screen.findByRole("form", { name: "Ask the librarian" });
    type("Your question", "x");
    send();
    await screen.findByText("nope");
    type("Your question", "xy");
    expect(screen.queryByText("nope")).toBeNull();
  });
});

describe("the requests list", () => {
  const WAITING = answer("waiting_for_a_name", { answer_id: "ca-20261020-b", quantity_name: "lamp_power", answered_at: "2026-10-20T10:05:00Z" });
  const ENTERED = answer("entered", { answer_id: "ca-20261020-a", answered_at: "2026-10-20T10:10:00Z" });

  it("lists each request with its kind, words, login, file name as text, state and answers", async () => {
    show({
      hash: "#/library/ask",
      requests: REQUESTS({
        example: true, example_note: EXAMPLE_ANSWERS, message: null,
        requests: [
          view({ item_id: "ci-1", kind: "enter_document", kind_words: "A document or value to enter", words: "the rated power", file: "ci-1--sheet.pdf", example: true, state: "Entered", answers: [ENTERED, WAITING] }),
          view({ item_id: "ci-2", words: "a second one" }),
        ],
      }),
    });
    const list = await screen.findByRole("region", { name: "Requests" });
    await within(list).findByText("the rated power");
    expect(within(list).getByText("A document or value to enter")).toBeTruthy();
    expect(within(list).getAllByText(/^member-1 · /).length).toBe(2);
    expect(within(list).getByText("File sent: ci-1--sheet.pdf")).toBeTruthy();
    expect(within(list).queryByRole("link")).toBeNull();
    expect(within(list).getByText("Entered", { selector: ".lib-state" })).toBeTruthy();
    expect(within(list).getByText("delivered · not answered yet")).toBeTruthy();
    const headOf = (words: string) => within(list).getByText(words).closest("li.lib-request")!.querySelector("p")! as HTMLElement;
    expect(within(headOf("the rated power")).getByText("example data")).toBeTruthy();
    expect(within(headOf("a second one")).queryByText("example data")).toBeNull();
    expect(within(list).getByText(EXAMPLE_ANSWERS)).toBeTruthy();
    const answers = within(list).getByRole("list", { name: "Answers" });
    expect(within(answers).getAllByRole("listitem").map((li) => li.querySelector("strong")!.textContent)).toEqual(["Entered", "Waiting for a name"]);
  });

  it("gives every number with its entry, grade, source and whether it covers the conditions", async () => {
    const a = answer("answered", {
      answer: "The lamp is 12 V.",
      numbers: [{ name: "lamp_voltage", value: 12, unit: "V", entry_id: "dia_lamp_voltage", grade: "E2", source: "maker's sheet", covers_conditions: "not_stated" }],
      gaps: [{ asked_for: "the lamp's power", looked_in: "devices" }],
    });
    show({ hash: "#/library/ask", requests: REQUESTS({ message: null, requests: [view({ answers: [a], state: "Answered" })] }) });
    const table = await screen.findByRole("table", { name: "Numbers" });
    expect(within(table).getAllByRole("cell").map((c) => c.textContent)).toEqual([
      "lamp_voltage", "12 V", "dia_lamp_voltage", "E2", "maker's sheet", "conditions not stated",
    ]);
    expect(screen.getByText(/Asked for: the lamp's power\. Looked in: devices\./)).toBeTruthy();
  });

  it("says an answer on disk cannot be read, with the reason, under its request and among the orphans", async () => {
    show({
      hash: "#/library/ask",
      requests: REQUESTS({
        message: null,
        requests: [view({ state: "an answer is on disk and cannot be read", unreadable: [{ file: "ca-20261020-100001-ab12.json", reason: "it is not valid JSON" }] })],
        orphans: [{ file: "ca-20261020-100002-cd34.json", reason: "it names no request in the inbox" }],
      }),
    });
    const list = await screen.findByRole("region", { name: "Requests" });
    expect(await within(list).findByText("An answer is on disk and cannot be read (ca-20261020-100001-ab12.json): it is not valid JSON")).toBeTruthy();
    expect(within(list).getByRole("heading", { name: "Answers that name no request in the inbox" })).toBeTruthy();
    const orphans = within(list).getByRole("list", { name: "Answers that name no request" });
    expect(orphans.textContent).toBe("An answer is on disk and cannot be read (ca-20261020-100002-cd34.json): it names no request in the inbox");
  });

  it("says there are no requests yet when the inbox has none", async () => {
    show({ hash: "#/library/withdraw" });
    expect(await screen.findByText("No requests yet.")).toBeTruthy();
    expect(screen.queryByText("example data")).toBeNull();
  });

  it("says why the list is empty when the server says so", async () => {
    show({ hash: "#/library/add", requests: REQUESTS({ message: "The librarian's inbox is not there." }) });
    expect(await screen.findByText("The librarian's inbox is not there.")).toBeTruthy();
  });

  it("is listed under each of the four forms and not under the pages or the data map", async () => {
    for (const hash of ["#/library/ask", "#/library/add", "#/library/withdraw", "#/library/offer"]) {
      const { unmount } = show({ hash });
      expect(await screen.findByRole("region", { name: "Requests" })).toBeTruthy();
      unmount();
    }
    for (const hash of ["#/library", "#/library/map"]) {
      const { unmount } = show({ hash });
      await screen.findByRole("tablist", { name: "Library" });
      expect(screen.queryByRole("region", { name: "Requests" })).toBeNull();
      unmount();
    }
  });

  it("says nowhere that the console does not send, or that the inbox is not open", async () => {
    show({ hash: "#/library/ask" });
    await screen.findByText("No requests yet.");
    expect(document.body.textContent).not.toMatch(/does not send|not open|Nothing you type here is kept/i);
  });
});
