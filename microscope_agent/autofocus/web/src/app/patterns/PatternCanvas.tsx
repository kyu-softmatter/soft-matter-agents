import { useEffect, useRef, useState } from "react";

import { GRADIENT_CSS, patternDuration, sampleTrack, targetLabel, timeColor, type Track } from "./model";

/** um in the pattern's plane -> canvas pixels */
export type ToPx = (x_um: number, y_um: number) => [number, number];

/**
 * Draw tracks over time: each segment coloured by when it is reached, gray at the
 * start to dark green at the end, and a marker where every target is at `t`
 * (piezo a square, a trap a circle with its number).
 */
export function drawTracks(
  ctx: CanvasRenderingContext2D,
  tracks: Track[],
  { t, toPx, lineWidth = 2 }: { t: number; toPx: ToPx; lineWidth?: number },
): void {
  const d = patternDuration({ tracks }) || 1;
  ctx.lineCap = "round";
  ctx.lineWidth = lineWidth;
  for (const tr of tracks) {
    const pts = tr.points;
    for (let i = 1; i < pts.length; i++) {
      const [ax, ay] = toPx(pts[i - 1][1] ?? 0, pts[i - 1][2] ?? 0);
      const [bx, by] = toPx(pts[i][1] ?? 0, pts[i][2] ?? 0);
      ctx.strokeStyle = timeColor((pts[i - 1][0] + pts[i][0]) / 2 / d);
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(bx, by);
      ctx.stroke();
    }
  }
  for (const tr of tracks) {
    const [, x, y] = sampleTrack(tr, t);
    const [px, py] = toPx(x, y);
    ctx.fillStyle = "#ffffff";
    ctx.strokeStyle = timeColor(t / d);
    ctx.lineWidth = 2;
    ctx.beginPath();
    if (tr.target === "piezo") ctx.rect(px - 5, py - 5, 10, 10);
    else ctx.arc(px, py, 6, 0, 2 * Math.PI);
    ctx.fill();
    ctx.stroke();
    if (tr.target !== "piezo") {
      ctx.fillStyle = "#ffffff";
      ctx.font = "11px sans-serif";
      ctx.fillText(tr.target.slice(5), px + 8, py - 8);
    }
  }
}

/** A canvas that redraws `tracks` whenever they, the time or the mapping change. */
export function PatternCanvas({
  tracks,
  t,
  width,
  height,
  toPx,
  background,
  className,
  label = "Pattern",
}: {
  tracks: Track[];
  t: number;
  width: number;
  height: number;
  toPx: ToPx;
  /** drawn first (grid, axes); none for an overlay */
  background?: (ctx: CanvasRenderingContext2D) => void;
  className?: string;
  label?: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const ctx = ref.current?.getContext("2d") ?? null;
    if (!ctx) return; // no canvas (tests): the markup is still there
    ctx.clearRect(0, 0, width, height);
    background?.(ctx);
    drawTracks(ctx, tracks, { t, toPx });
  }, [tracks, t, width, height, toPx, background]);
  return <canvas ref={ref} width={width} height={height} className={className} role="img" aria-label={label} />;
}

/** Play / pause, a time slider and the colour key. `t` is owned by the caller. */
export function PatternScrubber({
  duration,
  t,
  onTime,
  loop = false,
}: {
  duration: number;
  t: number;
  onTime: (t: number) => void;
  loop?: boolean;
}) {
  const [playing, setPlaying] = useState(false);
  const tRef = useRef(t);
  tRef.current = t;

  useEffect(() => {
    if (!playing || duration <= 0) return;
    let last = performance.now();
    let frame = 0;
    const step = (now: number) => {
      const next = tRef.current + (now - last) / 1000;
      last = now;
      if (next >= duration && !loop) {
        onTime(duration);
        setPlaying(false);
        return;
      }
      onTime(loop ? next % duration : next);
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [playing, duration, loop, onTime]);

  return (
    <div className="pattern-scrubber">
      <button
        type="button"
        onClick={() => {
          if (!playing && t >= duration) onTime(0);
          setPlaying((p) => !p);
        }}
        disabled={duration <= 0}
      >
        {playing ? "Pause" : "Play"}
      </button>
      <input
        type="range"
        aria-label="Pattern time"
        min={0}
        max={duration || 0}
        step={duration > 0 ? duration / 1000 : 1}
        value={Math.min(t, duration)}
        onChange={(e) => onTime(Number(e.target.value))}
      />
      <span data-testid="pattern-time">
        {t.toFixed(2)} / {duration.toFixed(2)} s
      </span>
      <span className="pattern-key" title="Colour by time: gray at the start, dark green at the end">
        0 s <span className="pattern-key-bar" style={{ background: GRADIENT_CSS }} /> {duration.toFixed(1)} s
      </span>
    </div>
  );
}


/** Where every target is at `t`: x, y and z in um (z is not visible in the drawing). */
export function PatternReadout({ tracks, t }: { tracks: Track[]; t: number }) {
  return (
    <ul className="pattern-readout" aria-label="Positions at this time">
      {tracks.map((tr) => {
        const [, x, y, z] = sampleTrack(tr, t);
        return (
          <li key={tr.target}>
            {targetLabel(tr.target)}: x {x.toFixed(2)}, y {y.toFixed(2)}, z {z.toFixed(2)} µm
          </li>
        );
      })}
    </ul>
  );
}
