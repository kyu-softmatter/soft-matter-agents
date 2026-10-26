import type { ComponentType } from "react";

/**
 * The app's areas, in navigation order. An area's screen lives in
 * `src/features/<id>/index.tsx` and is owned by that area's work package; the
 * shell only finds it (see web/README.md, "Adding an area screen").
 */
export const AREAS = [
  { id: "questions", label: "Questions" },
  { id: "instruments", label: "Instruments" },
  { id: "experiments", label: "Experiments" },
  { id: "simulation", label: "Simulation" },
  { id: "library", label: "Library" },
  { id: "results", label: "Results" },
  // shown in the navigation to an administrator only; the server refuses everyone else anyway
  { id: "admin", label: "Admin", adminOnly: true },
] as const;

/**
 * Screen folders that are in the tree and in no navigation. `features/live/` is reached from Instruments,
 * Cameras (console card 012), when the person presses Live view; it has no navigation entry of its own.
 */
export const OUT_OF_NAVIGATION = ["live"] as const;

export type AreaId = (typeof AREAS)[number]["id"];

export const DEFAULT_AREA: AreaId = "questions";

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
      if ((OUT_OF_NAVIGATION as readonly string[]).includes(id)) continue;
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
