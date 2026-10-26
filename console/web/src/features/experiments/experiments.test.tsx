import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { ScreenContextProvider } from "../../app/screenContext";
import { fakeTransport, type Route } from "../../test/fakes";
import { PATHS as IPATHS } from "../instruments/api";
import { PATHS } from "./api";
import ExperimentsScreen from "./index";

/** The Experiments screens (console card 014): show plans and runs, draft, and offer Run that sends nothing. */

const clients: Client[] = [];
afterEach(() => {
  clients.splice(0).forEach((c) => c.events.stop());
});

const SHA = "ab".repeat(32);
const EXAMPLE_NOTE =
  "This is example data: a copy of recorded files kept with the console, not from any run at this microscope. " +
  "Where each file came from is written in mock_data/SOURCE.md.";
const DRAFTS_NOTE = "Drafts are not saved yet: where a console draft lives is still to be designed. A draft you make below is shown and then gone.";
const NOT_BUILT = "Run is not built yet: the runtime has no part that receives this request, so nothing is sent.";

const OFFER_OFF = (why: string) => ({ offered: false, why_not: why, approval_name: null, approval_sha256: null, built: false, message: NOT_BUILT });
const OFFER_ON = { offered: true, why_not: null, approval_name: "appr-1-r1.json", approval_sha256: SHA, built: false, message: NOT_BUILT };

const plan = (over: Record<string, unknown> = {}) => ({
  plan_id: "plan-A", revision: 1, qid: "mic-1", version: 1, card_name: "plan.json", status: "approved",
  state: "approved", state_words: "approved: signed and on disk", plan_hash: "c".repeat(64),
  approval: {
    name: "appr-1-r1.json", id: "appr-1", approved_by: "kyuhwan", approved_at: "2026-09-25T10:00:00Z",
    signed_through: null, signed_words: "signed by hand",
  },
  void_approvals: [], run_ids: [], run_offer: OFFER_ON, ...over,
});

const run = (over: Record<string, unknown> = {}) => ({
  run_id: "run-20260924-003", plan_id: "plan-A", qid: "mic-1", plan_on_disk: true, state: "ended",
  how: "completed", how_words: "finished all its steps", started_at: "2026-09-24T10:00:00Z", finished_at: "2026-09-24T10:05:00Z",
  approval: { id: "appr-1", kind: "plan_approval", sha256: SHA, signed_through: null, signed_words: "signed by hand" },
  refusal: null, events: { count: 12, words: "12 events: 3 commands sent, 9 readings" }, hand_steps: [],
  waiting_line: null, tweezers_note: null, ...over,
});

const PLANS = (over: Record<string, unknown> = {}) => ({
  example: false, example_note: null, drafts_note: DRAFTS_NOTE, plans: [plan()], runs: [], problems: [], ...over,
});

const SAMPLE = (over: Record<string, unknown> = {}) => ({
  example: false, example_note: null, record: null,
  message: "No sample record yet: where a sample's record lives is still being designed.", loading_checks: [], ...over,
});

const PARTS = [
  { part: "frames_with_stage_readback", state: "not_built", why: "no run yet saves frames together with the stage's read-back position" },
  { part: "hole_fitter", state: "not_built", why: "the runtime has no hole fitter" },
  { part: "candidate_finder", state: "not_built", why: "the runtime has no candidate finder; a model's guesses are never drawn as candidates" },
  { part: "flags_and_confirmations", state: "not_built", why: "nowhere to write them" },
];
const MAP = (over: Record<string, unknown> = {}) => ({
  example: false, example_note: null, parts: PARTS, example_map: null, moves: [], flags: [], candidates: [],
  message: "The sample map is not built yet: it needs parts the runtime does not have. Nothing is drawn, flagged or confirmed here.", ...over,
});

const DRAFT_OUT = (kind: string, valid: boolean) => ({
  kind, card: { card: "plan", id: `plan-${kind}`, author: "human" }, valid,
  problems: valid ? [] : ["$.operation: refused by the schema for a light or exposure change"], range_problems: [],
  refused_today: ["Refused until you write a limit: your safety file has none for this part yet."],
  saved: false, note: "A draft is shown in full and saved nowhere.",
});

interface Opts {
  plans?: unknown;
  sample?: unknown;
  map?: unknown;
  hash?: string;
  run?: Route;
  draft?: Route;
}

function show(opts: Opts = {}) {
  window.location.hash = opts.hash ?? "#/experiments";
  const fake = fakeTransport({
    [PATHS.plans]: () => ({ status: 200, body: opts.plans ?? PLANS() }),
    [PATHS.sample]: () => ({ status: 200, body: opts.sample ?? SAMPLE() }),
    [PATHS.sampleMap]: () => ({ status: 200, body: opts.map ?? MAP() }),
    [PATHS.run]: opts.run ?? (() => ({ status: 200, body: { outcome: "not_built", message: NOT_BUILT, would_send: { run: SHA } } })),
    [IPATHS.draft]: opts.draft ?? ((init) => ({ status: 200, body: DRAFT_OUT(JSON.parse(String(init?.body)).kind, JSON.parse(String(init?.body)).kind === "trap_steps") })),
  });
  const client = new Client(fake.transport, "127.0.0.1");
  clients.push(client);
  render(
    <ClientProvider client={client}>
      <ScreenContextProvider area="experiments">
        <ExperimentsScreen />
      </ScreenContextProvider>
    </ClientProvider>,
  );
  const posts = () => fake.calls.filter((c) => c.init?.method === "POST");
  return { ...fake, client, posts };
}

const rowsOf = (table: HTMLElement) =>
  within(table).getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell").map((c) => c.textContent));

describe("the two pages", () => {
  it("offers Plan and Sample map, Plan first", async () => {
    show();
    const bar = await screen.findByRole("tablist", { name: "Experiments" });
    expect(within(bar).getAllByRole("tab").map((t) => t.textContent)).toEqual(["Plan", "Sample map"]);
    expect((await screen.findByRole("tab", { name: "Plan" })).getAttribute("aria-selected")).toBe("true");
  });

  it("opens the Sample map from its address", async () => {
    show({ hash: "#/experiments/sample-map" });
    expect((await screen.findByRole("tab", { name: "Sample map" })).getAttribute("aria-selected")).toBe("true");
  });
});

describe("Plan: the plans on disk", () => {
  it("lists each plan with its state in words, its approval and how it was signed, and its runs", async () => {
    show({
      plans: PLANS({
        plans: [
          plan({ run_ids: ["run-20260924-003"] }),
          plan({
            plan_id: "plan-B", revision: 2, status: "approved", state: "waiting_for_signature",
            state_words: "waiting for a signature", approval: null, run_offer: OFFER_OFF("Only an approved plan can be run; this one is waiting for a signature."),
          }),
          plan({
            plan_id: "plan-C", revision: 1, state: "approved",
            approval: {
              name: "appr-2-r1.json", id: "appr-2", approved_by: "kyuhwan", approved_at: "2026-09-25T10:00:00Z",
              signed_through: { via: "console", login: "kyuhwan" },
              signed_words: "signed through the console under the login kyuhwan (the runtime checks that login when it starts)",
            },
          }),
        ],
      }),
    });
    const table = await screen.findByRole("table", { name: "Plans" });
    const rows = rowsOf(table);
    expect(rows[0].slice(0, 5)).toEqual(["plan-A", "1", "approved: signed and on disk", "signed by hand, kyuhwan, 2026-09-25 10:00:00", "run-20260924-003"]);
    expect(rows[1].slice(0, 5)).toEqual(["plan-B", "2", "waiting for a signature", "no approval on disk", "none"]);
    expect(rows[2][3]).toContain("signed through the console under the login kyuhwan (the runtime checks that login when it starts)");
  });

  it("says why an approval on disk is void, naming the file", async () => {
    show({
      plans: PLANS({
        plans: [plan({ state: "waiting_for_signature", state_words: "waiting for a signature", approval: null,
          void_approvals: [{ name: "appr-old.json", why: "the plan changed after it was signed (the plan's hash is no longer the one approved)" }],
          run_offer: OFFER_OFF("Only an approved plan can be run.") })],
      }),
    });
    const void_ = await screen.findByRole("list", { name: "Approvals that do not cover plan-A" });
    expect(within(void_).getByText(/appr-old\.json: the plan changed after it was signed/)).toBeTruthy();
  });

  it("says there is no plan on disk when there is none", async () => {
    show({ plans: PLANS({ plans: [] }) });
    expect(await screen.findByText("No plan on disk.")).toBeTruthy();
    expect(screen.queryByRole("table", { name: "Plans" })).toBeNull();
  });

  it("shows the problems the files had, and does not hide the plans that were fine", async () => {
    show({ plans: PLANS({ problems: ["questions/mic-2/plan.json: not valid JSON"] }) });
    expect(await screen.findByText("questions/mic-2/plan.json: not valid JSON")).toBeTruthy();
    expect(screen.getByRole("table", { name: "Plans" })).toBeTruthy();
  });

  it("puts the example note on the page, naming the SOURCE file, only when the data is an example", async () => {
    show({ plans: PLANS({ example: true, example_note: EXAMPLE_NOTE }) });
    expect(await screen.findByText(/This is example data/)).toBeTruthy();
    expect(screen.getByText(/mock_data\/SOURCE\.md/)).toBeTruthy();
  });

  it("has no example note on a real tree", async () => {
    show();
    await screen.findByRole("table", { name: "Plans" });
    expect(screen.queryByText(/example data/i)).toBeNull();
  });
});

describe("Plan: the run offer", () => {
  it("offers Run on an approved plan with its approval file, and says what it is until the runtime has the part", async () => {
    show();
    expect(await screen.findByRole("button", { name: "Run" })).toBeTruthy();
    expect(screen.getByText(/not built yet/)).toBeTruthy();
  });

  it("pressing Run posts the plan's id and revision and shows 'not built yet' with what would be sent", async () => {
    const { posts } = show();
    fireEvent.click(await screen.findByRole("button", { name: "Run" }));
    expect(await screen.findByText(NOT_BUILT)).toBeTruthy();
    expect(screen.getByText(`Would send: {"run":"${SHA}"}`)).toBeTruthy();
    const sent = posts();
    expect(sent.map((c) => c.path)).toEqual([PATHS.run]);
    expect(JSON.parse(String(sent[0].init?.body))).toEqual({ plan_id: "plan-A", plan_revision: 1 });
  });

  it("shows no Run button on a plan that is not offered, and says why in the server's words", async () => {
    show({
      plans: PLANS({
        plans: [plan({ state: "waiting_for_signature", state_words: "waiting for a signature", approval: null,
          run_offer: OFFER_OFF("Only an approved plan can be run; this one is waiting for a signature.") })],
      }),
    });
    expect(await screen.findByText("Only an approved plan can be run; this one is waiting for a signature.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Run" })).toBeNull();
  });

  it("shows a refusal from the server in its words, and no 'not built' answer", async () => {
    show({
      run: () => ({ status: 409, body: { detail: { code: "not_approved", message: "The approval file is not on disk." } } }),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Run" }));
    expect(await screen.findByText(/The approval file is not on disk\./)).toBeTruthy();
    expect(screen.queryByText(NOT_BUILT)).toBeNull();
  });

  it("offers nothing that stands for the hand-over, a confirm or a stop of a run", async () => {
    show({ plans: PLANS({ plans: [plan({ run_ids: ["run-20260924-003"] })], runs: [run()] }) });
    await screen.findByRole("table", { name: "Plans" });
    const names = screen.getAllByRole("button").map((b) => b.textContent);
    expect(names.filter((n) => /confirm|hand over|stop|start/i.test(n ?? ""))).toEqual([]);
  });

  it("sends nothing when the page only opens", async () => {
    const { posts } = show();
    await screen.findByRole("table", { name: "Plans" });
    expect(posts()).toEqual([]);
  });
});

describe("Plan: the runs", () => {
  it("shows who signed and how, how it ended in words, when, and an event summary", async () => {
    show({ plans: PLANS({ runs: [run({ approval: { id: "appr-1", kind: "plan_approval", sha256: SHA, signed_through: { via: "console", login: "kyuhwan" }, signed_words: "signed through the console under the login kyuhwan (the runtime checks that login when it starts)" } })] }) });
    const sec = await screen.findByRole("region", { name: "Run run-20260924-003" });
    expect(within(sec).getByText("finished all its steps")).toBeTruthy();
    expect(within(sec).getByText(/signed through the console under the login kyuhwan/)).toBeTruthy();
    expect(within(sec).getByText("12 events: 3 commands sent, 9 readings")).toBeTruthy();
    expect(within(sec).getByText(/2026-09-24 10:00:00/)).toBeTruthy();
    expect(within(sec).getByText(/plan-A/)).toBeTruthy();
  });

  it("says a refused run was refused and why, and that no command went out", async () => {
    show({ plans: PLANS({ runs: [run({ how: "refused", how_words: "refused by the runtime before any command went out", refusal: "the approval's plan_hash does not match" })] }) });
    const sec = await screen.findByRole("region", { name: "Run run-20260924-003" });
    expect(within(sec).getByText("refused by the runtime before any command went out")).toBeTruthy();
    expect(within(sec).getByText(/the approval's plan_hash does not match/)).toBeTruthy();
  });

  it("a run with an open hand-step sheet says it waits at the microscope, and has NO button", async () => {
    const open = { sheet_id: "step-1", channel: "optical_tweezers", element: "laser", instruction: "Switch the laser on.", opened_at: "2026-09-24T10:01:00Z", confirmed: false, confirmed_at: null, confirmed_by: null, observed: null };
    show({ plans: PLANS({ runs: [run({ state: "running", how: null, how_words: null, finished_at: null, hand_steps: [open], waiting_line: "Waiting for a step at the microscope. Confirm it there." })] }) });
    const sec = await screen.findByRole("region", { name: "Run run-20260924-003" });
    expect(within(sec).getByText("Waiting for a step at the microscope. Confirm it there.")).toBeTruthy();
    expect(within(sec).getByText(/Switch the laser on\./)).toBeTruthy();
    expect(within(sec).queryAllByRole("button")).toEqual([]);
  });

  it("shows a confirmed hand step with who confirmed it and when", async () => {
    const done = { sheet_id: "step-1", channel: "sample", element: null, instruction: "Load the sample.", opened_at: "2026-09-24T10:01:00Z", confirmed: true, confirmed_at: "2026-09-24T10:02:00Z", confirmed_by: "kyuhwan", observed: "slide in place" };
    show({ plans: PLANS({ runs: [run({ hand_steps: [done] })] }) });
    const sec = await screen.findByRole("region", { name: "Run run-20260924-003" });
    expect(within(sec).getByText(/confirmed by kyuhwan, 2026-09-24 10:02:00/)).toBeTruthy();
    expect(within(sec).getByText(/slide in place/)).toBeTruthy();
    expect(within(sec).queryByText(/Waiting for a step/)).toBeNull();
  });

  it("a stop on a run that had traps says the laser is assumed on until the person confirms", async () => {
    const note = "tweezers laser: software cannot switch it; assumed on until you confirm";
    show({ plans: PLANS({ runs: [run({ how: "stopped_from_outside", how_words: "stopped from outside the run (a stop was sent)", tweezers_note: note })] }) });
    const sec = await screen.findByRole("region", { name: "Run run-20260924-003" });
    expect(within(sec).getByText(note)).toBeTruthy();
  });

  it("shows no tweezers note when the server sends none", async () => {
    show({ plans: PLANS({ runs: [run()] }) });
    const sec = await screen.findByRole("region", { name: "Run run-20260924-003" });
    expect(within(sec).queryByText(/tweezers laser/)).toBeNull();
  });

  it("says a run whose plan is not on disk has none to show beside it", async () => {
    show({ plans: PLANS({ runs: [run({ plan_on_disk: false })] }) });
    const sec = await screen.findByRole("region", { name: "Run run-20260924-003" });
    expect(within(sec).getByText(/plan is not on disk/)).toBeTruthy();
  });

  it("says no run yet when there is none", async () => {
    show();
    expect(await screen.findByText("No run on disk.")).toBeTruthy();
  });
});

describe("Plan: drafts", () => {
  it("says drafts are not saved yet, and that where one lives is still to be designed", async () => {
    show();
    expect(await screen.findByText(DRAFTS_NOTE)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Drafts waiting for a signature" })).toBeTruthy();
  });

  it("a trap pattern draft validates and shows the card, not saved", async () => {
    const { posts } = show();
    fireEvent.click(await screen.findByRole("button", { name: "Draft trap pattern" }));
    expect(await screen.findByText(/plan\.schema\.json accepts this card/)).toBeTruthy();
    expect(screen.getByText("Not saved.")).toBeTruthy();
    expect(posts().map((c) => c.path)).toEqual([IPATHS.draft]);
    expect(JSON.parse(String(posts()[0].init?.body)).kind).toBe("trap_steps");
  });

  it("a light draft shows the schema's refusal and is not offered for signing", async () => {
    show();
    fireEvent.change(await screen.findByLabelText("Kind of draft"), { target: { value: "aura" } });
    fireEvent.click(await screen.findByRole("button", { name: "Draft Aura III LED" }));
    expect(await screen.findByText(/refused by the schema for a light or exposure change/)).toBeTruthy();
    expect(screen.getByText("This draft is not offered for signing.")).toBeTruthy();
  });

  it("an exposure draft shows the schema's refusal too", async () => {
    show();
    fireEvent.change(await screen.findByLabelText("Kind of draft"), { target: { value: "camera_exposure" } });
    fireEvent.click(await screen.findByRole("button", { name: "Draft Camera red arm exposure" }));
    expect(await screen.findByText(/refused by the schema/)).toBeTruthy();
  });

  it("offers every kind the Instruments composer has", async () => {
    show();
    const sel = await screen.findByLabelText("Kind of draft");
    expect(within(sel).getAllByRole("option").map((o) => (o as HTMLOptionElement).value)).toEqual(["trap_steps", "aura", "dialamp", "camera_exposure", "piezo"]);
  });
});

describe("Sample map", () => {
  const open = (o: Opts = {}) => show({ hash: "#/experiments/sample-map", ...o });

  it("says each part is not built yet, and why", async () => {
    open();
    const list = await screen.findByRole("list", { name: "Parts of the sample map" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(4);
    for (const li of items) expect(within(li).getByText("not built yet")).toBeTruthy();
    expect(within(items[2]).getByText(/a model's guesses are never drawn as candidates/)).toBeTruthy();
  });

  it("draws nothing and offers no move, flag or confirmation", async () => {
    const { posts, container } = { ...open(), container: document.body };
    await screen.findByRole("list", { name: "Parts of the sample map" });
    expect(container.querySelector("canvas, svg, img")).toBeNull();
    expect(screen.queryAllByRole("button").map((b) => b.textContent).filter((n) => /move|flag|confirm|candidate/i.test(n ?? ""))).toEqual([]);
    expect(posts()).toEqual([]);
  });

  it("labels the example data and names the SOURCE file", async () => {
    open({ map: MAP({ example: true, example_note: EXAMPLE_NOTE }) });
    expect(await screen.findByText(/This is example data/)).toBeTruthy();
    expect(screen.getByText(/mock_data\/SOURCE\.md/)).toBeTruthy();
  });

  it("the sample panel says there is no record yet and invents no path", async () => {
    open();
    const panel = await screen.findByRole("region", { name: "Sample" });
    expect(within(panel).getByText("No sample record yet: where a sample's record lives is still being designed.")).toBeTruthy();
    expect(within(panel).queryByText(/\.json|\.md|kb\//)).toBeNull();
  });

  it("shows a loading check a hand-step sheet holds, as done at the microscope, from that run", async () => {
    open({
      sample: SAMPLE({ loading_checks: [{ run_id: "run-20260924-003", sheet_id: "step-1", confirmed_at: "2026-09-24T10:02:00Z", confirmed_by: "kyuhwan", words: "done at the microscope, from run-20260924-003's hand-step sheet" }] }),
    });
    const panel = await screen.findByRole("region", { name: "Sample" });
    expect(within(panel).getByText(/done at the microscope, from run-20260924-003's hand-step sheet/)).toBeTruthy();
    expect(within(panel).getByText(/kyuhwan, 2026-09-24 10:02:00/)).toBeTruthy();
  });

  it("shows no loading check when there is none", async () => {
    open();
    const panel = await screen.findByRole("region", { name: "Sample" });
    expect(within(panel).queryByText(/done at the microscope/)).toBeNull();
  });

  it("requests the sample and the map and nothing else on this page", async () => {
    const { calls } = open();
    await screen.findByRole("list", { name: "Parts of the sample map" });
    await waitFor(() => expect(calls.some((c) => c.path === PATHS.sample)).toBe(true));
    expect(calls.map((c) => c.path).filter((p) => p.startsWith("/api/") && !p.startsWith("/api/auth"))).toEqual(expect.arrayContaining([PATHS.sample, PATHS.sampleMap]));
    expect(calls.map((c) => c.path)).not.toContain(PATHS.run);
  });
});
