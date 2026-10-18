// The `tweezers` area: optical tweezer traps with the live view (card T-20261002-2205 stage 3).
//
// The traps come from the engine snapshot (`/api/state` -> `tweezers`); a move or on/off is
// the engine operation `trap_move` / `trap_set` (rule 12: the operator's control and an open
// experiment session, like any stage move), checked by `guards.TrapAxis`. The live view below
// shows every camera with the traps drawn in; a click on a frame moves the chosen trap there.
// The real tweezers are run by Tweez300, which stays open; this app never starts or closes it.

import { useCallback, useEffect, useMemo, useState } from "react";

import type { components } from "../../api/schema";
import { CommandRefused, useClient, useEngineEvents, useReadOnly } from "../../app/client";
import { type CamFrame, type FramePick, LiveView, type Trap, TrapOverlay } from "../../app/live";
import { RANGE_UM } from "../../app/patterns";

type Tweezers = components["schemas"]["TweezersState"];
type Permission = { allowed: boolean; reason: string | null };
const OPS = ["trap_move", "trap_set"] as const;
const REFRESH_ON = ["finished", "error", "aborted", "preflight_failed", "motion", "refused"] as const;

function message(e: unknown): string {
  return e instanceof CommandRefused ? e.detail : e instanceof Error ? e.message : String(e);
}

const round = (v: number) => Math.round(v * 100) / 100;

function TrapRow({
  trap,
  chosen,
  blocked,
  onChoose,
  onMove,
  onSet,
}: {
  trap: Trap;
  chosen: boolean;
  blocked: string | null;
  onChoose: () => void;
  onMove: (x: number, y: number, z: number) => void;
  onSet: (on: boolean) => void;
}) {
  const [x, setX] = useState(trap.x_um);
  const [y, setY] = useState(trap.y_um);
  const [z, setZ] = useState(trap.z_um ?? 0);
  useEffect(() => {
    setX(trap.x_um);
    setY(trap.y_um);
    setZ(trap.z_um ?? 0);
  }, [trap.x_um, trap.y_um, trap.z_um]);
  const num = (label: string, v: number, set: (v: number) => void) => (
    <input type="number" step="0.1" aria-label={`Trap ${trap.index} ${label}`} value={v} onChange={(e) => set(Number(e.target.value))} />
  );
  return (
    <tr className={chosen ? "trap-chosen" : undefined}>
      <td>
        <label>
          <input type="radio" name="trap-choice" checked={chosen} onChange={onChoose} aria-label={`Choose trap ${trap.index}`} /> T
          {trap.index}
        </label>
      </td>
      <td>
        <button type="button" aria-pressed={trap.on} disabled={blocked !== null} onClick={() => onSet(!trap.on)}>
          {trap.on ? "On" : "Off"}
        </button>
      </td>
      <td>{num("x µm", x, setX)}</td>
      <td>{num("y µm", y, setY)}</td>
      <td>{num("z µm", z, setZ)}</td>
      <td>{trap.power_pct === null || trap.power_pct === undefined ? "—" : `${trap.power_pct}%`}</td>
      <td>
        <button type="button" disabled={blocked !== null} onClick={() => onMove(x, y, z)}>
          Move
        </button>
      </td>
    </tr>
  );
}

export default function TweezersScreen() {
  const client = useClient();
  const readOnly = useReadOnly();
  const [tw, setTw] = useState<Tweezers | null | undefined>(undefined);
  const [perm, setPerm] = useState<Record<string, Permission> | null>(null);
  const [chosen, setChosen] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const snap = await client.get<{ tweezers?: Tweezers | null }>("/api/state");
      setTw(snap.tweezers ?? null);
      setPerm(await client.get<Record<string, Permission>>(`/api/permissions?ops=${OPS.join(",")}`));
    } catch (e) {
      setError(message(e));
    }
  }, [client]);

  useEffect(() => {
    void reload();
  }, [reload]);
  useEngineEvents(
    useCallback(() => void reload(), [reload]),
    REFRESH_ON,
  );

  const blocked = readOnly.readOnly
    ? (readOnly.why ?? "read-only")
    : perm === null
      ? "checking permissions…"
      : (OPS.map((op) => perm[op]).find((p) => p && !p.allowed)?.reason ?? null);

  const run = useCallback(
    async (op: (typeof OPS)[number], args: Record<string, unknown>, what: string) => {
      setDone(null);
      try {
        await client.command({ kind: "start", op, args });
        setError(null);
        setDone(what);
      } catch (e) {
        setError(message(e));
      }
    },
    [client],
  );

  const move = useCallback(
    (index: number, x: number, y: number, z: number) =>
      void run("trap_move", { trap: index, x_um: round(x), y_um: round(y), z_um: round(z) }, `Trap ${index} to (${round(x)}, ${round(y)}, ${round(z)}) µm sent`),
    [run],
  );

  const traps = useMemo(() => tw?.traps ?? [], [tw]);
  const overlay = useCallback(
    (frame: CamFrame) => <TrapOverlay traps={traps} meta={frame.meta} selected={chosen} />,
    [traps, chosen],
  );
  const pick = useCallback<FramePick>(
    ({ x_um, y_um, scaleKnown }) => {
      if (blocked !== null) {
        setError(`Cannot move: ${blocked}`);
        return;
      }
      const t = traps.find((q) => q.index === chosen);
      if (!t) return;
      const inside = (v: number, [lo, hi]: readonly number[]) => v >= lo && v <= hi;
      if (!inside(x_um, RANGE_UM.trap.x) || !inside(y_um, RANGE_UM.trap.y)) {
        setError(`(${round(x_um)}, ${round(y_um)}) µm is outside the provisional trap range`);
        return;
      }
      if (!scaleKnown) {
        // real tweezers never move on a guessed scale; the mock may, with a warning
        if (tw?.bench !== false) {
          setError("This frame does not say its pixel size: type the position in the table instead.");
          return;
        }
        setError("This frame does not say its pixel size; the click used an assumed scale (mock).");
      }
      move(chosen, x_um, y_um, t.z_um ?? 0);
    },
    [blocked, traps, chosen, move, tw],
  );

  return (
    <section className="tweezers" aria-label="Optical tweezers">
      <h2>Optical tweezers</h2>
      <p className="muted">
        Trap positions are µm from the centre of the camera field (x right, y down, orientation provisional). Tweez300
        stays running on the microscope PC; this app never starts or closes it. Laser power is set in Tweez300.
      </p>
      {tw === undefined && <p className="muted">Loading…</p>}
      {tw === null && <p className="muted">No tweezers on this setup. The Tweez300 connection is not wired yet.</p>}
      {tw && (
        <>
          <p data-testid="tweezers-kind">
            {tw.kind === "mock" ? "Mock tweezers (simulated, nothing is sent to Tweez300)" : `Tweezers: ${tw.kind}`} ·{" "}
            {tw.n_traps} traps
            {tw.error && <span className="warn"> · {tw.error}</span>}
          </p>
          {blocked && <p className="muted">Moves: {blocked}</p>}
          {error && (
            <p className="warn" role="alert">
              {error}
            </p>
          )}
          {done && <p role="status">{done}</p>}
          <table aria-label="Traps">
            <thead>
              <tr>
                <th>Trap</th>
                <th>Laser</th>
                <th>x µm</th>
                <th>y µm</th>
                <th>z µm</th>
                <th>Power</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {traps.map((t) => (
                <TrapRow
                  key={t.index}
                  trap={t}
                  chosen={t.index === chosen}
                  blocked={blocked}
                  onChoose={() => setChosen(t.index)}
                  onMove={(x, y, z) => move(t.index, x, y, z)}
                  onSet={(on) => void run("trap_set", { trap: t.index, on }, `Trap ${t.index} ${on ? "on" : "off"} sent`)}
                />
              ))}
            </tbody>
          </table>
          <p className="muted">Click on a frame to move trap {chosen} there.</p>
        </>
      )}
      <LiveView overlay={tw ? overlay : undefined} onPick={tw ? pick : undefined} />
    </section>
  );
}
