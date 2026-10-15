/**
 * Sample screen: router and permission types, paths, readPermissions() and the
 * provisional field list. All server traffic goes through the shell's client
 * (src/app/client.tsx).
 *
 * TEMPORARY until gen:api, T-009: the router types below are written by hand
 * from docs/screens/sample.md. When `src/api/schema.ts` has them, replace this
 * section with re-exports from there; nothing else in features/sample/ names a
 * router type from anywhere but this file.
 */

import type { Client } from "../../app/client";

// ------------------------------------------------------------ Router types

export type GeometryKind = "number" | "pair" | "choice";
export type GeometryRaw = number | [number, number] | string;

export interface GeometryField {
  key: string;
  label: string;
  kind: GeometryKind;
  unit: string | null;
  choices: string[] | null;
  default: GeometryRaw | null;
  /** feeds a safety limit in the engine (coverslip, sample thickness, orientation) */
  safety: boolean;
}

export interface ValueSource {
  kind: "entered" | "default" | "not_set";
  by: string | null;
  t: string | null;
}

export interface GeometryValue {
  value: GeometryRaw | null;
  source: ValueSource;
}

export interface Geometry {
  values: Record<string, GeometryValue>;
}

export interface SampleSummary {
  sample_id: string;
  /** from the first sample event, the legacy sample.json, or the folder for a reserved sample */
  created: string | null;
  fitted_at: string | null;
  /** the engine's hole_loop verdict: the fit is a closed loop */
  closed_loop: boolean;
  objectives_used: string[];
  last_session: { session_id: string; opened_at: string } | null;
  awaiting_return: boolean;
  /** made by sample_new, no session yet */
  reserved: boolean;
}

export interface Hole {
  centre_um: [number, number] | null;
  diameter_mm: number | null;
  fit_rms_um: number | null;
  n_points: number | null;
  arc_deg: number | null;
  fitted_at: string | null;
  /** the engine's own words about the fit, e.g. "partial trace" (T-031); shown as is */
  status: string | null;
}

export interface SampleDetail extends SampleSummary {
  dir: string;
  hole: Hole | null;
  /** counted in the engine's sample view */
  counts: { flags: number; candidates: number; visits: number; boundary_points: number };
}

export interface StepState {
  done: boolean;
  by: string | null;
  t: string | null;
}

export interface LoadingState {
  session_id: string | null;
  geometry: StepState;
  person: StepState;
  image: StepState & { ok: boolean | null; why: string | null; result_ref: string | null };
  /** decided by the engine's sample view; the screen never combines the steps */
  confirmed: boolean;
}

/** Sample-specific pre-click facts from this area's router, GET /api/sample/access */
export interface SampleAccess {
  /** local request only (G9) */
  can_open_folder: boolean;
  /** why sample_open / sample_new would be refused now (a session is open for another sample) */
  open_reason: string | null;
}

/** engine snapshot()["sample"] in GET /api/state (T-011) */
export interface CurrentSample {
  sample_id: string;
  reserved: boolean;
  session_id: string | null;
}

// ------------------------------------------------------------- Ops and paths

export const SAMPLE_OPS = [
  "sample_open",
  "sample_new",
  "sample_geometry_set",
  "loading_confirm_person",
  "loading_check_image",
] as const;
export type SampleOp = (typeof SAMPLE_OPS)[number];

const enc = encodeURIComponent;

export const PATHS = {
  state: "/api/state",
  list: "/api/sample/list",
  fields: "/api/sample/geometry-fields",
  detail: (id: string) => `/api/sample/${enc(id)}`,
  geometry: (id: string) => `/api/sample/${enc(id)}/geometry`,
  loading: (id: string) => `/api/sample/${enc(id)}/loading`,
  access: (id: string | null) => `/api/sample/access${id ? `?sample_id=${enc(id)}` : ""}`,
  openFolder: (id: string) => `/api/sample/${enc(id)}/open-folder`,
  permissions: (ops: readonly string[]) => `/api/permissions?ops=${ops.map(enc).join(",")}`,
};

// ---------------------------------------------------------------- Permissions

/**
 * Generic pre-click verdicts (ui-spec 7.0: remote, role, control, session, running op), the same
 * for every screen: `GET /api/permissions?ops=a,b` -> `{op: {allowed, reason}}` (T-009b, backed by
 * T-011 `check()`).
 */
export interface Permission {
  allowed: boolean;
  reason: string | null;
}
export type Permissions = Record<SampleOp, Permission>;

/** Shared texts for every screen (screen rules from AF 업무분배보조). */
export const CHECKING_PERMISSIONS = "Checking permissions…";
export const PERMISSION_CHECK_UNAVAILABLE = "Permission check unavailable";
export const READ_ONLY_REMOTE = "Read-only: remote view";

/**
 * The screen's only way to the shared verdicts. If `/api/permissions` cannot be read, or its answer
 * leaves an op out, that op is off with `PERMISSION_CHECK_UNAVAILABLE`. A failure never counts as
 * allowed. (The shell's Abort and Lights off do not go through this.)
 */
export async function readPermissions(client: Client, ops: readonly SampleOp[] = SAMPLE_OPS): Promise<Permissions> {
  let got: Partial<Permissions> = {};
  try {
    got = await client.get<Partial<Permissions>>(PATHS.permissions(ops));
  } catch {
    got = {};
  }
  const off: Permission = { allowed: false, reason: PERMISSION_CHECK_UNAVAILABLE };
  return Object.fromEntries(ops.map((op) => [op, got[op] ?? off])) as Permissions;
}

// ---------------------------------------------------------------- Field list

/**
 * The provisional F3.1 field list (PLAN 10절; docs/screens/sample.md 2), as the server serves it at
 * `GET /api/sample/geometry-fields`. The screen renders whatever that route returns; this copy is
 * for the tests' fake server and work before T-009.
 */
export const PROVISIONAL_FIELDS: GeometryField[] = [
  { key: "sample_size_mm", label: "Sample size", kind: "pair", unit: "mm", choices: null, default: [24, 50], safety: false },
  { key: "chamber_shape", label: "Chamber", kind: "choice", unit: null, choices: ["hole"], default: "hole", safety: false },
  { key: "hole_diameter_mm", label: "Hole diameter", kind: "number", unit: "mm", choices: null, default: null, safety: false },
  { key: "coverslip_thickness_um", label: "Coverslip thickness", kind: "number", unit: "µm", choices: null, default: 170, safety: true },
  { key: "sample_thickness_um", label: "Sample thickness", kind: "number", unit: "µm", choices: null, default: null, safety: true },
  { key: "orientation", label: "Orientation", kind: "choice", unit: null, choices: ["upright", "flipped"], default: null, safety: true },
];
