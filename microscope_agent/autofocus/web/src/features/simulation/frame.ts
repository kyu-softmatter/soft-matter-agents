/**
 * The trajectory frame both viewers draw (PLAN 2절 F6.3): the 2D Canvas viewer here and the 3D
 * Three.js viewer in `viewer3d/` (T-022). The server sends `FrameJson`, which is Python
 * `agents.simulation.Frame.to_dict()` field for field; `frameFromJson` turns it into typed arrays.
 */

/** GSD box order: [Lx, Ly, Lz, xy, xz, yz]. A 2D run has Lz = 0. */
export type Box = [number, number, number, number, number, number];

/** A frame as the server sends it. */
export interface FrameJson {
  index: number;
  step: number | null;
  n: number;
  dimensions: number;
  units: string;
  box: number[];
  types: string[];
  typeid: number[];
  /** flat [x0, y0, z0, x1, ...], 3 per particle; z = 0 in 2D */
  positions: number[];
  /** per-particle arrays the client asked for, one row per particle (rows may be lists) */
  fields: Record<string, unknown>;
}

export interface Frame {
  index: number;
  step: number | null;
  n: number;
  dimensions: 2 | 3;
  /** unit of positions and box, "m" for every run so far */
  units: string;
  box: Box;
  types: string[];
  typeid: Int32Array;
  /** flat x, y, z per particle, length 3n */
  positions: Float32Array;
  /**
   * Requested per-particle fields, flattened row by row: `fields[k].length / n` values per
   * particle (1 for a scalar such as "diameter", 4 for a quaternion "orientation").
   */
  fields: Record<string, number[]>;
}

export class FrameFormatError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "FrameFormatError";
  }
}

/** Check and convert a server frame. Throws FrameFormatError when the lengths do not match. */
export function frameFromJson(json: FrameJson): Frame {
  const { n } = json;
  if (!Number.isInteger(n) || n < 0) throw new FrameFormatError(`bad particle count ${n}`);
  if (json.positions.length !== 3 * n) {
    throw new FrameFormatError(`positions has ${json.positions.length} values for ${n} particles`);
  }
  if (json.typeid.length !== n) {
    throw new FrameFormatError(`typeid has ${json.typeid.length} values for ${n} particles`);
  }
  if (json.box.length !== 6) throw new FrameFormatError(`box has ${json.box.length} values, not 6`);
  if (json.dimensions !== 2 && json.dimensions !== 3) {
    throw new FrameFormatError(`dimensions must be 2 or 3, got ${json.dimensions}`);
  }
  const fields: Record<string, number[]> = {};
  for (const [name, rows] of Object.entries(json.fields ?? {})) {
    const flat = Array.isArray(rows) ? (rows.flat(Infinity) as unknown[]) : [];
    if (flat.length === 0 || flat.length % Math.max(n, 1) !== 0 || !flat.every(isNumber)) {
      throw new FrameFormatError(`field ${name} is not ${n} rows of numbers`);
    }
    fields[name] = flat as number[];
  }
  return {
    index: json.index,
    step: json.step,
    n,
    dimensions: json.dimensions,
    units: json.units,
    box: json.box.slice(0, 6) as Box,
    types: [...json.types],
    typeid: Int32Array.from(json.typeid),
    positions: Float32Array.from(json.positions),
    fields,
  };
}

function isNumber(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}
