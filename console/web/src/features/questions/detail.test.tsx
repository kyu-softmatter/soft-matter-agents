import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Client, ClientProvider } from "../../app/client";
import { ScreenContextProvider } from "../../app/screenContext";
import { fakeTransport, type Route } from "../../test/fakes";
import { type Card, PATHS, type QuestionCards, type QuestionDetail, type RunSummary } from "./api";
import { provenanceWord } from "./ui";
import QuestionsScreen from "./index";

/** One question and the sign dialog (console card 011): the screen and the dialog, which writes nothing. */

const QID = "mic-20260917-001";
const HASH = "sha256:2bd6c3fbe49cfe89e2a5d94f7943789f4543e02cbd68c2e69e3bc98aca8d6dd9";
const WRITTEN = "Approval written. The runtime reads it from disk now. Commit it yourself when you choose: no session may commit a file under approvals/.";
const WRITTEN_FILE = `appr-${QID}-r1.json`;
const SIGNING = "/api/console/signing";
const CHECK = "/api/console/sign-check";

const clients: Client[] = [];
afterEach(() => {
  clients.splice(0).forEach((c) => c.events.stop());
});

function card(name: string, kind: string, data: Record<string, unknown>, version = 1): Card {
  return { name, kind, version, status: (data.status as string) ?? null, created_at: (data.created_at as string) ?? null, data };
}

const GOAL = card("goal.json", "goal", {
  card: "goal", status: "VALIDATED", created_at: "2026-09-17T08:00:00Z", requested_by: "human", thread: "thr-gel-001",
  question: "Does this gel keep flowing more easily the longer it rests?", purpose: "screen",
  observable: { name: "tracer_diffusivity" }, numbers: [],
});
const AXIS = card("axis_bd_pairwise_a7.json", "axis", { card: "axis", verdict: "feasible", numbers: [], status: "VALIDATED" });
const SYNTHESIS = card("synthesis.json", "synthesis", { card: "synthesis", status: "VALIDATED", numbers: [] });
const PLAN = card("plan_microscope_mic-20260917-001.json", "plan", {
  card: "plan", status: "PROPOSED", revision: 1, purpose: "screen", observable: { name: "tracer_diffusivity" },
  system_configuration: { config: "brightfield", devices: ["dia_lamp", "objective_turret", "camera1", "motor_stage"] },
  actions: [
    { id: "act_stage", device: "motor_stage", action: "move_to_wall_distance", reversible: true },
    { id: "act_illum", device: "dia_lamp", action: "set_power", reversible: true },
    { id: "act_bleach_ref", device: "dia_lamp", action: "bleach_reference_field", reversible: false },
  ],
  numbers: [
    { name: "exposure_time", value: 0.007, unit: "s", source: "computed:geometric_middle", grade: "E5", precision: "order_of_magnitude" },
    { name: "illumination_power", value: 12, unit: "mW", source: "calibration:dia_lamp_power", grade: "E2", precision: "significant_figures" },
    { name: "guess_temp", value: 22, unit: "C", source: "assumed:room", grade: "E5", precision: "order_of_magnitude" },
  ],
  degraded: [],
});
const APPROVAL = (hash: string, status = "APPROVED") => ({
  name: "appr-mic-20260917-001-r1.json", agent: "microscope" as const, id: "appr-mic-20260917-001-r1", qid: QID, revision: 1,
  status, plan_id: "plan-1", plan_revision: 1, plan_hash: hash, approved_by: "kyuhwan", approved_at: "2026-09-17T09:00:00Z",
  source: "soft-matter-agents", plan_found: true, data: {},
});

function detailOf(over: Partial<QuestionDetail> = {}): QuestionDetail {
  return {
    summary: {
      qid: QID, agent: "microscope", title: "tracer diffusivity", status: "VALIDATED", created_at: "2026-09-17T08:00:00Z",
      updated_at: "2026-09-17T09:00:00Z", latest_version: 1, versions: [1], source: "soft-matter-agents",
    },
    version: 1, goal: GOAL, axes: [AXIS], plan: PLAN, synthesis: SYNTHESIS, refusals: [], results: [], others: [],
    documents: [], files: [], plan_hash: HASH, approvals: [], ...over,
  };
}

const RUN: RunSummary = {
  run_id: "run-20260918-001", agent: "microscope", qid: QID, plan_id: "plan-1", status: "complete",
  created_at: "2026-09-18T10:00:00Z", finished_at: "2026-09-18T10:05:00Z", backend: "micromanager", source: "soft-matter-agents",
};

interface Opts {
  detail?: QuestionDetail;
  signing?: Record<string, unknown> | null;
  check?: Route;
  runs?: RunSummary[] | "missing";
  cards?: QuestionCards;
  hash?: string;
}

const STATE = { person_named: true, is_person: true, practice: false, approvals_folder: true };

function show(opts: Opts = {}) {
  window.location.hash = opts.hash ?? `#/questions/questions/${QID}`;
  const detail = opts.detail ?? detailOf();
  const cards: QuestionCards = opts.cards ?? {
    requests: [],
    items: [],
    questions: [{
      qid: QID, agent: "microscope", title: "tracer diffusivity", status: "VALIDATED", created_at: "2026-09-17T08:00:00Z",
      steps: { asked: true, designed: true, signed: false, run: true, result: false, run_known: true },
    }],
  };
  const fake = fakeTransport({
    [PATHS.question(QID)]: () => ({ status: 200, body: detail }),
    [PATHS.question(QID, 1)]: () => ({ status: 200, body: detail }),
    [PATHS.questionCards]: () => ({ status: 200, body: cards }),
    [PATHS.runs()]: () =>
      opts.runs === "missing"
        ? { status: 404, body: { detail: { code: "runs_not_found", message: "the runs folder was not found" } } }
        : { status: 200, body: opts.runs ?? [RUN, { ...RUN, run_id: "run-20260918-099", qid: "mic-20990101-001" }] },
    [PATHS.run("microscope", RUN.run_id)]: () => ({ status: 200, body: { summary: RUN, records: {}, files: [], not_opened: [] } }),
    [PATHS.inbox]: () => ({
      status: 200,
      body: [{
        thread: "thr-gel-001", agent: "microscope", state: "open", turn: "microscope_agent", round: 2, updated_at: "2026-09-17T08:30:00Z",
        status: { state: "open" }, source: "soft-matter-agents",
        messages: [{ name: "r2_ask_experiment.md", round: 2, kind: "ask_experiment", card: null, text: "Round two, in words." }],
      }, {
        thread: "thr-other", agent: "microscope", state: "open", turn: "x", round: 1, updated_at: null, status: null,
        source: "soft-matter-agents", messages: [{ name: "r1_ask.md", round: 1, kind: "ask", card: null, text: "Not this question's." }],
      }],
    }),
    [PATHS.store]: () => ({ status: 200, body: { store: "soft-matter-agents", writable: true } }),
    [PATHS.permissions(["submit_question"])]: () => ({ status: 200, body: { submit_question: { allowed: true, reason: null } } }),
    [PATHS.suggestions]: () => ({ status: 200, body: [] }),
    [SIGNING]: () =>
      opts.signing === null ? { status: 500, body: { detail: "no" } } : { status: 200, body: opts.signing ?? STATE },
    [CHECK]: opts.check ?? (() => ({ status: 200, body: { outcome: "written", message: WRITTEN, file_name: WRITTEN_FILE } })),
  });
  const client = new Client(fake.transport, "127.0.0.1");
  clients.push(client);
  render(
    <ClientProvider client={client}>
      <ScreenContextProvider area="questions">
        <QuestionsScreen />
      </ScreenContextProvider>
    </ClientProvider>,
  );
  const posts = () => fake.calls.filter((c) => c.init?.method === "POST");
  return { ...fake, client, posts };
}

const page = () => screen.findByRole("region", { name: `Question ${QID}` });

describe("the question and its steps", () => {
  it("shows the question verbatim, who asked, when, and the five steps", async () => {
    show();
    const p = await page();
    expect(within(p).getByText("Does this gel keep flowing more easily the longer it rests?")).toBeTruthy();
    expect(p.textContent).toContain("human");
    expect(p.textContent).toContain("2026-09-17 08:00:00");
    const steps = await within(p).findByRole("list", { name: "Progress" });
    expect(within(steps).getAllByRole("listitem").map((s) => [s.textContent?.split(" (")[0], s.getAttribute("data-done")])).toEqual([
      ["Asked", "true"], ["Designed", "true"], ["Signed", "false"], ["Run", "true"], ["Result", "false"],
    ]);
  });

  it("shows a request written in the console, with nothing started", async () => {
    show({
      hash: "#/questions/requests/qr-20261023-091500-w3k8",
      cards: {
        requests: [{
          id: "qr-20261023-091500-w3k8", words: "How far apart are the wells at 4x?", login: "member-2", asked_at: "2026-10-23T09:15:00Z",
          addressed_to: "librarian", state: "written in the console · not delivered", runs_wait_for_signature: true,
        }],
        items: [],
        questions: [],
      },
    });
    const p = await screen.findByRole("region", { name: "Question request" });
    expect(p.textContent).toContain("How far apart are the wells at 4x?");
    expect(p.textContent).toContain("member-2");
    expect(p.textContent).toContain("written in the console · not delivered");
    expect(p.textContent).toContain("was not delivered to an agent");
    expect(p.textContent).not.toContain("picked this up");
    expect(p.textContent).toContain("Every run from it waits for the person's signature");
    expect(within(p).queryByRole("button", { name: "Review and sign" })).toBeNull();
  });
});

describe("versions, grades and the degraded banner (kept from the old detail view)", () => {
  it("lists every version the store returns, past v3, and reads the one picked", async () => {
    const d = detailOf({ summary: { ...detailOf().summary, latest_version: 5, versions: [1, 2, 5] }, version: 5 });
    const t = show({ detail: d });
    const picker = (await screen.findByLabelText("Version")) as HTMLSelectElement;
    expect([...picker.options].map((o) => o.textContent)).toEqual(["v1", "v2", "v5 (latest)"]);
    expect(t.calls.some((c) => c.path === PATHS.question(QID))).toBe(true);
  });

  it("shows grades exactly as the card has them, and the degraded banner", async () => {
    const goal = card("goal.json", "goal", {
      ...(GOAL.data as Record<string, unknown>),
      numbers: [{ name: "odd", value: 1, unit: "1", source: "assumed:x", grade: "E9", precision: "exact" }],
      degraded: ["librarian unreachable"],
    });
    show({ detail: detailOf({ goal }) });
    const list = await screen.findByRole("list", { name: "Cards made from this question" });
    fireEvent.click(within(list).getByRole("button", { name: /Goal/ }));
    const table = await within(list).findByRole("table", { name: "Numbers" });
    expect(within(table).getAllByTitle("grade as written on the card").map((g) => g.textContent)).toEqual(["E9"]);
    expect(within(list).getByRole("alert").textContent).toContain("librarian unreachable");
  });
});

describe("what an approval says about the plan it names", () => {
  it("says which plan each approval signs, in words", async () => {
    const other = { ...APPROVAL("sha256:" + "b".repeat(64)), name: "r2.json", id: "r2" };
    const gone = { ...APPROVAL("sha256:" + "c".repeat(64)), name: "r3.json", id: "r3", plan_found: false };
    show({ detail: detailOf({ approvals: [APPROVAL(HASH), other, gone] }) });
    const list = await screen.findByRole("list", { name: "Cards made from this question" });
    const buttons = within(list).getAllByRole("button").filter((b) => /^Approval/.test(b.textContent ?? ""));
    expect(buttons).toHaveLength(3);
    for (const b of buttons) fireEvent.click(b);
    const text = list.textContent ?? "";
    expect(text).toContain("signs this version's plan");
    expect(text).toContain("signs another version's plan");
    expect(text).toContain("signs a plan that is not in the question folder");
  });
});

describe("the summary", () => {
  it("carries its label and holds the goal's purpose and observable and the plan's steps", async () => {
    show();
    const s = await screen.findByRole("region", { name: "Summary" });
    expect(s.textContent).toContain("Put together from the cards");
    expect(s.textContent).toContain("screen");
    expect(s.textContent).toContain("tracer_diffusivity");
    expect(s.textContent).toContain("motor_stage");
    expect(s.textContent).toContain("move_to_wall_distance");
    expect(s.textContent).not.toContain("Written by the assistant");
  });

  it("labels anything the assistant wrote as the assistant's", async () => {
    const assistantGoal = card("goal.json", "goal", { ...GOAL.data as Record<string, unknown>, author: "assistant" });
    show({ detail: detailOf({ goal: assistantGoal }) });
    const s = await screen.findByRole("region", { name: "Summary" });
    expect(s.textContent).toContain("Written by the assistant");
    const rows = await screen.findByRole("list", { name: "Cards made from this question" });
    expect(within(rows).getByRole("button", { name: /Goal/ }).closest("li")?.textContent).toContain("Written by the assistant");
  });
});

describe("the cards made from the question, one row each", () => {
  it("has a row for the goal, design, synthesis, plan, approval, run and bridge round, and every row opens", async () => {
    show({ detail: detailOf({ approvals: [APPROVAL("sha256:" + "0".repeat(64))] }) });
    const list = await screen.findByRole("list", { name: "Cards made from this question" });
    await waitFor(() => expect(within(list).getAllByRole("button").length).toBeGreaterThanOrEqual(7));
    const labels = within(list).getAllByRole("button").map((b) => b.textContent ?? "");
    for (const want of [/^Goal/, /^Design/, /^Synthesis/, /^Plan · revision 1/, /^Approval/, /^Run/, /^Bridge · round 2/]) {
      expect(labels.some((l) => want.test(l)), String(want)).toBe(true);
    }
    // another thread's round, and another question's run, are not here
    expect(labels.filter((l) => /^Bridge/.test(l))).toHaveLength(1);
    expect(labels.filter((l) => /^Run/.test(l))).toEqual([expect.stringContaining("run-20260918-001")]);
    expect(labels.some((l) => l.includes("run-20260918-099"))).toBe(false);
    for (const b of within(list).getAllByRole("button")) {
      expect(b.getAttribute("aria-expanded")).toBe("false");
      fireEvent.click(b);
      expect(b.getAttribute("aria-expanded"), b.textContent ?? "").toBe("true");
      const body = b.closest("li")?.querySelector(".ask-row-body");
      expect(body && (body.textContent ?? "").trim().length, `row ${b.textContent} has main fields`).toBeGreaterThan(0);
    }
  });

  it("opens the plan to its numbers, each with its word: measured, computed, guessed", async () => {
    show();
    const list = await screen.findByRole("list", { name: "Cards made from this question" });
    fireEvent.click(within(list).getByRole("button", { name: /Plan · revision 1/ }));
    const table = await within(list).findByRole("table", { name: "Numbers" });
    const row = (name: string) => within(table).getByText(name).closest("tr") as HTMLElement;
    expect(row("exposure_time").textContent).toContain("computed");
    expect(row("illumination_power").textContent).toContain("measured");
    expect(row("guess_temp").textContent).toContain("guessed");
  });

  it("says in words what a source means and never hides one it does not know", () => {
    expect(provenanceWord("computed:geometric_middle")).toBe("computed");
    expect(provenanceWord("assumed:room")).toBe("guessed");
    expect(provenanceWord("operator_recall:x")).toBe("guessed");
    expect(provenanceWord("calibration:lamp")).toBe("measured");
    expect(provenanceWord("kb:tracer_diameter")).toBe("measured elsewhere");
    expect(provenanceWord("readback:z")).toBe("read back");
    expect(provenanceWord("sent:trap_strength")).toBe("sent");
    expect(provenanceWord("mystery:thing")).toBe("source: mystery:thing");
    expect(provenanceWord(undefined)).toBe("no source given");
  });

  it("shows the runs folder trouble in words and still shows the other rows", async () => {
    show({ runs: "missing" });
    const list = await screen.findByRole("list", { name: "Cards made from this question" });
    expect(within(list).getByRole("button", { name: /Goal/ })).toBeTruthy();
    expect(within(list).queryByRole("button", { name: /^Run/ })).toBeNull();
  });
});

describe("a plan waiting for a signature", () => {
  it("shows 'Review and sign' to the person's login only", async () => {
    show();
    const box = await screen.findByRole("region", { name: "Plan waiting for a signature" });
    expect(within(box).getByRole("button", { name: "Review and sign" })).toBeTruthy();
  });

  it("shows another login 'Waits for the person's signature' and no button", async () => {
    show({ signing: { ...STATE, is_person: false } });
    const box = await screen.findByRole("region", { name: "Plan waiting for a signature" });
    expect(box.textContent).toContain("Waits for the person's signature");
    expect(within(box).queryByRole("button")).toBeNull();
  });

  it("shows no one the button while the person's login is not named, and says so", async () => {
    show({ signing: { ...STATE, person_named: false, is_person: false } });
    const box = await screen.findByRole("region", { name: "Plan waiting for a signature" });
    expect(box.textContent).toContain("The person's login is not named yet");
    expect(within(box).queryByRole("button")).toBeNull();
  });

  it("shows no button when the signing state cannot be read", async () => {
    show({ signing: null });
    const box = await screen.findByRole("region", { name: "Plan waiting for a signature" });
    expect(within(box).queryByRole("button")).toBeNull();
  });

  it("is not there for a plan that an approval of its fingerprint already signs", async () => {
    show({ detail: detailOf({ approvals: [APPROVAL(HASH)] }) });
    await page();
    await screen.findByRole("list", { name: "Cards made from this question" });
    expect(screen.queryByRole("region", { name: "Plan waiting for a signature" })).toBeNull();
  });

  it("is still waiting when the approval is for another fingerprint, or is not an approval", async () => {
    show({ detail: detailOf({ approvals: [APPROVAL("sha256:" + "0".repeat(64)), { ...APPROVAL(HASH), name: "b.json", status: "DRAFT" }] }) });
    expect(await screen.findByRole("region", { name: "Plan waiting for a signature" })).toBeTruthy();
  });

  it("is not there when the question has no plan", async () => {
    show({ detail: detailOf({ plan: null, plan_hash: null }) });
    await page();
    await screen.findByRole("list", { name: "Cards made from this question" });
    expect(screen.queryByRole("region", { name: "Plan waiting for a signature" })).toBeNull();
  });
});

async function openDialog() {
  const box = await screen.findByRole("region", { name: "Plan waiting for a signature" });
  fireEvent.click(await within(box).findByRole("button", { name: "Review and sign" }));
  return screen.findByRole("dialog", { name: "Sign the plan" });
}

describe("the sign dialog", () => {
  it("shows the plan, its revision, steps, light and what cannot be undone", async () => {
    show();
    const d = await openDialog();
    expect(d.textContent).toContain("revision 1");
    expect(d.textContent).toContain("move_to_wall_distance");
    expect(d.textContent).toContain("set_power");
    expect(within(d).queryByRole("group", { name: "Light" })).toBeNull(); // no role is read from a name
    const touched = within(d).getByRole("group", { name: "Devices this plan touches" });
    expect(touched.textContent).toContain("dia_lamp");
    expect(touched.textContent).toContain("motor_stage");
    const undo = within(d).getByRole("group", { name: "What cannot be undone" });
    expect(undo.textContent).toContain("bleach_reference_field");
    expect(undo.textContent).not.toContain("move_to_wall_distance");
  });

  it("says when nothing in the plan is irreversible", async () => {
    const calm = card(PLAN.name, "plan", {
      ...(PLAN.data as Record<string, unknown>),
      actions: [{ id: "a", device: "motor_stage", action: "move", reversible: true }],
    });
    show({ detail: detailOf({ plan: calm }) });
    const d = await openDialog();
    expect(within(d).getByRole("group", { name: "What cannot be undone" }).textContent).toContain("Nothing in this plan is irreversible");
    expect(within(d).getByRole("group", { name: "Devices this plan touches" }).textContent).toContain("motor_stage");
  });

  it("lists every device the plan touches with the value it sets, a light named any way at all included", async () => {
    const odd = card(PLAN.name, "plan", {
      ...(PLAN.data as Record<string, unknown>),
      system_configuration: { config: "x", devices: ["beacon_9"] },
      actions: [{ id: "a1", device: "beacon_9", action: "set_output", reversible: true, parameters: ["output_level"] }],
      conditions: [{ parameter: "hold_time", number: "hold_time", device: "relay_3" }],
      numbers: [
        { name: "output_level", value: 3, unit: "mW", source: "computed:from_budget", grade: "E4", precision: "order_of_magnitude" },
        { name: "hold_time", value: 20, unit: "s", source: "assumed:x", grade: "E5", precision: "order_of_magnitude" },
      ],
    });
    show({ detail: detailOf({ plan: odd }) });
    const d = await openDialog();
    const touched = within(d).getByRole("group", { name: "Devices this plan touches" });
    expect(touched.textContent).toContain("beacon_9");
    expect(touched.textContent).toContain("set_output");
    expect(touched.textContent).toContain("output_level: 3 mW (computed)");
    expect(touched.textContent).toContain("relay_3");
    expect(touched.textContent).toContain("hold_time: 20 s (guessed)");
  });

  it("says when a value a step names is not in the plan, never inventing one", async () => {
    const bare = card(PLAN.name, "plan", {
      ...(PLAN.data as Record<string, unknown>),
      actions: [{ id: "a1", device: "beacon_9", action: "set_output", reversible: true, parameters: ["missing_number"] }],
      numbers: [],
    });
    show({ detail: detailOf({ plan: bare }) });
    const d = await openDialog();
    expect(within(d).getByRole("group", { name: "Devices this plan touches" }).textContent).toContain(
      "missing_number: no value given in the plan",
    );
  });

  it("lists the operation's moves and the trap steps' traps as what is set", async () => {
    const op = card(PLAN.name, "plan", {
      card: "plan", status: "PROPOSED", revision: 1, numbers: [], actions: [],
      operation: { device: "piezo_stage", moves: [{ id: "m1", axis: "x", kind: "step", target_um: 310, role: "verify_mapping" }] },
      trap_steps: { device: "optical_tweezers", objective: "100x", steps: [{ id: "s1", kind: "create", trap: "trap_1", x_um: 2, y_um: 0, strength: 1 }] },
    });
    show({ detail: detailOf({ plan: op }) });
    const d = await openDialog();
    const touched = within(d).getByRole("group", { name: "Devices this plan touches" });
    expect(touched.textContent).toContain("piezo_stage");
    expect(touched.textContent).toContain("step x to 310 um");
    expect(touched.textContent).toContain("optical_tweezers");
    expect(touched.textContent).toContain("create trap_1 at 2, 0 um, strength 1");
  });

  it("lists an action that does not say it is reversible among what cannot be undone", async () => {
    const quiet = card(PLAN.name, "plan", {
      ...(PLAN.data as Record<string, unknown>),
      actions: [{ id: "a1", device: "motor_stage", action: "move" }, { id: "a2", device: "dia_lamp", action: "set_power", reversible: true }],
    });
    show({ detail: detailOf({ plan: quiet }) });
    const d = await openDialog();
    const undo = within(d).getByRole("group", { name: "What cannot be undone" });
    expect(undo.textContent).toContain("motor_stage · move");
    expect(undo.textContent).not.toContain("set_power");
  });

  it("shows the full fingerprint, exactly", async () => {
    show();
    const d = await openDialog();
    expect(within(d).getByTestId("fingerprint").textContent).toBe(HASH);
  });

  it("has a password field typed again, never pre-filled", async () => {
    show();
    const d = await openDialog();
    const pw = within(d).getByLabelText("Your password, again") as HTMLInputElement;
    expect(pw.type).toBe("password");
    expect(pw.value).toBe("");
    expect(pw.autocomplete).not.toBe("on");
    expect((within(d).getByRole("button", { name: "Sign" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("sends the fingerprint and the password to the server, and shows what it wrote and who commits it", async () => {
    const t = show();
    const d = await openDialog();
    fireEvent.change(within(d).getByLabelText("Your password, again"), { target: { value: "my-password-1" } });
    fireEvent.click(within(d).getByRole("button", { name: "Sign" }));
    const status = (await within(d).findByRole("status")).textContent ?? "";
    expect(status).toContain(WRITTEN);
    expect(status).toContain(WRITTEN_FILE);
    expect((within(d).getByRole("button", { name: "Sign" }) as HTMLButtonElement).disabled).toBe(true); // once
    const sent = t.posts();
    expect(sent.map((p) => p.path)).toEqual([CHECK]); // the one call, and no other write anywhere
    expect(JSON.parse(String(sent[0].init?.body))).toEqual({ qid: QID, plan_hash: HASH, password: "my-password-1" });
    expect(document.body.textContent).not.toContain("my-password-1");
    expect((within(d).getByLabelText("Your password, again") as HTMLInputElement).value).toBe(""); // not kept
  });

  it("refuses a wrong password in words and keeps the dialog open", async () => {
    show({ check: () => ({ status: 401, body: { detail: { code: "bad_credentials", message: "Wrong password." } } }) });
    const d = await openDialog();
    fireEvent.change(within(d).getByLabelText("Your password, again"), { target: { value: "nope-nope-1" } });
    fireEvent.click(within(d).getByRole("button", { name: "Sign" }));
    expect((await within(d).findByRole("alert")).textContent).toBe("Wrong password.");
    expect(screen.getByRole("dialog", { name: "Sign the plan" })).toBeTruthy();
  });

  it("shows the throttle's words when there have been too many wrong passwords", async () => {
    show({
      check: () => ({
        status: 429,
        body: { detail: { code: "too_many_attempts", message: "Too many wrong passwords. Try again in 15 minutes." } },
        headers: { "Retry-After": "900" },
      }),
    });
    const d = await openDialog();
    fireEvent.change(within(d).getByLabelText("Your password, again"), { target: { value: "x-x-x-x-x-1" } });
    fireEvent.click(within(d).getByRole("button", { name: "Sign" }));
    expect((await within(d).findByRole("alert")).textContent).toContain("Try again in 15 minutes");
  });

  it("under the mock store shows a practice login as signed, and says nothing was written", async () => {
    show({
      signing: { ...STATE, practice: true },
      check: () => ({ status: 200, body: { outcome: "practice_signed", message: "Practice: this login is shown as signed. Nothing was written." } }),
    });
    const d = await openDialog();
    fireEvent.change(within(d).getByLabelText("Your password, again"), { target: { value: "my-password-1" } });
    fireEvent.click(within(d).getByRole("button", { name: "Sign" }));
    expect((await within(d).findByRole("status")).textContent).toContain("Nothing was written");
    fireEvent.click(within(d).getByRole("button", { name: "Close" }));
    const box = await screen.findByRole("region", { name: "Plan waiting for a signature" });
    expect(box.textContent).toContain("Signed (practice)");
    expect(box.textContent).toContain("nothing was written");
  });

  it("when the approvals folder is not there, says nothing can be signed and offers no other place", async () => {
    const t = show({ signing: { ...STATE, approvals_folder: false } });
    const d = await openDialog();
    expect(d.textContent).toContain("Nothing can be signed here");
    expect(d.textContent).toContain("microscope_runtime/approvals/");
    expect(d.textContent).not.toContain("microscope_agent");
    expect(within(d).queryByLabelText("Your password, again")).toBeNull();
    expect(within(d).queryByRole("button", { name: "Sign" })).toBeNull();
    expect(t.posts()).toHaveLength(0);
    expect(within(d).getByTestId("fingerprint").textContent).toBe(HASH); // the plan can still be read
  });

  it("closes without sending anything", async () => {
    const t = show();
    const d = await openDialog();
    fireEvent.click(within(d).getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Sign the plan" })).toBeNull());
    expect(t.posts()).toHaveLength(0);
  });
});

describe("the numbers in the plan that nothing sets (card 021)", () => {
  const HEADING = "Numbers in this plan that nothing sets";
  const unused = (numbers: Array<{ name: unknown; value?: unknown; unit?: unknown; from: string }>) => ({
    worked_out: true,
    numbers,
    reason: null,
  });
  const section = (d: HTMLElement) => within(d).getByRole("group", { name: HEADING });
  const signEnabled = async (d: HTMLElement) => {
    fireEvent.change(within(d).getByLabelText("Your password, again"), { target: { value: "my-password-1" } });
    return !(within(d).getByRole("button", { name: "Sign" }) as HTMLButtonElement).disabled;
  };

  it("lists each number as name, value, unit and how it was got, after the devices and before what cannot be undone", async () => {
    show({
      detail: detailOf({
        unused_numbers: unused([
          { name: "exposure_time", value: 0.007, unit: "s", from: "numbers[0]" },
          { name: "illumination_power", value: 12, unit: "mW", from: "numbers[1]" },
          { name: "guess_temp", value: 22, unit: "C", from: "numbers[2]" },
        ]),
      }),
    });
    const d = await openDialog();
    const items = within(section(d)).getAllByRole("listitem").map((li) => li.textContent);
    expect(items).toEqual([
      "exposure_time: 0.007 s (computed)",
      "illumination_power: 12 mW (measured)",
      "guess_temp: 22 C (guessed)",
    ]);
    expect(section(d).querySelector("legend")?.textContent).toBe(HEADING); // the heading the person reads
    const groups = within(d).getAllByRole("group").map((g) => g.getAttribute("aria-label"));
    expect(groups.indexOf(HEADING)).toBe(groups.indexOf("Devices this plan touches") + 1);
    expect(groups.indexOf("What cannot be undone")).toBe(groups.indexOf(HEADING) + 1);
  });

  it("takes how a number was got from the card's own entry at from, and not from the list", async () => {
    show({
      detail: detailOf({
        unused_numbers: unused([
          { name: "illumination_power", value: 12, unit: "mW", from: "numbers[2]" }, // the list says numbers[2]: a guess
          { name: "nothing_there", value: 1, unit: "s", from: "numbers[9]" }, // no such entry
        ]),
      }),
    });
    const d = await openDialog();
    expect(within(section(d)).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "illumination_power: 12 mW (guessed)",
      "nothing_there: 1 s (no source given)",
    ]);
  });

  it("prints nothing after the value when the unit is null or 1", async () => {
    show({
      detail: detailOf({
        unused_numbers: unused([
          { name: "spare", value: 1, unit: "1", from: "numbers[0]" },
          { name: "ratio", value: 3, unit: null, from: "numbers[1]" },
          { name: "count", value: 5, unit: "count", from: "numbers[2]" },
        ]),
      }),
    });
    const d = await openDialog();
    expect(within(section(d)).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "spare: 1 (computed)",
      "ratio: 3 (measured)",
      "count: 5 count (guessed)",
    ]);
  });

  it("shows a name or a unit that is not a string as the card holds it", async () => {
    show({
      detail: detailOf({
        unused_numbers: unused([
          { name: 5, value: 4, unit: "s", from: "numbers[0]" },
          { name: "bleach_window", value: 4, unit: 7, from: "numbers[1]" },
          { name: { a: 1 }, value: 4, unit: { y: 2 }, from: "numbers[2]" },
        ]),
      }),
    });
    const d = await openDialog();
    expect(within(section(d)).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "5: 4 s (computed)",
      "bleach_window: 4 7 (measured)",
      '{"a":1}: 4 {"y":2} (guessed)',
    ]);
  });

  it("says that every number is used when the list is empty", async () => {
    show({ detail: detailOf({ unused_numbers: unused([]) }) });
    const d = await openDialog();
    expect(section(d).textContent).toContain(
      "Every number in this plan is one the run sets, hands to a step, sizes itself by, or checks against.",
    );
    expect(within(section(d)).queryAllByRole("listitem")).toHaveLength(0);
  });

  it("says in an alert, with the reason, when the numbers could not be worked out", async () => {
    show({
      detail: detailOf({
        unused_numbers: { worked_out: false, numbers: [], reason: "An action of this plan is written as a bare value." },
      }),
    });
    const d = await openDialog();
    const alert = within(section(d)).getByRole("alert");
    expect(alert.textContent).toBe(
      "The numbers nothing sets could not be worked out from this plan: An action of this plan is written as a bare value.",
    );
    expect(within(section(d)).queryAllByRole("listitem")).toHaveLength(0);
    expect(section(d).textContent).not.toContain("Every number in this plan");
  });

  it("shows no section when there is no list at all", async () => {
    show({ detail: detailOf({ unused_numbers: null }) });
    const d = await openDialog();
    expect(within(d).queryByRole("group", { name: HEADING })).toBeNull();
  });

  it("shows no section when the field is absent altogether, as from a server from before this card", async () => {
    show({ detail: detailOf() });
    const d = await openDialog();
    expect(within(d).queryByRole("group", { name: HEADING })).toBeNull();
  });

  it("changes nothing about signing: Sign is enabled the same, in every state, and sends the same", async () => {
    const states = [
      undefined,
      unused([{ name: "guess_temp", value: 22, unit: "C", from: "numbers[2]" }]),
      unused([]),
      { worked_out: false, numbers: [], reason: "An action of this plan is written as a bare value." },
    ];
    for (const u of states) {
      const t = show({ detail: detailOf({ unused_numbers: u }) });
      const d = await openDialog();
      expect((within(d).getByRole("button", { name: "Sign" }) as HTMLButtonElement).disabled).toBe(true); // no password
      expect(await signEnabled(d)).toBe(true);
      fireEvent.click(within(d).getByRole("button", { name: "Sign" }));
      await within(d).findByRole("status");
      expect(t.posts().map((p) => p.path)).toEqual([CHECK]);
      expect(JSON.parse(String(t.posts()[0].init?.body))).toEqual({ qid: QID, plan_hash: HASH, password: "my-password-1" });
      cleanup();
      window.location.hash = "";
    }
  });

  it("shows the mock's shipped microscope plan's list, as the server gave it", async () => {
    // the entry as the shipped plan mic-20260925-002 holds it; the server test reads the file itself
    const shipped = card("plan_microscope_mic-20260925-002.json", "plan", {
      card: "plan", status: "PROPOSED", revision: 2, purpose: "screen",
      actions: [{ id: "a1", device: "stand_ti2e", action: "read_objective", reversible: true }],
      numbers: [{ name: "nosepiece_position", value: 5, unit: "count", source: "operator_read:kyuhwan_20260925", grade: "E3" }],
    });
    show({
      detail: detailOf({
        plan: shipped,
        unused_numbers: unused([{ name: "nosepiece_position", value: 5, unit: "count", from: "numbers[0]" }]),
      }),
    });
    const d = await openDialog();
    expect(within(section(d)).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "nosepiece_position: 5 count (source: operator_read:kyuhwan_20260925)",
    ]);
  });
});
