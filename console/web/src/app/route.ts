import { useCallback, useSyncExternalStore } from "react";

import { type AreaId, DEFAULT_AREA, isAreaId } from "./areas";

/**
 * Hash routes `#/<area>/<rest>`: FastAPI serves one index.html, so no server
 * routes are needed. The shell routes on `<area>` only and hands `<rest>`
 * (anything after the area, query included) to the area untouched, e.g.
 * `#/simulation/runs/run-20260924-001` -> area "simulation", rest "runs/run-20260924-001".
 * Areas link to each other with plain hrefs; they never import each other.
 */
export interface Route {
  area: AreaId;
  rest: string;
}

export function parseHash(hash: string): Route {
  const path = hash.replace(/^#\/?/, "");
  const m = /^([^/?]*)\/?(.*)$/.exec(path) ?? ["", "", ""];
  const id = m[1];
  if (!isAreaId(id)) return { area: DEFAULT_AREA, rest: "" };
  return { area: id, rest: m[2] };
}

export function areaFromHash(hash: string): AreaId {
  return parseHash(hash).area;
}

/** The href for an area, with an optional rest: `areaHref("map", "flags/3")` -> `#/map/flags/3`. */
export function areaHref(area: AreaId, rest = ""): string {
  const r = rest.replace(/^\/+/, "");
  if (r === "") return `#/${area}`;
  return r.startsWith("?") ? `#/${area}${r}` : `#/${area}/${r}`;
}

export function hashOfArea(id: AreaId): string {
  return areaHref(id);
}

// One route store for the app. A navigation from code updates it at once; the
// browser's own hashchange (back button, typed URL, links) updates it too, and is
// a no-op when it only echoes a navigation already applied.
let current: Route = parseHash(typeof window === "undefined" ? "" : window.location.hash);
const listeners = new Set<() => void>();

function update(next: Route): void {
  if (next.area === current.area && next.rest === current.rest) return;
  current = next;
  listeners.forEach((fn) => fn());
}

function onHashChange(): void {
  update(parseHash(window.location.hash));
}

function subscribe(fn: () => void): () => void {
  if (listeners.size === 0) window.addEventListener("hashchange", onHashChange);
  listeners.add(fn);
  // the hash may have changed while nobody listened (tests, first mount)
  onHashChange();
  return () => {
    listeners.delete(fn);
    if (listeners.size === 0) window.removeEventListener("hashchange", onHashChange);
  };
}

const getRoute = (): Route => current;

/** Open a route from code. */
export function navigate(href: string): void {
  if (window.location.hash !== href) window.location.hash = href;
  update(parseHash(href));
}

function useRoute(): Route {
  return useSyncExternalStore(subscribe, getRoute);
}

/** For the shell: the area in view and a way to open another. */
export function useArea(): [AreaId, (id: AreaId) => void] {
  const { area } = useRoute();
  const go = useCallback((id: AreaId) => navigate(areaHref(id)), []);
  return [area, go];
}

/**
 * For area screens: the part of the hash after the area, and a setter that
 * keeps the area. `const [rest, setRest] = useAreaPath();`
 */
export function useAreaPath(): [string, (rest: string) => void] {
  const { area, rest } = useRoute();
  const set = useCallback((r: string) => navigate(areaHref(area, r)), [area]);
  return [rest, set];
}
