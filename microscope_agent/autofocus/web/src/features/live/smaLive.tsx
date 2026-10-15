/**
 * Live view on the microscope through soft-matter-agents (its card 062; the person's decision of
 * 2026-10-07): switch on a live-view list the person approved, see its frames, switch it off.
 * "Live on" names the list by its sha256 and nothing else; the host checks the list and runs it
 * as an ordinary run. "Live off" is that run's own stop. The console opens no camera itself.
 */

import { useEffect, useState } from "react";

import { useClient } from "../../app/client";
import {
  fetchPermissions,
  type LiveList,
  type LiveOnResult,
  type LiveState,
  PATHS,
  type Permission,
} from "../console/api";
import { FollowedRun } from "../console/runs";
import { errorText } from "../console/ui";

export const LIVE_ON = "Live on";
export const LIVE_OFF = "Live off";
export const LIVE_OP = "live_on";
/** What "Live off" does, in words (agreed with the microscope seat, card 062). */
export const LIVE_OFF_NOTE =
  "Live off stops the run (lamp off, shutters closed). Closing this page does not stop it; " +
  "it ends by itself at the frame ceiling.";

function rec(v: unknown): Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

/**
 * The values the person wrote in a list (soft-matter-agents live_view_list.schema.json, 48242a2),
 * for the picker: label, lamp intensity, camera, exposure, frame ceiling, and whether it adds
 * fluorescence excitation (a separate approval on that side). A missing value shows as "—".
 */
export function listSummary(l: LiveList): string {
  const d = rec(l.data);
  const lamp = rec(d.transmitted_lamp);
  const cam = rec(d.camera);
  const show = (v: unknown) => (v === undefined || v === null ? "—" : String(v));
  const parts = [
    show(d.label),
    `${show(lamp.device ?? "lamp")} intensity ${show(rec(lamp.intensity).value)}`,
    `${show(cam.device ?? "camera")} exposure ${show(cam.exposure_ms)} ms`,
    `frame ceiling ${show(cam.frame_ceiling)}`,
  ];
  if (d.excitation !== undefined) parts.push("adds fluorescence excitation");
  return parts.join(" · ");
}

export function SmaLiveSwitch() {
  const client = useClient();
  const [state, setState] = useState<LiveState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [perm, setPerm] = useState<Permission | null>(null);
  const [pick, setPick] = useState("");
  const [busy, setBusy] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [refused, setRefused] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let live = true;
    client.get<LiveState>(PATHS.live).then(
      (s) => {
        if (!live) return;
        setState(s);
        setLoadError(null);
        setPick((p) => (p !== "" && s.lists.some((l) => l.sha256 === p) ? p : (s.lists[0]?.sha256 ?? "")));
      },
      (e: unknown) => live && setLoadError(errorText(e)),
    );
    fetchPermissions(client, [LIVE_OP]).then(
      (p) => live && setPerm(p[LIVE_OP]),
      () => live && setPerm({ allowed: false, reason: "Permission check unavailable" }),
    );
    return () => {
      live = false;
    };
  }, [client, tick]);

  const press = async () => {
    setBusy(true);
    setRefused(null);
    try {
      const r = await client.post<LiveOnResult>(PATHS.liveOn, { sha256: pick });
      if (r?.outcome === "started" && r.run_id) setRunId(r.run_id);
      else setRefused(r?.reason ?? "the live-view host refused without a reason");
    } catch (e: unknown) {
      setRefused(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  if (loadError !== null) {
    return <p className="muted">Microscope live view (soft-matter-agents): unavailable: {loadError}</p>;
  }
  if (state === null) return null;
  const why = !state.available ? state.why_not : perm !== null && !perm.allowed ? perm.reason : null;
  return (
    <section aria-label="Microscope live view" className="console-followed">
      <div className="patterns-bar">
        <strong>Microscope live view</strong>
        <label>
          List{" "}
          <select aria-label="Live-view list" value={pick} onChange={(e) => setPick(e.target.value)}>
            {state.lists.map((l) => (
              <option key={l.sha256} value={l.sha256}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" disabled={busy || why !== null || pick === "" || perm === null} onClick={() => void press()}>
          {LIVE_ON}
        </button>
        <button type="button" onClick={() => setTick((t) => t + 1)}>Refresh</button>
        {why !== null && <span className="muted">{why}</span>}
      </div>
      {state.lists
        .filter((l) => l.sha256 === pick)
        .map((l) => (
          <p key={l.sha256} className="muted">
            Approved list: {listSummary(l)} · sha256 {l.sha256.slice(0, 12)}…
          </p>
        ))}
      {refused !== null && (
        <p role="alert" className="warn">
          Live on refused: {refused}
        </p>
      )}
      {runId !== null && (
        <>
          <FollowedRun agent="microscope" runId={runId} abortLabel={LIVE_OFF} note={LIVE_OFF_NOTE} />
          <button type="button" onClick={() => setRunId(null)}>Hide this run</button>
        </>
      )}
    </section>
  );
}
