/**
 * The simulation area's routes (`rest` after `#/simulation/`):
 *   ""                   the list of runs
 *   "runs"               the list of runs
 *   "runs/<run_id>"      one run (the console links here)
 * Anything else shows the list.
 */
export function parseSimRest(rest: string): { runId: string | null } {
  const path = rest.split("?")[0].replace(/\/+$/, "");
  const m = /^runs\/([^/]+)$/.exec(path);
  if (!m) return { runId: null };
  try {
    return { runId: decodeURIComponent(m[1]) };
  } catch {
    return { runId: null };
  }
}

export function runRest(runId: string): string {
  return `runs/${encodeURIComponent(runId)}`;
}
