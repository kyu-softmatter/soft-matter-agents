import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

import type { Frame } from "../frame";
import { TrajectoryScene, typeColor } from "./scene";
import "./viewer3d.css";

/** What the viewer needs from a renderer. Tests pass a fake: jsdom has no WebGL. */
export interface Renderer {
  setPixelRatio(ratio: number): void;
  setSize(width: number, height: number, updateStyle?: boolean): void;
  render(scene: THREE.Scene, camera: THREE.Camera): void;
  dispose(): void;
}

export type CreateRenderer = (canvas: HTMLCanvasElement) => Renderer;

export const createWebGLRenderer: CreateRenderer = (canvas) =>
  new THREE.WebGLRenderer({ canvas, antialias: true });

export interface Viewer3DProps {
  /** The frame to draw; the shared playback controls outside the viewer choose it. */
  frame: Frame | null;
  createRenderer?: CreateRenderer;
}

interface Parts {
  scene: TrajectoryScene;
  renderer: Renderer;
  controls: OrbitControls;
  draw: () => void;
}

/**
 * The 3D trajectory viewer (PLAN 2절 F6.3). Draws one frame at a time with GPU instancing,
 * the box edges, and a camera to rotate (drag), zoom (wheel) and pan (right drag). It renders
 * only when the frame, the camera or the size changes.
 */
export function Viewer3D({ frame, createRenderer = createWebGLRenderer }: Viewer3DProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const partsRef = useRef<Parts | null>(null);
  const frameRef = useRef(frame);
  frameRef.current = frame;
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    if (!wrap || !canvas) return;
    let renderer: Renderer;
    try {
      renderer = createRenderer(canvas);
    } catch (e) {
      setFailed(e instanceof Error ? e.message : String(e));
      return;
    }
    const scene = new TrajectoryScene();
    const controls = new OrbitControls(scene.camera, canvas);
    const draw = () => renderer.render(scene.scene, scene.camera);
    controls.addEventListener("change", draw);
    renderer.setPixelRatio(window.devicePixelRatio || 1);

    const resize = () => {
      const w = wrap.clientWidth;
      const h = wrap.clientHeight;
      if (w > 0 && h > 0) {
        renderer.setSize(w, h, false);
        scene.setAspect(w, h);
      }
      draw();
    };
    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(resize);
      observer.observe(wrap);
    } else {
      window.addEventListener("resize", resize);
    }
    partsRef.current = { scene, renderer, controls, draw };
    scene.update(frameRef.current);
    resize();

    return () => {
      partsRef.current = null;
      observer?.disconnect();
      window.removeEventListener("resize", resize);
      controls.removeEventListener("change", draw);
      controls.dispose();
      scene.dispose();
      renderer.dispose();
    };
  }, [createRenderer]);

  useEffect(() => {
    const parts = partsRef.current;
    if (!parts || parts.scene.frame === frame) return;
    const before = parts.scene.frame?.dimensions;
    parts.scene.update(frame);
    if (frame && frame.dimensions !== before) {
      parts.controls.target.set(0, 0, 0);
      parts.controls.update();
    }
    parts.draw();
  }, [frame]);

  const resetView = () => {
    const parts = partsRef.current;
    if (!parts) return;
    parts.scene.resetCamera();
    parts.controls.target.set(0, 0, 0);
    parts.controls.update();
    parts.draw();
  };

  return (
    <div className="viewer3d" ref={wrapRef}>
      <canvas className="viewer3d-canvas" ref={canvasRef} aria-label="3D trajectory view" />
      {failed !== null ? (
        <p className="viewer3d-message" role="alert">
          The 3D view needs WebGL, which this browser could not start: {failed}
        </p>
      ) : frame === null ? (
        <p className="viewer3d-message">No frame to show.</p>
      ) : null}
      {failed === null && frame !== null && (
        <div className="viewer3d-overlay">
          <div className="viewer3d-info">
            Frame {frame.index}
            {frame.step !== null && <> · step {frame.step}</>}
            {" · "}
            {frame.n} particles{frame.dimensions === 2 && " · 2D"}
          </div>
          <ul className="viewer3d-legend" aria-label="Particle types">
            {frame.types.map((t, i) => (
              <li key={`${i}-${t}`}>
                <span className="viewer3d-swatch" style={{ background: typeColor(i) }} />
                {t}
              </li>
            ))}
          </ul>
          <button type="button" className="viewer3d-reset" onClick={resetView}>
            Reset view
          </button>
          <div className="viewer3d-hint">Drag to rotate · wheel to zoom · right-drag to pan</div>
        </div>
      )}
    </div>
  );
}
