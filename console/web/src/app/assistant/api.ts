// Temporary until gen:api, T-009: the assistant API types are written by hand from T-013 as
// merged on main (fc5329f: runner.Answer, tools.Proposal, the ask() events and
// connection_status) and from T-009's GET /api/permissions. The HTTP paths below are this
// screen's proposal for server/api/assistant.py; once it is in and `npm run gen:api` has run,
// the types come from src/api/ and this file keeps only the clients.

import type { Client } from "../client";

export interface Usage {
  input_tokens?: number;
  output_tokens?: number;
  cache_creation_input_tokens?: number;
  cache_read_input_tokens?: number;
}

export interface Status {
  provider: string; // "fake" | "anthropic"
  connected: boolean;
  data_stage: string; // D7: prompt_only | text | images
}

export interface ExpectedGate {
  checked: boolean;
  enabled: boolean | null;
  reasons: string[];
}

export interface Proposal {
  proposal_id: string;
  conversation_id: string;
  tool: string;
  command: { kind: string; op?: string; args?: Record<string, unknown> };
  summary: string;
  /** the model's own words: grade "model" */
  reason: string;
  expected_gate: ExpectedGate;
  origin: string;
  status: "proposed" | "confirmed" | "rejected" | "failed";
  created_t: number;
  decided_by: string | null;
  decided_t: number | null;
  note: string;
  op_id: string | null;
}

export interface ToolCall {
  id: string;
  name: string;
  kind: string; // "read" | "action" | "unknown"
  is_error?: boolean;
  proposal_id?: string;
}

export interface Answer {
  conversation_id: string;
  text: string;
  stop_reason: string;
  provider: string;
  usage: Usage;
  tool_calls: ToolCall[];
  proposals: Proposal[];
  grade: string; // always "model"
}

/** One line of the streamed answer (runner.Assistant.ask on_event). */
export type AskEvent =
  | { type: "text"; text: string }
  | { type: "tool_call"; id: string; name: string; input: unknown; kind: string }
  | { type: "usage"; usage: Usage }
  | { type: "error"; error: string }
  | { type: "done"; answer: Answer };

export interface Conversation {
  conversation_id: string;
  messages: { role: "user" | "assistant"; content: { type: string; text?: string }[] }[];
  usage: Usage;
  proposals: Proposal[];
}

export interface Permission {
  allowed: boolean;
  reason: string;
}

export interface AskRequest {
  question: string;
  context: Record<string, unknown>;
  conversation_id: string | null;
}

export interface AssistantApi {
  /** null when the assistant endpoints do not answer */
  status(): Promise<Status | null>;
  /** streams events to `onEvent`; resolves with the final answer */
  ask(req: AskRequest, onEvent: (ev: AskEvent) => void): Promise<Answer>;
  conversation(id: string): Promise<Conversation>;
  confirm(proposalId: string): Promise<Proposal>;
  reject(proposalId: string, note?: string): Promise<Proposal>;
  /** T-009b GET /api/permissions?ops=a,b */
  permissions(ops: string[]): Promise<Record<string, Permission>>;
}

export class AssistantError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

// -- the real client: the app's shared client ------------------------------------------------

/**
 * Over `useClient()` (T-014b): reads go through `client.get` and decisions through
 * `client.post`, so a 401 / 423 starts the shell's re-login and a 403 `remote_view` turns the
 * app read-only; any other refusal is the action's own reason and stays on the card.
 *
 * The answer is an NDJSON stream: `ask` uses `client.postStream` (T-010-11), which applies the
 * same rules and returns the response unread. No socket of its own.
 *
 * Paths (fixed in the T-013 card for T-013b's router): GET status, POST ask (NDJSON stream of
 * AskEvent), GET conversations/{id}, POST proposals/{id}/confirm, POST proposals/{id}/reject.
 */
export function clientAssistantApi(client: Client): AssistantApi {
  const decided = async (path: string, body: unknown): Promise<Proposal> => {
    const p = await client.post<Proposal>(path, body);
    if (p === null) throw new AssistantError(500, "the server sent no proposal back");
    return p;
  };
  return {
    status: async () => {
      try {
        return await client.get<Status>("/api/assistant/status");
      } catch {
        return null;
      }
    },
    ask: async (req, onEvent) => {
      const r = await client.postStream("/api/assistant/ask", req); // refusals already thrown
      if (!r.body) throw new AssistantError(500, "the answer stream is empty");
      return readAnswer(r.body, onEvent);
    },
    conversation: (id) => client.get(`/api/assistant/conversations/${encodeURIComponent(id)}`),
    confirm: (id) => decided(`/api/assistant/proposals/${encodeURIComponent(id)}/confirm`, {}),
    reject: (id, note = "") => decided(`/api/assistant/proposals/${encodeURIComponent(id)}/reject`, { note }),
    permissions: (ops) => client.get(`/api/permissions?ops=${ops.map(encodeURIComponent).join(",")}`),
  };
}

export async function readAnswer(body: NonNullable<Response["body"]>, onEvent: (ev: AskEvent) => void): Promise<Answer> {
  const reader = body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  let answer: Answer | null = null;
  const line = (s: string) => {
    if (!s.trim()) return;
    const ev = JSON.parse(s) as AskEvent;
    onEvent(ev);
    if (ev.type === "done") answer = ev.answer;
    if (ev.type === "error") throw new AssistantError(500, ev.error);
  };
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    lines.forEach(line);
  }
  line(buffer);
  if (answer === null) throw new AssistantError(500, "the answer stream ended early");
  return answer;
}

// -- the fake: a scripted provider in memory, for tests and before the router -------------------

export interface FakeStep {
  /** streamed text pieces */
  text?: string[];
  /** a read tool the fake "runs" */
  read?: string;
  /** an action tool: becomes a proposal card */
  propose?: { tool: string; command: Proposal["command"]; summary: string; reason: string; gate?: ExpectedGate };
}

export interface FakeAssistantApi extends AssistantApi {
  readonly asked: AskRequest[];
  readonly decisions: { proposal_id: string; decision: "confirm" | "reject" }[];
}

export function createFakeAssistantApi(
  opts: {
    status?: Status | null;
    script?: FakeStep[];
    permissions?: Record<string, Permission> | "unavailable";
  } = {},
): FakeAssistantApi {
  const status = opts.status === undefined ? { provider: "fake", connected: false, data_stage: "text" } : opts.status;
  const script = opts.script ?? [{ text: ["This is the fake provider. ", "No model was called."] }];
  const asked: AskRequest[] = [];
  const decisions: FakeAssistantApi["decisions"] = [];
  const conversations = new Map<string, Conversation>();
  const proposals = new Map<string, Proposal>();
  let n = 0;

  const decide = async (id: string, decision: "confirm" | "reject", note = "") => {
    const p = proposals.get(id);
    if (!p || p.status !== "proposed") throw new AssistantError(409, `${id} is not waiting for a decision`);
    decisions.push({ proposal_id: id, decision });
    Object.assign(p, {
      status: decision === "confirm" ? "confirmed" : "rejected",
      decided_by: "otto@example.test",
      decided_t: 2,
      note,
      op_id: decision === "confirm" ? `op-${id}` : null,
    });
    return { ...p };
  };

  return {
    asked,
    decisions,
    status: async () => status,
    async ask(req, onEvent) {
      asked.push(req);
      const cid = req.conversation_id ?? `conv-fake${++n}`;
      const conv = conversations.get(cid) ?? { conversation_id: cid, messages: [], usage: {}, proposals: [] };
      conversations.set(cid, conv);
      conv.messages.push({ role: "user", content: [{ type: "text", text: req.question }] });
      const calls: ToolCall[] = [];
      const made: Proposal[] = [];
      let text = "";
      for (const step of script) {
        for (const t of step.text ?? []) {
          text += t;
          onEvent({ type: "text", text: t });
        }
        if (step.read) {
          const id = `tu-${++n}`;
          onEvent({ type: "tool_call", id, name: step.read, input: {}, kind: "read" });
          calls.push({ id, name: step.read, kind: "read" });
        }
        if (step.propose) {
          const id = `tu-${++n}`;
          onEvent({ type: "tool_call", id, name: step.propose.tool, input: {}, kind: "action" });
          const p: Proposal = {
            proposal_id: `prop-${n}`,
            conversation_id: cid,
            tool: step.propose.tool,
            command: step.propose.command,
            summary: step.propose.summary,
            reason: step.propose.reason,
            expected_gate: step.propose.gate ?? { checked: true, enabled: true, reasons: [] },
            origin: "assistant",
            status: "proposed",
            created_t: 1,
            decided_by: null,
            decided_t: null,
            note: "",
            op_id: null,
          };
          proposals.set(p.proposal_id, p);
          conv.proposals.push(p);
          made.push({ ...p });
          calls.push({ id, name: step.propose.tool, kind: "action", proposal_id: p.proposal_id });
        }
      }
      const usage = { input_tokens: 1200, output_tokens: 80, cache_read_input_tokens: 1000 };
      onEvent({ type: "usage", usage });
      conv.messages.push({ role: "assistant", content: [{ type: "text", text }] });
      const answer: Answer = {
        conversation_id: cid,
        text,
        stop_reason: "end_turn",
        provider: status?.provider ?? "fake",
        usage,
        tool_calls: calls,
        proposals: made,
        grade: "model",
      };
      onEvent({ type: "done", answer });
      return answer;
    },
    async conversation(id) {
      const c = conversations.get(id);
      if (!c) throw new AssistantError(404, `no conversation ${id}`);
      return { ...c, proposals: c.proposals.map((p) => ({ ...p })) };
    },
    confirm: (id) => decide(id, "confirm"),
    reject: (id, note) => decide(id, "reject", note),
    async permissions(ops) {
      if (opts.permissions === "unavailable") throw new AssistantError(503, "permissions unavailable");
      const table = opts.permissions ?? {};
      return Object.fromEntries(ops.map((op) => [op, table[op] ?? { allowed: true, reason: "" }]));
    },
  };
}
