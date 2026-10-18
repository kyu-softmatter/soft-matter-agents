/**
 * "Configured hardware": every device the Micro-Manager `.cfg` declares, as a hub tree, with the
 * connection state the last `hardware_scan` found for it. The tree comes from
 * `GET /api/hardware/config` (the server parses the file); the state is the scan's device list
 * joined by label. Nothing here reaches the hardware: "Check connections" is the read-only scan.
 */

import { useMemo, useState } from "react";

import type { ConfigDevice, ConfigTreeOut, DeviceRow, HardwareProfileOut } from "./api";

export type ConnState = "connected" | "loaded" | "read_failed" | "missing" | "unchecked";

export const CONN_TEXT: Record<ConnState, string> = {
  connected: "Connected",
  loaded: "Loaded, no read-back",
  read_failed: "Loaded, read failed",
  missing: "Not loaded",
  unchecked: "Not checked",
};

const LINK_TEXT: Record<string, string> = {
  parent: "Parent line in the config",
  port: "talks through this serial port",
  inferred: "same adapter library as the hub (no Parent line; inferred)",
};

const SOURCE_TEXT: Record<string, string> = {
  scanned: "loaded by the last scan",
  "scanned-copy": "same file as the last scan loaded",
  server: "the config mm-real would load",
  repo: "repository copy",
};

const isProblem = (s: ConnState) => s === "missing" || s === "read_failed";

/** The connection state of one configured device, from the last scan (null = never scanned). */
export function connState(label: string, scanned: Map<string, DeviceRow> | null): ConnState {
  if (scanned === null) return "unchecked";
  const d = scanned.get(label);
  if (!d || !d.present) return "missing";
  if (d.read_back === true) return "connected";
  if (d.read_back === false) return "read_failed";
  return "loaded";
}

interface Node {
  device: ConfigDevice;
  state: ConnState;
  children: Node[];
  problems: number; // problem devices in this subtree, itself excluded
}

const foldable = (n: Node) => n.children.length > 1;

/** Hub tree in config order; a parent the file does not declare puts the device at the top. */
export function buildTree(devices: ConfigDevice[], scanned: Map<string, DeviceRow> | null): Node[] {
  const labels = new Set(devices.map((d) => d.label));
  const kids = new Map<string | null, ConfigDevice[]>();
  for (const d of devices) {
    const p = d.parent && labels.has(d.parent) ? d.parent : null;
    kids.set(p, [...(kids.get(p) ?? []), d]);
  }
  const make = (d: ConfigDevice): Node => {
    const children = (kids.get(d.label) ?? []).map(make);
    const problems = children.reduce((n, c) => n + c.problems + Number(isProblem(c.state)), 0);
    return { device: d, state: connState(d.label, scanned), children, problems };
  };
  return (kids.get(null) ?? []).map(make);
}

function Badge({ state }: { state: ConnState }) {
  return <span className="hw-badge" data-state={state}>{CONN_TEXT[state]}</span>;
}

function Details({ d, scan }: { d: ConfigDevice; scan: DeviceRow | undefined }) {
  const labels = Object.entries(d.state_labels ?? {});
  const pre = Object.entries(d.preinit ?? {});
  return (
    <dl className="hw-dl hw-cfg-details">
      <dt>Adapter</dt><dd>{d.library} / {d.adapter}</dd>
      {d.parent ? <><dt>Depends on</dt><dd>{d.parent} ({LINK_TEXT[d.link ?? ""] ?? d.link})</dd></> : null}
      {d.port ? <><dt>Port</dt><dd>{d.port}</dd></> : null}
      {d.roles && d.roles.length > 0 ? <><dt>Core role</dt><dd>{d.roles.join(", ")}</dd></> : null}
      {scan ? <><dt>Scan</dt><dd>{scan.type ?? "type not reported"}{scan.description ? ` · ${scan.description}` : ""}
        {scan.write_verified === true ? " · write verified" : ""}{scan.note ? ` · ${scan.note}` : ""}</dd></> : null}
      {labels.length > 0 ? <><dt>States</dt><dd>{labels.map(([k, v]) => `${k}: ${v}`).join(" · ")}</dd></> : null}
      {pre.length > 0 ? <><dt>Pre-init</dt><dd>{pre.map(([k, v]) => `${k}=${v}`).join(" · ")}</dd></> : null}
      {d.line ? <><dt>Config line</dt><dd>{d.line}</dd></> : null}
    </dl>
  );
}

function TreeRow({ node, depth, scanned, open, toggle, detail, setDetail, selected, onSelect }: {
  node: Node;
  depth: number;
  scanned: Map<string, DeviceRow> | null;
  open: Set<string>;
  toggle: (label: string) => void;
  detail: string | null;
  setDetail: (label: string | null) => void;
  selected: string | null;
  onSelect: (label: string) => void;
}) {
  const d = node.device;
  const hasKids = node.children.length > 0;
  // a single dependent (COM10 -> CSUW1-Hub, NIDAQHub -> LUNF-Blanking) is always shown, no fold
  const foldable = node.children.length > 1;
  const expanded = !foldable || open.has(d.label);
  const showDetail = detail === d.label;
  return (
    <li className="hw-cfg-node" data-problem={isProblem(node.state) ? "true" : undefined}>
      <div className="hw-cfg-row" style={{ paddingLeft: `${depth * 1.2}rem` }} aria-selected={selected === d.label}>
        {foldable ? (
          <button type="button" className="hw-cfg-toggle" aria-expanded={expanded}
                  aria-label={`${expanded ? "Collapse" : "Expand"} ${d.label}`} onClick={() => toggle(d.label)}>
            {expanded ? "▾" : "▸"}
          </button>
        ) : <span className="hw-cfg-toggle" aria-hidden="true" />}
        <button type="button" className="hw-cfg-label" aria-expanded={showDetail}
                onClick={() => { setDetail(showDetail ? null : d.label); onSelect(d.label); }}>
          {d.label}
        </button>
        <Badge state={node.state} />
        <span className="muted">{d.adapter}{d.roles && d.roles.length > 0 ? ` · ${d.roles.join(", ")}` : ""}</span>
        {foldable ? (
          <span className={node.problems > 0 ? "hw-cfg-rollup hw-warn" : "hw-cfg-rollup muted"}>
            {node.children.length} part{node.children.length === 1 ? "" : "s"}
            {node.problems > 0 ? ` · ${node.problems} with problems` : ""}
          </span>
        ) : null}
        {d.link === "inferred" ? <span className="muted" title={LINK_TEXT.inferred}>(inferred)</span> : null}
      </div>
      {showDetail ? (
        <div style={{ paddingLeft: `${depth * 1.2 + 1.6}rem` }}>
          <Details d={d} scan={scanned?.get(d.label)} />
        </div>
      ) : null}
      {hasKids && expanded ? (
        <ul className="hw-cfg-tree">
          {node.children.map((c) => (
            <TreeRow key={c.device.label} node={c} depth={depth + 1} scanned={scanned} open={open} toggle={toggle}
                     detail={detail} setDetail={setDetail} selected={selected} onSelect={onSelect} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function short(sha: string | null | undefined): string {
  return sha ? sha.slice(0, 12) : "no hash";
}

export function ConfigTreePanel({ tree, profile, loadError, checkBlocked, onCheck, onPick, selected, onSelect }: {
  tree: ConfigTreeOut | null;
  profile: HardwareProfileOut;
  loadError: string | null;
  checkBlocked: string | null;
  onCheck: () => void;
  onPick: (path: string) => void;
  selected: string | null;
  onSelect: (label: string) => void;
}) {
  const p = profile.profile;
  const scanned = useMemo(
    () => (p ? new Map((p.devices ?? []).filter((d) => d.present).map((d) => [d.label, d])) : null),
    [p],
  );
  const devices = useMemo(() => tree?.devices ?? [], [tree]);
  const roots = useMemo(() => buildTree(devices, scanned), [devices, scanned]);
  // hubs with a problem below them start open; the rest start closed
  const [toggled, setToggled] = useState<Set<string>>(new Set());
  const open = useMemo(() => {
    const s = new Set<string>();
    const walk = (n: Node) => {
      const start = n.problems > 0;
      if (start !== toggled.has(n.device.label)) s.add(n.device.label);
      n.children.forEach(walk);
    };
    roots.forEach(walk);
    return s;
  }, [roots, toggled]);
  const toggle = (label: string) =>
    setToggled((t) => { const n = new Set(t); if (n.has(label)) n.delete(label); else n.add(label); return n; });
  const [detail, setDetail] = useState<string | null>(null);

  const counts = devices.reduce<Record<ConnState, number>>(
    (c, d) => ({ ...c, [connState(d.label, scanned)]: c[connState(d.label, scanned)] + 1 }),
    { connected: 0, loaded: 0, read_failed: 0, missing: 0, unchecked: 0 },
  );
  const inCfg = new Set(devices.map((d) => d.label));
  const extra = [...(scanned?.keys() ?? [])].filter((l) => !inCfg.has(l) && l !== "Core").sort();
  const scannedSha = typeof p?.config?.sha256 === "string" ? p.config.sha256 : null;
  const scannedPath = typeof p?.config?.path === "string" ? p.config.path : null;
  const otherConfig = p && tree?.sha256 && scannedSha !== tree.sha256;
  const folds: Node[] = [];
  const collect = (n: Node) => { if (foldable(n)) folds.push(n); n.children.forEach(collect); };
  roots.forEach(collect);
  const allOpen = folds.every((n) => open.has(n.device.label));
  const setAll = (wantOpen: boolean) => {
    const t = new Set<string>();
    const walk = (n: Node) => {
      if (foldable(n) && (n.problems > 0) !== wantOpen) t.add(n.device.label);
      n.children.forEach(walk);
    };
    roots.forEach(walk);
    setToggled(t);
  };

  return (
    <section aria-label="Configured hardware">
      <h3>Configured hardware</h3>
      {loadError ? <p className="hw-warn">Could not read the config: {loadError}</p> : null}
      {tree?.error ? <p className="hw-warn">{tree.error}</p> : null}
      <div className="hw-row">
        <label>
          Config{" "}
          <select aria-label="Config file" value={tree?.path ?? ""} disabled={(tree?.available ?? []).length < 2}
                  onChange={(e) => onPick(e.target.value)}>
            {(tree?.available ?? []).map((c) => (
              <option key={c.path} value={c.path}>{c.name} ({SOURCE_TEXT[c.source] ?? c.source})</option>
            ))}
            {tree && !tree.path ? <option value="">no config found</option> : null}
          </select>
        </label>
        {/* why it is off is already written next to "Scan hardware" above; here only on hover */}
        <button type="button" disabled={checkBlocked !== null} title={checkBlocked ?? undefined} onClick={onCheck}>
          Check connections
        </button>
        <span className="muted">Runs the read-only hardware scan. Nothing moves or turns on.</span>
      </div>
      {tree?.path ? <p className="muted hw-cfg-path">{tree.path} ({short(tree.sha256)})</p> : null}
      {!p ? <p className="muted">Not checked yet: the states below fill in after "Check connections".</p> : null}
      {otherConfig ? (
        <p className="hw-warn">
          The last scan loaded a different config ({scannedPath ?? "path not reported"}, {short(scannedSha)}).
          States below compare this file with that scan.
        </p>
      ) : null}
      {devices.length > 0 ? (
        <>
          <p aria-label="Connection summary">
            {devices.length} devices
            {p ? ` · ${counts.connected} connected` : ""}
            {counts.loaded > 0 ? ` · ${counts.loaded} loaded without read-back` : ""}
            {counts.read_failed > 0 ? ` · ${counts.read_failed} read failed` : ""}
            {counts.missing > 0 ? ` · ${counts.missing} not loaded` : ""}
            {p ? ` · checked ${p.detected_at}` : ""}
            {folds.length > 0 ? (
              <>
                {" "}
                <button type="button" className="hw-link" onClick={() => setAll(!allOpen)}>
                  {allOpen ? "Collapse all" : "Expand all"}
                </button>
              </>
            ) : null}
          </p>
          <ul className="hw-cfg-tree" aria-label="Config devices">
            {roots.map((n) => (
              <TreeRow key={n.device.label} node={n} depth={0} scanned={scanned} open={open} toggle={toggle}
                       detail={detail} setDetail={setDetail} selected={selected} onSelect={onSelect} />
            ))}
          </ul>
        </>
      ) : tree && !tree.error ? <p className="muted">The config declares no devices.</p> : null}
      {extra.length > 0 ? (
        <p className="muted">Loaded in the scan but not in this config: {extra.join(", ")}</p>
      ) : null}
      {(tree?.warnings ?? []).length > 0 ? (
        <ul className="hw-reason muted">{tree?.warnings?.map((w) => <li key={w}>{w}</li>)}</ul>
      ) : null}
    </section>
  );
}
