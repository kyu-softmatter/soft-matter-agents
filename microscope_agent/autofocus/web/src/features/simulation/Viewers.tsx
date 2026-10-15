import { type ComponentType, lazy, Suspense, useState } from "react";

import type { Frame } from "./frame";
import type { Playback } from "./playback";
import { PlaybackControls } from "./PlaybackControls";
import type { Plane } from "./project";
import { Viewer2D } from "./Viewer2D";

/** What the 3D viewer takes; anything more (e.g. T-022's createRenderer) is passed through. */
export type Viewer3DProps = { frame: Frame | null } & Record<string, unknown>;
type Viewer3DModule = { Viewer3D: ComponentType<Viewer3DProps> };

/**
 * The 3D viewer is T-022's folder `viewer3d/`. It is looked up at build time, so this screen
 * builds whether or not that folder is there, and `three` is fetched only when 3D is opened.
 */
export function lazyViewer3D(modules: Record<string, () => Promise<Viewer3DModule>>): ComponentType<Viewer3DProps> | null {
  const load = Object.values(modules)[0];
  return load ? lazy(() => load().then((m) => ({ default: m.Viewer3D }))) : null;
}

const Found3D = lazyViewer3D(import.meta.glob<Viewer3DModule>("./viewer3d/index.tsx"));

export function Viewers({
  frame,
  nFrames,
  playback,
  error,
  viewer3d = Found3D,
}: {
  frame: Frame | null;
  nFrames: number;
  playback: Playback;
  error: string | null;
  viewer3d?: ComponentType<Viewer3DProps> | null;
}) {
  const [mode, setMode] = useState<"2d" | "3d">("2d");
  const [plane, setPlane] = useState<Plane>("xy");
  const [wrap, setWrap] = useState(true);
  const View3D = viewer3d;
  const is3d = frame?.dimensions === 3;

  return (
    <section className="sim-panel" aria-label="Trajectory">
      <div className="sim-row" role="group" aria-label="View">
        <button type="button" aria-pressed={mode === "2d"} onClick={() => setMode("2d")}>
          2D
        </button>
        <button type="button" aria-pressed={mode === "3d"} onClick={() => setMode("3d")}>
          3D
        </button>
        {mode === "2d" ? (
          <>
            <label>
              plane{" "}
              <select value={plane} onChange={(e) => setPlane(e.target.value as Plane)} aria-label="Plane" disabled={!is3d}>
                <option value="xy">xy</option>
                <option value="xz">xz</option>
                <option value="yz">yz</option>
              </select>
            </label>
            <label>
              <input type="checkbox" checked={wrap} onChange={(e) => setWrap(e.target.checked)} /> wrap into box
            </label>
          </>
        ) : null}
        {frame ? (
          <span className="muted">
            {frame.n} particles · {frame.dimensions}D · types {frame.types.join(", ")}
          </span>
        ) : null}
      </div>
      {error ? <p role="alert">Frame: {error}</p> : null}
      {mode === "2d" ? (
        <Viewer2D frame={frame} plane={is3d ? plane : "xy"} wrap={wrap} />
      ) : View3D ? (
        <Suspense fallback={<p className="muted">Loading 3D viewer…</p>}>
          <View3D frame={frame} />
        </Suspense>
      ) : (
        <p className="placeholder">3D viewer: not available yet</p>
      )}
      <PlaybackControls playback={playback} nFrames={nFrames} step={frame?.step} />
    </section>
  );
}
