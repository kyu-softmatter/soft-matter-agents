import { useEffect, useRef } from "react";

import type { components } from "../../api/schema";
import type { FrameMeta } from "./frames";
import { frameScale } from "./PatternOverlay";

export type Trap = components["schemas"]["TrapOut"];

/**
 * Where each trap is over one camera frame (um from the field centre, x right, y down):
 * a ring for every trap, filled when it is on, the chosen one thicker with its number.
 * Display only; a move goes through the trap_move operation.
 */
export function TrapOverlay({ traps, meta, selected }: { traps: Trap[]; meta: FrameMeta; selected?: number | null }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const { width: w, height: h } = meta;
  const { umPerPx } = frameScale(meta);
  useEffect(() => {
    const ctx = ref.current?.getContext("2d") ?? null;
    if (!ctx) return;
    ctx.clearRect(0, 0, w, h);
    for (const t of traps) {
      const x = w / 2 + t.x_um / umPerPx;
      const y = h / 2 + t.y_um / umPerPx;
      const chosen = t.index === selected;
      ctx.beginPath();
      ctx.arc(x, y, chosen ? 12 : 9, 0, 2 * Math.PI);
      ctx.lineWidth = chosen ? 3 : 1.5;
      ctx.setLineDash(t.on ? [] : [4, 3]);
      ctx.strokeStyle = t.on ? "#4dd0e1" : "#9e9e9e";
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = t.on ? "#4dd0e1" : "#9e9e9e";
      ctx.font = chosen ? "bold 12px sans-serif" : "11px sans-serif";
      ctx.fillText(`T${t.index}${t.on ? "" : " off"}`, x + 14, y - 10);
    }
  }, [traps, w, h, umPerPx, selected]);
  return <canvas ref={ref} width={w} height={h} className="live-overlay" role="img" aria-label="Traps over the frame" />;
}
