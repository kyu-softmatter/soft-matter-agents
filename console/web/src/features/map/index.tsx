/**
 * The `map` area: sample map (PLAN F4). Contract: docs/screens/map.md. Wording: ui-spec 5.1, 7.4.
 * The screen shows what the engine decided; it never decides safety itself, never raises Z after
 * a click-move, and never puts the mosaic into the prompt context (D7).
 */

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";

import { areaHref, useAreaPath } from "../../app/route";
import { useScreenContext } from "../../app/screenContext";
import {
  type CommandInput,
  CommandRefused,
  type EventOut,
  useClient,
  useEngineEvents,
  useEventsConnected,
  useReadOnly,
} from "../../app/client";
import { EncoderZ } from "../../app/Verdict";
import {
  mapRoutes,
  readSnapshot,
  type Candidate,
  type Flag,
  type MapState,
  type Permissions,
  type ResultDetail,
  type ResultSummary,
} from "./api";
import { IDLE, clickMoveReducer, clickMoveText, type ClickMove, type EngineEvent } from "./clickMove";
import {
  clock,
  diameterOff,
  distanceUm,
  fieldOfViewUm,
  fitView,
  holeFitStatus,
  inBox,
  isRetired,
  mapExtent,
  visibleCandidates,
  visibleFlags,
} from "./geometry";
import { MapCanvas } from "./MapCanvas";
import { ALL_LAYERS_ON, buildScene, LAYER_LABEL, LAYERS, type LayerSet } from "./scene";
import "./map.css";

/** every op this screen can send; their pre-click reasons come from GET /api/permissions */
const MAP_OPS = [
  "edge_trace", "boundary_mark", "boundary_undo", "boundary_reset", "scan_4x", "sample_map",
  "goto_xy", "map_flag", "map_flag_retire", "candidate_confirm", "candidate_reject",
] as const;
type MapOp = (typeof MAP_OPS)[number];
/** one fallback for every screen: no answer from /api/permissions disables the controls */
const PERMISSION_UNAVAILABLE = "Permission check unavailable";
/** events after which the shared permission answer may have changed */
const RECHECK_ON = new Set(["started", "finished", "aborted", "error", "sample_opened", "confirm_required"]);
const SPEED_MIN = 10;
const SPEED_MAX = 1000;

type Control = "trace" | "scan" | "boundary" | "flag" | "candidate";

interface OpInfo {
  control: Control | "goto";
  op: string;
}

interface TraceProgress {
  status: string | null;
  path_um: number | null;
  n_points: number | null;
}

interface ScanProgress {
  tile: number | null;
  n_tiles: number | null;
  dropped: number | null;
}

interface PendingConfirm {
  op_id: string;
  key: string;
  text: string;
}

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const str = (v: unknown): string | null => (typeof v === "string" ? v : null);
const fmt = (v: number | null | undefined, d = 0) => (v == null ? "—" : v.toFixed(d));

function why(e: unknown): string {
  if (e instanceof CommandRefused) return e.detail;
  return e instanceof Error ? e.message : String(e);
}

function sampleFromRest(rest: string): string | null {
  const q = rest.includes("?") ? rest.slice(rest.indexOf("?") + 1) : "";
  const id = new URLSearchParams(q).get("sample_id");
  return id && id.trim() !== "" ? id : null;
}


const WIDTH = 640;
const HEIGHT = 640;

export default function MapScreen() {
  const width = WIDTH;
  const height = HEIGHT;
  const client = useClient();
  const api = useMemo(() => mapRoutes(client), [client]);
  const { readOnly, why: readOnlyWhy } = useReadOnly();
  const connected = useEventsConnected();
  const [rest] = useAreaPath();
  const pinnedSample = sampleFromRest(rest);
  const [openSample, setOpenSample] = useState<string | null>(null);
  const sampleId = pinnedSample ?? openSample;

  const [perms, setPerms] = useState<Permissions | null>(null);
  const [pos, setPos] = useState<{ x: number | null; y: number | null; z: number | null }>({ x: null, y: null, z: null });
  const [objective, setObjective] = useState<string | null>(null);

  const [mapState, setMapState] = useState<MapState | null>(null);
  const [results, setResults] = useState<ResultSummary[]>([]);
  const [resultId, setResultId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ResultDetail | null>(null);
  const [flags, setFlags] = useState<Flag[]>([]);
  const [cands, setCands] = useState<Candidate[]>([]);
  const [showRetired, setShowRetired] = useState(false);
  const [showRejected, setShowRejected] = useState(false);
  const [layers, setLayers] = useState<LayerSet>(ALL_LAYERS_ON);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [hover, setHover] = useState<[number, number] | null>(null);
  const [move, dispatch] = useReducer(clickMoveReducer, IDLE);

  const [active, setActive] = useState<Partial<Record<Control, string>>>({});
  const [refusal, setRefusal] = useState<Partial<Record<Control, string>>>({});
  const [trace, setTrace] = useState<TraceProgress>({ status: null, path_um: null, n_points: null });
  const [scan, setScan] = useState<ScanProgress>({ tile: null, n_tiles: null, dropped: null });
  const [confirm, setConfirm] = useState<PendingConfirm | null>(null);
  const [selFlag, setSelFlag] = useState<string | null>(null);
  const [selCand, setSelCand] = useState<string | null>(null);

  const ops = useRef(new Map<string, OpInfo>());
  const early = useRef<EngineEvent[]>([]);
  const sampleRef = useRef(sampleId);
  sampleRef.current = sampleId;

  // ------------------------------------------------------------------ loading

  const recheck = useCallback(() => {
    api
      .permissions(MAP_OPS)
      .then(setPerms)
      .catch(() => setPerms(Object.fromEntries(MAP_OPS.map((op) => [op, { allowed: false, reason: PERMISSION_UNAVAILABLE }]))));
  }, [api]);

  useEffect(recheck, [recheck]);

  const reloadMap = useCallback(async () => {
    const id = sampleRef.current;
    if (!id) return;
    try {
      setMapState(await api.mapState(id));
      setLoadError(null);
    } catch (e) {
      setLoadError(why(e));
    }
  }, [api]);

  const reloadResults = useCallback(async () => {
    const id = sampleRef.current;
    if (id) setResults(await api.results(id).catch(() => []));
  }, [api]);

  const reloadRecords = useCallback(async () => {
    const id = sampleRef.current;
    if (!id) return;
    const [f, c] = await Promise.all([
      api.flags(id, showRetired).catch(() => [] as Flag[]),
      api.candidates(id, showRejected).catch(() => [] as Candidate[]),
    ]);
    setFlags(f);
    setCands(c);
  }, [api, showRetired, showRejected]);

  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const loadSnapshot = useCallback(() => {
    client
      .get<Record<string, unknown>>("/api/state")
      .then((raw) => {
        if (!alive.current) return;
        const s = readSnapshot(raw);
        setOpenSample(s.sample);
        if (s.objective) setObjective(s.objective);
        if (s.position) setPos({ x: s.position.x_um, y: s.position.y_um, z: s.position.z_um });
      })
      .catch(() => undefined);
  }, [client]);

  useEffect(loadSnapshot, [loadSnapshot]);

  useEffect(() => {
    setMapState(null);
    setResults([]);
    setResultId(null);
    setDetail(null);
    if (!sampleId) return;
    void reloadMap();
    void reloadResults();
  }, [sampleId, reloadMap, reloadResults]);

  useEffect(() => {
    void reloadRecords();
  }, [sampleId, reloadRecords]);

  useEffect(() => {
    if (!sampleId || !resultId) {
      setDetail(null);
      return;
    }
    let live = true;
    api.result(sampleId, resultId).then((d) => live && setDetail(d)).catch(() => live && setDetail(null));
    return () => {
      live = false;
    };
  }, [api, sampleId, resultId]);

  // ------------------------------------------------------------------ events

  const reloadsRef = useRef({ reloadMap, reloadResults, reloadRecords });
  reloadsRef.current = { reloadMap, reloadResults, reloadRecords };

  const handleOpEvent = useCallback((ev: EngineEvent, info: OpInfo) => {
    const d = ev.data ?? {};
    const c = info.control;
    if (c === "goto") return; // the click-move reducer has it
    switch (ev.kind) {
      case "preflight_failed":
        setRefusal((r) => ({ ...r, [c]: str(d.why) ?? "refused by the engine" }));
        setActive((a) => ({ ...a, [c]: undefined }));
        ops.current.delete(ev.op_id);
        break;
      case "started":
        setRefusal((r) => ({ ...r, [c]: undefined }));
        break;
      case "progress":
        if (c === "trace") {
          setTrace((t) => ({
            status: str(d.status) ?? t.status,
            path_um: num(d.path_um) ?? t.path_um,
            n_points: num(d.n_points) ?? t.n_points,
          }));
        } else if (c === "scan") {
          setScan((s) => ({
            tile: num(d.tile) ?? s.tile,
            n_tiles: num(d.n_tiles) ?? s.n_tiles,
            dropped: num(d.dropped) ?? s.dropped,
          }));
        }
        break;
      case "confirm_required":
        setConfirm({
          op_id: ev.op_id,
          key: str(d.key) ?? "",
          text: str(d.prompt) ?? str(d.text) ?? str(d.key) ?? `${info.op} asks to continue`,
        });
        break;
      case "finished":
      case "aborted":
      case "error": {
        setActive((a) => ({ ...a, [c]: undefined }));
        setConfirm((p) => (p && p.op_id === ev.op_id ? null : p));
        if (ev.kind !== "finished") setRefusal((r) => ({ ...r, [c]: str(d.why) ?? str(d.message) ?? `${info.op} ${ev.kind}` }));
        ops.current.delete(ev.op_id);
        if (c === "scan") void reloadsRef.current.reloadResults();
        void reloadsRef.current.reloadMap();
        void reloadsRef.current.reloadRecords();
        break;
      }
    }
  }, []);

  const onEvent = useCallback(
    (ev: EngineEvent) => {
      const d = ev.data ?? {};
      dispatch({ type: "event", ev });
      if (RECHECK_ON.has(ev.kind)) recheck();
      switch (ev.kind) {
        case "position": {
          setPos((p) => ({ x: num(d.x_um) ?? p.x, y: num(d.y_um) ?? p.y, z: num(d.z_um) ?? p.z }));
          const o = str(d.objective);
          if (o) setObjective(o);
          return;
        }
        case "objective": {
          const o = str(d.label) ?? str(d.objective);
          if (o) setObjective(o);
          return;
        }
        case "sample_opened":
          setOpenSample(str(d.sample_id));
          return;
        case "map_changed": {
          const id = str(d.sample_id);
          if (id === null || id === sampleRef.current) {
            void reloadsRef.current.reloadMap();
            void reloadsRef.current.reloadRecords();
          }
          return;
        }
      }
      const info = ops.current.get(ev.op_id);
      if (info) handleOpEvent(ev, info);
      else if (ev.op_id) early.current = [...early.current.slice(-99), ev];
    },
    [handleOpEvent, recheck],
  );

  const onEventOut = useCallback(
    (ev: EventOut) => onEvent({ kind: ev.kind, op_id: ev.op_id, data: ev.data ?? {} }),
    [onEvent],
  );
  useEngineEvents(onEventOut);

  // events sent while the socket was down are lost: re-read everything when it comes back
  const wasConnected = useRef(connected);
  useEffect(() => {
    if (connected && !wasConnected.current) {
      loadSnapshot();
      recheck();
      void reloadsRef.current.reloadMap();
      void reloadsRef.current.reloadResults();
      void reloadsRef.current.reloadRecords();
    }
    wasConnected.current = connected;
  }, [connected, recheck, loadSnapshot]);

  const track = useCallback(
    (op_id: string, info: OpInfo) => {
      ops.current.set(op_id, info);
      const mine = early.current.filter((e) => e.op_id === op_id);
      early.current = early.current.filter((e) => e.op_id !== op_id);
      for (const e of mine) handleOpEvent(e, info);
    },
    [handleOpEvent],
  );

  const start = useCallback(
    async (control: Control, op: string, args: Record<string, unknown>) => {
      setRefusal((r) => ({ ...r, [control]: undefined }));
      try {
        const op_id = await client.command({ kind: "start", op, args });
        if (control === "trace" || control === "scan") setActive((a) => ({ ...a, [control]: op_id }));
        track(op_id, { control, op });
      } catch (e) {
        setRefusal((r) => ({ ...r, [control]: why(e) }));
      }
    },
    [client, track],
  );

  const send = useCallback(
    async (control: Control, cmd: CommandInput) => {
      try {
        await client.command(cmd);
      } catch (e) {
        setRefusal((r) => ({ ...r, [control]: why(e) }));
      }
    },
    [client],
  );

  const writeRecord = useCallback(
    async (control: "flag" | "candidate", op: string, call: () => Promise<string>) => {
      setRefusal((r) => ({ ...r, [control]: undefined }));
      try {
        track(await call(), { control, op });
      } catch (e) {
        setRefusal((r) => ({ ...r, [control]: why(e) }));
      }
    },
    [track],
  );

  // ------------------------------------------------------------------ derived

  /** null when allowed; else the shared reason (the first refused op wins) */
  const reasonFor = (...want: MapOp[]): string | null => {
    if (readOnly) return `Read-only: ${readOnlyWhy ?? "remote view"}`;
    if (perms === null) return "Checking permissions…";
    for (const op of want) {
      const p = perms[op];
      if (!p) return PERMISSION_UNAVAILABLE; // an op missing from the answer
      if (!p.allowed) return p.reason ?? `${op} is not allowed`;
    }
    return null;
  };
  const moveReason = reasonFor("goto_xy");
  const fit = holeFitStatus(mapState);
  const allowed = detail?.allowed_box_um ?? mapState?.allowed_box_um ?? null;
  const here: [number, number] | null = pos.x !== null && pos.y !== null ? [pos.x, pos.y] : null;

  const view = useMemo(
    () => fitView(mapExtent(mapState, [detail?.mosaic, detail?.scan_box_um]), width, height, here ?? [0, 0]),
    // the view follows the sample, not every position update
    [mapState, detail, width, height],
  );

  const items = useMemo(
    () =>
      buildScene(
        {
          state: mapState,
          mosaic:
            sampleId && detail?.has_mosaic && detail.mosaic
              ? { url: api.mosaicUrl(sampleId, detail.result_id), extent: detail.mosaic }
              : null,
          scanBox: allowed,
          flags,
          candidates: cands,
          showRetired,
          showRejected,
          field: here ? { x_um: here[0], y_um: here[1], fov_um: fieldOfViewUm(objective) } : null,
          pin: move.target && move.phase !== "idle" ? { x: move.target[0], y: move.target[1], refused: move.phase === "refused" } : null,
          staleFit: fit === "previous_session",
        },
        layers,
      ),
    [api, sampleId, mapState, detail, allowed, flags, cands, showRetired, showRejected, here, objective, move, fit, layers],
  );

  const ctxDetails = useMemo(() => {
    const d: Record<string, unknown> = {};
    if (sampleId) d.sample_id = sampleId;
    if (move.target) d.region = { x_um: Math.round(move.target[0]), y_um: Math.round(move.target[1]) };
    if (selFlag) d.flag_id = selFlag;
    if (selCand) d.candidate_id = selCand;
    if (mapState?.hole) d.hole = { diameter_mm: mapState.hole.diameter_mm, fitted_at: mapState.hole.fitted_at, fit };
    return d;
  }, [sampleId, move.target, selFlag, selCand, mapState, fit]);
  useScreenContext(ctxDetails);

  // ------------------------------------------------------------------ actions

  const pick = useCallback(
    (p: [number, number]) => {
      if (!sampleId || moveReason) return;
      if (move.phase === "submitting" || ["planned", "confirm", "retracting", "moving"].includes(move.phase)) return;
      dispatch({ type: "click", x_um: p[0], y_um: p[1] });
      client
        .command({ kind: "start", op: "goto_xy", args: { sample_id: sampleId, x_um: p[0], y_um: p[1] } })
        .then((op_id) => {
          ops.current.set(op_id, { control: "goto", op: "goto_xy" });
          dispatch({ type: "submitted", op_id });
        })
        .catch((e) => dispatch({ type: "submit_failed", why: why(e) }));
    },
    [client, sampleId, moveReason, move.phase],
  );

  if (!sampleId) {
    return (
      <section className="map-screen">
        <h2>Sample map</h2>
        <p>
          No sample open. Open one in the <a href={areaHref("sample")}>Sample</a> area.
        </p>
      </section>
    );
  }

  const spanUm = view.width / view.pxPerUm;
  const hoverText = hover
    ? [
        `${hover[0].toFixed(0)}, ${hover[1].toFixed(0)} µm`,
        here ? `${distanceUm(hover, here).toFixed(0)} µm from here` : null,
        allowed && !inBox(allowed, hover[0], hover[1]) ? "outside the scanned area" : null,
      ]
        .filter(Boolean)
        .join(" · ")
    : null;

  return (
    <section className="map-screen" data-readonly={moveReason ? "true" : undefined}>
      <header className="map-head">
        <h2>Sample map · {sampleId}</h2>
        {loadError && <p className="map-error" role="alert">{loadError}</p>}
      </header>

      <div className="map-body">
        <div className="map-main">
          <MapCanvas view={view} items={items} onHover={setHover} onPick={pick} disabled={moveReason !== null} />
          <p className="map-scale" data-testid="map-scale">
            {spanUm.toFixed(0)} um across   +stage x ←  +y ↓
          </p>
          <p className="map-hover" data-testid="map-hover">{hoverText ?? " "}</p>
          {moveReason && <p className="map-readonly" data-testid="move-reason">Click-to-move: {moveReason}</p>}
          <ClickMoveBanner
            move={move}
            z={pos.z}
            onAnswer={(ok) => {
              if (move.op_id) void client.command({ kind: "confirm", op_id: move.op_id, args: { key: move.confirmKey, ok } }).catch(() => undefined);
              dispatch({ type: "answered" });
            }}
            onDismiss={() => dispatch({ type: "clear" })}
          />
          {confirm && (
            <div className="map-confirm" role="dialog" aria-label="Confirm">
              <p>{confirm.text}</p>
              <button
                onClick={() => {
                  void send("trace", { kind: "confirm", op_id: confirm.op_id, args: { key: confirm.key, ok: true } });
                  setConfirm(null);
                }}
              >
                Continue
              </button>
              <button
                onClick={() => {
                  void send("trace", { kind: "confirm", op_id: confirm.op_id, args: { key: confirm.key, ok: false } });
                  setConfirm(null);
                }}
              >
                Cancel
              </button>
            </div>
          )}
          <fieldset className="map-layers">
            <legend>Layers</legend>
            {LAYERS.map((l) => (
              <label key={l}>
                <input
                  type="checkbox"
                  checked={layers[l]}
                  onChange={(e) => setLayers((s) => ({ ...s, [l]: e.target.checked }))}
                />
                {LAYER_LABEL[l]}
              </label>
            ))}
            <label>
              <input type="checkbox" checked={showRetired} onChange={(e) => setShowRetired(e.target.checked)} />
              Show retired flags
            </label>
            <label>
              <input type="checkbox" checked={showRejected} onChange={(e) => setShowRejected(e.target.checked)} />
              Show rejected candidates
            </label>
          </fieldset>
        </div>

        <aside className="map-side">
          <SequencePanel fit={fit} scanReason={reasonFor("scan_4x") ?? refusal.scan ?? null} />
          <HolePanel state={mapState} fit={fit} />
          <TracePanel
            disabled={reasonFor("edge_trace")}
            boundaryDisabled={reasonFor("boundary_mark", "boundary_undo", "boundary_reset")}
            refusal={refusal.trace ?? refusal.boundary ?? null}
            running={active.trace ?? null}
            progress={trace}
            defaultDiameter={mapState?.expected_diameter_mm ?? null}
            onStart={(speed, diameter) =>
              void start("trace", "edge_trace", { sample_id: sampleId, speed_um_s: speed, hole_diameter_mm: diameter, light: "bf" })
            }
            onStop={() => active.trace && void send("trace", { kind: "abort", op_id: active.trace })}
            onSpeed={(speed) => active.trace && void send("trace", { kind: "update", op_id: active.trace, args: { speed_um_s: speed } })}
            onBoundary={(op) => void start("boundary", op, { sample_id: sampleId })}
          />
          <ScanPanel
            reasonFor={(op) => reasonFor(op) ?? (fit === "this_session" ? null : "Trace the hole edge in brightfield first")}
            refusal={refusal.scan ?? null}
            running={active.scan ?? null}
            progress={scan}
            onStart={(op, args) => void start("scan", op, { sample_id: sampleId, ...args })}
            onStop={() => active.scan && void send("scan", { kind: "abort", op_id: active.scan })}
          />
          <ResultsPanel results={results} selected={resultId} detail={detail} onSelect={setResultId} />
          <FlagsPanel
            flags={visibleFlags(flags, showRetired)}
            here={here}
            disabled={reasonFor("map_flag")}
            retireDisabled={reasonFor("map_flag_retire")}
            refusal={refusal.flag ?? null}
            selected={selFlag}
            onSelect={setSelFlag}
            onAdd={(body) => void writeRecord("flag", "map_flag", () => api.addFlag(sampleId, body))}
            onRetire={(id) => void writeRecord("flag", "map_flag_retire", () => api.retireFlag(sampleId, id))}
          />
          <CandidatesPanel
            candidates={visibleCandidates(cands, showRejected)}
            disabled={reasonFor("candidate_confirm", "candidate_reject")}
            refusal={refusal.candidate ?? null}
            selected={selCand}
            onSelect={setSelCand}
            onDecide={(id, d) =>
              void writeRecord("candidate", d === "confirm" ? "candidate_confirm" : "candidate_reject", () =>
                api.decideCandidate(sampleId, id, d),
              )
            }
          />
        </aside>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------- pieces

function Reason({ text }: { text: string | null | undefined }) {
  return text ? <span className="map-reason">{text}</span> : null;
}

function ClickMoveBanner({
  move,
  z,
  onAnswer,
  onDismiss,
}: {
  move: ClickMove;
  z: number | null;
  onAnswer: (ok: boolean) => void;
  onDismiss: () => void;
}) {
  const text = clickMoveText(move);
  if (text === null) return null;
  const zSafe = move.plan?.z_safe_um;
  const plan = typeof zSafe === "number" ? <span className="map-plan">plan Z {zSafe.toFixed(1)} µm</span> : null;
  const t = move.target ? `(${move.target[0].toFixed(0)}, ${move.target[1].toFixed(0)})` : "";
  return (
    <div className={`map-move map-move-${move.phase}`} role="status" data-testid="click-move" data-phase={move.phase}>
      {move.phase === "confirm" ? (
        <div role="dialog" aria-label="Retract Z">
          <p>
            Retract <EncoderZ readbackUm={move.zReadUm ?? z} /> -&gt; {plan}, then move to {t}
          </p>
          <button onClick={() => onAnswer(true)}>Retract and move</button>
          <button onClick={() => onAnswer(false)}>Cancel</button>
        </div>
      ) : move.phase === "retracting" ? (
        <p>
          {text}: <EncoderZ readbackUm={z} /> -&gt; {plan}
        </p>
      ) : move.phase === "arrived" ? (
        <p>
          {text} Z left retracted at <EncoderZ readbackUm={move.arrived?.z_um ?? z} />: refocus with a scan tile or{" "}
          <a href={areaHref("objective")}>focus_100x</a>.
        </p>
      ) : (
        <p>{text}</p>
      )}
      {(move.phase === "refused" || move.phase === "arrived" || move.phase === "ended") && (
        <button onClick={onDismiss}>Dismiss</button>
      )}
    </div>
  );
}

/** step 2 shows the engine's reason (e.g. a partial trace); the screen does not judge the fit itself */
function SequencePanel({ fit, scanReason }: { fit: ReturnType<typeof holeFitStatus>; scanReason: string | null }) {
  const traced = fit === "this_session";
  const reason = scanReason ?? (traced ? null : "Trace the hole edge in brightfield first");
  return (
    <section className="map-panel" aria-label="Sequence">
      <h3>Sequence</h3>
      <ol>
        <li data-done={traced ? "true" : undefined}>Trace the hole edge (brightfield){traced ? " · done" : ""}</li>
        <li>
          Scan (particle light)
          <Reason text={reason} />
        </li>
      </ol>
    </section>
  );
}

function HolePanel({ state, fit }: { state: MapState | null; fit: ReturnType<typeof holeFitStatus> }) {
  const h = state?.hole ?? null;
  return (
    <section className="map-panel" aria-label="Hole">
      <h3>Hole</h3>
      {!h ? (
        <p>No hole fit yet</p>
      ) : (
        <>
          <p className={fit === "this_session" ? "map-fit" : "map-fit map-warn"} data-testid="hole-fit">
            {fit === "this_session"
              ? `Hole fit ${clock(h.fitted_at)} (this session)`
              : `Hole fit ${clock(h.fitted_at)}, previous session: re-trace before scanning`}
          </p>
          <p>
            Centre ({h.centre_um[0].toFixed(1)}, {h.centre_um[1].toFixed(1)}) µm · ⌀ {h.diameter_mm.toFixed(3)} mm · rms{" "}
            {fmt(h.fit_rms_um, 1)} µm · {fmt(h.n_points)} points · {fmt(h.arc_deg)}°
          </p>
          {diameterOff(h, state?.expected_diameter_mm ?? null) && (
            <p className="map-warn">Diameter differs from the expected {state?.expected_diameter_mm} mm by more than 20 %</p>
          )}
        </>
      )}
    </section>
  );
}

function TracePanel({
  disabled,
  boundaryDisabled,
  refusal,
  running,
  progress,
  defaultDiameter,
  onStart,
  onStop,
  onSpeed,
  onBoundary,
}: {
  disabled: string | null;
  boundaryDisabled: string | null;
  refusal: string | null;
  running: string | null;
  progress: TraceProgress;
  defaultDiameter: number | null;
  onStart: (speed: number, diameter: number | null) => void;
  onStop: () => void;
  onSpeed: (speed: number) => void;
  onBoundary: (op: "boundary_mark" | "boundary_undo" | "boundary_reset") => void;
}) {
  const [speed, setSpeed] = useState(100);
  const [diameter, setDiameter] = useState<string>("");
  const d = diameter.trim() === "" ? defaultDiameter : Number(diameter);
  const change = (v: number) => {
    const s = Math.min(SPEED_MAX, Math.max(SPEED_MIN, v));
    setSpeed(s);
    if (running) onSpeed(s);
  };
  const off = disabled !== null;
  return (
    <section className="map-panel" aria-label="Edge trace">
      <h3>Edge trace</h3>
      <label>
        Speed (µm/s)
        <input type="number" min={SPEED_MIN} max={SPEED_MAX} value={speed} disabled={off} onChange={(e) => change(Number(e.target.value))} />
      </label>
      <label>
        Expected diameter (mm)
        <input
          type="number"
          step="0.01"
          value={diameter}
          placeholder={defaultDiameter === null ? "" : String(defaultDiameter)}
          disabled={off}
          onChange={(e) => setDiameter(e.target.value)}
        />
      </label>
      <div>
        {running ? (
          <button onClick={onStop}>Stop</button>
        ) : (
          <button disabled={off} onClick={() => onStart(speed, d !== null && Number.isFinite(d) ? d : null)}>
            Start tracing
          </button>
        )}
        <button disabled={off || !running} onClick={() => change(speed * 2)}>+</button>
        <button disabled={off || !running} onClick={() => change(speed / 2)}>-</button>
      </div>
      <div>
        <button disabled={boundaryDisabled !== null} onClick={() => onBoundary("boundary_mark")}>Mark edge here</button>
        <button disabled={boundaryDisabled !== null} onClick={() => onBoundary("boundary_undo")}>Undo last point</button>
        <button disabled={boundaryDisabled !== null} onClick={() => onBoundary("boundary_reset")}>Clear boundary</button>
      </div>
      <Reason text={disabled ?? boundaryDisabled ?? refusal} />
      {running && (
        <p>
          {progress.status ?? "tracing"} · path {fmt(progress.path_um)} µm · {fmt(progress.n_points)} points
        </p>
      )}
    </section>
  );
}

function ScanPanel({
  reasonFor,
  refusal,
  running,
  progress,
  onStart,
  onStop,
}: {
  reasonFor: (op: "scan_4x" | "sample_map") => string | null;
  refusal: string | null;
  running: string | null;
  progress: ScanProgress;
  onStart: (op: "scan_4x" | "sample_map", args: Record<string, unknown>) => void;
  onStop: () => void;
}) {
  const [kind, setKind] = useState<"scan_4x" | "sample_map">("scan_4x");
  const [exposure, setExposure] = useState("");
  const [dryRun, setDryRun] = useState(false);
  const [focus, setFocus] = useState<"per_tile" | "plane">("per_tile");
  const disabled = reasonFor(kind);
  const off = disabled !== null;
  const go = () => {
    const exposure_ms = exposure.trim() === "" ? null : Number(exposure);
    const args: Record<string, unknown> = { exposure_ms, dry_run: dryRun };
    if (kind === "sample_map") Object.assign(args, { focus, light: "bf" });
    onStart(kind, args);
  };
  return (
    <section className="map-panel" aria-label="Scan">
      <h3>Scan</h3>
      <label>
        Kind
        <select value={kind} onChange={(e) => setKind(e.target.value as "scan_4x" | "sample_map")}>
          <option value="scan_4x">4x scan, particle light</option>
          <option value="sample_map">Sample map, brightfield</option>
        </select>
      </label>
      <label>
        Exposure (ms, blank = auto)
        <input type="number" value={exposure} disabled={off} onChange={(e) => setExposure(e.target.value)} />
      </label>
      <label>
        <input type="checkbox" checked={dryRun} disabled={off} onChange={(e) => setDryRun(e.target.checked)} />
        Dry run
      </label>
      {kind === "sample_map" && (
        <label>
          Focus
          <select value={focus} disabled={off} onChange={(e) => setFocus(e.target.value as "per_tile" | "plane")}>
            <option value="per_tile">per tile</option>
            <option value="plane">plane</option>
          </select>
        </label>
      )}
      <div>
        {running ? (
          <button onClick={onStop}>Stop</button>
        ) : (
          <button disabled={off} onClick={go}>
            Start scan
          </button>
        )}
      </div>
      <Reason text={disabled ?? refusal} />
      {running && (
        <p>
          Tile {fmt(progress.tile)}/{fmt(progress.n_tiles)} · dropped frames {fmt(progress.dropped)}
        </p>
      )}
    </section>
  );
}

function ResultsPanel({
  results,
  selected,
  detail,
  onSelect,
}: {
  results: ResultSummary[];
  selected: string | null;
  detail: ResultDetail | null;
  onSelect: (id: string | null) => void;
}) {
  return (
    <section className="map-panel" aria-label="Results">
      <h3>Results</h3>
      {results.length === 0 ? (
        <p>No scans yet</p>
      ) : (
        <ul>
          {results.map((r) => (
            <li key={r.result_id}>
              <label>
                <input
                  type="radio"
                  name="map-result"
                  checked={selected === r.result_id}
                  onChange={() => onSelect(r.result_id)}
                />
                {r.result_id} · {r.kind} · {r.n_tiles} tiles{r.has_mosaic ? " · mosaic" : ""}
              </label>
            </li>
          ))}
        </ul>
      )}
      {detail && (
        <table className="map-tiles">
          <thead>
            <tr>
              <th>Tile</th>
              <th>x, y (µm)</th>
              <th>Focus</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            {detail.tiles.map((t) => (
              <tr key={t.name}>
                <td>{t.name}</td>
                <td>
                  {t.x_um.toFixed(1)}, {t.y_um.toFixed(1)}
                </td>
                <td>
                  <EncoderZ readbackUm={t.z_focus_um} />
                </td>
                <td>{t.focus_note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function FlagsPanel({
  flags,
  here,
  disabled,
  retireDisabled,
  refusal,
  selected,
  onSelect,
  onAdd,
  onRetire,
}: {
  flags: Flag[];
  here: [number, number] | null;
  disabled: string | null;
  retireDisabled: string | null;
  refusal: string | null;
  selected: string | null;
  onSelect: (id: string | null) => void;
  onAdd: (body: { x_um: number; y_um: number; name: string; note: string; replaces?: string }) => void;
  onRetire: (id: string) => void;
}) {
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editNote, setEditNote] = useState("");
  const off = disabled !== null;
  return (
    <section className="map-panel" aria-label="Flags">
      <h3>Flags</h3>
      <ul>
        {flags.map((f) => (
          <li key={f.flag_id} data-selected={selected === f.flag_id ? "true" : undefined}>
            <button className="map-link" onClick={() => onSelect(selected === f.flag_id ? null : f.flag_id)}>
              {f.name}
            </button>{" "}
            {f.note} · {clock(f.t)} · {f.objective ?? "—"} · {f.x_um.toFixed(1)}, {f.y_um.toFixed(1)} · <EncoderZ readbackUm={f.z_um} />
            {isRetired(f) && (
              <span className="map-muted" data-testid={`retired-${f.flag_id}`}>
                {" "}· retired{f.retired_by ? ` by ${f.retired_by}` : ""}
                {f.retired_at != null ? ` at ${clock(f.retired_at)}` : ""}
              </span>
            )}
            {!isRetired(f) && (
              <>
                {" "}
                <button disabled={retireDisabled !== null} onClick={() => onRetire(f.flag_id)}>
                  Retire
                </button>
                <button
                  disabled={off}
                  onClick={() => {
                    setEditing(f.flag_id);
                    setEditNote(f.note);
                  }}
                >
                  Edit note
                </button>
              </>
            )}
            {editing === f.flag_id && (
              <span>
                <input aria-label="New note" value={editNote} onChange={(e) => setEditNote(e.target.value)} />
                <button
                  disabled={off}
                  onClick={() => {
                    onAdd({ x_um: f.x_um, y_um: f.y_um, name: f.name, note: editNote, replaces: f.flag_id });
                    setEditing(null);
                  }}
                >
                  Save
                </button>
              </span>
            )}
          </li>
        ))}
      </ul>
      <div className="map-flag-add">
        <input aria-label="Flag name" placeholder="name" value={name} disabled={off} onChange={(e) => setName(e.target.value)} />
        <input aria-label="Flag note" placeholder="note" value={note} disabled={off} onChange={(e) => setNote(e.target.value)} />
        <button
          disabled={off || here === null || name.trim() === ""}
          onClick={() => {
            if (!here) return;
            onAdd({ x_um: here[0], y_um: here[1], name: name.trim(), note });
            setName("");
            setNote("");
          }}
        >
          Flag current position
        </button>
      </div>
      <Reason text={disabled ?? retireDisabled ?? refusal} />
    </section>
  );
}

const SOURCE_LABEL: Record<string, string> = {
  classical_candidate: "candidate (computed)",
  person_confirmed: "confirmed",
  person_rejected: "rejected",
};

function CandidatesPanel({
  candidates,
  disabled,
  refusal,
  selected,
  onSelect,
  onDecide,
}: {
  candidates: Candidate[];
  disabled: string | null;
  refusal: string | null;
  selected: string | null;
  onSelect: (id: string | null) => void;
  onDecide: (id: string, d: "confirm" | "reject") => void;
}) {
  const off = disabled !== null;
  return (
    <section className="map-panel" aria-label="Candidates">
      <h3>Candidates</h3>
      {candidates.length === 0 ? (
        <p>No candidates</p>
      ) : (
        <ul>
          {candidates.map((c) => (
            <li key={c.candidate_id} data-source={c.source} data-selected={selected === c.candidate_id ? "true" : undefined}>
              <button className="map-link" onClick={() => onSelect(selected === c.candidate_id ? null : c.candidate_id)}>
                {c.candidate_id}
              </button>{" "}
              {SOURCE_LABEL[c.source] ?? c.source}
              {c.source !== "classical_candidate" && c.by ? ` by ${c.by}` : ""}
              {c.source !== "classical_candidate" && c.decided_at != null ? ` at ${clock(c.decided_at)}` : ""}
              {" "}· {c.x_um.toFixed(1)}, {c.y_um.toFixed(1)}
              {c.source === "classical_candidate" && (
                <>
                  {" "}
                  <button disabled={off} onClick={() => onDecide(c.candidate_id, "confirm")}>
                    Confirm
                  </button>
                  <button disabled={off} onClick={() => onDecide(c.candidate_id, "reject")}>
                    Reject
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      <Reason text={disabled ?? refusal} />
    </section>
  );
}
