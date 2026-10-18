import type { ComponentType } from "react";

/**
 * The app's areas, in navigation order. An area's screen lives in
 * `src/features/<id>/index.tsx` and is owned by that area's work package; the
 * shell only finds it (see web/README.md, "Adding an area screen").
 */
export const AREAS = [
  { id: "console", label: "Console" },
  { id: "hardware", label: "Hardware" },
  { id: "sample", label: "Sample" },
  { id: "map", label: "Map" },
  { id: "objective", label: "Objective" },
  { id: "live", label: "Live" },
  { id: "simulation", label: "Simulation" },
  { id: "results", label: "Results" },
  { id: "patterns", label: "Patterns" },
  { id: "tweezers", label: "Tweezers" },
  { id: "sessions", label: "Sessions" },
  // shown in the navigation to an admin only; the server refuses everyone else anyway
  { id: "accounts", label: "Accounts", adminOnly: true },
] as const;

export type AreaId = (typeof AREAS)[number]["id"];

export const DEFAULT_AREA: AreaId = "console";

export type AreaModule = { default: ComponentType };
export type AreaLoader = () => Promise<AreaModule>;

export interface AreaEntry {
  id: AreaId;
  label: string;
  /** in the navigation for an admin only */
  adminOnly?: boolean;
  /** undefined while the area has no `index.tsx`: the shell shows a placeholder */
  load?: AreaLoader;
}

export function isAreaId(value: string): value is AreaId {
  return AREAS.some((a) => a.id === value);
}

/** `../features/<id>/index.tsx` -> `<id>`; null for any other path. */
export function areaIdOfPath(path: string): string | null {
  const m = /\/features\/([^/]+)\/index\.tsx$/.exec(path);
  return m ? m[1] : null;
}

/**
 * Pair the fixed area list with the screen modules that exist. A feature folder
 * that is not in AREAS is ignored with a warning: adding an area to the
 * navigation is a shell change, not something a feature folder can do.
 */
export function buildRegistry(
  modules: Record<string, AreaLoader>,
  warn: (msg: string) => void = console.warn,
): AreaEntry[] {
  const found = new Map<string, AreaLoader>();
  for (const [path, load] of Object.entries(modules)) {
    const id = areaIdOfPath(path);
    if (id === null) continue;
    if (!isAreaId(id)) {
      warn(`features/${id}/index.tsx is not a registered area; ignored`);
      continue;
    }
    found.set(id, load);
  }
  return AREAS.map((a) => ({
    id: a.id,
    label: a.label,
    ...("adminOnly" in a && a.adminOnly ? { adminOnly: true } : {}),
    load: found.get(a.id),
  }));
}

// Vite resolves this at build time. A new `features/<id>/index.tsx` is picked up
// without editing this file.
const featureModules = import.meta.glob<AreaModule>("../features/*/index.tsx");

export const registry: AreaEntry[] = buildRegistry(featureModules);
