/** Run list and run detail (ui-spec 7.1). Simulation progress and trajectories live in the simulation area. */

import { useEffect, useState } from "react";

import { areaHref } from "../../app/route";
import { useClient } from "../../app/client";
import { AGENTS, type Agent, PATHS, type RunDetail, type RunStream, type RunSummary, stopRun } from "./api";
import { asArray, errorText, Fields, isRecord, Json, Loaded, shortTime, show, useLoad } from "./ui";

/** How often a running run's events and frame are read again (the file and the tap, not a device). */
export const FOLLOW_MS = 1000;
export const ABORT_LABEL = "Abort this run";
/** OD-30: soft-matter-agents keeps a run going when its viewer goes, and so does the console. */
export const CLOSE_NOTE = "Closing this page does not stop the run.";

export function RunList({ runs, onOpen }: { runs: RunSummary[]; onOpen: (agent: Agent, runId: string) => void }) {
  const [agent, setAgent] = useState("");
  const shown = runs.filter((r) => agent === "" || r.agent === agent);
  return (
    <section aria-label="Runs">
      <div className="console-filters">
        <label>
          Agent{" "}
          <select value={agent} onChange={(e) => setAgent(e.target.value)}>
            <option value="">All</option>
            {AGENTS.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </label>
        <span className="console-muted">{shown.length} of {runs.length}</span>
      </div>
      <table className="console-table">
        <thead>
          <tr>
            <th>run_id</th><th>Agent</th><th>qid</th><th>plan_id</th><th>Backend</th><th>Started</th>
            <th>Finished</th><th>Approval</th><th>Outcome</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((r) => (
            <tr key={`${r.agent}/${r.run_id}`}>
              <td><button className="console-link" onClick={() => onOpen(r.agent, r.run_id)}>{r.run_id}</button></td>
              <td>{r.agent}</td>
              <td>{r.qid ?? "—"}</td>
              <td>{r.plan_id ?? "—"}</td>
              <td>{r.backend ?? "—"}</td>
              <td>{shortTime(r.created_at)}</td>
              <td>{shortTime(r.finished_at)}</td>
              <td>{r.approval_kind ?? "—"}</td>
              <td>{r.status ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {shown.length === 0 && <p className="console-muted">No runs.</p>}
    </section>
  );
}

const LOG_NOTES = ["no_plan_because", "not_dispatched", "approved_commands", "approval", "stop_criteria"] as const;
const SIM_CONFIG = ["parameters_si", "envelope_check", "seed"] as const;
const SIM_OBSERVABLES = ["observable", "fit", "uncertainty", "relaxation"] as const;

export function RunDetailView({ agent, runId, refreshKey }: { agent: Agent; runId: string; refreshKey: number }) {
  const client = useClient();
  const state = useLoad(() => client.get<RunDetail>(PATHS.run(agent, runId)), [client, agent, runId, refreshKey]);
  return (
    <>
      {agent === "microscope" && <FollowedRun agent={agent} runId={runId} />}
      <Loaded state={state}>{(d) => <RunBody run={d} />}</Loaded>
    </>
  );
}

/**
 * A run soft-matter-agents executes (its plan.md 11-25): the events it has written so far, its
 * latest frame from its frame tap, and Abort on its own stop channel. Read again every FOLLOW_MS
 * while it runs; nothing is read once it has ended. A run that is not followed says why the
 * console cannot stop it, in words.
 */
export function FollowedRun({
  agent,
  runId,
  abortLabel = ABORT_LABEL,
  note,
}: {
  agent: Agent;
  runId: string;
  /** "Live off" for a live view; the request is the same stop */
  abortLabel?: string;
  /** what the button does, in words, instead of the default text */
  note?: string;
}) {
  const client = useClient();
  const [stream, setStream] = useState<RunStream | null>(null);
  const [events, setEvents] = useState<Record<string, unknown>[]>([]);
  const [readError, setReadError] = useState<string | null>(null);
  const [frameTick, setFrameTick] = useState(0);

  useEffect(() => {
    let live = true;
    let since = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    setStream(null);
    setEvents([]);
    setReadError(null);
    const read = async () => {
      try {
        const s = await client.get<RunStream>(PATHS.runStream(agent, runId, since || undefined));
        if (!live) return;
        since = s.total;
        setStream(s);
        setReadError(null);
        if (s.events.length > 0) setEvents((old) => [...old, ...s.events.filter(isRecord)]);
        setFrameTick((t) => t + 1);
        if (s.state === "running") timer = setTimeout(read, FOLLOW_MS);
      } catch (e: unknown) {
        if (!live) return;
        setReadError(errorText(e));
        timer = setTimeout(read, FOLLOW_MS * 5);
      }
    };
    void read();
    return () => {
      live = false;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [client, agent, runId]);

  if (stream === null) {
    return readError === null ? null : <p className="console-muted">Run events unavailable: {readError}</p>;
  }
  if (!stream.followed) {
    return (
      <section aria-label="Followed run" className="console-followed">
        <p className="console-muted">Abort: {stream.stop_unavailable}</p>
      </section>
    );
  }
  return (
    <section aria-label="Followed run" className="console-followed">
      <header className="console-detail-head">
        <span className="console-status">{stream.state === "running" ? "running" : `ended: ${stream.ended_how ?? "unknown"}`}</span>
        <span className="console-tag">soft-matter-agents run</span>
        {stream.plan_id !== null && <span>{stream.plan_id}</span>}
      </header>
      <AbortRun agent={agent} runId={runId} stream={stream} label={abortLabel} note={note} />
      {readError !== null && <p className="console-muted">Last read failed: {readError}</p>}
      {stream.frame_tap && <TapFrame agent={agent} runId={runId} tick={frameTick} />}
      <Events events={events} label="Run events (events.jsonl)" />
    </section>
  );
}

function AbortRun({
  agent,
  runId,
  stream,
  label,
  note,
}: {
  agent: Agent;
  runId: string;
  stream: RunStream;
  label: string;
  note?: string;
}) {
  const client = useClient();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [refused, setRefused] = useState<string | null>(null);
  const press = async () => {
    setBusy(true);
    setRefused(null);
    try {
      const r = await stopRun(client, agent, runId, reason || (label === ABORT_LABEL ? "" : label));
      setAnswer(r.message);
    } catch (e: unknown) {
      setRefused(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  if (!stream.can_stop) {
    return (
      <div className="console-abort">
        <button type="button" className="console-abort-button" disabled title={stream.stop_unavailable ?? undefined}>
          {label}
        </button>{" "}
        <span className="console-muted">{stream.stop_unavailable}</span>
        {answer !== null && <p className="console-muted">{answer}</p>}
      </div>
    );
  }
  return (
    <div className="console-abort">
      <label>
        Reason{" "}
        <input value={reason} maxLength={300} placeholder="optional" onChange={(e) => setReason(e.target.value)} />
      </label>{" "}
      <button type="button" className="console-abort-button" disabled={busy} onClick={() => void press()}>
        {label}
      </button>{" "}
      <span className="console-muted">
        {note ?? `Sent to the run's own stop channel; the run aborts and records who asked. ${CLOSE_NOTE}`}
      </span>
      {answer !== null && <p role="status">{answer}</p>}
      {refused !== null && <p role="alert" className="console-error">{refused}</p>}
    </div>
  );
}

/** The run's latest frame, a copy its frame tap hands over; the console opens no camera. */
function TapFrame({ agent, runId, tick }: { agent: Agent; runId: string; tick: number }) {
  return (
    <figure className="console-tap">
      <img src={`${PATHS.runFrame(agent, runId)}?t=${tick}`} alt={`Latest frame of ${runId}`} />
      <figcaption className="console-muted">
        Latest frame from the run's own acquisition (display range 0.5–99.5 percentile); blank until it acquires one.
      </figcaption>
    </figure>
  );
}

function RunBody({ run }: { run: RunDetail }) {
  const s = run.summary;
  const rec = (name: string) => (isRecord(run.records[name]) ? (run.records[name] as Record<string, unknown>) : undefined);
  const log = rec("log.json");
  const config = rec("config.json");
  const observables = rec("observables.json");
  return (
    <section aria-label={`Run ${s.run_id}`} className="console-detail">
      <header className="console-detail-head">
        <h2>{s.run_id}</h2>
        <span>{s.agent}</span>
        <span className="console-status">{s.status ?? "—"}</span>
        {s.source !== "soft-matter-agents" && <span className="console-tag">{s.source}</span>}
      </header>
      <Fields obj={{ ...s }} keys={["qid", "plan_id", "backend", "created_at", "finished_at"]} />
      {s.agent === "simulation" && (
        <p>
          <a href={areaHref("simulation", `runs/${s.run_id}`)}>Open in Simulation</a>{" "}
          <span className="console-muted">progress, trajectory, download</span>
        </p>
      )}
      {log !== undefined && <Fields obj={log} keys={LOG_NOTES} />}
      {config !== undefined && <Fields obj={config} keys={SIM_CONFIG} />}
      {observables !== undefined && <Fields obj={observables} keys={SIM_OBSERVABLES} />}
      {log !== undefined && <Events events={asArray(log.events)} />}
      {run.not_opened.length > 0 && <p className="console-muted">Not opened: {run.not_opened.join(", ")}</p>}
      {Object.entries(run.records).map(([name, value]) => <Json key={name} label={name} value={value} />)}
      <p className="console-muted">Files: {run.files.map((f) => f.name).join(", ") || "—"}</p>
    </section>
  );
}

/** The log's events in file order (already time order). */
function Events({ events, label = "Events" }: { events: unknown[]; label?: string }) {
  const rows = events.filter(isRecord);
  if (rows.length === 0) return null;
  return (
    <table className="console-table" aria-label={label}>
      <thead>
        <tr><th>t</th><th>Event</th><th>Fields</th></tr>
      </thead>
      <tbody>
        {rows.map((e, i) => {
          const { event, t_wall, t_mono, ...rest } = e;
          return (
            <tr key={i}>
              <td>{show(t_wall ?? t_mono)}</td>
              <td>{show(event)}</td>
              <td className="console-ellipsis">{show(rest)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
