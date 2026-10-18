/**
 * Console area: the agents' questions, runs and inbox, and asking a question
 * (PLAN F1, ui-spec 7.1, docs/screens/console.md). Reads only; the one write is a question to
 * the mock store, which the server allows or refuses.
 *
 * `rest` forms (after `#/console/`):
 *   "" | "questions"          question list
 *   "questions/<qid>"         one question, latest version
 *   "runs"                    run list
 *   "runs/<agent>/<run_id>"   one run
 *   "inbox"                   inbox threads
 *   "ask"                     ask a question
 *
 * Data is read when the area opens and on "Refresh"; nothing polls.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useClient, useEventsConnected, useReadOnly } from "../../app/client";
import { useAreaPath } from "../../app/route";
import { useScreenContext } from "../../app/screenContext";
import {
  AGENTS,
  type Agent,
  fetchPermissions,
  type InboxThread,
  PATHS,
  type QuestionSummary,
  READ_ONLY_REMOTE,
  type RunSummary,
  type StoreInfo,
  SUBMIT_OP,
} from "./api";
import "./console.css";
import { Inbox } from "./inbox";
import { QuestionDetailView, QuestionList, type QuestionSelection } from "./questions";
import { RunDetailView, RunList } from "./runs";
import { SubmitForm, submitReason } from "./submit";
import { Loaded, useLoad } from "./ui";

type Tab = "questions" | "runs" | "inbox" | "ask";

interface View {
  tab: Tab;
  qid?: string;
  agent?: Agent;
  runId?: string;
}

export function parseRest(rest: string): View {
  const parts = rest.replace(/[?#].*$/, "").split("/").filter((p) => p !== "").map(decodeURIComponent);
  switch (parts[0]) {
    case "questions":
      return parts[1] ? { tab: "questions", qid: parts[1] } : { tab: "questions" };
    case "runs": {
      const agent = AGENTS.find((a) => a === parts[1]);
      return agent && parts[2] ? { tab: "runs", agent, runId: parts[2] } : { tab: "runs" };
    }
    case "inbox":
      return { tab: "inbox" };
    case "ask":
      return { tab: "ask" };
    default:
      return { tab: "questions" };
  }
}

const TABS: { id: Tab; label: string }[] = [
  { id: "questions", label: "Questions" },
  { id: "runs", label: "Runs" },
  { id: "inbox", label: "Inbox" },
  { id: "ask", label: "Ask" },
];

export default function ConsoleScreen() {
  const client = useClient();
  const readOnly = useReadOnly();
  const connected = useEventsConnected();
  const [rest, setRest] = useAreaPath();
  const view = parseRest(rest);
  const [refreshKey, setRefreshKey] = useState(0);
  const [sel, setSel] = useState<QuestionSelection | undefined>(undefined);
  const onSelect = useCallback((s: QuestionSelection) => setSel(s), []);

  // re-read when the event socket comes back after a drop (the server may have restarted); not a poll
  const link = useRef({ open: connected, dropped: false });
  useEffect(() => {
    const s = link.current;
    if (!connected && s.open) s.dropped = true;
    if (connected && s.dropped) {
      s.dropped = false;
      setRefreshKey((k) => k + 1);
    }
    s.open = connected;
  }, [connected]);

  const storeInfo = useLoad(() => client.get<StoreInfo>(PATHS.store), [client, refreshKey]);
  const perms = useLoad(() => fetchPermissions(client, [SUBMIT_OP]), [client, refreshKey]);
  const questions = useLoad(() => client.get<QuestionSummary[]>(PATHS.questions()), [client, refreshKey]);
  const runs = useLoad(() => client.get<RunSummary[]>(PATHS.runs()), [client, refreshKey]);
  const inbox = useLoad(() => client.get<InboxThread[]>(PATHS.inbox), [client, refreshKey]);

  // prompt context (X1): short ids only, no card bodies (D7)
  const qid = view.qid;
  const version = qid !== undefined ? sel?.version : undefined;
  const cardKind = qid !== undefined ? sel?.card_kind : undefined;
  const details = useMemo(() => {
    const d: Record<string, string | number> = {};
    if (qid !== undefined) d.qid = qid;
    if (version !== undefined) d.version = version;
    if (cardKind !== undefined) d.card_kind = cardKind;
    if (view.runId !== undefined) d.run_id = view.runId;
    if (view.agent !== undefined) d.agent = view.agent;
    return d;
  }, [qid, version, cardKind, view.runId, view.agent]);
  useScreenContext(details);

  const store = storeInfo.data;
  return (
    <div className="console">
      <div className="console-bar">
        <nav role="tablist" aria-label="Console" className="console-tabs">
          {TABS.map((t) => (
            <button key={t.id} role="tab" aria-selected={view.tab === t.id} onClick={() => setRest(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
        {store !== undefined && (
          <span className="console-tag">
            Store: {store.store}{store.writable ? "" : " (read-only)"}
          </span>
        )}
        {readOnly.readOnly && (
          <span className="console-tag" title={readOnly.why ?? undefined}>{READ_ONLY_REMOTE}</span>
        )}
        <button onClick={() => setRefreshKey((k) => k + 1)}>Refresh</button>
      </div>

      {view.tab === "questions" && view.qid === undefined && (
        <Loaded state={questions}>
          {(qs) => <QuestionList questions={qs} onOpen={(q) => setRest(`questions/${encodeURIComponent(q)}`)} />}
        </Loaded>
      )}
      {view.tab === "questions" && view.qid !== undefined && (
        <>
          <button className="console-link" onClick={() => setRest("questions")}>← All questions</button>
          <QuestionDetailView key={view.qid} qid={view.qid} refreshKey={refreshKey} onSelect={onSelect} />
        </>
      )}
      {view.tab === "runs" && view.runId === undefined && (
        <Loaded state={runs}>
          {(rs) => (
            <RunList runs={rs} onOpen={(a, r) => setRest(`runs/${a}/${encodeURIComponent(r)}`)} />
          )}
        </Loaded>
      )}
      {view.tab === "runs" && view.agent !== undefined && view.runId !== undefined && (
        <>
          <button className="console-link" onClick={() => setRest("runs")}>← All runs</button>
          <RunDetailView agent={view.agent} runId={view.runId} refreshKey={refreshKey} />
        </>
      )}
      {view.tab === "inbox" && <Loaded state={inbox}>{(ts) => <Inbox threads={ts} />}</Loaded>}
      {view.tab === "ask" && (
        <SubmitForm reason={submitReason(readOnly, perms, storeInfo)} onSubmitted={() => setRefreshKey((k) => k + 1)} />
      )}
    </div>
  );
}
