import { act, fireEvent, render, screen } from "@testing-library/react";
import { useMemo } from "react";
import * as THREE from "three";
import { describe, expect, it, vi } from "vitest";

import { fakeClient } from "../fakeClient";
import { frameFromJson, type Frame } from "../frame";
import { usePlayback } from "../playback";
import { frameJson } from "./testFrames";
import { Viewer3D, type CreateRenderer, type Renderer } from "./index";

/** A renderer that records what it was asked to draw, since jsdom has no WebGL. */
function fakeRenderer() {
  const drawn: { count: number; camera: THREE.Vector3 }[] = [];
  const renderer: Renderer = {
    setPixelRatio: vi.fn(),
    setSize: vi.fn(),
    render: vi.fn((scene: THREE.Scene, camera: THREE.Camera) => {
      const mesh = scene.children.find((c): c is THREE.InstancedMesh => c instanceof THREE.InstancedMesh);
      drawn.push({ count: mesh?.count ?? -1, camera: camera.position.clone() });
    }),
    dispose: vi.fn(),
  };
  const create: CreateRenderer = vi.fn(() => renderer);
  return { renderer, create, drawn, last: () => drawn[drawn.length - 1] };
}

const frames: Frame[] = [12, 20, 7].map((n, index) =>
  frameFromJson(frameJson({ n, index, step: index * 100, types: ["A", "B"] })),
);

describe("Viewer3D", () => {
  it("draws the frame it is given, one instance per particle", () => {
    const r = fakeRenderer();
    render(<Viewer3D frame={frames[0]} createRenderer={r.create} />);
    expect(r.create).toHaveBeenCalledTimes(1);
    expect(r.last().count).toBe(12);
    expect(screen.getByText(/Frame 0 · step 0 · 12 particles/)).toBeTruthy();
  });

  it("redraws when the frame changes, without a new renderer", () => {
    const r = fakeRenderer();
    const { rerender } = render(<Viewer3D frame={frames[0]} createRenderer={r.create} />);
    rerender(<Viewer3D frame={frames[1]} createRenderer={r.create} />);
    expect(r.last().count).toBe(20);
    expect(r.create).toHaveBeenCalledTimes(1);
  });

  it("does not redraw for the same frame", () => {
    const r = fakeRenderer();
    const { rerender } = render(<Viewer3D frame={frames[0]} createRenderer={r.create} />);
    const before = r.drawn.length;
    rerender(<Viewer3D frame={frames[0]} createRenderer={r.create} />);
    expect(r.drawn.length).toBe(before);
  });

  it("shows a message and draws no particles without a frame", () => {
    const r = fakeRenderer();
    render(<Viewer3D frame={null} createRenderer={r.create} />);
    expect(screen.getByText("No frame to show.")).toBeTruthy();
    expect(r.drawn.every((d) => d.count <= 0)).toBe(true);
  });

  it("lists the particle types", () => {
    const r = fakeRenderer();
    render(<Viewer3D frame={frames[0]} createRenderer={r.create} />);
    const legend = screen.getByRole("list", { name: "Particle types" });
    expect(legend.textContent).toBe("AB");
  });

  it("puts the camera back on Reset view", () => {
    const r = fakeRenderer();
    render(<Viewer3D frame={frames[0]} createRenderer={r.create} />);
    const start = r.last().camera.clone();
    const camera = vi.mocked(r.renderer.render).mock.calls[0][1];
    camera.position.set(5, -3, 1); // as a drag would
    fireEvent.click(screen.getByRole("button", { name: "Reset view" }));
    expect(r.last().camera.distanceTo(start)).toBeCloseTo(0);
  });

  it("says so when WebGL cannot start", () => {
    const create: CreateRenderer = () => {
      throw new Error("no WebGL context");
    };
    render(<Viewer3D frame={frames[0]} createRenderer={create} />);
    expect(screen.getByRole("alert").textContent).toContain("needs WebGL");
  });

  it("frees the renderer on unmount", () => {
    const r = fakeRenderer();
    const { unmount } = render(<Viewer3D frame={frames[0]} createRenderer={r.create} />);
    unmount();
    expect(r.renderer.dispose).toHaveBeenCalled();
  });
});

describe("Viewer3D on the mock trajectories", () => {
  it("draws the fake client's 3D and 2D runs", async () => {
    const client = fakeClient(() => 0);
    const r = fakeRenderer();
    const f3 = frameFromJson(await client.getFrame("mock-sim-3d-fault", 0));
    const { rerender } = render(<Viewer3D frame={f3} createRenderer={r.create} />);
    expect(r.last().count).toBe(128);
    const f3b = frameFromJson(await client.getFrame("mock-sim-3d-fault", 5));
    rerender(<Viewer3D frame={f3b} createRenderer={r.create} />);
    expect(screen.getByText(/Frame 5 · step 250 · 128 particles/)).toBeTruthy();

    const f2 = frameFromJson(await client.getFrame("mock-sim-2d-done", 0));
    rerender(<Viewer3D frame={f2} createRenderer={r.create} />);
    expect(r.last().count).toBe(64);
    expect(r.last().camera.x).toBeCloseTo(0);
    expect(r.last().camera.y).toBeCloseTo(0);
    expect(screen.getByText(/64 particles · 2D/)).toBeTruthy();
  });
});

describe("Viewer3D with the shared playback controls", () => {
  function Screen({ create }: { create: CreateRenderer }) {
    const p = usePlayback(frames.length);
    const frame = useMemo(() => frames[p.index] ?? null, [p.index]);
    return (
      <>
        <button type="button" onClick={() => p.setIndex(p.index + 1)}>next</button>
        <button type="button" onClick={() => p.setIndex(0)}>first</button>
        <Viewer3D frame={frame} createRenderer={create} />
      </>
    );
  }

  it("draws the frame the controls step to", () => {
    const r = fakeRenderer();
    render(<Screen create={r.create} />);
    expect(r.last().count).toBe(12);
    fireEvent.click(screen.getByRole("button", { name: "next" }));
    expect(r.last().count).toBe(20);
    fireEvent.click(screen.getByRole("button", { name: "next" }));
    expect(r.last().count).toBe(7);
    fireEvent.click(screen.getByRole("button", { name: "first" }));
    expect(r.last().count).toBe(12);
    expect(r.create).toHaveBeenCalledTimes(1);
  });

  it("follows playback as it plays", () => {
    vi.useFakeTimers();
    try {
      const r = fakeRenderer();
      function Playing() {
        const p = usePlayback(frames.length);
        return (
          <>
            <button type="button" onClick={p.play}>play</button>
            <Viewer3D frame={frames[p.index] ?? null} createRenderer={r.create} />
          </>
        );
      }
      render(<Playing />);
      fireEvent.click(screen.getByRole("button", { name: "play" }));
      for (let t = 0; t < 100; t++) {
        act(() => {
          vi.advanceTimersByTime(50);
        });
      }
      const counts = r.drawn.map((d) => d.count);
      expect(counts).toContain(20);
      expect(counts).toContain(7);
    } finally {
      vi.useRealTimers();
    }
  });
});
