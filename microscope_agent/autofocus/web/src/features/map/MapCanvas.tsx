import { type MouseEvent, useEffect, useRef, useState } from "react";

import { toCanvas, toStage, type View } from "./geometry";
import type { Item } from "./scene";

// jsdom has no 2D canvas; tests read the scene instead of pixels
const CAN_PAINT = typeof navigator === "undefined" || !/jsdom/i.test(navigator.userAgent);

const COLOR = {
  scan: "#7a7a7a",
  visit: "#8a94a6",
  visit_in_focus: "#2e9d4f",
  field: "#e07b00",
  boundary: "#d33",
  hole: "#d33",
  stale: "#c98a00",
  candidate: "#1f6fd1",
  rejected: "#888",
  flag: "#7b3fb5",
  pin: "#111",
  refused: "#d33",
};

function paint(ctx: CanvasRenderingContext2D, v: View, items: Item[], images: Map<string, HTMLImageElement>) {
  ctx.clearRect(0, 0, v.width, v.height);
  ctx.lineWidth = 1.5;
  for (const it of items) {
    switch (it.kind) {
      case "image": {
        const img = images.get(it.url);
        if (!img || !img.complete) break;
        // the PNG has +x right, +y up (row 0 = y1); the map has both axes flipped
        const [u, w] = toCanvas(v, it.extent.x0, it.extent.y1);
        ctx.save();
        ctx.translate(u, w);
        ctx.scale(-1, -1);
        ctx.drawImage(img, 0, 0, (it.extent.x1 - it.extent.x0) * v.pxPerUm, (it.extent.y1 - it.extent.y0) * v.pxPerUm);
        ctx.restore();
        break;
      }
      case "rect": {
        const [ua, wa] = toCanvas(v, it.box.x0, it.box.y0);
        const [ub, wb] = toCanvas(v, it.box.x1, it.box.y1);
        ctx.strokeStyle = COLOR[it.style];
        ctx.setLineDash(it.style === "scan" ? [6, 4] : []);
        ctx.strokeRect(Math.min(ua, ub), Math.min(wa, wb), Math.abs(ub - ua), Math.abs(wb - wa));
        ctx.setLineDash([]);
        if (it.style === "field") {
          const [u, w] = toCanvas(v, (it.box.x0 + it.box.x1) / 2, (it.box.y0 + it.box.y1) / 2);
          ctx.beginPath();
          ctx.moveTo(u - 6, w);
          ctx.lineTo(u + 6, w);
          ctx.moveTo(u, w - 6);
          ctx.lineTo(u, w + 6);
          ctx.stroke();
        }
        break;
      }
      case "point": {
        const [u, w] = toCanvas(v, it.x, it.y);
        ctx.fillStyle = COLOR.boundary;
        ctx.fillRect(u - 2, w - 2, 4, 4);
        break;
      }
      case "circle": {
        const [u, w] = toCanvas(v, it.x, it.y);
        ctx.strokeStyle = it.stale ? COLOR.stale : COLOR.hole;
        ctx.beginPath();
        ctx.arc(u, w, it.r_um * v.pxPerUm, 0, 2 * Math.PI);
        ctx.moveTo(u - 5, w - 5);
        ctx.lineTo(u + 5, w + 5);
        ctx.moveTo(u + 5, w - 5);
        ctx.lineTo(u - 5, w + 5);
        ctx.stroke();
        break;
      }
      case "candidate": {
        const [u, w] = toCanvas(v, it.x, it.y);
        ctx.strokeStyle = ctx.fillStyle = it.mark === "cross" ? COLOR.rejected : COLOR.candidate;
        ctx.beginPath();
        if (it.mark === "cross") {
          ctx.moveTo(u - 4, w - 4);
          ctx.lineTo(u + 4, w + 4);
          ctx.moveTo(u + 4, w - 4);
          ctx.lineTo(u - 4, w + 4);
          ctx.stroke();
        } else {
          ctx.arc(u, w, 4, 0, 2 * Math.PI);
          if (it.mark === "filled") ctx.fill();
          else ctx.stroke();
        }
        break;
      }
      case "flag": {
        const [u, w] = toCanvas(v, it.x, it.y);
        ctx.strokeStyle = ctx.fillStyle = COLOR.flag;
        ctx.globalAlpha = it.retired ? 0.4 : 1;
        ctx.beginPath();
        ctx.moveTo(u, w);
        ctx.lineTo(u, w - 14);
        ctx.lineTo(u + 9, w - 10);
        ctx.lineTo(u, w - 6);
        ctx.stroke();
        ctx.fillText(it.label, u + 11, w - 6);
        ctx.globalAlpha = 1;
        break;
      }
      case "pin": {
        const [u, w] = toCanvas(v, it.x, it.y);
        ctx.strokeStyle = it.refused ? COLOR.refused : COLOR.pin;
        ctx.beginPath();
        if (it.refused) {
          ctx.moveTo(u - 6, w - 6);
          ctx.lineTo(u + 6, w + 6);
          ctx.moveTo(u + 6, w - 6);
          ctx.lineTo(u - 6, w + 6);
        } else {
          ctx.arc(u, w, 6, 0, 2 * Math.PI);
        }
        ctx.stroke();
        break;
      }
    }
  }
}

function eventToStage(e: MouseEvent<HTMLCanvasElement>, v: View): [number, number] {
  const r = e.currentTarget.getBoundingClientRect();
  // jsdom reports a 0x0 rect: treat client px as canvas px
  const sx = r.width > 0 ? v.width / r.width : 1;
  const sy = r.height > 0 ? v.height / r.height : 1;
  return toStage(v, (e.clientX - r.left) * sx, (e.clientY - r.top) * sy);
}

export function MapCanvas({
  view,
  items,
  onHover,
  onPick,
  disabled,
}: {
  view: View;
  items: Item[];
  onHover: (p: [number, number] | null) => void;
  onPick: (p: [number, number]) => void;
  disabled: boolean;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const images = useRef(new Map<string, HTMLImageElement>());
  const [loaded, setLoaded] = useState(0);

  useEffect(() => {
    if (!CAN_PAINT) return;
    for (const it of items) {
      if (it.kind !== "image" || images.current.has(it.url)) continue;
      const img = new Image();
      img.onload = () => setLoaded((n) => n + 1);
      img.src = it.url;
      images.current.set(it.url, img);
    }
    const ctx = ref.current?.getContext("2d");
    if (ctx) paint(ctx, view, items, images.current);
  }, [view, items, loaded]);

  return (
    <canvas
      ref={ref}
      className="map-canvas"
      data-testid="map-canvas"
      data-disabled={disabled ? "true" : undefined}
      width={view.width}
      height={view.height}
      onMouseMove={(e) => onHover(eventToStage(e, view))}
      onMouseLeave={() => onHover(null)}
      onClick={(e) => {
        if (!disabled) onPick(eventToStage(e, view));
      }}
    />
  );
}
