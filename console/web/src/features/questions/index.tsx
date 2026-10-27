/**
 * Questions area (formerly the Console area; PLAN F1, ui-spec 7.1, docs/screens/console.md). The
 * first screen is the question window -- one field, an Ask choice, Send -- with a card per question
 * below it (console cards 010 and 019). The write is a question: to the microscope or the simulation
 * into that agent's inbox, to the librarian or the agents a request in the console's own folder that
 * reaches no agent. The server allows or refuses it. The rest reads only.
 *
 * `rest` forms (after `#/questions/`):
 *   "" | "questions"          the question window and its cards
 *   "questions/<qid>"         one question, latest version
 *   "runs"                    run list
 *   "runs/<agent>/<run_id>"   one run
 *   "inbox"                   inbox threads
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
  type QuestionCards,
  READ_ONLY_REMOTE,
  type RunSummary,
  type StoreInfo,
  SUBMIT_OP,
} from "./api";
import "./console.css";
import { Inbox } from "./inbox";
import { AskBox, submitReason } from "./ask";
import { QuestionCardsView } from "./cards";
import { QuestionPage, RequestPage } from "./detail";
import { RunDetailView, RunList } from "./runs";
import { Loaded, useLoad } from "./ui";

type Tab = "questions" | "runs" | "inbox";

interface View {
  tab: Tab;
  qid?: string;
  requestId?: string;
  agent?: Agent;
  runId?: string;
}

export function parseRest(rest: string): View {
  const parts = rest.replace(/[?#].*$/, "").split("/").filter((p) => p !== "").map(decodeURIComponent);
  switch (parts[0]) {
    case "questions":
      return parts[1] ? { tab: "questions", qid: parts[1] } : { tab: "questions" };
    case "requests":
      return parts[1] ? { tab: "questions", requestId: parts[1] } : { tab: "questions" };
    case "runs": {
      const agent = AGENTS.find((a) => a === parts[1]);
      return agent && parts[2] ? { tab: "runs", agent, runId: parts[2] } : { tab: "runs" };
    }
    case "inbox":
      return { tab: "inbox" };
    default:
      return { tab: "questions" };
  }
}

const TABS: { id: Tab; label: string }[] = [
  { id: "questions", label: "Questions" },
  { id: "runs", label: "Runs" },
  { id: "inbox", label: "Inbox" },
];

export default function ConsoleScreen() {
  const client = useClient();
  const readOnly = useReadOnly();
  const connected = useEventsConnected();
  const [rest, setRest] = useAreaPath();
  const view = parseRest(rest);
  const [refreshKey, setRefreshKey] = useState(0);
  const [shownVersion, setShownVersion] = useState<number | undefined>(undefined);
  const onSelect = useCallback((v: number) => setShownVersion(v), []);

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
  const cards = useLoad(() => client.get<QuestionCards>(PATHS.questionCards), [client, refreshKey]);
  const runs = useLoad(() => client.get<RunSummary[]>(PATHS.runs()), [client, refreshKey]);
  const inbox = useLoad(() => client.get<InboxThread[]>(PATHS.inbox), [client, refreshKey]);

  // prompt context (X1): short ids only, no card bodies (D7)
  const qid = view.qid;
  const version = qid !== undefined ? shownVersion : undefined;
  const details = useMemo(() => {
    const d: Record<string, string | number> = {};
    if (qid !== undefined) d.qid = qid;
    if (version !== undefined) d.version = version;
    if (view.runId !== undefined) d.run_id = view.runId;
    if (view.agent !== undefined) d.agent = view.agent;
    return d;
  }, [qid, version, view.runId, view.agent]);
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

      {view.tab === "questions" && view.qid === undefined && view.requestId === undefined && (
        <>
          <AskBox
            reason={submitReason(readOnly, perms, storeInfo)}
            refreshKey={refreshKey}
            onWritten={() => setRefreshKey((k) => k + 1)}
          />
          <Loaded state={cards}>
            {(c) => (
              <QuestionCardsView
                cards={c}
                onOpen={(q) => setRest(`questions/${encodeURIComponent(q)}`)}
                onOpenRequest={(id) => setRest(`requests/${encodeURIComponent(id)}`)}
              />
            )}
          </Loaded>
        </>
      )}
      {view.tab === "questions" && view.qid !== undefined && (
        <>
          <button className="console-link" onClick={() => setRest("questions")}>← All questions</button>
          <QuestionPage key={view.qid} qid={view.qid} refreshKey={refreshKey} onSelect={onSelect} />
        </>
      )}
      {view.tab === "questions" && view.requestId !== undefined && (
        <>
          <button className="console-link" onClick={() => setRest("questions")}>← All questions</button>
          <Loaded state={cards}>{(c) => <RequestPage id={view.requestId ?? ""} cards={c.requests} />}</Loaded>
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
    </div>
  );
}
