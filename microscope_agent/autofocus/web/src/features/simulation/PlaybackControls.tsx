import { type Playback, SPEEDS } from "./playback";

/** Play, pause, step, scrub and speed, shared by the 2D and 3D viewers. */
export function PlaybackControls({ playback, nFrames, step }: { playback: Playback; nFrames: number; step?: number | null }) {
  const { index, playing, speed, setIndex, play, pause, setSpeed } = playback;
  const last = Math.max(nFrames - 1, 0);
  return (
    <div className="sim-playback" role="group" aria-label="Playback">
      <button type="button" onClick={() => setIndex(0)} disabled={index === 0} aria-label="First frame">
        ⏮
      </button>
      <button type="button" onClick={() => setIndex(index - 1)} disabled={index === 0} aria-label="Previous frame">
        ◀
      </button>
      {playing ? (
        <button type="button" onClick={pause}>
          Pause
        </button>
      ) : (
        <button type="button" onClick={play} disabled={nFrames <= 1}>
          Play
        </button>
      )}
      <button type="button" onClick={() => setIndex(index + 1)} disabled={index >= last} aria-label="Next frame">
        ▶
      </button>
      <button type="button" onClick={() => setIndex(last)} disabled={index >= last} aria-label="Last frame">
        ⏭
      </button>
      <input
        type="range"
        min={0}
        max={last}
        value={index}
        onChange={(e) => setIndex(Number(e.target.value))}
        aria-label="Frame"
        disabled={nFrames <= 1}
      />
      <span className="sim-frame-label">
        frame {nFrames ? index : "–"} / {last}
        {step != null ? ` · step ${step}` : ""}
      </span>
      <label>
        speed{" "}
        <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} aria-label="Speed">
          {SPEEDS.map((s) => (
            <option key={s} value={s}>
              {s}×
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
