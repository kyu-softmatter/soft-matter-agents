import type { FrameMeta } from "./frames";

/** Used when a frame does not say its pixel size; the overlay then says the scale is assumed. */
export const ASSUMED_PIXEL_UM = 0.1;

/** um per displayed pixel of this frame, and whether the frame said so. */
export function frameScale(meta: FrameMeta): { umPerPx: number; known: boolean } {
  const px = meta.meta && typeof meta.meta.pixel_um === "number" ? (meta.meta.pixel_um as number) : null;
  const known = px !== null && px > 0;
  return { umPerPx: (known ? px : ASSUMED_PIXEL_UM) * Math.max(1, meta.binning), known };
}
