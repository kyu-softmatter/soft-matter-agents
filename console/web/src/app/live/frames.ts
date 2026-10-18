import type { components } from "../../api/schema";

export type FrameMeta = components["schemas"]["WsFrame"];
type WsError = components["schemas"]["WsError"];

export type FrameMessage =
  | { kind: "frame"; meta: FrameMeta; jpeg: Blob }
  | { kind: "error"; status: number; detail: string };

/**
 * `/ws/frames` sends each frame as a text message (WsFrame) followed by exactly
 * one binary message, the JPEG (T-009 ws.py). This pairs them. A binary message
 * with no metadata before it, or of the wrong length, is dropped rather than
 * shown with somebody else's numbers.
 */
export class FramePairer {
  private pending: FrameMeta | null = null;

  feed(data: unknown): FrameMessage | null {
    if (typeof data === "string") {
      let msg: Record<string, unknown>;
      try {
        msg = JSON.parse(data) as Record<string, unknown>;
      } catch {
        this.pending = null;
        return null;
      }
      if (msg.type === "frame") {
        this.pending = msg as unknown as FrameMeta;
        return null;
      }
      if (msg.type === "error") {
        this.pending = null;
        const err = msg as unknown as WsError;
        return { kind: "error", status: Number(err.status ?? 0), detail: String(err.detail ?? "") };
      }
      return null;
    }
    if (data instanceof Blob) {
      const meta = this.pending;
      this.pending = null;
      if (!meta || (meta.jpeg_bytes && data.size !== meta.jpeg_bytes)) return null;
      return { kind: "frame", meta, jpeg: data };
    }
    return null;
  }
}

/** Frames per second over the last `n` arrivals (ms timestamps). */
export class FpsMeter {
  private times: number[] = [];

  constructor(private n = 10) {}

  tick(nowMs: number): number | null {
    this.times.push(nowMs);
    if (this.times.length > this.n) this.times.shift();
    if (this.times.length < 2) return null;
    const span = this.times[this.times.length - 1] - this.times[0];
    return span > 0 ? ((this.times.length - 1) * 1000) / span : null;
  }
}
