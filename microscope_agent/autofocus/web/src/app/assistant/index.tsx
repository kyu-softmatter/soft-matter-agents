import { Component, type ErrorInfo, type FormEvent, type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { useReadOnly } from "../client";
import { useCurrentScreenContext } from "../screenContext";
import type { Answer, AskEvent, Conversation, Proposal, Status, Usage } from "./api";
import { blockedReason, useAssistantApi, useConversationId, usePermissions } from "./hooks";
import { commandOp, ProposalCard } from "./ProposalCard";
import "./assistant.css";

const SUBMIT_QUESTION = "submit_question"; // T-018 Action, checked by the server (D16)

interface Turn {
  question: string;
  /** streamed so far, or the final text */
  text: string;
  tools: { id: string; name: string; kind: string }[];
  usage: Usage | null;
  proposals: string[];
  error: string | null;
  done: boolean;
}

function tokens(u: Usage): string {
  const input = (u.input_tokens ?? 0) + (u.cache_read_input_tokens ?? 0) + (u.cache_creation_input_tokens ?? 0);
  const cached = u.cache_read_input_tokens ? `, ${u.cache_read_input_tokens} cached` : "";
  return `${input} in${cached} · ${u.output_tokens ?? 0} out`;
}

function addUsage(a: Usage | null, b: Usage): Usage {
  const out: Usage = { ...(a ?? {}) };
  for (const k of ["input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"] as const)
    out[k] = (out[k] ?? 0) + (b[k] ?? 0);
  return out;
}

/** Turns from a stored conversation: user questions without the screen context, assistant text. */
export function turnsFrom(conv: Conversation): Turn[] {
  const turns: Turn[] = [];
  for (const m of conv.messages) {
    const texts = m.content.filter((b) => b.type === "text" && typeof b.text === "string").map((b) => b.text as string);
    if (m.role === "user") {
      const question = texts.filter((t) => !t.startsWith("<screen_context>")).join("\n");
      if (question)
        turns.push({ question, text: "", tools: [], usage: null, proposals: [], error: null, done: true });
    } else if (turns.length > 0) {
      turns[turns.length - 1].text += texts.join("");
    }
  }
  const last = turns[turns.length - 1];
  if (last) last.proposals = conv.proposals.map((p) => p.proposal_id);
  return turns;
}

function ConnectionLine({ status }: { status: Status | null | undefined }) {
  if (status === undefined) return <p className="muted pb-conn">Assistant: checking…</p>;
  if (status === null)
    return (
      <p className="pb-conn pb-warn" role="status">
        Assistant: not connected (the server does not answer)
      </p>
    );
  return (
    <p className="pb-conn" role="status">
      Assistant: {status.provider === "fake" && <span className="pb-badge">fake</span>}{" "}
      {status.connected ? (
        <span>connected to Claude</span>
      ) : (
        <span className="pb-warn">
          not connected
          {status.provider === "fake" ? " (fake provider: answers are canned, no model is called)" : " (no API key on the server)"}
        </span>
      )}
      <span className="muted"> · data sent: {status.data_stage}</span>
    </p>
  );
}

/**
 * The prompt box on every screen (PLAN X1, X2). It sends the question with the context of the
 * screen in view, streams the answer, and shows each proposed command as a card. Confirm and
 * Reject go to the server, which checks the permission again; the engine's gates and guards
 * still decide what runs.
 */
function PromptBoxView() {
  const api = useAssistantApi();
  const context = useCurrentScreenContext();
  const { readOnly, why } = useReadOnly();
  const [status, setStatus] = useState<Status | null | undefined>(undefined);
  const [conversationId, setConversationId] = useConversationId();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [proposals, setProposals] = useState<Record<string, Proposal>>({});
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [epoch, setEpoch] = useState(0);

  useEffect(() => {
    let live = true;
    api.status().then((s) => live && setStatus(s));
    return () => {
      live = false;
    };
  }, [api]);

  // pick up the conversation this tab already had (another screen, or a reload)
  useEffect(() => {
    if (!conversationId) return;
    let live = true;
    api
      .conversation(conversationId)
      .then((c) => {
        if (!live) return;
        setTurns(turnsFrom(c));
        setProposals(Object.fromEntries(c.proposals.map((p) => [p.proposal_id, p])));
      })
      .catch(() => live && setConversationId(null)); // the server restarted: start a new one
    return () => {
      live = false;
    };
    // on mount only: later answers are already in state
  }, [api]);

  const ops = useMemo(
    () => [SUBMIT_QUESTION, ...Object.values(proposals).filter((p) => p.status === "proposed").map(commandOp)],
    [proposals],
  );
  const permissions = usePermissions(api, ops, epoch);
  const askBlocked = readOnly ? `Read only: ${why ?? "remote view"}` : blockedReason(permissions, SUBMIT_QUESTION);

  const patchLast = useCallback((fn: (t: Turn) => Turn) => {
    setTurns((ts) => (ts.length ? [...ts.slice(0, -1), fn(ts[ts.length - 1])] : ts));
  }, []);

  const onEvent = useCallback(
    (ev: AskEvent) => {
      if (ev.type === "text") patchLast((t) => ({ ...t, text: t.text + ev.text }));
      else if (ev.type === "tool_call") patchLast((t) => ({ ...t, tools: [...t.tools, { id: ev.id, name: ev.name, kind: ev.kind }] }));
      else if (ev.type === "usage") patchLast((t) => ({ ...t, usage: addUsage(t.usage, ev.usage) }));
    },
    [patchLast],
  );

  const ask = async (ev: FormEvent) => {
    ev.preventDefault();
    const q = question.trim();
    if (!q || askBlocked) return;
    setAsking(true);
    setQuestion("");
    setTurns((ts) => [...ts, { question: q, text: "", tools: [], usage: null, proposals: [], error: null, done: false }]);
    try {
      const { area, ...details } = context;
      const answer: Answer = await api.ask({ question: q, context: { area, ...details }, conversation_id: conversationId }, onEvent);
      setConversationId(answer.conversation_id);
      setProposals((ps) => ({ ...ps, ...Object.fromEntries(answer.proposals.map((p) => [p.proposal_id, p])) }));
      patchLast((t) => ({ ...t, text: answer.text, usage: answer.usage, proposals: answer.proposals.map((p) => p.proposal_id), done: true }));
    } catch (e) {
      patchLast((t) => ({ ...t, error: e instanceof Error ? e.message : String(e), done: true }));
    } finally {
      setAsking(false);
    }
  };

  const decide = (p: Proposal, how: "confirm" | "reject") => async () => {
    const next = how === "confirm" ? await api.confirm(p.proposal_id) : await api.reject(p.proposal_id);
    setProposals((ps) => ({ ...ps, [next.proposal_id]: next }));
    setEpoch((n) => n + 1);
  };

  const cardBlocked = (p: Proposal) => (readOnly ? `Read only: ${why ?? "remote view"}` : blockedReason(permissions, commandOp(p)));

  return (
    <div className="pb">
      <ConnectionLine status={status} />
      <ol className="pb-turns" aria-label="Conversation">
        {turns.map((t, i) => (
          <li key={i} className="pb-turn">
            <p className="pb-q">{t.question}</p>
            {t.tools.length > 0 && (
              <ul className="pb-tools" aria-label="Tool calls">
                {t.tools.map((c) => (
                  <li key={c.id}>
                    {c.kind === "action" ? "proposed" : "read"}: <code>{c.name}</code>
                  </li>
                ))}
              </ul>
            )}
            {(t.text || !t.done) && (
              <div className="pb-a">
                <span className="pb-grade" title="Written by the model, not measured">
                  model
                </span>{" "}
                {t.text || <span className="muted">…</span>}
              </div>
            )}
            {t.error && (
              <p className="pb-warn" role="alert">
                {t.error}
              </p>
            )}
            {t.proposals.map((id) =>
              proposals[id] ? (
                <ProposalCard
                  key={id}
                  proposal={proposals[id]}
                  blocked={cardBlocked(proposals[id])}
                  onConfirm={decide(proposals[id], "confirm")}
                  onReject={decide(proposals[id], "reject")}
                />
              ) : null,
            )}
            {t.usage && <p className="muted pb-usage">Tokens: {tokens(t.usage)}</p>}
          </li>
        ))}
      </ol>
      <form className="pb-form" aria-label="Ask the assistant" onSubmit={ask}>
        <textarea
          aria-label="Question"
          value={question}
          placeholder={`Ask about ${context.area}…`}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={asking || askBlocked !== null}
          rows={3}
        />
        <div className="pb-actions">
          <button type="submit" disabled={asking || askBlocked !== null || !question.trim()}>
            {asking ? "Asking…" : "Ask"}
          </button>
          {askBlocked && <span className="muted pb-blocked">{askBlocked}</span>}
          {conversationId && (
            <button
              type="button"
              className="pb-link"
              disabled={asking}
              onClick={() => {
                setConversationId(null);
                setTurns([]);
                setProposals({});
              }}
            >
              New conversation
            </button>
          )}
        </div>
      </form>
    </div>
  );
}

class PromptBoxBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("prompt box failed", error, info.componentStack);
  }

  render() {
    if (this.state.error)
      return (
        <p className="pb-warn pb" role="status">
          Prompt box unavailable: {this.state.error.message}
        </p>
      );
    return this.props.children;
  }
}

/** The shell's prompt slot loads this. A failure here never takes the screens down with it. */
export default function PromptBox() {
  return (
    <PromptBoxBoundary>
      <PromptBoxView />
    </PromptBoxBoundary>
  );
}
