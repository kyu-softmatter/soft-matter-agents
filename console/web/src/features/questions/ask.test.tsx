import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { ScreenContextProvider } from "../../app/screenContext";
import { fakeTransport } from "../../test/fakes";
import {
  ADDRESSEES,
  CHECKING_PERMISSIONS,
  LEFT_TO_THE_AGENTS,
  NOT_DELIVERED,
  PERMISSION_CHECK_UNAVAILABLE,
  READ_ONLY_REMOTE,
  READ_ONLY_STORE_REASON,
} from "./api";
import { submitReason } from "./ask";
import QuestionsScreen from "./index";
import { consoleRoutes, FAKE_DATA, type FakeData, MOCK_STORE, READ_ONLY_STORE } from "./testData";

/** The first screen (console card 010): one field, an Ask choice, Send; autocomplete from disk; the cards. */

const clients: Client[] = [];
afterEach(() => {
  clients.splice(0).forEach((c) => c.events.stop());
});

function show(data: FakeData = FAKE_DATA, hash = "#/questions", hostname = "127.0.0.1") {
  window.location.hash = hash;
  const { routes, submitted } = consoleRoutes(data);
  const fake = fakeTransport(routes);
  const client = new Client(fake.transport, hostname);
  clients.push(client);
  render(
    <ClientProvider client={client}>
      <ScreenContextProvider area="questions">
        <QuestionsScreen />
      </ScreenContextProvider>
    </ClientProvider>,
  );
  const gets = (path: string) => fake.calls.filter((c) => c.path === path && c.init?.method !== "POST").length;
  const posts = () => fake.calls.filter((c) => c.init?.method === "POST");
  return { ...fake, client, submitted, gets, posts };
}

/** What an older version of the console wrote: a request left to the agents. Still read, never offered. */
const LEFT_REQUEST = {
  id: "qr-20261024-174512-k3p9", words: "Is the stage drifting at night?", login: "member-2",
  asked_at: "2026-10-24T17:45:12Z", addressed_to: "agents_decide" as const, state: NOT_DELIVERED,
  runs_wait_for_signature: true,
};

const field = () => screen.getByLabelText("Your question") as HTMLTextAreaElement;
const send = () => screen.getByRole("button", { name: "Send" }) as HTMLButtonElement;
const type = (v: string) => fireEvent.change(field(), { target: { value: v } });
const ready = async () => {
  await waitFor(() => expect(send().disabled).toBe(true)); // no words yet
  await screen.findByRole("region", { name: "Question cards" });
};

/** Ask `to` the words and read the status line the form shows. */
async function sendTo(words: string, to: string) {
  const t = show();
  await ready();
  type(words);
  fireEvent.change(screen.getByLabelText("Ask"), { target: { value: to } });
  await waitFor(() => expect(send().disabled).toBe(false));
  await act(async () => void fireEvent.click(send()));
  const status = await screen.findByRole("status");
  return { t, status };
}

describe("the field", () => {
  it("is one field, an Ask choice and Send, with no purpose and no observable", async () => {
    show();
    const form = await screen.findByRole("form", { name: "Ask a question" });
    expect(form.querySelectorAll("textarea, input[type=text], input:not([type])")).toHaveLength(1);
    const ask = screen.getByLabelText("Ask") as HTMLSelectElement;
    const [placeholder, ...choices] = [...ask.options];
    expect([placeholder.value, placeholder.textContent, placeholder.disabled]).toEqual(["", "Choose who to ask", true]);
    expect(choices.map((o) => [o.value, o.textContent])).toEqual([
      ["microscope", "The microscope"],
      ["simulation", "The simulation"],
      ["librarian", "The librarian"],
    ]);
    expect(choices.map((o) => [o.value, o.textContent])).toEqual(ADDRESSEES.map((a) => [a.value, a.label]));
    expect(ask.value).toBe(""); // none picked: the placeholder shows
    expect(screen.queryByLabelText(/purpose/i)).toBeNull();
    expect(screen.queryByLabelText(/observable/i)).toBeNull();
    expect(screen.queryByRole("tab", { name: "Ask" })).toBeNull();
  });

  it("has the three choices in words the person uses, and no choice left to the agents", () => {
    expect(ADDRESSEES.map((a) => a.label)).toEqual(["The microscope", "The simulation", "The librarian"]);
    expect(screen.queryByText(/let the agents decide/i)).toBeNull();
  });

  it("keeps Send off while no one is picked, even with words typed, and picking a choice sends nothing", async () => {
    const t = show();
    await ready();
    type("Is the bead stuck?");
    expect(send().disabled).toBe(true); // words, but nobody asked
    fireEvent.submit(screen.getByRole("form", { name: "Ask a question" }));
    expect(t.posts()).toHaveLength(0);
    fireEvent.change(screen.getByLabelText("Ask"), { target: { value: "microscope" } });
    await waitFor(() => expect(send().disabled).toBe(false));
    expect(t.posts()).toHaveLength(0); // picking sends nothing
    expect(field().value).toBe("Is the bead stuck?");
  });

  it("keeps Send off when someone is picked and the words are blank", async () => {
    show();
    await ready();
    fireEvent.change(screen.getByLabelText("Ask"), { target: { value: "librarian" } });
    type("   ");
    expect(send().disabled).toBe(true);
  });

  it("empties both the words and the choice after a send", async () => {
    await sendTo("Is the bead stuck?", "microscope");
    expect(field().value).toBe("");
    expect((screen.getByLabelText("Ask") as HTMLSelectElement).value).toBe("");
    expect(send().disabled).toBe(true);
  });

  it("keeps the words and the choice when the server refused the send", async () => {
    show({ ...FAKE_DATA, postRefusal: { status: 403, body: { detail: { code: "role", message: "No." } } } });
    await ready();
    type("How fast?");
    fireEvent.change(screen.getByLabelText("Ask"), { target: { value: "simulation" } });
    await waitFor(() => expect(send().disabled).toBe(false));
    await act(async () => void fireEvent.click(send()));
    await screen.findByRole("alert");
    expect(field().value).toBe("How fast?");
    expect((screen.getByLabelText("Ask") as HTMLSelectElement).value).toBe("simulation");
  });

  it("sends the words exactly as typed and the choice, and nothing else", async () => {
    const t = show();
    await ready();
    const typed = "  Does it flow\n  more easily?  ";
    type(typed);
    fireEvent.change(screen.getByLabelText("Ask"), { target: { value: "simulation" } });
    await waitFor(() => expect(send().disabled).toBe(false));
    await act(async () => void fireEvent.click(send()));
    await waitFor(() => expect(t.submitted).toHaveLength(1));
    expect(t.submitted[0]).toEqual({ words: typed, addressed_to: "simulation" });
    expect(Object.keys(t.submitted[0]).sort()).toEqual(["addressed_to", "words"]);
    const sent = JSON.parse(String(t.posts()[0].init?.body));
    expect(sent.words).toBe(typed); // byte-equal: nothing trimmed on the way
    expect(t.posts().map((p) => p.path)).toEqual(["/api/console/question-requests"]);
  });

  it("says 'Sent to the microscope as question <id>.' when the microscope was asked", async () => {
    const { status } = await sendTo("Is the bead stuck?", "microscope");
    expect(status.textContent).toBe("Sent to the microscope as question mic-20261026-c001.");
    expect(field().value).toBe(""); // sent: the field is free for the next
  });

  it("says 'Sent to the simulation as question <id>.' when the simulation was asked", async () => {
    const { status } = await sendTo("Does it relax?", "simulation");
    expect(status.textContent).toBe("Sent to the simulation as question sim-20261026-c001.");
  });

  it("says 'Sent to the librarian.' when the librarian was asked, and the card has no question id", async () => {
    const { t, status } = await sendTo("Which entry holds the pixel size?", "librarian");
    expect(status.textContent).toBe("Sent to the librarian.");
    expect(field().value).toBe("");
    expect(t.submitted[0]).toEqual({ words: "Which entry holds the pixel size?", addressed_to: "librarian" });
    await waitFor(() => expect(t.gets("/api/console/question-cards")).toBe(2));
    const cards = screen.getByRole("region", { name: "Question cards" });
    const card = cards.querySelector("article[data-kind='item']") as HTMLElement;
    expect(card.querySelector(".ask-words")?.textContent).toBe("Which entry holds the pixel size?");
    expect(card.textContent).toContain("The librarian");
    expect(card.textContent).toContain("delivered · not answered yet");
    expect(card.textContent).not.toMatch(/null|undefined|· $/);
    expect(card.textContent).not.toContain("waits for the person's signature");
  });

  it("says nothing of an inbox not being open: that is over", async () => {
    const { status } = await sendTo("Is the bead stuck?", "microscope");
    expect(status.textContent).not.toMatch(/until the agents|not picked up|new inbox/i);
  });

  it("does not send an empty or blank field", async () => {
    const t = show();
    await ready();
    expect(send().disabled).toBe(true);
    type("   \n ");
    expect(send().disabled).toBe(true);
    fireEvent.submit(screen.getByRole("form", { name: "Ask a question" }));
    expect(t.posts()).toHaveLength(0);
  });

  it("reads the cards again after a send, so the new request is there", async () => {
    const t = show();
    await ready();
    expect(t.gets("/api/console/question-cards")).toBe(1);
    type("A new question");
    fireEvent.change(screen.getByLabelText("Ask"), { target: { value: "microscope" } });
    await waitFor(() => expect(send().disabled).toBe(false));
    await act(async () => void fireEvent.click(send()));
    await waitFor(() => expect(t.gets("/api/console/question-cards")).toBe(2));
    expect(await screen.findByText("A new question")).toBeTruthy();
  });
});

describe("who may send (the server decides; the screen shows why)", () => {
  it("orders the reasons: remote view, permission, then a store that cannot take it", () => {
    const LOCAL = { readOnly: false, why: null };
    const ok = { data: { submit_question: { allowed: true, reason: null } } };
    const viewer = { data: { submit_question: { allowed: false, reason: "This login can only look" } } };
    const remote = { readOnly: true, why: "remote view" };
    expect(submitReason(LOCAL, ok, { data: MOCK_STORE })).toBeUndefined();
    expect(submitReason(LOCAL, ok, { data: READ_ONLY_STORE })).toBe(READ_ONLY_STORE_REASON);
    expect(submitReason(LOCAL, viewer, { data: READ_ONLY_STORE })).toBe("This login can only look");
    expect(submitReason(remote, ok, { data: MOCK_STORE })).toBe(READ_ONLY_REMOTE);
    expect(submitReason(LOCAL, {}, { data: MOCK_STORE })).toBe(CHECKING_PERMISSIONS);
    expect(submitReason(LOCAL, { data: {} }, { data: MOCK_STORE })).toBe(PERMISSION_CHECK_UNAVAILABLE);
    expect(submitReason(LOCAL, { error: "HTTP 502" }, { data: MOCK_STORE })).toBe(PERMISSION_CHECK_UNAVAILABLE);
  });

  it("is disabled, with the reason, for a store that cannot take a request", async () => {
    const t = show({ ...FAKE_DATA, store: READ_ONLY_STORE });
    expect(await screen.findByText(READ_ONLY_STORE_REASON)).toBeTruthy();
    type("How fast?");
    expect(send().disabled).toBe(true);
    fireEvent.submit(screen.getByRole("form", { name: "Ask a question" }));
    expect(t.posts()).toHaveLength(0);
  });

  it("shows the shared permission reason for a viewer", async () => {
    show({ ...FAKE_DATA, permissions: { submit_question: { allowed: false, reason: "Needs the operator role" } } });
    expect(await screen.findByText("Needs the operator role")).toBeTruthy();
    type("q");
    expect(send().disabled).toBe(true);
  });

  it("is greyed out on a remote screen, with the read-only badge", async () => {
    show(FAKE_DATA, "#/questions", "lab-pc.example.test");
    expect((await screen.findAllByText(READ_ONLY_REMOTE)).length).toBeGreaterThan(0);
    type("q");
    expect(send().disabled).toBe(true);
  });

  it("disables Send when the permission check cannot be read", async () => {
    show({ ...FAKE_DATA, permissions: null });
    expect(await screen.findByText(PERMISSION_CHECK_UNAVAILABLE)).toBeTruthy();
    type("q");
    expect(send().disabled).toBe(true);
  });

  it("shows a non-remote 403 next to the form and leaves the app writable", async () => {
    const t = show({
      ...FAKE_DATA,
      postRefusal: { status: 403, body: { detail: { code: "role", message: "This login can only look: it cannot ask a question." } } },
    });
    await ready();
    type("How fast?");
    fireEvent.change(screen.getByLabelText("Ask"), { target: { value: "microscope" } });
    await waitFor(() => expect(send().disabled).toBe(false));
    await act(async () => void fireEvent.click(send()));
    const form = screen.getByRole("form", { name: "Ask a question" });
    expect((await within(form).findByRole("alert")).textContent).toBe("This login can only look: it cannot ask a question.");
    expect(t.client.readOnly.get()).toEqual({ readOnly: false, why: null });
    expect(field().value).toBe("How fast?"); // not lost: the person can try again
  });

  it("a 403 remote_view on send switches the app to read-only (the shell's rule)", async () => {
    const t = show({
      ...FAKE_DATA,
      postRefusal: { status: 403, body: { detail: { code: "remote_view", message: "remote view: no" } } },
    });
    await ready();
    type("How fast?");
    fireEvent.change(screen.getByLabelText("Ask"), { target: { value: "microscope" } });
    await waitFor(() => expect(send().disabled).toBe(false));
    await act(async () => void fireEvent.click(send()));
    await waitFor(() => expect(t.client.readOnly.get().readOnly).toBe(true));
    expect(send().disabled).toBe(true);
  });
});

describe("autocomplete: only strings already on disk, each labelled", () => {
  async function typeAndSee(value: string) {
    const t = show();
    await ready();
    type(value);
    return t;
  }

  it("offers nothing while the field is empty", async () => {
    show();
    await ready();
    expect(screen.queryByRole("listbox", { name: "Suggestions" })).toBeNull();
  });

  it("offers an earlier question and a registered name, each with its label", async () => {
    await typeAndSee("pix");
    const list = await screen.findByRole("listbox", { name: "Suggestions" });
    const options = within(list).getAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual(["pixel_sizeregistered name"]);
    cleanupField();
    type("how far");
    const again = await screen.findByRole("listbox", { name: "Suggestions" });
    expect(within(again).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "How far apart are the wells at 4x?earlier question",
    ]);
  });

  it("offers nothing that is not in the list from the disk, and matches without case", async () => {
    await typeAndSee("REFRACTIVE");
    const list = await screen.findByRole("listbox", { name: "Suggestions" });
    expect(within(list).getAllByRole("option")).toHaveLength(1);
    cleanupField();
    type("zzzz nothing like it");
    expect(screen.queryByRole("listbox", { name: "Suggestions" })).toBeNull();
  });

  it("matches an earlier question without regard to case", async () => {
    await typeAndSee("HOW FAR APART");
    expect(await screen.findByRole("option", { name: /How far apart/ })).toBeTruthy();
  });

  it("offers nothing again once the field has been emptied", async () => {
    await typeAndSee("how far");
    await screen.findByRole("listbox", { name: "Suggestions" });
    type("");
    expect(screen.queryByRole("listbox", { name: "Suggestions" })).toBeNull();
    type("   ");
    expect(screen.queryByRole("listbox", { name: "Suggestions" })).toBeNull();
  });

  it("an empty disk offers nothing", async () => {
    show({ ...FAKE_DATA, suggestions: [], cards: { requests: [], items: [], questions: [] } });
    await ready();
    type("a");
    expect(screen.queryByRole("listbox", { name: "Suggestions" })).toBeNull();
  });

  it("choosing an earlier question inserts its text and sends nothing", async () => {
    const t = await typeAndSee("how far");
    fireEvent.click(await screen.findByRole("option", { name: /How far apart/ }));
    expect(field().value).toBe("How far apart are the wells at 4x?");
    expect(t.posts()).toHaveLength(0);
    expect(screen.queryByRole("listbox", { name: "Suggestions" })).toBeNull();
  });

  it("choosing a registered name replaces the word being typed and sends nothing", async () => {
    const t = await typeAndSee("What is the pix");
    fireEvent.click(await screen.findByRole("option", { name: /pixel_size/ }));
    expect(field().value).toBe("What is the pixel_size");
    expect(t.posts()).toHaveLength(0);
  });

  it("reads the suggestions once, not on every key", async () => {
    const t = show();
    await ready();
    for (const v of ["p", "pi", "pix", "pixe"]) type(v);
    await screen.findByRole("listbox", { name: "Suggestions" });
    expect(t.gets("/api/console/suggestions")).toBe(1);
  });

  it("never offers the stores contents: the cards' titles are not suggestions", async () => {
    await typeAndSee("structural");
    expect(screen.queryByRole("listbox", { name: "Suggestions" })).toBeNull();
  });
});

function cleanupField() {
  fireEvent.change(field(), { target: { value: "" } });
}

describe("the cards below the field", () => {
  it("shows a request written in the console as 'written in the console · not delivered'", async () => {
    show();
    const cards = await screen.findByRole("region", { name: "Question cards" });
    const req = within(cards).getByText("How far apart are the wells at 4x?").closest("article") as HTMLElement;
    expect(req.textContent).toContain("written in the console · not delivered");
    expect(req.textContent).not.toContain("not picked up");
    expect(req.textContent).toContain("member-2");
    expect(req.textContent).toContain("The librarian");
    expect(req.textContent).toContain("Every run from it waits for the person's signature");
    expect(within(req).queryByRole("list", { name: "Progress" })).toBeNull(); // nothing to measure yet
  });

  it("shows an earlier request left to the agents with its addressee in words, never the raw value", async () => {
    show({ ...FAKE_DATA, cards: { ...FAKE_DATA.cards, requests: [LEFT_REQUEST, ...FAKE_DATA.cards.requests] } });
    const cards = await screen.findByRole("region", { name: "Question cards" });
    const req = within(cards).getByText("Is the stage drifting at night?").closest("article") as HTMLElement;
    expect(req.textContent).toContain("written in the console · not delivered");
    expect(req.textContent).toContain(LEFT_TO_THE_AGENTS);
    expect(LEFT_TO_THE_AGENTS).toBe("Left to the agents · no longer offered");
    expect(req.textContent).not.toContain("agents_decide");
    expect(req.textContent).not.toContain("agents decide");
  });

  it("shows the same words on that request's own page", async () => {
    show({ ...FAKE_DATA, cards: { ...FAKE_DATA.cards, requests: [LEFT_REQUEST] } }, "#/questions/requests/qr-20261024-174512-k3p9");
    const p = await screen.findByRole("region", { name: "Question request" });
    expect(p.textContent).toContain(LEFT_TO_THE_AGENTS);
    expect(p.textContent).not.toContain("agents_decide");
    expect(p.textContent).not.toContain("agents decide");
  });

  it("shows every item delivered to an inbox, newest first, each with its words, login, time, agent and question id", async () => {
    show();
    const cards = await screen.findByRole("region", { name: "Question cards" });
    const items = [...cards.querySelectorAll("article[data-kind='item']")] as HTMLElement[];
    expect(items.map((a) => a.querySelector(".ask-words")?.textContent)).toEqual([
      "Is the stage drifting?", "How long does relaxation take?", "Image the whole well at 40x", "What is the pixel size?",
    ]);
    const first = items[0];
    expect(first.textContent).toContain("otto");
    expect(first.textContent).toContain("The microscope");
    expect(first.textContent).toContain("mic-20261026-c004");
    expect(first.textContent).toContain("Every run from it waits for the person's signature.");
    expect(within(first).queryByRole("list", { name: "Progress" })).toBeNull();
    expect(items[1].textContent).toContain("The simulation");
    expect(items[2].textContent).toContain("member-2");
  });

  it("shows exactly one of the four states on an item, the reason as written", async () => {
    show();
    const cards = await screen.findByRole("region", { name: "Question cards" });
    const items = [...cards.querySelectorAll("article[data-kind='item']")] as HTMLElement[];
    expect(items.map((a) => a.querySelector(".console-tag")?.textContent)).toEqual([
      "delivered · not answered yet",
      "taken up as sim-20261026-c002",
      "refused · that objective is not on this stand",
      "an answer is on disk and cannot be read",
    ]);
    for (const a of items) expect(a.querySelectorAll(".console-tag")).toHaveLength(1);
  });

  it("shows a question just sent to the microscope as an item card on the next read", async () => {
    const { t } = await sendTo("A fresh one", "microscope");
    await waitFor(() => expect(t.gets("/api/console/question-cards")).toBe(2));
    const cards = screen.getByRole("region", { name: "Question cards" });
    const first = cards.querySelector("article[data-kind='item']") as HTMLElement;
    expect(first.querySelector(".ask-words")?.textContent).toBe("A fresh one");
    expect(first.textContent).toContain("delivered · not answered yet");
  });

  it("shows the agents' questions with the five-step bar, from the files", async () => {
    show();
    const cards = await screen.findByRole("region", { name: "Question cards" });
    const sim = within(cards).getByText("structural relaxation time").closest("article") as HTMLElement;
    const steps = within(within(sim).getByRole("list", { name: "Progress" })).getAllByRole("listitem");
    expect(steps.map((s) => [s.textContent?.split(" (")[0], s.getAttribute("data-done")])).toEqual([
      ["Asked", "true"], ["Designed", "true"], ["Signed", "false"], ["Run", "true"], ["Result", "true"],
    ]);
    const mic = within(cards).getByText("tracer diffusivity").closest("article") as HTMLElement;
    const micSteps = within(within(mic).getByRole("list", { name: "Progress" })).getAllByRole("listitem");
    expect(micSteps.map((s) => s.getAttribute("data-done"))).toEqual(["true", "false", "false", "unknown", "false"]);
    expect(micSteps[3].textContent).toContain("not known");
  });

  it("has no table of purposes and observables any more", async () => {
    show();
    await screen.findByRole("region", { name: "Question cards" });
    expect(screen.queryByRole("columnheader", { name: "Purpose" })).toBeNull();
    expect(screen.queryByRole("columnheader", { name: "Observable" })).toBeNull();
  });

  it("opens an agents' question on a click, on the question's own page", async () => {
    show();
    const cards = await screen.findByRole("region", { name: "Question cards" });
    fireEvent.click(within(cards).getByRole("button", { name: /structural relaxation time/ }));
    expect(window.location.hash).toBe("#/questions/questions/sim-20260923-001");
    expect(await screen.findByRole("region", { name: "Question sim-20260923-001" })).toBeTruthy();
  });

  it("opens a request written in the console on a click, on its own page", async () => {
    show();
    const cards = await screen.findByRole("region", { name: "Question cards" });
    fireEvent.click(within(cards).getByRole("button", { name: /How far apart are the wells at 4x\?/ }));
    expect(window.location.hash).toBe("#/questions/requests/qr-20261023-091500-w3k8");
    expect(await screen.findByRole("region", { name: "Question request" })).toBeTruthy();
  });

  it("says plainly when there are no questions yet", async () => {
    show({ ...FAKE_DATA, cards: { requests: [], items: [], questions: [] }, suggestions: [] });
    expect(await screen.findByText("No questions yet.")).toBeTruthy();
  });

  it("does not say there are no questions when only an inbox item is there", async () => {
    const item = FAKE_DATA.cards.items[0];
    show({ ...FAKE_DATA, cards: { requests: [], items: [item], questions: [] } });
    expect(await screen.findByText(item.words)).toBeTruthy();
    expect(screen.queryByText("No questions yet.")).toBeNull();
  });

  it("reads once on open, again on Refresh; no polling", async () => {
    const t = show();
    await screen.findByRole("region", { name: "Question cards" });
    expect(t.gets("/api/console/question-cards")).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(t.gets("/api/console/question-cards")).toBe(2));
  });
});

describe("a question delivered to the librarian", () => {
  const answered = {
    answer_id: "ca-20261027-101500-ab12", item_id: "ci-20261027-101000-cd34", answered_by: "librarian",
    answered_at: "2026-10-27T10:15:00Z", outcome: "answered", reason: "The store holds it.", kb_version: "kbv-0123456789ab",
    answer: "The pixel size is 6.5 um.", entries_cited: [], numbers: [], gaps: [], entries_marked: [], other_side: [],
    quantity_name: null, entries_made: [], example: false,
  };
  const item = {
    item_id: "ci-20261027-101000-cd34", question_id: null, agent: "librarian" as const, words: "What is the pixel size?",
    login: "otto", asked_at: "2026-10-27T10:10:00Z", state: "Answered", runs_wait_for_signature: false,
    latest_answer: answered,
  };

  it("shows its latest answer as the Library shows one, and no question id or signature note", async () => {
    show({ ...FAKE_DATA, cards: { requests: [], items: [item], questions: [] } });
    const cards = await screen.findByRole("region", { name: "Question cards" });
    const card = cards.querySelector("article[data-kind='item']") as HTMLElement;
    expect(card.textContent).toContain("otto");
    expect(card.textContent).toContain("The librarian");
    expect(card.textContent).not.toContain("null");
    expect(card.textContent).not.toContain("waits for the person's signature");
    const latest = within(card).getByRole("list", { name: "Latest answer" });
    expect(within(latest).getByText("Answered")).toBeTruthy();
    expect(within(latest).getByText("The pixel size is 6.5 um.")).toBeTruthy();
    expect(within(card).queryByText("example data")).toBeNull();
  });

  it("shows no answer list while there is no answer", async () => {
    show({ ...FAKE_DATA, cards: { requests: [], items: [{ ...item, latest_answer: null, state: "delivered · not answered yet" }], questions: [] } });
    const cards = await screen.findByRole("region", { name: "Question cards" });
    expect(within(cards).getByText("delivered · not answered yet")).toBeTruthy();
    expect(within(cards).queryByRole("list", { name: "Latest answer" })).toBeNull();
  });
});
