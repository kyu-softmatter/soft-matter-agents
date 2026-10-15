import { useEffect, useRef } from "react";

import type { Frame } from "./frame";
import { type Plane, projectFrame, typeColor } from "./project";

export interface Viewer2DProps {
  frame: Frame | null;
  plane?: Plane;
  wrap?: boolean;
  /** CSS pixels; the canvas is square */
  size?: number;
}

/** The 2D trajectory viewer (PLAN 2절 F6.3): one frame on a Canvas, colored by particle type. */
export function Viewer2D({ frame, plane = "xy", wrap = true, size = 480 }: Viewer2DProps) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return; // jsdom has no 2D context
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(size * dpr);
    canvas.height = Math.round(size * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size, size);
    if (!frame) return;
    const p = projectFrame(frame, plane, size, wrap);
    if (p.box) {
      ctx.strokeStyle = "#b9b6af";
      ctx.lineWidth = 1;
      ctx.strokeRect(p.box.x, p.box.y, p.box.w, p.box.h);
    }
    for (let i = 0; i < frame.n; i++) {
      ctx.beginPath();
      ctx.arc(p.xs[i], p.ys[i], p.r[i], 0, 2 * Math.PI);
      ctx.fillStyle = typeColor(frame.typeid[i]);
      ctx.fill();
    }
  }, [frame, plane, wrap, size]);

  return (
    <canvas
      ref={ref}
      className="sim-canvas"
      style={{ width: size, height: size }}
      role="img"
      aria-label={frame ? `Frame ${frame.index}, ${frame.n} particles, ${plane} plane` : "No frame"}
    />
  );
}
