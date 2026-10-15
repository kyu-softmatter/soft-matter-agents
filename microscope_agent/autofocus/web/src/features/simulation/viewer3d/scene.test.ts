import * as THREE from "three";
import { describe, expect, it, vi } from "vitest";

import { frameFromJson } from "../frame";
import { boxEdges, defaultRadius, LARGE_N, lengthScale, TrajectoryScene, typeColor } from "./scene";
import { frameJson } from "./testFrames";

describe("box", () => {
  it("draws 12 edges for a 3D box and 4 for a 2D one", () => {
    expect(boxEdges([2, 2, 2, 0, 0, 0], 3).length).toBe(12 * 6);
    expect(boxEdges([2, 2, 0, 0, 0, 0], 2).length).toBe(4 * 6);
  });

  it("centres the box on the origin and scales it", () => {
    const e = boxEdges([4, 2, 6, 0, 0, 0], 3, 2);
    const xs = e.filter((_, i) => i % 3 === 0);
    const zs = e.filter((_, i) => i % 3 === 2);
    expect(Math.min(...xs)).toBeCloseTo(-1);
    expect(Math.max(...xs)).toBeCloseTo(1);
    expect(Math.min(...zs)).toBeCloseTo(-1.5);
    expect(Math.max(...zs)).toBeCloseTo(1.5);
  });

  it("keeps a 2D box in the z = 0 plane", () => {
    const e = boxEdges([3, 3, 0, 0, 0, 0], 2);
    expect(e.filter((_, i) => i % 3 === 2).every((z) => z === 0)).toBe(true);
  });

  it("tilts a triclinic box by xy", () => {
    // a2 = (xy * Ly, Ly, 0): the top edge is shifted by xy * Ly in x.
    const e = boxEdges([2, 2, 0, 0.5, 0, 0], 2);
    const pts = Array.from({ length: e.length / 3 }, (_, i) => [e[3 * i], e[3 * i + 1]]);
    const topX = pts.filter(([, y]) => y > 0).map(([x]) => x);
    const bottomX = pts.filter(([, y]) => y < 0).map(([x]) => x);
    expect(Math.min(...topX) - Math.min(...bottomX)).toBeCloseTo(1);
  });
});

describe("scales", () => {
  it("maps the largest box edge to one scene unit, whatever the units", () => {
    expect(lengthScale(frameFromJson(frameJson({ n: 3, box: [2e-6, 3e-6, 1e-6, 0, 0, 0] })))).toBeCloseTo(3e-6);
  });

  it("falls back to the spread of the points when the box is empty", () => {
    expect(lengthScale(frameFromJson(frameJson({ n: 2, box: [0, 0, 0, 0, 0, 0], spread: 5 })))).toBeGreaterThan(0);
  });

  it("sizes particles from the number density", () => {
    const f = frameFromJson(frameJson({ n: 1000, box: [10, 10, 10, 0, 0, 0] }));
    expect(defaultRadius(f)).toBeCloseTo(0.4);
    const f2 = frameFromJson(frameJson({ n: 100, box: [10, 10, 0, 0, 0, 0], dimensions: 2 }));
    expect(defaultRadius(f2)).toBeCloseTo(0.4);
  });

  it("gives every type id a colour", () => {
    expect(typeColor(0)).not.toBe(typeColor(1));
    expect(typeColor(10)).toBe(typeColor(0));
  });
});

describe("TrajectoryScene", () => {
  it("draws one instance per particle of the frame", () => {
    const s = new TrajectoryScene();
    s.update(frameFromJson(frameJson({ n: 50 })));
    expect(s.count).toBe(50);
    expect(s.particles).toBeInstanceOf(THREE.InstancedMesh);
    expect(s.scene.children).toContain(s.particles);
    s.dispose();
  });

  it("follows the particle count from frame to frame, growing when needed", () => {
    const s = new TrajectoryScene();
    s.update(frameFromJson(frameJson({ n: 10 })));
    const first = s.particles;
    s.update(frameFromJson(frameJson({ n: 4 })));
    expect(s.count).toBe(4);
    expect(s.particles).toBe(first);
    s.update(frameFromJson(frameJson({ n: 300 })));
    expect(s.count).toBe(300);
    expect(s.scene.children.filter((c) => c instanceof THREE.InstancedMesh)).toHaveLength(1);
    s.dispose();
  });

  it("places instances at the scaled positions", () => {
    const s = new TrajectoryScene();
    const f = frameFromJson(frameJson({ n: 3, box: [4e-6, 4e-6, 4e-6, 0, 0, 0] }));
    s.update(f);
    const m = new THREE.Matrix4();
    const v = new THREE.Vector3();
    for (let i = 0; i < 3; i++) {
      s.particles.getMatrixAt(i, m);
      v.setFromMatrixPosition(m);
      expect(v.x).toBeCloseTo(f.positions[3 * i] / 4e-6);
      expect(v.y).toBeCloseTo(f.positions[3 * i + 1] / 4e-6);
      expect(v.z).toBeCloseTo(f.positions[3 * i + 2] / 4e-6);
    }
    s.dispose();
  });

  it("colours instances by type", () => {
    const s = new TrajectoryScene();
    s.update(frameFromJson(frameJson({ n: 4, types: ["A", "B"] })));
    const c = new THREE.Color();
    s.particles.getColorAt(1, c);
    expect(c.getHexString()).toBe(new THREE.Color(typeColor(1)).getHexString());
    s.dispose();
  });

  it("uses diameters when the frame carries them", () => {
    const s = new TrajectoryScene();
    const json = frameJson({ n: 2, box: [10, 10, 10, 0, 0, 0] });
    json.fields = { diameter: [2, 4] };
    s.update(frameFromJson(json));
    const m = new THREE.Matrix4();
    const scale = new THREE.Vector3();
    s.particles.getMatrixAt(1, m);
    scale.setFromMatrixScale(m);
    expect(scale.x).toBeCloseTo(2 / 10);
    s.dispose();
  });

  it("keeps one box buffer across frames instead of a new one per frame", () => {
    const s = new TrajectoryScene();
    s.update(frameFromJson(frameJson({ n: 5, index: 0 })));
    const attr = s.box.geometry.getAttribute("position");
    const version = (attr as THREE.BufferAttribute).version;
    s.update(frameFromJson(frameJson({ n: 5, index: 1 })));
    expect(s.box.geometry.getAttribute("position")).toBe(attr);
    expect((attr as THREE.BufferAttribute).version).toBe(version); // same box: not rewritten

    s.update(frameFromJson(frameJson({ n: 5, box: [12, 10, 10, 0, 0, 0] })));
    expect(s.box.geometry.getAttribute("position")).toBe(attr);
    expect((attr as THREE.BufferAttribute).version).toBeGreaterThan(version);
    const xs = (attr.array as Float32Array).filter((_, i) => i % 3 === 0);
    expect(Math.max(...xs)).toBeCloseTo(0.5);

    const geometry = s.box.geometry;
    const disposed = vi.fn();
    geometry.addEventListener("dispose", disposed);
    s.update(frameFromJson(frameJson({ n: 5, box: [10, 10, 0, 0, 0, 0], dimensions: 2 })));
    expect(disposed).toHaveBeenCalled();
    expect(s.box.geometry.getAttribute("position").count).toBe(8);
    s.dispose();
  });

  it("draws nothing for no frame", () => {
    const s = new TrajectoryScene();
    s.update(frameFromJson(frameJson({ n: 5 })));
    s.update(null);
    expect(s.count).toBe(0);
    expect(s.box.visible).toBe(false);
    s.dispose();
  });

  it("uses coarser spheres for large frames", () => {
    const s = new TrajectoryScene();
    s.update(frameFromJson(frameJson({ n: 10 })));
    const fine = (s.particles.geometry as THREE.SphereGeometry).parameters.widthSegments;
    s.update(frameFromJson(frameJson({ n: LARGE_N + 1 })));
    expect(s.count).toBe(LARGE_N + 1);
    expect((s.particles.geometry as THREE.SphereGeometry).parameters.widthSegments).toBeLessThan(fine);
    s.dispose();
  });

  it("looks straight down z at a 2D run", () => {
    const s = new TrajectoryScene();
    s.update(frameFromJson(frameJson({ n: 5, box: [5, 5, 0, 0, 0, 0], dimensions: 2 })));
    expect(s.camera.position.x).toBe(0);
    expect(s.camera.position.y).toBe(0);
    expect(s.camera.position.z).toBeGreaterThan(0);
    s.dispose();
  });
});
