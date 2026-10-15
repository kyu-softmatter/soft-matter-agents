// The `sessions` area: experiment sessions (PLAN F7), contract docs/screens/sessions.md.
//
// Route rest forms:  ""  the list;  "<session_id>"  the list with that session's detail.
// Data goes through the shell's shared client (useClient, useReadOnly, useEventsConnected);
// the /api/sessions shapes are temporary in api.ts until gen:api.
// Disabled actions stay visible with their reason next to them (ui-spec 7.0).

import { useCallback, useEffect, useMemo, useState } from "react";

import { CommandRefused, useClient, useEventsConnected, useReadOnly } from "../../app/client";
import { useAreaPath } from "../../app/route";
import { useScreenContext } from "../../app/screenContext";
import { placeholderNotice } from "../../app/unavailable";
import {
  blockedBy,
  PATHS,
  type Permissions,
  readCurrentSample,
  readPermissions,
  SESSION_OPS,
  type SessionDetail,
  type SessionFilter,
  type SessionStatus,
  type SessionSummary,
} from "./api";

function errorText(e: unknown): string {
  if (e instanceof CommandRefused) return e.detail;
  return e instanceof Error ? e.message : String(e);
}

function Reason({ text }: { text: string | null }) {
  return text ? <span className="reason" role="note">{text}</span> : null;
}

function yesNo(v: boolean | null | undefined): string {
  return v === null || v === undefined ? "unknown" : v ? "yes" : "no";
}

function shortHash(h: string | null | undefined): string {
  return h ? h.slice(0, 12) : "none";
}

export default function SessionsScreen() {
  const client = useClient();
  const { readOnly } = useReadOnly();
  const connected = useEventsConnected();
  const [rest, setRest] = useAreaPath();
  const selectedId = rest.split("?")[0] || null;

  const [filter, setFilter] = useState<SessionFilter>({});
  const [list, setList] = useState<SessionSummary[]>([]);
  const [current, setCurrent] = useState<SessionSummary | null>(null);
  const [sample, setSample] = useState<string | null>(null);
  // null until the first answer; readPermissions turns an unreadable check into "unavailable" for all
  const [perms, setPerms] = useState<Permissions | null>(null);
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  // the placeholder engine has no records store: one notice instead of the 503 (app/unavailable)
  const [unavailable, setUnavailable] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0); // bump to reload

  useEffect(() => {
    let live = true;
    // permissions load on their own: if they fail, the list and detail stay available
    readPermissions(client, SESSION_OPS).then((p) => live && setPerms(p));
    Promise.all([
      client.get<SessionSummary[]>(PATHS.list(filter)),
      client.get<SessionSummary | null>(PATHS.current),
      readCurrentSample(client),
    ])
      .then(([l, c, s]) => {
        if (!live) return;
        setList(l);
        setCurrent(c);
        setSample(s);
      })
      .catch((e) => {
        if (!live) return;
        const notice = placeholderNotice(e);
        if (notice !== null) setUnavailable(notice);
        else setError(errorText(e));
      });
    return () => {
      live = false;
    };
    // `connected`: re-read after the event socket comes back (events in the gap are lost).
    // A session_changed event (T-011, G2) will bump `version` once it is in the event kinds.
  }, [client, filter, version, connected]);

  useEffect(() => {
    let live = true;
    if (!selectedId) {
      setDetail(null);
      return;
    }
    client
      .get<SessionDetail>(PATHS.detail(selectedId))
      .then((d) => live && setDetail(d))
      .catch((e) => {
        if (!live) return;
        setDetail(null);
        setError(errorText(e));
      });
    return () => {
      live = false;
    };
  }, [client, selectedId, version]);

  const ctx = useMemo(
    () => ({
      ...(selectedId ? { session_id: selectedId } : {}),
      ...((detail?.sample_id ?? current?.sample_id) ? { sample_id: detail?.sample_id ?? current?.sample_id } : {}),
    }),
    [selectedId, detail?.sample_id, current?.sample_id],
  );
  useScreenContext(ctx);

  const act = useCallback(
    async (run: () => Promise<SessionDetail | null>) => {
      setBusy(true);
      setError(null);
      try {
        const d = await run();
        setNote("");
        if (d) setRest(d.session_id);
        setVersion((v) => v + 1);
      } catch (e) {
        setError(errorText(e));
      } finally {
        setBusy(false);
      }
    },
    [setRest],
  );

  // shared reasons first (role, control, remote: GET /api/permissions), then this area's own
  const denied = (op: string): string | null => blockedBy(readOnly, perms, op);
  const openReason =
    denied("session_open") ??
    (current ? `${current.session_id} is open; close it first` : null) ??
    (sample ? null : "Open or create a sample first");
  const closeReason = !detail
    ? null
    : denied("session_close") ??
      (detail.status === "closed" ? `Session ${detail.session_id} is closed (read-only)` : null);
  const continueReason = !detail
    ? null
    : denied("session_continue") ??
      (detail.status === "open" ? "Close this session first" : null) ??
      (current ? `${current.session_id} is open; close it first` : null);

  if (unavailable !== null) {
    return (
      <section aria-label="Experiment sessions">
        <h2>Experiment sessions</h2>
        <p className="muted" role="status">
          {unavailable}
        </p>
      </section>
    );
  }

  return (
    <section aria-label="Experiment sessions">
      <h2>Experiment sessions</h2>

      <p data-testid="current">
        {current ? `Open: ${current.session_id} · ${current.sample_id}` : "No experiment session"}
      </p>
      <div>
        <button disabled={busy || !!openReason} onClick={() => act(() => client.post<SessionDetail>(PATHS.open))}>
          {sample ? `Open experiment session for ${sample}` : "Open experiment session"}
        </button>{" "}
        <Reason text={openReason} />
      </div>

      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}

      <fieldset>
        <legend>Filter</legend>
        <label>
          User{" "}
          <input value={filter.user ?? ""} onChange={(e) => setFilter({ ...filter, user: e.target.value || undefined })} />
        </label>{" "}
        <label>
          Sample{" "}
          <input value={filter.sample ?? ""} onChange={(e) => setFilter({ ...filter, sample: e.target.value || undefined })} />
        </label>{" "}
        <label>
          Status{" "}
          <select
            value={filter.status ?? ""}
            onChange={(e) => setFilter({ ...filter, status: (e.target.value || undefined) as SessionStatus | undefined })}
          >
            <option value="">any</option>
            <option value="open">open</option>
            <option value="closed">closed</option>
          </select>
        </label>
      </fieldset>

      <table aria-label="Sessions">
        <thead>
          <tr>
            <th>Session</th>
            <th>User</th>
            <th>Sample</th>
            <th>Status</th>
            <th>Started</th>
            <th>Closed</th>
            <th>Continues</th>
            <th>Reflected</th>
          </tr>
        </thead>
        <tbody>
          {list.map((s) => (
            <tr key={s.session_id} aria-selected={s.session_id === selectedId}>
              <td>
                <button className="link" onClick={() => setRest(s.session_id)}>
                  {s.session_id}
                </button>
              </td>
              <td>{s.user_name || s.user_id}</td>
              <td>{s.sample_id}</td>
              <td>{s.status}</td>
              <td>{s.started_at}</td>
              <td>{s.closed_at ?? ""}</td>
              <td>{s.continues ?? ""}</td>
              <td>{yesNo(s.reflected)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {list.length === 0 && <p>No experiment sessions match.</p>}

      {detail && (
        <article aria-label="Session detail">
          <h3>{detail.session_id}</h3>
          <dl>
            <dt>User</dt>
            <dd>{detail.user_name ? `${detail.user_name} (${detail.user_id})` : detail.user_id}</dd>
            <dt>Sample</dt>
            <dd>{detail.sample_id}</dd>
            <dt>Status</dt>
            <dd>{detail.status}</dd>
            <dt>Started</dt>
            <dd>{detail.started_at}</dd>
            <dt>Closed</dt>
            <dd>{detail.closed_at ?? "still open"}</dd>
            <dt>Code commit (as recorded)</dt>
            <dd>
              <code title={detail.code.commit ?? ""}>{shortHash(detail.code.commit)}</code>
              {detail.code.dirty ? " · uncommitted changes" : detail.code.dirty === null ? " · unknown" : ""}
              {detail.code.error ? ` (${detail.code.error})` : ""}
            </dd>
            <dt>Hardware profile sha256 (as recorded)</dt>
            <dd>
              <code title={detail.hardware_profile?.sha256 ?? ""}>{shortHash(detail.hardware_profile?.sha256)}</code>
            </dd>
            <dt>Continues</dt>
            <dd>{detail.continues ?? "none"}</dd>
            <dt>Reflected by the librarian</dt>
            <dd>{yesNo(detail.reflected)}</dd>
            {detail.close_note && (
              <>
                <dt>Close note</dt>
                <dd>{detail.close_note}</dd>
              </>
            )}
          </dl>

          <h4>Records</h4>
          <ul>
            {detail.records.map((r) => (
              <li key={r.name}>
                {r.name}: {r.lines} lines
              </li>
            ))}
          </ul>

          <h4>Files</h4>
          <p>
            {detail.manifest.files} files, {detail.manifest.bytes} bytes
            {Object.entries(detail.manifest.by_where).map(([w, k]) => ` · ${w}: ${k}`)}
          </p>

          <h4>Log (latest)</h4>
          <ol>
            {detail.log_tail.map((l, i) => (
              <li key={i}>
                {l.t} {l.level} {l.msg}
              </li>
            ))}
          </ol>

          <div>
            <label>
              Note <input value={note} onChange={(e) => setNote(e.target.value)} disabled={!!closeReason} />
            </label>{" "}
            <button disabled={busy || !!closeReason} onClick={() => act(() => client.post<SessionDetail>(PATHS.close(detail.session_id), { note }))}>
              Close
            </button>{" "}
            <Reason text={closeReason} />
          </div>
          <div>
            <button disabled={busy || !!continueReason} onClick={() => act(() => client.post<SessionDetail>(PATHS.continueFrom(detail.session_id)))}>
              Continue with this sample
            </button>{" "}
            <Reason text={continueReason} />
          </div>
        </article>
      )}
    </section>
  );
}
