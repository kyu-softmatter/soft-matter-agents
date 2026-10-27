/**
 * The console's wire types, taken from the generated `src/api/schema.ts` (the console router's
 * pydantic models and T-009b's `PermissionOut`), plus what the schema does not cover: the paths,
 * the shared reason texts, the one permissions call and the question POST. Reads go through the
 * shell's client (`src/app/client.tsx`).
 */

import { type Client, CommandRefused } from "../../app/client";
import type { components } from "../../api/schema";

type Schemas = components["schemas"];

export type QuestionSummary = Schemas["QuestionSummaryOut"];
export type QuestionDetail = Schemas["QuestionDetailOut"];
export type Card = Schemas["CardOut"];
export type DocumentText = Schemas["DocumentOut"];
export type FileInfo = QuestionDetail["files"][number];
export type RunSummary = Schemas["RunSummaryOut"];
export type RunDetail = Schemas["RunDetailOut"];
export type InboxMessage = Schemas["InboxMessageOut"];
export type InboxThread = Schemas["InboxThreadOut"];
/** A plan_approval card of a seat's approvals/ (read only). */
export type Approval = Schemas["ApprovalOut"];
/** `GET /api/console/store`: which store is behind the console, and whether it takes a question. */
export type StoreInfo = Schemas["StoreOut"];
/** One answer of `GET /api/permissions?ops=...` (T-009b): may I, and if not, why and the code. */
export type Permission = Schemas["PermissionOut"];
export type Permissions = Record<string, Permission>;
/** What the question window sends: the words as typed and the Ask choice. Nothing else. */
export type AskIn = Schemas["QuestionRequestIn"];
/** What was written into the console's own folder: `contracts/schemas/question_request.schema.json`, exactly. */
export type QuestionRequest = Schemas["QuestionRequestOut"];
/** What was written into an agent's inbox: `contracts/schemas/console_inbox_item.schema.json`'s `console_question`, exactly. */
export type ConsoleQuestion = Schemas["ConsoleQuestionOut"];
/** What the question POST answers, told apart by `artifact`. */
export type AskResult = ConsoleQuestion | QuestionRequest;
export type RequestCard = Schemas["RequestCardOut"];
/** An item delivered to the microscope's or the simulation's inbox, with what became of it. */
export type ItemCard = Schemas["ItemCardOut"];
export type QuestionProgress = Schemas["QuestionProgressOut"];
export type QuestionCards = Schemas["QuestionCardsOut"];
export type Suggestion = Schemas["SuggestionOut"];
export type Addressee = AskIn["addressed_to"];
/** What the sign dialog may offer this login (card 011). The runtime decides from the person's own file. */
export type SigningState = Schemas["SigningStateOut"];
export type SignCheck = Schemas["SignCheckOut"];
export type SignCheckIn = Schemas["SignCheckIn"];
/** A run soft-matter-agents executes, as its events.jsonl says so far (plan.md 11-25). */
export type RunStream = Schemas["RunStreamOut"];
export type StopResult = Schemas["StopOut"];
/** soft-matter-agents' live view (its card 062): the host and the approved lists. */
export type LiveState = Schemas["LiveOut"];
export type LiveList = Schemas["LiveListOut"];
export type LiveOnResult = Schemas["LiveOnOut"];

export type Agent = QuestionSummary["agent"];
export const AGENTS: readonly Agent[] = ["microscope", "simulation"];

/** The permission op for asking a question (D16: operator on the microscope PC). */
export const SUBMIT_OP = "submit_question";

/** Shared texts for every screen (screen rules from the AF work-assignment assistant). */
export const CHECKING_PERMISSIONS = "Checking permissions…";
export const PERMISSION_CHECK_UNAVAILABLE = "Permission check unavailable";
export const READ_ONLY_REMOTE = "Read-only: remote view";
/** ui-spec 7.1: the console's own rule, a store that is not the mock store. */
export const READ_ONLY_STORE_REASON = "Submitting to soft-matter-agents is not connected yet (read-only)";

/** The Ask choice, in the order the person sees it. */
export const ADDRESSEES: readonly { value: Addressee; label: string }[] = [
  { value: "agents_decide", label: "Let the agents decide" },
  { value: "microscope", label: "The microscope" },
  { value: "simulation", label: "The simulation" },
  { value: "librarian", label: "The librarian" },
];

/** The state a request written in the console carries: it went to no agent. */
export const NOT_DELIVERED = "written in the console · not delivered";

/** What the form says after Send, in the person's words. A question to an agent is told its id; the rest are plainly not sent. */
export function afterSend(result: AskResult, to: Addressee): string {
  if (result.artifact === "console_question") {
    return `Sent to the ${to === "simulation" ? "simulation" : "microscope"} as question ${result.question_id}.`;
  }
  return to === "librarian"
    ? "Not delivered: the console does not send to the librarian yet."
    : "Not delivered: no agent takes a question left to the agents yet.";
}

const seg = encodeURIComponent;

function query(params: Record<string, string | number | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined) q.set(k, String(v));
  const s = q.toString();
  return s === "" ? "" : `?${s}`;
}

export const PATHS = {
  store: "/api/console/store",
  questions: (agent?: Agent) => `/api/console/questions${query({ agent })}`,
  questionRequests: "/api/console/question-requests",
  questionCards: "/api/console/question-cards",
  suggestions: "/api/console/suggestions",
  signing: "/api/console/signing",
  signCheck: "/api/console/sign-check",
  question: (qid: string, version?: number) => `/api/console/questions/${seg(qid)}${query({ version })}`,
  runs: (agent?: Agent) => `/api/console/runs${query({ agent })}`,
  run: (agent: Agent, runId: string) => `/api/console/runs/${seg(agent)}/${seg(runId)}`,
  runStream: (agent: Agent, runId: string, since?: number) =>
    `/api/console/runs/${seg(agent)}/${seg(runId)}/stream${query({ since })}`,
  runFrame: (agent: Agent, runId: string) => `/api/console/runs/${seg(agent)}/${seg(runId)}/frame`,
  runStop: (agent: Agent, runId: string) => `/api/console/runs/${seg(agent)}/${seg(runId)}/stop`,
  inbox: "/api/console/inbox",
  live: "/api/console/live",
  liveOn: "/api/console/live/on",
  approvals: (agent?: Agent) => `/api/console/approvals${query({ agent })}`,
  permissions: (ops: readonly string[]) => `/api/permissions?ops=${ops.map(seg).join(",")}`,
};

/** The one permissions call. A missing op counts as unavailable (screen rule). */
export async function fetchPermissions(client: Client, ops: readonly string[]): Promise<Permissions> {
  const got = await client.get<Permissions>(PATHS.permissions(ops));
  const out: Permissions = {};
  for (const op of ops) out[op] = got[op] ?? { allowed: false, reason: PERMISSION_CHECK_UNAVAILABLE };
  return out;
}

/**
 * `POST /api/console/question-requests`: a question to the microscope or the simulation is written into
 * that agent's inbox; one to the librarian or left to the agents is a request in the console's own
 * folder, not delivered. Goes through the shell's `client.post`: only a 403 with code `remote_view`
 * switches the app to read-only; any other refusal (a viewer, a store that cannot take it, an inbox
 * that is not there) is thrown with its reason and shown next to the form.
 */
export async function askQuestion(client: Client, body: AskIn): Promise<AskResult> {
  const r = await client.post<AskResult>(PATHS.questionRequests, body);
  if (r === null) throw new CommandRefused(502, "the server returned no request");
  return r;
}

/**
 * `POST /api/console/sign-check` (the name it was built under; it signs since card 013): the server checks
 * the person's password for the plan whose fingerprint the dialog showed and, on a real tree, writes one
 * approval into `microscope_runtime/approvals/`. Under the mock store nothing is written. Every refusal
 * (wrong password, the throttle, a changed plan, a missing approvals folder or login file, a login that is
 * not the person's) is thrown with its reason, in words.
 */
export async function signCheck(client: Client, body: SignCheckIn): Promise<SignCheck> {
  const r = await client.post<SignCheck>(PATHS.signCheck, body);
  if (r === null) throw new CommandRefused(502, "the server returned no answer");
  return r;
}

/**
 * `POST .../stop`: the console's Abort for a run soft-matter-agents executes, sent on the run's
 * own loopback stop channel. A stop like the engine's abort: the microscope PC always, a remote
 * viewer when remote abort is on (D13). Any refusal is thrown with its reason.
 */
export async function stopRun(client: Client, agent: Agent, runId: string, reason: string): Promise<StopResult> {
  const r = await client.post<StopResult>(PATHS.runStop(agent, runId), { reason });
  if (r === null) throw new CommandRefused(502, "the server returned no answer to the stop");
  return r;
}
