/**
 * Fixtures for the console tests, shaped like the T-008 mock store's records, and the server
 * routes that answer from them on the shell's `fakeTransport` (no network).
 */

import type { Route } from "../../test/fakes";
import {
  type AskIn,
  type Card,
  type ConsoleQuestion,
  type InboxThread,
  type LibrarianRequest,
  NOT_DELIVERED,
  PATHS,
  type Permissions,
  type QuestionCards,
  type QuestionDetail,
  type QuestionRequest,
  type QuestionSummary,
  READ_ONLY_STORE_REASON,
  type RunDetail,
  type StoreInfo,
  SUBMIT_OP,
  type Suggestion,
} from "./api";

export interface FakeData {
  store: StoreInfo;
  /** the shared permission answer; null makes `/api/permissions` fail */
  permissions: Permissions | null;
  /** every version of every question, one QuestionDetail each */
  questions: QuestionDetail[];
  runs: RunDetail[];
  inbox: InboxThread[];
  /** the cards below the question field: requests written, and the agents' questions with steps */
  cards: QuestionCards;
  /** what autocomplete may offer: strings already on disk */
  suggestions: Suggestion[];
  /** the POST refuses with this whatever the permission answer said (it may be stale) */
  postRefusal?: { status: number; body: unknown };
}

/** The login the fake server says wrote a request. */
export const FAKE_LOGIN = "otto";

/**
 * Routes for `fakeTransport`, answering like the console router would (docs/screens/console.md).
 * The POST follows the server's order: permission 403, then a store that cannot take it, 409.
 */
export function consoleRoutes(data: FakeData): { routes: Record<string, Route>; submitted: AskIn[] } {
  const questions = [...data.questions];
  const submitted: AskIn[] = [];
  const requests = [...data.cards.requests];
  const items = [...data.cards.items];
  const ok = (body: unknown) => ({ status: 200, body });
  const latest = (qid: string) => {
    const vs = questions.filter((d) => d.summary.qid === qid);
    return vs.find((d) => d.version === vs[0].summary.latest_version) ?? vs[0];
  };
  const routes: Record<string, Route> = {
    [PATHS.store]: () => ok(data.store),
    [PATHS.permissions([SUBMIT_OP])]: () =>
      data.permissions === null ? { status: 502, body: { detail: "Bad Gateway" } } : ok(data.permissions),
    [PATHS.questions()]: () => {
      const qids = [...new Set(questions.map((d) => d.summary.qid))].sort().reverse();
      return ok(qids.map((q) => latest(q).summary));
    },
    [PATHS.questionCards]: () => ok({ requests, items, questions: data.cards.questions }),
    [PATHS.suggestions]: () => ok([...requests.map((r) => ({ text: r.words, kind: "earlier question" })), ...data.suggestions.filter((s) => s.kind === "registered name")]),
    [PATHS.runs()]: () => ok(data.runs.map((r) => r.summary)),
    [PATHS.inbox]: () => ok(data.inbox),
  };
  for (const d of data.questions) {
    routes[PATHS.question(d.summary.qid, d.version)] = () => ok(d);
    routes[PATHS.question(d.summary.qid)] = () => ok(latest(d.summary.qid));
  }
  for (const r of data.runs) routes[PATHS.run(r.summary.agent, r.summary.run_id)] = () => ok(r);

  routes[PATHS.questionRequests] = (init) => {
    if (data.postRefusal !== undefined) return data.postRefusal;
    const perm = data.permissions?.[SUBMIT_OP];
    if (perm === undefined || !perm.allowed) {
      return { status: 403, body: { detail: { code: perm?.code ?? "role", message: perm?.reason ?? "refused" } } };
    }
    if (!data.store.writable) {
      return { status: 409, body: { detail: { code: "read_only_store", message: READ_ONLY_STORE_REASON } } };
    }
    const body = JSON.parse(String(init?.body)) as AskIn;
    submitted.push(body);
    const asked_by = {
      login: FAKE_LOGIN,
      console_role: { may_ask: true, may_draft: true, agents: ["microscope", "simulation", "librarian"], may_ask_model_run: true },
    } satisfies QuestionRequest["asked_by"];
    if (body.addressed_to === "microscope" || body.addressed_to === "simulation") {
      // delivered into the agent's inbox: an item, and no request file beside it
      const prefix = body.addressed_to === "microscope" ? "mic" : "sim";
      const n = submitted.filter((x) => x.addressed_to === body.addressed_to).length; // this fake's own sends, from c001
      const sent: ConsoleQuestion = {
        artifact: "console_question", schema_version: "0.1", item_id: `ci-20261026-12000${n}-abcd`,
        question_id: `${prefix}-20261026-c${String(n).padStart(3, "0")}`, words: body.words, asked_by,
        asked_at: "2026-10-26T12:00:00Z", asker_mark: { kind: "other_login" }, attachments: [],
      };
      items.unshift({
        item_id: sent.item_id, question_id: sent.question_id, agent: body.addressed_to, words: sent.words,
        login: FAKE_LOGIN, asked_at: sent.asked_at, state: "delivered · not answered yet", runs_wait_for_signature: true,
      });
      return { status: 201, body: sent };
    }
    if (body.addressed_to === "librarian") {
      // delivered into the librarian's inbox as an `ask` request: an item card with no question id and no signature note
      const n = submitted.filter((x) => x.addressed_to === "librarian").length;
      const sent: LibrarianRequest = {
        artifact: "console_store_request", schema_version: "0.1", item_id: `ci-20261027-12000${n}-abcd`,
        words: body.words, asked_by, asked_at: "2026-10-27T12:00:00Z", asker_mark: { kind: "other_login" },
        attachments: [], request: { kind: "ask" },
      };
      items.unshift({
        item_id: sent.item_id, question_id: null, agent: "librarian", words: sent.words, login: FAKE_LOGIN,
        asked_at: sent.asked_at, state: "delivered · not answered yet", runs_wait_for_signature: false, latest_answer: null,
      });
      return { status: 201, body: sent };
    }
    const written: QuestionRequest = {
      artifact: "question_request", schema_version: "0.1", id: `qr-20261001-12000${submitted.length}-abcd`,
      words: body.words, asked_by, asked_at: "2026-10-01T12:00:00Z", addressed_to: body.addressed_to,
    };
    requests.unshift({
      id: written.id, words: written.words, login: FAKE_LOGIN, asked_at: written.asked_at,
      addressed_to: written.addressed_to, state: NOT_DELIVERED, runs_wait_for_signature: true,
    });
    return { status: 201, body: written };
  };
  return { routes, submitted };
}

export const MOCK_STORE: StoreInfo = { store: "mock", writable: true };
export const READ_ONLY_STORE: StoreInfo = { store: "soft-matter-agents", writable: false };
/** a store that cannot take a request (the server answers 409 read_only_store) */

function summary(over: Partial<QuestionSummary> & Pick<QuestionSummary, "qid" | "agent">): QuestionSummary {
  return {
    title: over.qid, status: "DRAFT", created_at: "2026-09-23T10:00:00Z", updated_at: "2026-09-24T14:40:00Z",
    latest_version: 1, versions: [1], source: "mock", ...over,
  };
}

function card(name: string, kind: string, version: number, data: Record<string, unknown>): Card {
  return { name, kind, version, status: (data.status as string) ?? null, created_at: null, data };
}

function detail(s: QuestionSummary, version: number, cards: Partial<QuestionDetail>): QuestionDetail {
  return {
    summary: s, version, goal: null, axes: [], plan: null, synthesis: null, refusals: [], results: [], others: [],
    documents: [], files: [], ...cards,
  };
}

// versions 1, 2 and 5: the picker must list whatever the store returns
const SIM = summary({
  qid: "sim-20260923-001", agent: "simulation", title: "structural relaxation time", status: "DRAFT",
  latest_version: 5, versions: [1, 2, 5],
});
const MIC = summary({
  qid: "mic-20260925-001", agent: "microscope", title: "tracer diffusivity", status: "VALIDATED",
  created_at: "2026-09-25T09:00:00Z", purpose: "verify", intent: "explore", observable_name: "tracer_diffusivity",
});

const NUMBERS = [
  { name: "bead_diameter", value: 5, unit: "um", source: "kb:tracer_diameter_measured", grade: "E2", precision: "significant_figures" },
  { name: "diffusivity", value: 0.09, unit: "um^2/s", source: "computed:stokes_einstein", grade: "E4", precision: "order_of_magnitude" },
  { name: "odd", value: 1, unit: "1", source: "assumed:x", grade: "E9", precision: "exact" },
];

const SIM_V5_GOAL = card("v5_goal.json", "goal", 5, {
  card: "goal", status: "DRAFT", purpose: "characterize", observable: { name: "structural_relaxation_time" },
  numbers: NUMBERS,
  assumptions: [{ statement: "The sweep corners.", authorised_by: "kyuhwan_20260923" }],
  degraded: ["librarian unreachable"],
});

export const FAKE_DATA: FakeData = {
  store: MOCK_STORE,
  permissions: { submit_question: { allowed: true, reason: null } },
  questions: [
    detail(SIM, 1, {
      goal: card("goal.json", "goal", 1, { card: "goal", status: "DRAFT", numbers: NUMBERS.slice(0, 1), degraded: [] }),
      refusals: [card("refusal_s4_sim-20260923-001.json", "refusal", 1, { card: "refusal", stage: "S4", reason_code: "budget" })],
    }),
    detail(SIM, 2, {
      axes: [card("v2_axis_bd_pairwise_a7.json", "axis", 2, { card: "axis", verdict: "feasible" })],
    }),
    detail(SIM, 5, {
      goal: SIM_V5_GOAL,
      axes: [
        card("v5_axis_bd_pairwise_a1.json", "axis", 5, { card: "axis", verdict: "feasible" }),
        card("v5_axis_bd_pairwise_a7.json", "axis", 5, { card: "axis", verdict: "infeasible" }),
      ],
    }),
    detail(MIC, 1, {
      goal: card("goal.json", "goal", 1, { card: "goal", status: "VALIDATED", numbers: [], degraded: [] }),
    }),
  ],
  runs: [
    {
      summary: {
        run_id: "run-20260924-001-smoke-g2k2", agent: "simulation", qid: "sim-20260923-001", plan_id: "plan-x",
        status: "complete", created_at: "2026-09-24T20:00:00Z", finished_at: "2026-09-24T20:10:00Z",
        backend: "hoomd", source: "mock", approval_kind: "smoke_auto",
      },
      records: {
        "config.json": { seed: 7, parameters_si: { dt: 0.001 } },
        "log.json": { events: [{ t_mono: 0.1, event: "gate", tier: 1 }, { t_mono: 9, event: "complete" }] },
      },
      files: [{ name: "config.json", size: 10 }, { name: "trajectory.gsd", size: 9_000_000 }],
      not_opened: ["trajectory.gsd"],
    } satisfies RunDetail,
    {
      summary: {
        run_id: "run-20260924-003", agent: "microscope", qid: null, plan_id: null, status: null,
        created_at: "2026-09-24T19:06:52Z", finished_at: null, backend: "micromanager", source: "mock",
      },
      records: { "log.json": { no_plan_because: "No plan fits this run.", events: [{ t_wall: "19:07", event: "not_dispatched" }] } },
      files: [{ name: "log.json", size: 10 }],
      not_opened: [],
    },
  ],
  inbox: [
    {
      thread: "thr-tracer-diffusivity-001", agent: "microscope", state: "open", turn: "microscope_agent", round: 2,
      updated_at: "2026-09-22T03:47:24Z", status: { state: "open" }, source: "mock",
      messages: [{ name: "r2_ask_experiment.md", round: 2, kind: "ask_experiment", card: null, text: "Round two." }],
    },
  ],
  cards: {
    requests: [
      {
        id: "qr-20261023-091500-w3k8", words: "How far apart are the wells at 4x?", login: "member-2",
        asked_at: "2026-10-23T09:15:00Z", addressed_to: "librarian", state: NOT_DELIVERED,
        runs_wait_for_signature: true,
      },
    ],
    // newest first, as the server sends them: one card in each of the four states
    items: [
      {
        item_id: "ci-20261026-101500-aaaa", question_id: "mic-20261026-c004", agent: "microscope",
        words: "Is the stage drifting?", login: "otto", asked_at: "2026-10-26T10:15:00Z",
        state: "delivered · not answered yet", runs_wait_for_signature: true,
      },
      {
        item_id: "ci-20261026-091500-bbbb", question_id: "sim-20261026-c002", agent: "simulation",
        words: "How long does relaxation take?", login: "otto", asked_at: "2026-10-26T09:15:00Z",
        state: "taken up as sim-20261026-c002", runs_wait_for_signature: true,
      },
      {
        item_id: "ci-20261026-081500-cccc", question_id: "mic-20261026-c003", agent: "microscope",
        words: "Image the whole well at 40x", login: "member-2", asked_at: "2026-10-26T08:15:00Z",
        state: "refused · that objective is not on this stand", runs_wait_for_signature: true,
      },
      {
        item_id: "ci-20261026-071500-dddd", question_id: "mic-20261026-c001", agent: "microscope",
        words: "What is the pixel size?", login: "otto", asked_at: "2026-10-26T07:15:00Z",
        state: "an answer is on disk and cannot be read", runs_wait_for_signature: true,
      },
    ],
    questions: [
      {
        qid: "sim-20260923-001", agent: "simulation", title: "structural relaxation time", status: "DRAFT",
        created_at: "2026-09-23T10:00:00Z",
        steps: { asked: true, designed: true, signed: false, run: true, result: true, run_known: true },
      },
      {
        qid: "mic-20260925-001", agent: "microscope", title: "tracer diffusivity", status: "VALIDATED",
        created_at: "2026-09-25T09:00:00Z",
        steps: { asked: true, designed: false, signed: false, run: false, result: false, run_known: false },
      },
    ],
  },
  suggestions: [
    { text: "How far apart are the wells at 4x?", kind: "earlier question" },
    { text: "pixel_size", kind: "registered name" },
    { text: "refractive_index", kind: "registered name" },
  ],

};
