/**
 * Fixtures for the console tests, shaped like the T-008 mock store's records, and the server
 * routes that answer from them on the shell's `fakeTransport` (no network).
 */

import type { Route } from "../../test/fakes";
import {
  type Card,
  type InboxThread,
  PATHS,
  type Permissions,
  type QuestionDetail,
  type QuestionSummary,
  READ_ONLY_STORE_REASON,
  type RunDetail,
  type StoreInfo,
  SUBMIT_OP,
  type SubmitIn,
} from "./api";

export interface FakeData {
  store: StoreInfo;
  /** the shared permission answer; null makes `/api/permissions` fail */
  permissions: Permissions | null;
  /** every version of every question, one QuestionDetail each */
  questions: QuestionDetail[];
  runs: RunDetail[];
  inbox: InboxThread[];
  /** the POST refuses with this whatever the permission answer said (it may be stale) */
  postRefusal?: { status: number; body: unknown };
}

/**
 * Routes for `fakeTransport`, answering like the console router would (docs/screens/console.md).
 * The POST follows the server's order: permission 403, then read-only store 409.
 */
export function consoleRoutes(data: FakeData): { routes: Record<string, Route>; submitted: SubmitIn[] } {
  const questions = [...data.questions];
  const submitted: SubmitIn[] = [];
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
    [PATHS.runs()]: () => ok(data.runs.map((r) => r.summary)),
    [PATHS.inbox]: () => ok(data.inbox),
  };
  for (const d of data.questions) {
    routes[PATHS.question(d.summary.qid, d.version)] = () => ok(d);
    routes[PATHS.question(d.summary.qid)] = () => ok(latest(d.summary.qid));
  }
  for (const r of data.runs) routes[PATHS.run(r.summary.agent, r.summary.run_id)] = () => ok(r);

  const list = routes[PATHS.questions()];
  routes[PATHS.questions()] = (init) => {
    if (init?.method !== "POST") return list(init);
    if (data.postRefusal !== undefined) return data.postRefusal;
    const perm = data.permissions?.[SUBMIT_OP];
    if (perm === undefined || !perm.allowed) {
      return { status: 403, body: { detail: { code: perm?.code ?? "role", message: perm?.reason ?? "refused" } } };
    }
    if (!data.store.writable) {
      return { status: 409, body: { detail: { code: "read_only_store", message: READ_ONLY_STORE_REASON } } };
    }
    const body = JSON.parse(String(init.body)) as SubmitIn;
    submitted.push(body);
    const qid = `${body.target === "microscope" ? "mic" : "sim"}-20261001-${900 + submitted.length}`;
    const card: Card = {
      name: "goal.json", kind: "goal", version: 1, status: "DRAFT", created_at: "2026-10-01T00:00:00Z",
      data: { card: "goal", qid, status: "DRAFT", question: body.text, origin: "dino-autofocus mock" },
    };
    const s: QuestionSummary = {
      qid, agent: body.target, title: body.text, status: "DRAFT", created_at: card.created_at,
      updated_at: card.created_at, latest_version: 1, versions: [1], source: "mock-submitted",
    };
    questions.push({
      summary: s, version: 1, goal: card, axes: [], plan: null, synthesis: null, refusals: [], results: [],
      others: [], documents: [], files: [],
    });
    return { status: 201, body: s };
  };
  return { routes, submitted };
}

export const MOCK_STORE: StoreInfo = { store: "mock", writable: true };
export const READ_ONLY_STORE: StoreInfo = { store: "soft-matter-agents", writable: false };

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
};
