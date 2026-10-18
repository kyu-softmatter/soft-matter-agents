// The 3D trajectory scene, kept apart from the WebGL renderer so it can be tested in jsdom.
//
// One InstancedMesh draws every particle; its colour per instance comes from the type id.
// Positions arrive in metres (see ../frame.ts); the scene divides them by the largest box edge,
// so the box is about one unit across whatever the run's length scale is. The box follows GSD:
// [Lx, Ly, Lz, xy, xz, yz], centred on the origin, Lz = 0 for a 2D run.

import * as THREE from "three";

import type { Frame } from "../frame";

// Colours for type ids 0, 1, ...; repeats past the end.
export const TYPE_COLORS = [
  "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
  "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
];

export function typeColor(typeid: number): string {
  return TYPE_COLORS[((typeid % TYPE_COLORS.length) + TYPE_COLORS.length) % TYPE_COLORS.length];
}

type Box = Frame["box"];

/** The length that maps to one scene unit: the largest box edge, or the spread of the points. */
export function lengthScale(frame: Frame): number {
  const [lx, ly, lz] = frame.box;
  const edge = Math.max(Math.abs(lx), Math.abs(ly), Math.abs(lz));
  if (edge > 0 && Number.isFinite(edge)) return edge;
  let m = 0;
  for (const v of frame.positions) if (Number.isFinite(v)) m = Math.max(m, Math.abs(v));
  return m > 0 ? 2 * m : 1;
}

/** The box corners, in metres. 8 for a 3D box, 4 (z = 0) for a 2D one. */
export function boxCorners(box: Box, dimensions: 2 | 3): THREE.Vector3[] {
  const [lx, ly, lz, xy, xz, yz] = box;
  const a1 = new THREE.Vector3(lx, 0, 0);
  const a2 = new THREE.Vector3(xy * ly, ly, 0);
  const a3 = dimensions === 3 ? new THREE.Vector3(xz * lz, yz * lz, lz) : new THREE.Vector3();
  const origin = a1.clone().add(a2).add(a3).multiplyScalar(-0.5);
  const ks = dimensions === 3 ? [0, 1] : [0];
  const out: THREE.Vector3[] = [];
  for (const k of ks)
    for (const [i, j] of [[0, 0], [1, 0], [1, 1], [0, 1]])
      out.push(origin.clone().addScaledVector(a1, i).addScaledVector(a2, j).addScaledVector(a3, k));
  return out;
}

/** Line segment end points of the box edges, flat [x, y, z, ...]: 12 edges in 3D, 4 in 2D. */
export function boxEdges(box: Box, dimensions: 2 | 3, scale = 1): Float32Array {
  const c = boxCorners(box, dimensions);
  const pairs: [number, number][] = [[0, 1], [1, 2], [2, 3], [3, 0]];
  if (dimensions === 3) pairs.push([4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]);
  const out = new Float32Array(pairs.length * 6);
  pairs.forEach(([a, b], e) => {
    out.set([c[a].x, c[a].y, c[a].z, c[b].x, c[b].y, c[b].z].map((v) => v / scale), e * 6);
  });
  return out;
}

/**
 * A drawing radius in metres when the frame has no diameters: a bit under half the mean
 * spacing, so particles at the average density do not overlap.
 */
export function defaultRadius(frame: Frame): number {
  const [lx, ly, lz] = frame.box.map(Math.abs);
  const n = Math.max(frame.n, 1);
  const spacing = frame.dimensions === 3 && lz > 0 ? Math.cbrt((lx * ly * lz) / n)
    : lx > 0 && ly > 0 ? Math.sqrt((lx * ly) / n) : lengthScale(frame) / Math.cbrt(n);
  return 0.4 * spacing;
}

/** Per-particle radii in metres: half of `fields.diameter` when the frame carries it. */
function radii(frame: Frame): (i: number) => number {
  const d = frame.fields.diameter;
  const r0 = defaultRadius(frame);
  if (Array.isArray(d) && d.length === frame.n) {
    return (i) => (Number.isFinite(d[i]) && d[i] > 0 ? d[i] / 2 : r0);
  }
  return () => r0;
}

const SPHERE_SEGMENTS = { wide: 16, high: 12 };
const SMALL_SPHERE_SEGMENTS = { wide: 8, high: 6 }; // over LARGE_N particles
export const LARGE_N = 20_000;

/** The scene graph for one trajectory: particles, box and lights. `update` takes each frame. */
export class TrajectoryScene {
  readonly scene = new THREE.Scene();
  readonly camera = new THREE.PerspectiveCamera(45, 1, 0.01, 100);
  readonly box: THREE.LineSegments;
  particles: THREE.InstancedMesh;
  /** The frame now drawn, or null before the first one. */
  frame: Frame | null = null;
  private dimensions: 2 | 3 | null = null;
  private boxKey = "";
  private material = new THREE.MeshStandardMaterial({ roughness: 0.6, metalness: 0.0 });
  private matrix = new THREE.Matrix4();
  private color = new THREE.Color();

  constructor() {
    this.scene.background = new THREE.Color("#101418");
    this.scene.add(new THREE.AmbientLight("#ffffff", 0.6));
    const sun = new THREE.DirectionalLight("#ffffff", 1.6);
    sun.position.set(1, 2, 3);
    this.scene.add(sun);
    this.box = new THREE.LineSegments(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({ color: "#c8d0d8" }),
    );
    this.scene.add(this.box);
    this.particles = this.makeMesh(0, false);
    this.scene.add(this.particles);
  }

  /** How many particles are drawn. */
  get count(): number {
    return this.particles.count;
  }

  update(frame: Frame | null): void {
    this.frame = frame;
    if (frame === null) {
      this.particles.count = 0;
      this.box.visible = false;
      return;
    }
    const scale = lengthScale(frame);
    this.setBox(frame.box, frame.dimensions, scale);
    this.box.visible = true;

    const n = frame.n;
    const small = n > LARGE_N;
    if (n > this.particles.instanceMatrix.count || this.isSmall() !== small) {
      this.scene.remove(this.particles);
      this.disposeMesh(this.particles);
      this.particles = this.makeMesh(Math.max(n, 1), small);
      this.scene.add(this.particles);
    }
    const r = radii(frame);
    const p = frame.positions;
    for (let i = 0; i < n; i++) {
      const s = r(i) / scale;
      this.matrix.makeScale(s, s, s).setPosition(p[3 * i] / scale, p[3 * i + 1] / scale, p[3 * i + 2] / scale);
      this.particles.setMatrixAt(i, this.matrix);
      this.particles.setColorAt(i, this.color.set(typeColor(frame.typeid[i] ?? 0)));
    }
    this.particles.count = n;
    this.particles.instanceMatrix.needsUpdate = true;
    if (this.particles.instanceColor) this.particles.instanceColor.needsUpdate = true;
    this.particles.computeBoundingSphere();

    if (this.dimensions !== frame.dimensions) {
      this.dimensions = frame.dimensions;
      this.resetCamera();
    }
  }

  /** Back to the starting view: oblique for 3D, straight down the z axis for 2D. */
  resetCamera(): void {
    const d = 2.2;
    if (this.dimensions === 2) this.camera.position.set(0, 0, d);
    else this.camera.position.set(d * 0.6, d * 0.45, d * 0.75);
    this.camera.up.set(0, 1, 0);
    this.camera.lookAt(0, 0, 0);
    this.camera.updateProjectionMatrix();
  }

  setAspect(width: number, height: number): void {
    if (width <= 0 || height <= 0) return;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  dispose(): void {
    this.disposeMesh(this.particles);
    this.box.geometry.dispose();
    (this.box.material as THREE.Material).dispose();
    this.material.dispose();
  }

  /**
   * Box edges, rewritten only when the box changes. The same attribute is reused while the
   * edge count stays the same, so playback does not leave a GPU buffer behind per frame.
   */
  private setBox(box: Box, dimensions: 2 | 3, scale: number): void {
    const key = [...box, dimensions, scale].join(",");
    if (key === this.boxKey) return;
    this.boxKey = key;
    const edges = boxEdges(box, dimensions, scale);
    const old = this.box.geometry.getAttribute("position") as THREE.BufferAttribute | undefined;
    if (old && old.array.length === edges.length) {
      (old.array as Float32Array).set(edges);
      old.needsUpdate = true;
    } else {
      // A new edge count (2D <-> 3D): a fresh geometry, so the old buffer is freed.
      this.box.geometry.dispose();
      this.box.geometry = new THREE.BufferGeometry();
      this.box.geometry.setAttribute("position", new THREE.BufferAttribute(edges, 3));
    }
    this.box.geometry.computeBoundingSphere();
  }

  private isSmall(): boolean {
    const g = this.particles.geometry as THREE.SphereGeometry;
    return g.parameters.widthSegments === SMALL_SPHERE_SEGMENTS.wide;
  }

  private makeMesh(capacity: number, small: boolean): THREE.InstancedMesh {
    const seg = small ? SMALL_SPHERE_SEGMENTS : SPHERE_SEGMENTS;
    const mesh = new THREE.InstancedMesh(
      new THREE.SphereGeometry(1, seg.wide, seg.high),
      this.material,
      Math.max(capacity, 1),
    );
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    mesh.count = 0;
    mesh.frustumCulled = false;
    return mesh;
  }

  private disposeMesh(mesh: THREE.InstancedMesh): void {
    mesh.geometry.dispose();
    mesh.dispose();
  }
}
