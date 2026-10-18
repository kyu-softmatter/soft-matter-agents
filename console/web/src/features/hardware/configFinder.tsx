/**
 * "Find or make a config": which listed Micro-Manager `.cfg` matches what the last scan loaded
 * (`GET /api/hardware/config/match`), or a new cfg drafted from the scan
 * (`GET /api/hardware/config/draft`). Saving writes a new file in the settings folder
 * (`POST /api/hardware/config/draft`, local operator, never overwrites); it never becomes the
 * active config here. Download keeps it in the browser only. Nothing here reaches the hardware.
 */

import { useState } from "react";

import { CommandRefused, type Client } from "../../app/client";
import {
  type ConfigChoice,
  type ConfigDraftOut,
  type ConfigMatchOut,
  NO_BASE,
  readConfigDraft,
  readConfigMatch,
  READ_ONLY_REMOTE,
  saveConfigDraft,
} from "./api";

const pct = (score: number) => `${Math.round(score * 100)}%`;

function listText(items: string[] | undefined, max = 6): string {
  const xs = items ?? [];
  if (xs.length === 0) return "";
  return xs.length <= max ? xs.join(", ") : `${xs.slice(0, max).join(", ")} … (+${xs.length - max})`;
}

const errText = (e: unknown) => (e instanceof CommandRefused ? e.detail : e instanceof Error ? e.message : String(e));

function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name.endsWith(".cfg") ? name : `${name}.cfg`;
  a.click();
  URL.revokeObjectURL(url);
}

export function ConfigFinderPanel({ client, scanned, readOnly, available, onShow, onSaved }: {
  client: Client;
  scanned: boolean;
  readOnly: boolean;
  available: ConfigChoice[];
  onShow: (path: string) => void;
  onSaved: (path: string) => void;
}) {
  const [match, setMatch] = useState<ConfigMatchOut | null>(null);
  const [draft, setDraft] = useState<ConfigDraftOut | null>(null);
  const [base, setBase] = useState<string>(""); // "" = the best match
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const find = async () => {
    setBusy(true);
    setError(null);
    try {
      setMatch(await readConfigMatch(client));
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const makeDraft = async (b: string) => {
    setBusy(true);
    setError(null);
    setSaved(null);
    try {
      const d = await readConfigDraft(client, b || null);
      setDraft(d);
      setName((n) => n || d.suggested_name);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const out = await saveConfigDraft(client, name, base || null);
      if (out) {
        setSaved(out.path);
        onSaved(out.path);
      }
    } catch (e) {
      setError(`not saved: ${errText(e)}`);
    } finally {
      setBusy(false);
    }
  };

  const off = scanned ? null : "Scan first: both work from the last scan.";
  const rows = match?.rows ?? [];
  const best = rows[0];
  return (
    <section aria-label="Find or make a config">
      <h3>Find or make a config</h3>
      <div className="hw-row">
        <button type="button" disabled={off !== null || busy} onClick={() => void find()}>Find matching config</button>
        <button type="button" disabled={off !== null || busy} onClick={() => void makeDraft(base)}>Draft config from scan</button>
        <span className="muted">{off ?? "Compares or builds from the devices the last scan loaded. Nothing moves."}</span>
      </div>
      {error ? <p className="hw-warn">{error}</p> : null}

      {match ? (
        match.error ? <p className="muted">{match.error}</p> : (
          <>
            <p aria-label="Match verdict">
              {best && best.exact ? <>Exact match: <strong>{best.name}</strong> declares every scanned device and nothing else.</>
                : best && best.score > 0 ? <>No exact match. Closest: <strong>{best.name}</strong> ({pct(best.score)}). A draft from the scan may fit better.</>
                  : "No listed config declares the scanned devices. Draft one from the scan."}
            </p>
            <table className="hw-table" aria-label="Config matches">
              <thead>
                <tr><th>Config</th><th>Match</th><th>Not loaded (in cfg)</th><th>Not in cfg (loaded)</th><th>Different adapter</th><th /></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.path} data-problem={r.exact ? undefined : "true"}>
                    <td>{r.name} <span className="muted">({r.source})</span></td>
                    <td>{pct(r.score)}{r.exact ? " · exact" : ""}</td>
                    <td>{listText(r.missing)}</td>
                    <td>{listText(r.extra)}</td>
                    <td>{listText(r.differs)}</td>
                    <td><button type="button" className="hw-link" onClick={() => onShow(r.path)}>Show</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )
      ) : null}

      {draft ? (
        <div className="hw-draft" aria-label="Config draft">
          <div className="hw-row">
            <label>
              Base for missing details{" "}
              <select aria-label="Draft base" value={base}
                      onChange={(e) => { setBase(e.target.value); void makeDraft(e.target.value); }}>
                <option value="">best match{draft.base && !base ? ` (${draft.base.name})` : ""}</option>
                <option value={NO_BASE}>none: from the scan only</option>
                {available.map((c) => <option key={c.path} value={c.path}>{c.name} ({c.source})</option>)}
              </select>
            </label>
          </div>
          <ul className="hw-draft-notes">
            <li>{draft.devices} devices{draft.base ? `; details the scan did not report from ${draft.base.name}` : "; no base config"}
              {draft.from_base && draft.from_base.length > 0 ? ` (${draft.from_base.length} items)` : ""}</li>
            {draft.load_check
              ? <li className="hw-warn">The bench (mm-real) would refuse to load it: {draft.load_check}</li>
              : <li>The bench (mm-real) load check passes: loading it sets nothing on a motion device.</li>}
            {draft.unknown_adapter && draft.unknown_adapter.length > 0
              ? <li className="hw-warn">Adapter not reported, left commented out: {listText(draft.unknown_adapter)}</li> : null}
            {draft.hub_found && draft.hub_found.length > 0
              ? <li>Reported by a hub but not loaded (commented out): {listText(draft.hub_found)}</li> : null}
            {(draft.warnings ?? []).map((w) => <li key={w} className="muted">{w}</li>)}
          </ul>
          <pre className="hw-draft-text" aria-label="Draft text">{draft.text}</pre>
          <div className="hw-row">
            <input aria-label="File name" value={name} onChange={(e) => setName(e.target.value)} />
            <span className="muted">.cfg</span>
            <button type="button" disabled={readOnly || busy || name.trim() === ""} title={readOnly ? READ_ONLY_REMOTE : undefined}
                    onClick={() => void save()}>Save as new file</button>
            <button type="button" onClick={() => download(name || draft.suggested_name, draft.text)}>Download</button>
          </div>
          {saved ? (
            <p aria-label="Saved">
              Saved to {saved}. It is listed under Config now; the active config is unchanged
              (to use it, set <code>mm_config</code> in settings.json).
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
