// Frames for the viewer3d tests, in the server's JSON form (Python Frame.to_dict).
import type { FrameJson } from "../frame";

export interface FrameSpec {
  n: number;
  index?: number;
  step?: number | null;
  box?: [number, number, number, number, number, number];
  dimensions?: 2 | 3;
  types?: string[];
  /** Half-width of the cube the points fill when the box is empty. */
  spread?: number;
}

/** `n` particles spread over the box (deterministic), type ids cycling through `types`. */
export function frameJson({
  n,
  index = 0,
  step = 0,
  box = [10, 10, 10, 0, 0, 0],
  dimensions = box[2] === 0 ? 2 : 3,
  types = ["A"],
  spread = 1,
}: FrameSpec): FrameJson {
  const positions: number[] = [];
  const half = box.slice(0, 3).map((l) => (l > 0 ? l / 2 : spread));
  for (let i = 0; i < n; i++) {
    const u = ((i * 0.618034) % 1) * 2 - 1;
    const v = ((i * 0.414214) % 1) * 2 - 1;
    const w = ((i * 0.732051) % 1) * 2 - 1;
    positions.push(u * half[0], v * half[1], dimensions === 3 ? w * half[2] : 0);
  }
  return {
    index,
    step,
    n,
    dimensions,
    units: "m",
    box: [...box],
    types: [...types],
    typeid: Array.from({ length: n }, (_, i) => i % types.length),
    positions,
    fields: {},
  };
}
