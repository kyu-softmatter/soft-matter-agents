import { useCallback } from "react";

import { PatternCanvas, type PatternOut, patternTime, type ToPx } from "../patterns";
import type { FrameMeta } from "./frames";

/** Used when a frame does not say its pixel size; the overlay then says the scale is assumed. */
export const ASSUMED_PIXEL_UM = 0.1;

/** um per displayed pixel of this frame, and whether the frame said so. */
export function frameScale(meta: FrameMeta): { umPerPx: number; known: boolean } {
  const px = meta.meta && typeof meta.meta.pixel_um === "number" ? (meta.meta.pixel_um as number) : null;
  const known = px !== null && px > 0;
  return { umPerPx: (known ? px : ASSUMED_PIXEL_UM) * Math.max(1, meta.binning), known };
}

/**
 * The pattern drawn over one camera frame: um from the centre of the field to the
 * frame's pixels (x right, y down as on the image), coloured by time, with markers
 * where each target is at `t`, a 10 µm scale bar and the scale it used. The canvas
 * has the frame's own size and is stretched with the image, so they stay aligned.
 */
export function PatternOverlay({ pattern, t, meta }: { pattern: PatternOut; t: number; meta: FrameMeta }) {
  const { width: w, height: h } = meta;
  const { umPerPx, known } = frameScale(meta);
  const toPx = useCallback<ToPx>((x, y) => [w / 2 + x / umPerPx, h / 2 + y / umPerPx], [w, h, umPerPx]);
  const caption = useCallback(
    (ctx: CanvasRenderingContext2D) => {
      const bar = 10 / umPerPx;
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(12, h - 18, bar, 3);
      ctx.font = "11px sans-serif";
      ctx.fillText("10 µm", 12, h - 24);
      ctx.fillStyle = known ? "#ffffff" : "#ffb020";
      ctx.fillText(`${umPerPx.toFixed(3)} µm/px${known ? "" : " (assumed)"}`, 12 + bar + 8, h - 14);
    },
    [h, umPerPx, known],
  );
  return (
    <PatternCanvas
      tracks={pattern.tracks}
      t={patternTime(pattern, t)}
      width={w}
      height={h}
      toPx={toPx}
      background={caption}
      className="live-overlay"
      label={`Pattern ${pattern.name} over the frame`}
    />
  );
}

