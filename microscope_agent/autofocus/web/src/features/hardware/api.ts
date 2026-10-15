/**
 * The hardware screen's wire types and reads. Router and permission types come from the
 * generated `src/api/schema.ts` (server/api/hardware.py, T-009b `/api/permissions`); this
 * file adds only what the schema does not cover: the shape of the engine's `status` summary,
 * the shared reason texts, the paths and the permission fallback.
 */

import type { components } from "../../api/schema";
import type { Client } from "../../app/client";

type Schemas = components["schemas"];

export type DeviceRow = Schemas["DeviceRow"];
export type ObjectiveRow = Schemas["ObjectiveRow"];
export type ConfirmedItem = Schemas["ConfirmedItem"];
export type HardwareProfile = Schemas["HardwareProfile"];
export type PreviousProfile = Schemas["PreviousProfile"];
export type HardwareProfileOut = Schemas["HardwareProfileOut"];
export type GateRow = Schemas["GateRow"];
export type StatusResultOut = Schemas["StatusResultOut"];
export type Permission = Schemas["PermissionOut"];
export type Permissions = Record<string, Permission>;

/**
 * Micro-Manager `.cfg` reads (server/api/hardware.py): `/config` the device tree, `/config/match`
 * every listed cfg against the last scan, `/config/draft` a cfg drafted from the scan.
 * `ConfigChoice.source`: "scanned" | "scanned-copy" | "server" | "repo" | "saved";
 * `ConfigDevice.link`: "parent" | "port" | "inferred" | null.
 */
export type ConfigChoice = Schemas["ConfigChoice"];
export type ConfigDevice = Schemas["ConfigDevice"];
export type ConfigTreeOut = Schemas["ConfigTreeOut"];
export type ConfigMatchRow = Schemas["ConfigMatchRow"];
export type ConfigMatchOut = Schemas["ConfigMatchOut"];
export type ConfigDraftOut = Schemas["ConfigDraftOut"];
export type ConfigSaveIn = Schemas["ConfigSaveIn"];
export type ConfigSavedOut = Schemas["ConfigSavedOut"];

/** The draft base meaning "from the scan alone" (`no_base=true`). */
export const NO_BASE = "__scan_only__";

/** The gate key for `light_set` in one mode (T-028: one row per mode). */
export const lightGateKey = (mode: "brightfield" | "aura" | "off") => `light_set:${mode}`;

/**
 * `StatusResultOut.summary` is the engine's dict (untyped in the schema): the fields
 * `status` reports (operations-spec 2).
 */
export interface StatusSummary {
  nosepiece_label?: string;
  nosepiece_state?: number;
  z_um?: number | null;
  pfs_enabled?: boolean | string;
  pfs_locked?: boolean | string;
  pfs_in_range?: string;
}

/** The commands this screen sends; `lights_off` is a command kind, the rest are `start` ops. */
export const SCREEN_OPS = ["hardware_scan", "hardware_confirm", "status", "light_set", "lights_off"] as const;

/** Shared texts for every screen (screen rules from AF 업무분배보조). */
export const CHECKING_PERMISSIONS = "Checking permissions…";
export const PERMISSION_CHECK_UNAVAILABLE = "Permission check unavailable";
export const READ_ONLY_REMOTE = "Read-only: remote view";

export const PATHS = {
  profile: "/api/hardware/profile",
  gates: "/api/hardware/gates",
  status: "/api/hardware/status",
  config: (path?: string | null) =>
    path ? `/api/hardware/config?path=${encodeURIComponent(path)}` : "/api/hardware/config",
  configMatch: "/api/hardware/config/match",
  configDraft: (base?: string | null) =>
    base === NO_BASE ? "/api/hardware/config/draft?no_base=true"
      : base ? `/api/hardware/config/draft?base=${encodeURIComponent(base)}` : "/api/hardware/config/draft",
  permissions: (ops: readonly string[]) => `/api/permissions?ops=${ops.map(encodeURIComponent).join(",")}`,
};

/**
 * When `/api/permissions` cannot be read, every control is off with the shared reason.
 * The exception is `lights_off`: a stop stays available, like the shell's Abort and Lights
 * off. A remote screen still greys it out through the shell's read-only flag (D2).
 */
export function permissionsUnavailable(ops: readonly string[]): Permissions {
  const out: Permissions = {};
  for (const op of ops) {
    out[op] = op === "lights_off"
      ? { allowed: true, reason: null }
      : { allowed: false, reason: PERMISSION_CHECK_UNAVAILABLE };
  }
  return out;
}

export async function readPermissions(client: Client, ops: readonly string[]): Promise<Permissions> {
  try {
    return await client.get<Permissions>(PATHS.permissions(ops));
  } catch {
    return permissionsUnavailable(ops);
  }
}

export const readProfile = (client: Client) => client.get<HardwareProfileOut>(PATHS.profile);
export const readGates = (client: Client) => client.get<GateRow[]>(PATHS.gates);
export const readStatus = (client: Client) => client.get<StatusResultOut | null>(PATHS.status);
export const readConfig = (client: Client, path?: string | null) =>
  client.get<ConfigTreeOut>(PATHS.config(path));
export const readConfigMatch = (client: Client) => client.get<ConfigMatchOut>(PATHS.configMatch);
export const readConfigDraft = (client: Client, base?: string | null) =>
  client.get<ConfigDraftOut>(PATHS.configDraft(base));
export const saveConfigDraft = (client: Client, name: string, base?: string | null) => {
  const body: ConfigSaveIn = base === NO_BASE
    ? { name, base: null, no_base: true }
    : { name, base: base ?? null, no_base: false };
  return client.post<ConfigSavedOut>(PATHS.configDraft(), body);
};
