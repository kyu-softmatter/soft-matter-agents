/**
 * `hardware` area (PLAN F2, ui-spec 7.2, contract docs/screens/hardware.md).
 * Shows the last detection, the gate verdict and the light read-back. Talks to the
 * server only through the shell's client; refusals are drawn, not decided, here.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import { type CommandIn, CommandRefused, type EventOut, useClient, useEngineEvents, useEventsConnected, useReadOnly } from "../../app/client";
import { useScreenContext } from "../../app/screenContext";
import { useEngineStatus } from "../../app/status";
import {
  type ConfigTreeOut,
  type GateRow,
  type HardwareProfileOut,
  type Permissions,
  readConfig,
  readGates,
  readPermissions,
  readProfile,
  lightGateKey,
  readStatus,
  SCREEN_OPS,
  type StatusResultOut,
} from "./api";
import {
  blockedBy,
  CameraPiezoPanel,
  ConfirmedPanel,
  CurrentStatePanel,
  DevicesPanel,
  GatesPanel,
  type LightRecord,
  LightsPanel,
  ObjectivesPanel,
  Reason,
  SummaryPanel,
} from "./panels";
import { ConfigFinderPanel } from "./configFinder";
import { ConfigTreePanel } from "./configTree";
import "./hardware.css";

type NoticeKey = "scan" | "confirm" | "status" | "lights";

const NOTICE_OF_OP: Record<string, NoticeKey> = {
  hardware_scan: "scan",
  hardware_confirm: "confirm",
  status: "status",
  light_set: "lights",
};

/** After these the engine's answer to "may I" can change: re-read permissions. */
const LIFECYCLE = new Set(["started", "finished", "aborted", "error", "preflight_failed", "refused"]);

const EMPTY_PROFILE: HardwareProfileOut = { profile: null, path: null, sha256: null };

function failureText(ev: EventOut): string {
  const d = ev.data ?? {};
  if (ev.kind === "error") return `error: ${String(d.message ?? "unknown")}`;
  const checks = Array.isArray(d.checks) ? (d.checks as { ok?: boolean; why?: string; name?: string }[]) : [];
  const why = checks.filter((c) => c.ok === false).map((c) => c.why ?? c.name ?? "check failed");
  return `preflight failed: ${why.length > 0 ? why.join("; ") : String(d.why ?? "no reason given")}`;
}

export default function HardwareScreen() {
  const client = useClient();
  const { readOnly } = useReadOnly();
  const connected = useEventsConnected();
  const engine = useEngineStatus(); // positions, lights and running ops, as the status bar reads them
  const [profile, setProfile] = useState<HardwareProfileOut>(EMPTY_PROFILE);
  const [gates, setGates] = useState<GateRow[]>([]);
  const [status, setStatus] = useState<StatusResultOut | null>(null);
  const [permissions, setPermissions] = useState<Permissions | null>(null); // null = first check loading
  const [lightEvent, setLightEvent] = useState<{ records: LightRecord[]; t: number | null }>({ records: [], t: null });
  const [notices, setNotices] = useState<Partial<Record<NoticeKey, string>>>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [device, setDevice] = useState<string | null>(null);
  const [gate, setGate] = useState<string | null>(null);
  const [includeProperties, setIncludeProperties] = useState(true);
  const [piezoPort, setPiezoPort] = useState(""); // "" skips the piezo (contract G10)
  const [cfgTree, setCfgTree] = useState<ConfigTreeOut | null>(null);
  const [cfgPath, setCfgPath] = useState<string | null>(null); // null = the server's first choice
  const [cfgError, setCfgError] = useState<string | null>(null);

  const reloadProfile = useCallback(async () => {
    try {
      const [p, g] = await Promise.all([readProfile(client), readGates(client)]);
      setProfile(p);
      setGates(g);
      setLoadError(null);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
    }
  }, [client]);

  const reloadConfig = useCallback(async () => {
    try {
      setCfgTree(await readConfig(client, cfgPath));
      setCfgError(null);
    } catch (e) {
      setCfgError(e instanceof Error ? e.message : String(e));
    }
  }, [client, cfgPath]);

  const reloadStatus = useCallback(async () => {
    try {
      setStatus(await readStatus(client));
    } catch {
      // keep what we had; the panel says "status not run yet" if nothing
    }
  }, [client]);

  const reloadPermissions = useCallback(async () => {
    setPermissions(await readPermissions(client, SCREEN_OPS));
  }, [client]);

  // first load, and again after every (re)connect: events in a gap are lost
  useEffect(() => {
    void reloadProfile();
    void reloadStatus();
    void reloadPermissions();
  }, [reloadProfile, reloadStatus, reloadPermissions, connected]);

  useEffect(() => {
    void reloadConfig();
  }, [reloadConfig, connected]);

  const onEvent = useCallback(
    (ev: EventOut) => {
      const data = ev.data ?? {};
      const op = typeof data.op === "string" ? data.op : "";
      if (ev.kind === "light_changed") {
        setLightEvent({ records: Array.isArray(data.records) ? (data.records as LightRecord[]) : [], t: ev.t });
        return;
      }
      if (!LIFECYCLE.has(ev.kind)) return;
      void reloadPermissions();
      if (ev.kind === "finished" && op === "status") {
        setStatus({ op_id: ev.op_id ?? "", t: ev.t, user_id: null, summary: (data.summary ?? {}) as StatusResultOut["summary"] });
      }
      const key = NOTICE_OF_OP[op];
      if (key && ev.kind !== "started") {
        const text = ev.kind === "aborted" ? `stopped: ${String(data.why ?? "")}`
          : ev.kind === "error" || ev.kind === "preflight_failed" ? failureText(ev)
          : undefined;
        setNotices((n) => ({ ...n, [key]: text }));
      }
      if (op === "hardware_scan" || op === "hardware_confirm") void reloadProfile();
      // a scan may load another cfg, which then becomes the server's first choice
      if (op === "hardware_scan" && ev.kind === "finished") void reloadConfig();
    },
    [reloadPermissions, reloadProfile, reloadConfig],
  );
  useEngineEvents(onEvent);

  const details = useMemo(() => {
    const d: Record<string, unknown> = {};
    if (device) d.device = device;
    if (gate) {
      d.gate = gate;
      d.gate_reasons = gates.find((g) => g.op === gate)?.reasons ?? [];
    }
    return d;
  }, [device, gate, gates]);
  useScreenContext(details);

  const send = useCallback(
    async (key: NoticeKey, cmd: CommandIn) => {
      setNotices((n) => ({ ...n, [key]: undefined }));
      try {
        await client.command(cmd);
      } catch (e) {
        const detail = e instanceof CommandRefused ? e.detail : String(e);
        setNotices((n) => ({ ...n, [key]: `refused: ${detail}` }));
      }
    },
    [client],
  );

  // the permission is per op; the gate row may be per argument (light_set:aura, T-028)
  const blocked = (op: string, gateKey = op) =>
    blockedBy(readOnly, permissions, op, gates.find((g) => g.op === gateKey));
  const runningOp = engine.running[0]?.op || null;
  const scanBlocked = blocked("hardware_scan");
  const confirmBlocked = blocked("hardware_confirm");
  const statusBlocked = blocked("status");
  const brightfieldBlocked = blocked("light_set", lightGateKey("brightfield"));
  const auraBlocked = blocked("light_set", lightGateKey("aura"));
  const offBlocked = blockedBy(readOnly, permissions, "lights_off");
  const start = (op: string, args: Record<string, unknown> = {}): CommandIn =>
    ({ kind: "start", op, op_id: "", args });
  const runScan = () => send("scan", start("hardware_scan", { include_properties: includeProperties, piezo_port: piezoPort }));

  return (
    <div className="hw-screen">
      <h2>Hardware</h2>
      {loadError ? <p className="hw-warn">Could not load the hardware profile: {loadError}</p> : null}

      <section aria-label="Scan">
        <div className="hw-row">
          <button type="button" disabled={scanBlocked !== null}
                  onClick={runScan}>
            Scan hardware
          </button>
          <label>
            <input type="checkbox" checked={includeProperties} disabled={scanBlocked !== null}
                   onChange={(e) => setIncludeProperties(e.target.checked)} /> all properties
          </label>
          <input aria-label="Piezo port" placeholder="piezo port (empty = skip)" value={piezoPort}
                 disabled={scanBlocked !== null} onChange={(e) => setPiezoPort(e.target.value)} />
          <span className="muted">Reads only. Nothing moves or turns on.</span>
          <Reason text={scanBlocked} />
        </div>
        <Reason text={notices.scan ?? null} />
      </section>

      <ConfigTreePanel tree={cfgTree} profile={profile} loadError={cfgError} checkBlocked={scanBlocked}
                       onCheck={runScan} onPick={setCfgPath} selected={device} onSelect={setDevice} />
      <ConfigFinderPanel client={client} scanned={profile.profile !== null} readOnly={readOnly}
                         available={cfgTree?.available ?? []} onShow={setCfgPath} onSaved={setCfgPath} />

      <div className="hw-grid">
        <SummaryPanel out={profile} />
        <CurrentStatePanel status={status} zUm={engine.positions?.z_um} blocked={statusBlocked}
                           onRun={() => send("status", start("status"))} />
        <LightsPanel lights={engine.lights} records={lightEvent.records} lightsT={lightEvent.t}
                     brightfieldBlocked={brightfieldBlocked} auraBlocked={auraBlocked} offBlocked={offBlocked} running={runningOp}
                     onBrightfield={() => send("lights", start("light_set", { mode: "brightfield" }))}
                     onAura={(line, percent) => send("lights", start("light_set", { mode: "aura", line, percent }))}
                     onOff={() => send("lights", { kind: "lights_off", op: "", op_id: "" })} />
        <CameraPiezoPanel out={profile} />
      </div>
      <Reason text={notices.status ?? notices.lights ?? null} />

      <GatesPanel gates={gates} selected={gate} onSelect={setGate} />
      <DevicesPanel devices={profile.profile?.devices ?? []} selected={device} onSelect={setDevice} />
      <ObjectivesPanel out={profile} />
      <ConfirmedPanel out={profile} blocked={confirmBlocked}
                      onSave={(name, value) => send("confirm", start("hardware_confirm", { items: { [name]: value } }))} />
      <Reason text={notices.confirm ?? null} />
    </div>
  );
}
