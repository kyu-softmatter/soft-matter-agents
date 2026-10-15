import { useEffect, useRef, useState } from "react";

import type { CamFrame } from "./LiveView";

const GREEN = "#00ff00";
const MAGENTA = "#ff00ff";

/**
 * The colour a camera gets in the merged view: the blue camera green, the red camera
 * magenta (a pair that stays readable with red-green colour blindness); others by order.
 * Where both are bright the merge turns white.
 */
export function mergeColor(camera: string, index: number): string {
  if (/blue/i.test(camera)) return GREEN;
  if (/red/i.test(camera)) return MAGENTA;
  return index % 2 === 0 ? GREEN : MAGENTA;
}

/** Decode from the JPEG bytes, not the blob URL: the live view frees a camera's URL as soon
 * as its next frame arrives, which can be before an image loaded from it finishes. */
const decode = (jpeg: Blob): Promise<ImageBitmap> => createImageBitmap(jpeg);

/**
 * One canvas: each camera's 8-bit frame tinted with its colour and added up. The
 * frames are the server's display-scaled JPEGs, so each camera keeps its own
 * display range; the size is the first camera's, others are scaled onto it.
 */
export function MergedView({ frames }: { frames: CamFrame[] }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [error, setError] = useState<string | null>(null);
  const key = frames.map((f) => f.url).join(" ");

  useEffect(() => {
    let live = true;
    const out = canvas.current;
    const ctx = out?.getContext("2d") ?? null;
    if (!out || !ctx) {
      setError("This browser cannot draw the merged view.");
      return;
    }
    if (typeof createImageBitmap !== "function") {
      setError("This browser cannot draw the merged view.");
      return;
    }
    Promise.all(frames.map((f) => decode(f.jpeg))).then(
      (imgs) => {
        if (!live) {
          imgs.forEach((b) => b.close());
          return;
        }
        const w = imgs[0].width;
        const h = imgs[0].height;
        out.width = w;
        out.height = h;
        const tint = document.createElement("canvas");
        tint.width = w;
        tint.height = h;
        const t = tint.getContext("2d");
        if (!t) return;
        ctx.globalCompositeOperation = "source-over";
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, w, h);
        imgs.forEach((img, i) => {
          t.globalCompositeOperation = "source-over";
          t.drawImage(img, 0, 0, w, h);
          t.globalCompositeOperation = "multiply";
          t.fillStyle = mergeColor(frames[i].camera, i);
          t.fillRect(0, 0, w, h);
          ctx.globalCompositeOperation = "lighter";
          ctx.drawImage(tint, 0, 0);
        });
        imgs.forEach((b) => b.close());
        setError(null);
      },
      (e) => live && setError(e instanceof Error ? e.message : String(e)),
    );
    return () => {
      live = false;
    };
    // keyed on the urls: they change with every frame, while `frames` is rebuilt each render
  }, [key]);

  return (
    <>
      <canvas ref={canvas} className="live-frame" aria-label="Merged camera frame" role="img" />
      {error && <p className="muted">{error}</p>}
    </>
  );
}
