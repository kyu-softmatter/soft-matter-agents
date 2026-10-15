import { type ReactNode, useEffect, useRef, useState } from "react";

import { useClient } from "../client";
import { EncoderZ } from "../Verdict";
import { FpsMeter, type FrameMeta, FramePairer } from "./frames";
import { MergedView, mergeColor } from "./MergedView";
import { frameScale } from "./PatternOverlay";

type Conn = "connecting" | "open" | "closed" | "unsupported";

/** Several cameras: both at once, one composite, or one of them. */
export type Mode = "side" | "merged" | `one:${string}`;

/** Shown whenever more than one camera is on screen: the frames are paired by the host
 * clock, not a hardware trigger (the server's `time_base: "software"`). */
export const TIME_BASE_NOTE =
  "Frames overlaid by host arrival time, not simultaneous; display only. " +
  "No timing, correlation or coincidence analysis from this view. " +
  "Simultaneous capture is a hardware-triggered soft-matter-agents plan.";

export interface CamFrame {
  camera: string;
  url: string;
  /** the JPEG itself: the merged view decodes this, never `url`, which is freed on the next frame */
  jpeg: Blob;
  meta: FrameMeta;
  fps: number | null;
}

const RETRY_MS = 2000;

// a module constant: a new default function on every render would reconnect each time
const performanceNow = () => performance.now();

/** The camera a frame came from; "" when the server names none (one-camera engines). */
const cameraOf = (meta: FrameMeta) => meta.camera ?? "";

function FrameInfo({ frame, testIds }: { frame: CamFrame; testIds: boolean }) {
  const { meta, fps } = frame;
  const id = (s: string) => (testIds ? s : undefined);
  const z = meta.meta && typeof meta.meta.z_um === "number" ? (meta.meta.z_um as number) : null;
  return (
    <>
      <span data-testid={id("live-time")}>frame {new Date(meta.t * 1000).toLocaleTimeString()}</span>
      <span data-testid={id("live-fps")}>{fps === null ? "— fps" : `${fps.toFixed(1)} fps`}</span>
      <span className="muted" data-testid={id("live-size")}>
        #{meta.seq} · {meta.width}×{meta.height} (bin {meta.binning} of {meta.source_width}×{meta.source_height}) ·
        display {meta.display_min.toFixed(0)}–{meta.display_max.toFixed(0)} counts
      </span>
      {z !== null && (
        <span
          data-testid={id("live-z")}
          title="ZDrive encoder read when the frame was taken from the camera buffer; it can lag the exposure"
        >
          <EncoderZ readbackUm={z} />
        </span>
      )}
    </>
  );
}

/** Something drawn over a frame (the pattern overlay), sized to that frame. */
export type Overlay = (frame: CamFrame) => ReactNode;

/** A click on a frame, in um from the centre of the field (x right, y down as on the image). */
export type FramePick = (p: { camera: string; x_um: number; y_um: number; scaleKnown: boolean }) => void;

function Stack({
  frame,
  overlay,
  onPick,
  children,
}: {
  frame: CamFrame;
  overlay?: Overlay;
  onPick?: FramePick;
  children: ReactNode;
}) {
  if (!overlay && !onPick) return <>{children}</>;
  const pick = onPick
    ? (e: React.MouseEvent<HTMLDivElement>) => {
        const box = e.currentTarget.getBoundingClientRect();
        if (box.width <= 0 || box.height <= 0) return;
        const { umPerPx, known } = frameScale(frame.meta);
        const px = ((e.clientX - box.left) / box.width) * frame.meta.width;
        const py = ((e.clientY - box.top) / box.height) * frame.meta.height;
        onPick({
          camera: frame.camera,
          x_um: (px - frame.meta.width / 2) * umPerPx,
          y_um: (py - frame.meta.height / 2) * umPerPx,
          scaleKnown: known,
        });
      }
    : undefined;
  return (
    <div className={onPick ? "live-stack live-pick" : "live-stack"} onClick={pick} data-testid="live-stack">
      {children}
      {overlay?.(frame)}
    </div>
  );
}

function CameraPanel({ frame, overlay, onPick }: { frame: CamFrame; overlay?: Overlay; onPick?: FramePick }) {
  return (
    <figure className="live-panel" aria-label={`Camera ${frame.camera}`}>
      <figcaption className="live-info">
        <strong>{frame.camera}</strong>
        <FrameInfo frame={frame} testIds={false} />
      </figcaption>
      <Stack frame={frame} overlay={overlay} onPick={onPick}>
        <img className="live-frame" src={frame.url} alt={`Live frame ${frame.camera}`} />
      </Stack>
    </figure>
  );
}

/**
 * The live view: the server bins each camera frame to about 800 px and sends it
 * as JPEG (T-009 /ws/frames, about 10 fps per camera). With one camera it shows
 * the frame, its time and the receive rate. With two (the dual-camera stand)
 * both arrive on the same socket, told apart by `camera`: side by side, merged
 * (blue camera green, red camera magenta) or one at a time. Display only: raw
 * frames stay on disk, and the two cameras' frames are paired by host arrival time
 * (`time_base: "software"`), not by a hardware trigger, so nothing about timing,
 * correlation or coincidence may be read off a side-by-side or merged view (P-01;
 * simultaneous capture is a hardware-triggered soft-matter-agents plan).
 */
export function LiveView({
  now = performanceNow,
  overlay,
  onPick,
  onFrame,
}: {
  now?: () => number;
  overlay?: Overlay;
  /** a click on a frame (the Tweezers area moves the chosen trap there) */
  onPick?: FramePick;
  /** every frame as it arrives (the focus panel keeps their scores and z) */
  onFrame?: (frame: CamFrame) => void;
}) {
  const client = useClient();
  // a ref, so a new callback each render does not reconnect the socket
  const frameSink = useRef(onFrame);
  frameSink.current = onFrame;
  const [cams, setCams] = useState<Record<string, CamFrame>>({});
  const [mode, setMode] = useState<Mode>("side");
  const [conn, setConn] = useState<Conn>("connecting");
  const [detail, setDetail] = useState<string | null>(null);
  const urls = useRef(new Map<string, string>());

  useEffect(() => {
    let live = true;
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let unsupported = false; // the engine has no frames: do not retry
    const pairer = new FramePairer();
    const meters = new Map<string, FpsMeter>();
    const held = urls.current;

    const connect = () => {
      if (!live) return;
      setConn("connecting");
      const ws = client.transport.openSocket("/ws/frames");
      socket = ws;
      ws.binaryType = "blob";
      ws.onopen = () => live && setConn("open");
      ws.onmessage = (msg) => {
        if (!live) return;
        const got = pairer.feed(msg.data);
        if (!got) return;
        if (got.kind === "error") {
          setDetail(got.detail);
          if (got.status === 501) {
            unsupported = true;
            setConn("unsupported");
          }
          return;
        }
        const camera = cameraOf(got.meta);
        const next = URL.createObjectURL(got.jpeg);
        const old = held.get(camera);
        if (old) URL.revokeObjectURL(old);
        held.set(camera, next);
        let meter = meters.get(camera);
        if (!meter) meters.set(camera, (meter = new FpsMeter()));
        const fps = meter.tick(now());
        const frame: CamFrame = { camera, url: next, jpeg: got.jpeg, meta: got.meta, fps };
        setCams((c) => ({ ...c, [camera]: frame }));
        frameSink.current?.(frame);
      };
      ws.onclose = () => {
        socket = null;
        if (!live || unsupported) return;
        setConn("closed");
        timer = setTimeout(connect, RETRY_MS);
      };
    };
    connect();
    return () => {
      live = false;
      if (timer) clearTimeout(timer);
      socket?.close();
      held.forEach((u) => URL.revokeObjectURL(u));
      held.clear();
    };
  }, [client, now]);

  const names = Object.keys(cams).sort();
  const frames = names.map((n) => cams[n]);
  const single = frames.length === 1 ? frames[0] : null;
  const shown: Mode = mode.startsWith("one:") && !cams[mode.slice(4)] ? "side" : mode;

  return (
    <div className="live">
      <div className="live-info" data-testid="live-info">
        <span data-testid="live-conn">
          {conn === "open" ? "frames: connected" : conn === "unsupported" ? "frames: not available" : `frames: ${conn}`}
        </span>
        {single && <FrameInfo frame={single} testIds />}
        {frames.length > 1 && (
          <span className="live-modes" role="group" aria-label="Camera view">
            {(["side", "merged", ...names.map((n) => `one:${n}` as const)] as Mode[]).map((m) => (
              <button key={m} type="button" aria-pressed={shown === m} onClick={() => setMode(m)}>
                {m === "side" ? "Side by side" : m === "merged" ? "Merged" : m.slice(4)}
              </button>
            ))}
          </span>
        )}
      </div>
      {detail && conn === "unsupported" && <p className="muted">{detail}</p>}
      {frames.length > 1 && (
        <p className="muted" data-testid="live-timebase">
          {TIME_BASE_NOTE}
        </p>
      )}
      {frames.length === 0 && <p className="muted">No frame yet.</p>}
      {single && (
        <Stack frame={single} overlay={overlay} onPick={onPick}>
          <img className="live-frame" src={single.url} alt="Live camera frame" />
        </Stack>
      )}
      {frames.length > 1 && shown === "side" && (
        <div className="live-side">
          {frames.map((f) => (
            <CameraPanel key={f.camera} frame={f} overlay={overlay} onPick={onPick} />
          ))}
        </div>
      )}
      {frames.length > 1 && shown === "merged" && (
        <figure className="live-panel" aria-label="Merged cameras">
          <figcaption className="live-info">
            {frames.map((f, i) => (
              <span key={f.camera} className="live-legend">
                <span className="live-swatch" style={{ background: mergeColor(f.camera, i) }} /> {f.camera} #{f.meta.seq}
              </span>
            ))}
          </figcaption>
          <Stack frame={frames[0]} overlay={overlay} onPick={onPick}>
            <MergedView frames={frames} />
          </Stack>
        </figure>
      )}
      {frames.length > 1 && shown.startsWith("one:") && <CameraPanel frame={cams[shown.slice(4)]} overlay={overlay} onPick={onPick} />}
    </div>
  );
}
