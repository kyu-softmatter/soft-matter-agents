/**
 * Temporary until gen:api covers the objective router (T-009): hand-written types for
 * `/api/objective/*` (docs/screens/objective.md section 1) and `/api/permissions` (T-009b),
 * and the reads that use them. Commands, events and `/api/state` go through the shell's
 * client (`src/app/client.tsx`). When `src/api/schema.ts` has these paths, swap the types
 * below for imports from it; nothing else changes.
 */

import type { Client } from "../../app/client";

// ---------- /api/objective/* ----------

export interface ObjectiveState {
  nosepiece_state: number;
  label: string;
  pixel_um: number;
  z_um: number | null;
  pfs: { enabled: boolean; locked: boolean; in_range: string };
  immersion_loaded_this_session: { loaded: boolean; immersion: string; at: string; by: string } | null;
  awaiting_return: { since: string; return_xy_um: [number, number]; objective_before: string } | null;
  running: { op_id: string; op: string; step: number; n_steps: number } | null;
}

export interface LensRow {
  nosepiece_state: number;
  label: string;
  registry_key: string;
  magnification: number;
  na: number;
  immersion: "dry" | "oil" | "water";
  working_distance_um: number | null;
  selectable: boolean;
  /** engine text from objective_options() (T-028), shown as is */
  disabled_reason: string | null;
}

export interface PlanStep {
  step: number;
  name: string;
  target: string;
}

export interface ObjectivePlan {
  steps: PlanStep[];
  /** Y step-out for loading (PLAN v1.3, T-029 plan(cmd).escape), read-only on screen */
  escape: {
    allowed: boolean;
    /** engine refusal (guards.step_out_target, the stage Y limit), shown as is */
    reason: string | null;
    /** e.g. "checked at preflight: position not known yet" when the plan could not decide */
    note?: string | null;
    sign: "+Y" | "-Y";
    dy_um: number;
    /** e.g. "unmeasured provisional" */
    mark: string;
    /** on for an immersion lens, off between dry lenses */
    default: boolean;
  };
  immersion: "dry" | "oil" | "water";
  approach_target_um: number;
  approach_step_um: number;
  /** e.g. "unmeasured provisional" */
  approach_step_mark: string;
  refusal: string | null;
}

export interface Focus100xDefaults {
  z_4x_focus_um: number | null;
  lab_offset_um: number;
  centre_um: number | null;
  half_um: number;
  step_um: number;
  fine_half_um: number;
  fine_step_um: number;
  exposure_ms: number;
  metric: "peak" | "vollath";
  ceiling_um: number | null;
  above_4x_focus: boolean;
  immersion_loaded_this_session: boolean;
}

// ---------- /api/permissions (T-009b) ----------

export interface Permission {
  allowed: boolean;
  /** first disabled reason (ui-spec 7.0), shown as is */
  reason: string | null;
}

export type Permissions = Record<string, Permission>;

/** ops whose permission this screen asks for */
export const SCREEN_OPS = ["objective_change", "focus_100x", "confirm"] as const;

/** the one fallback for every screen when /api/permissions cannot be read, or leaves an op out */
export const PERMISSION_UNAVAILABLE: Permission = { allowed: false, reason: "Permission check unavailable" };
/** while the first permission check is loading (same text on every screen) */
export const PERMISSION_LOADING: Permission = { allowed: false, reason: "Checking permissions…" };

/** perms: undefined = first check loading, null = could not be read */
export function permissionOf(perms: Permissions | null | undefined, op: string): Permission {
  if (perms === undefined) return PERMISSION_LOADING;
  if (perms === null) return PERMISSION_UNAVAILABLE;
  return perms[op] ?? PERMISSION_UNAVAILABLE;
}

// ---------- paths and reads ----------

export const PATHS = {
  state: "/api/objective/state",
  lenses: "/api/objective/lenses",
  plan: (targetState: number, escape: boolean) => `/api/objective/plan?target_state=${targetState}&escape=${escape}`,
  focusDefaults: (centreUm?: number) =>
    centreUm === undefined ? "/api/objective/focus100x/defaults" : `/api/objective/focus100x/defaults?centre_um=${centreUm}`,
  permissions: (ops: readonly string[]) => `/api/permissions?ops=${ops.join(",")}`,
};

export const readState = (c: Client) => c.get<ObjectiveState>(PATHS.state);
export const readLenses = (c: Client) => c.get<LensRow[]>(PATHS.lenses);
export const readPlan = (c: Client, targetState: number, escape: boolean) =>
  c.get<ObjectivePlan>(PATHS.plan(targetState, escape));
export const readFocusDefaults = (c: Client, centreUm?: number) =>
  c.get<Focus100xDefaults>(PATHS.focusDefaults(centreUm));
export const readPermissions = (c: Client) => c.get<Permissions>(PATHS.permissions(SCREEN_OPS));
