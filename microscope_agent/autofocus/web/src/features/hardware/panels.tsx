/**
 * Panels of the hardware screen (ui-spec 7.2). They draw what the server and
 * engine report; none of them decides a gate or a permission.
 */

import { useState } from "react";

import type { LightsView } from "../../app/status";
import { EncoderZ } from "../../app/Verdict";
import {
  CHECKING_PERMISSIONS,
  type DeviceRow,
  type GateRow,
  type HardwareProfileOut,
  PERMISSION_CHECK_UNAVAILABLE,
  type Permissions,
  READ_ONLY_REMOTE,
  type StatusResultOut,
  type StatusSummary,
} from "./api";

const NOT_REPORTED = "not reported";

/**
 * Why a button is off, or null. The order is: the shell's read-only flag (remote view), then
 * the permission answer (role, control, session, running op: T-009b / T-011), then this area's
 * feature gate. Every reason is copied from the shell or the server; none is worked out here.
 * `permissions` is null while the first check is loading.
 */
export function blockedBy(
  readOnly: boolean,
  permissions: Permissions | null,
  op: string,
  gate?: GateRow,
): string | null {
  if (readOnly) return READ_ONLY_REMOTE;
  if (permissions === null) return CHECKING_PERMISSIONS;
  const p = permissions[op];
  if (!p) return PERMISSION_CHECK_UNAVAILABLE;
  if (!p.allowed) return p.reason ?? PERMISSION_CHECK_UNAVAILABLE;
  if (gate && !gate.enabled) return `${gate.op} is off: ${gate.reasons?.[0] ?? "no reason given"}`;
  return null;
}

function yesNo(v: boolean | null | undefined, unknown = NOT_REPORTED): string {
  return v === true ? "yes" : v === false ? "no" : unknown;
}

function short(sha: string | null | undefined): string {
  return sha ? sha.slice(0, 12) : NOT_REPORTED;
}

export function Reason({ text }: { text: string | null }) {
  return text ? <span className="hw-reason muted">{text}</span> : null;
}

/** How many changed keys "Since previous" lists before "show all". */
export const CHANGES_SHOWN = 8;

function ChangeList({ keys }: { keys: string[] }) {
  const [all, setAll] = useState(false);
  if (keys.length <= CHANGES_SHOWN) return <>changed: {keys.join(", ")}</>;
  const shown = all ? keys : keys.slice(0, CHANGES_SHOWN);
  return (
    <>
      <span className={all ? "hw-changes hw-changes-all" : "hw-changes"}>
        changed ({keys.length}): {shown.join(", ")}{all ? "" : ", …"}
      </span>{" "}
      <button type="button" className="hw-link" aria-expanded={all} onClick={() => setAll(!all)}>
        {all ? "show fewer" : `show all ${keys.length}`}
      </button>
    </>
  );
}

export function SummaryPanel({ out }: { out: HardwareProfileOut }) {
  const p = out.profile;
  const error = out.error ? <p className="hw-warn">Engine could not read the hardware state: {out.error}</p> : null;
  if (!p) {
    return (
      <section aria-label="Detection summary">
        <h3>Detection summary</h3>
        {error}
        <p className="muted">Not scanned yet. Use "Scan hardware".</p>
      </section>
    );
  }
  const changed = out.previous?.changed ?? [];
  const diff = !out.previous
    ? "no previous profile"
    : changed.length > 0
      ? <ChangeList keys={changed.map((c) => c.key)} />
      : "no changes";
  const configPath = typeof p.config?.path === "string" ? p.config.path : NOT_REPORTED;
  const configSha = typeof p.config?.sha256 === "string" ? p.config.sha256 : null;
  return (
    <section aria-label="Detection summary">
      <h3>Detection summary</h3>
      {error}
      <dl className="hw-dl">
        <dt>Detected</dt><dd>{p.detected_at}</dd>
        <dt>Backend</dt><dd>{p.backend_kind}{p.bench === false ? " (not the bench)" : ""}</dd>
        <dt>Host</dt><dd>{p.host ?? NOT_REPORTED}</dd>
        <dt>Config</dt><dd>{configPath} ({short(configSha)})</dd>
        <dt>Profile</dt><dd>{out.path ?? NOT_REPORTED} ({short(out.sha256)})</dd>
        <dt>Since previous</dt><dd>{diff}</dd>
      </dl>
    </section>
  );
}

function isProblem(d: DeviceRow): boolean {
  return !d.present || d.read_back === false;
}

/** Problem devices first, then by label. */
export function sortDevices(devices: DeviceRow[]): DeviceRow[] {
  return [...devices].sort(
    (a, b) => Number(isProblem(b)) - Number(isProblem(a)) || a.label.localeCompare(b.label),
  );
}

export function DevicesPanel({ devices, selected, onSelect }: {
  devices: DeviceRow[];
  selected: string | null;
  onSelect: (label: string) => void;
}) {
  return (
    <section aria-label="Devices">
      <h3>Devices</h3>
      {devices.length === 0 ? <p className="muted">No devices reported.</p> : (
        <table className="hw-table">
          <thead>
            <tr><th>Device</th><th>Type</th><th>Loaded</th><th>Reads back</th><th>Write verified</th><th>Note</th></tr>
          </thead>
          <tbody>
            {sortDevices(devices).map((d) => (
              <tr key={d.label} data-problem={isProblem(d) ? "true" : undefined}
                  aria-selected={selected === d.label} onClick={() => onSelect(d.label)}>
                <td>{d.label}</td>
                <td>{d.type ?? d.role ?? NOT_REPORTED}</td>
                <td>{yesNo(d.present)}</td>
                <td>{yesNo(d.read_back)}</td>
                <td>{yesNo(d.write_verified, "not tested")}</td>
                <td>{d.note ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

export function ObjectivesPanel({ out }: { out: HardwareProfileOut }) {
  const rows = out.profile?.objectives ?? [];
  return (
    <section aria-label="Objectives">
      <h3>Objectives</h3>
      {rows.length === 0 ? <p className="muted">No objectives reported.</p> : (
        <table className="hw-table">
          <thead>
            <tr><th>Position</th><th>Label</th><th>Mag</th><th>NA</th><th>Immersion</th><th>Working distance</th><th>Pixel</th></tr>
          </thead>
          <tbody>
            {rows.map((o) => (
              <tr key={o.label}>
                <td>{o.state ?? NOT_REPORTED}</td>
                <td>{o.label}</td>
                <td>{o.magnification != null ? `${o.magnification}x` : NOT_REPORTED}</td>
                <td>{o.na ?? NOT_REPORTED}</td>
                <td>{o.immersion ?? NOT_REPORTED}</td>
                <td>{o.working_distance_um != null ? `${o.working_distance_um} µm` : "not set"}</td>
                <td>{o.pixel_um != null ? `${o.pixel_um} µm` : NOT_REPORTED}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

export function CameraPiezoPanel({ out }: { out: HardwareProfileOut }) {
  const c = out.profile?.camera;
  const pz = out.profile?.piezo;
  const piezo = !pz ? NOT_REPORTED
    : pz.error ? `error: ${pz.error}`
    : !pz.port ? "skipped"
    : pz.connected ? `connected on ${pz.port}` : `not connected (${pz.port})`;
  return (
    <section aria-label="Camera and piezo">
      <h3>Camera and piezo</h3>
      <dl className="hw-dl">
        <dt>Camera</dt><dd>{c?.name ?? NOT_REPORTED}</dd>
        <dt>Bit depth</dt>
        <dd>{c?.bit_depth != null ? `${c.bit_depth}-bit (ceiling ${c.ceiling_adu ?? 2 ** c.bit_depth - 1})` : NOT_REPORTED}</dd>
        <dt>Sensor</dt><dd>{c?.sensor ? `${c.sensor[0]} × ${c.sensor[1]}` : NOT_REPORTED}</dd>
        <dt>Piezo</dt><dd>{piezo}</dd>
      </dl>
    </section>
  );
}

export function ConfirmedPanel({ out, blocked, onSave }: {
  out: HardwareProfileOut;
  blocked: string | null;
  onSave: (name: string, value: string) => void;
}) {
  const items = Object.entries(out.profile?.human_confirmed ?? {});
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  return (
    <section aria-label="Human-confirmed items">
      <h3>Human-confirmed items</h3>
      {items.length === 0 ? <p className="muted">None entered.</p> : (
        <table className="hw-table">
          <thead><tr><th>Item</th><th>Value</th><th>By</th><th>At</th></tr></thead>
          <tbody>
            {items.map(([k, v]) => (
              <tr key={k}><td>{k}</td><td>{v.value}</td><td>{v.by ?? ""}</td><td>{v.at ?? ""}</td></tr>
            ))}
          </tbody>
        </table>
      )}
      <form className="hw-row" onSubmit={(e) => {
        e.preventDefault();
        if (name.trim() && value.trim()) onSave(name.trim(), value.trim());
      }}>
        <fieldset disabled={blocked !== null}>
          <input aria-label="Item" placeholder="Item, e.g. DiaLamp intensity" value={name}
                 onChange={(e) => setName(e.target.value)} />
          <input aria-label="Value" placeholder="Value" value={value} onChange={(e) => setValue(e.target.value)} />
          <button type="submit">Save</button>
        </fieldset>
        <Reason text={blocked} />
      </form>
    </section>
  );
}

function needs(g: GateRow): string {
  const r = g.requires;
  return [...(r?.devices ?? []), ...(r?.objectives ?? []), ...(r?.confirmed ?? []), ...(r?.checks ?? [])].join(", ");
}

/** Off rows first, then by op. */
export function sortGates(gates: GateRow[]): GateRow[] {
  return [...gates].sort((a, b) => Number(a.enabled) - Number(b.enabled) || a.op.localeCompare(b.op));
}

export function GatesPanel({ gates, selected, onSelect }: {
  gates: GateRow[];
  selected: string | null;
  onSelect: (op: string) => void;
}) {
  return (
    <section aria-label="Gates">
      <h3>Gates</h3>
      {gates.length === 0 ? <p className="muted">No gate verdict yet.</p> : (
        <table className="hw-table">
          <thead><tr><th>Feature</th><th>State</th><th>Why off</th><th>Needs</th></tr></thead>
          <tbody>
            {sortGates(gates).map((g) => (
              <tr key={g.op} data-off={g.enabled ? undefined : "true"} aria-selected={selected === g.op}
                  onClick={() => onSelect(g.op)}>
                <td>{g.op}</td>
                <td>{g.enabled ? "On" : "Off"}</td>
                <td>{(g.reasons ?? []).length > 0 ? <ul>{(g.reasons ?? []).map((r) => <li key={r}>{r}</li>)}</ul> : ""}</td>
                <td>{needs(g)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function pfsText(v: boolean | string | undefined): string {
  return typeof v === "boolean" ? (v ? "yes" : "no") : (v ?? NOT_REPORTED);
}

export function CurrentStatePanel({ status, zUm, blocked, onRun }: {
  status: StatusResultOut | null;
  zUm: number | null | undefined;
  blocked: string | null;
  onRun: () => void;
}) {
  const s = status?.summary as StatusSummary | undefined;
  return (
    <section aria-label="Current state">
      <h3>Current state</h3>
      <dl className="hw-dl">
        <dt>Objective</dt><dd>{s?.nosepiece_label ?? NOT_REPORTED}</dd>
        <dt>Z</dt><dd><EncoderZ readbackUm={zUm ?? s?.z_um} /></dd>
        <dt>PFS</dt>
        <dd>{s ? `enabled ${pfsText(s.pfs_enabled)}, locked ${pfsText(s.pfs_locked)}, ${s.pfs_in_range ?? NOT_REPORTED}` : NOT_REPORTED}</dd>
        <dt>Read at</dt><dd>{status ? new Date(status.t * 1000).toLocaleTimeString() : "status not run yet"}</dd>
      </dl>
      <button type="button" disabled={blocked !== null} onClick={onRun}>Show objective / Z / PFS</button>
      <Reason text={blocked} />
    </section>
  );
}

/** A readback record in `light_changed.records` (T-002 `Readback`). */
export interface LightRecord {
  device: string;
  property?: string;
  wanted: unknown;
  read: unknown;
  verified: boolean;
}

/**
 * One lamp from the one light shape (server/schemas/state.py `Lights`): DiaLamp
 * `{state, intensity}`, Aura `{state, lines: {LINE: percent}}`.
 */
function lightPart(name: string, on: boolean, raw: unknown): string {
  if (!on) return `${name} OFF`;
  const r = raw && typeof raw === "object" ? (raw as { intensity?: unknown; lines?: unknown }) : {};
  if (r.lines && typeof r.lines === "object") {
    const lines = Object.entries(r.lines as Record<string, unknown>)
      .map(([line, pct]) => `${line} ${typeof pct === "number" ? pct : "?"} %`);
    if (lines.length > 0) return `${name} ${lines.join(", ")}`;
  }
  if (typeof r.intensity === "number") return `${name} ON (${r.intensity})`;
  return `${name} ON`;
}

/**
 * ui-spec 5.2: the read-back, never the requested value. `view` is the shell's reading of
 * `/api/state` and `light_changed` (`src/app/status.ts`); `records` are the last event's
 * readback records, used to say what did not match.
 */
export function lightText(view: LightsView | null, records: LightRecord[] = []): { text: string; warn: boolean } {
  if (!view || view.lights.length === 0) return { text: "Lights: no read-back yet", warn: true };
  if (view.verified === false || view.error || view.lights.some((l) => l.on === null)) {
    const bad = records.filter((r) => !r.verified)
      .map((r) => `${r.device} read ${String(r.read)}, wanted ${String(r.wanted)}`);
    const detail = bad.length > 0 ? bad
      : view.error ? [view.error]
      : view.lights.filter((l) => l.on === null).map((l) => `${l.name} unknown`);
    return { text: `Lights not confirmed${detail.length > 0 ? `: ${detail.join("; ")}` : ""}`, warn: true };
  }
  return { text: view.lights.map((l) => lightPart(l.name, l.on === true, l.raw)).join(" · "), warn: false };
}

export function LightsPanel({ lights, records, lightsT, brightfieldBlocked, auraBlocked, offBlocked, running, onBrightfield, onAura, onOff }: {
  lights: LightsView | null;
  records: LightRecord[];
  lightsT: number | null | undefined;
  /** light_set has one gate row per mode (T-028), so each button has its own reason */
  brightfieldBlocked: string | null;
  auraBlocked: string | null;
  offBlocked: string | null;
  running: string | null;
  onBrightfield: () => void;
  onAura: (line: string, percent: number) => void;
  onOff: () => void;
}) {
  const [line, setLine] = useState("GREEN");
  const [percent, setPercent] = useState(1);
  const { text, warn } = lightText(lights, records);
  return (
    <section aria-label="Lights">
      <h3>Lights</h3>
      <p className={warn ? "hw-warn" : undefined} data-testid="light-state">
        {text}
        {lightsT ? <span className="muted"> (read {new Date(lightsT * 1000).toLocaleTimeString()})</span> : null}
      </p>
      <div className="hw-row" data-testid="light-brightfield">
        <button type="button" disabled={brightfieldBlocked !== null} onClick={onBrightfield}>Brightfield on</button>
        <Reason text={brightfieldBlocked} />
      </div>
      <div className="hw-row" data-testid="light-aura">
        <input aria-label="Aura line" value={line} disabled={auraBlocked !== null}
               onChange={(e) => setLine(e.target.value)} />
        <input aria-label="Aura percent" type="number" min={0} max={100} step={0.1} value={percent}
               disabled={auraBlocked !== null} onChange={(e) => setPercent(Number(e.target.value))} />
        <button type="button" disabled={auraBlocked !== null} onClick={() => onAura(line, percent)}>
          Aura {line} {percent} % on
        </button>
        <Reason text={auraBlocked} />
      </div>
      <div className="hw-row">
        <button type="button" disabled={offBlocked !== null} onClick={onOff}>Lights off</button>
        {running && offBlocked === null ? <span className="muted">stops {running}</span> : null}
        <Reason text={offBlocked} />
      </div>
    </section>
  );
}
