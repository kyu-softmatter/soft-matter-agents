/**
 * Areas that need dino's own records (samples, experiment sessions) are not there when the
 * console runs with the placeholder engine, for instance while it is attached to
 * soft-matter-agents (`--backend placeholder --store sma`). The server then refuses with 503
 * `no_sample_store` or `no_records`. The screens show this one sentence instead of the raw
 * refusal, and nothing else, because every control there would be refused the same way.
 */

import { CommandRefused } from "./client";

/** The refusal codes that mean "this server has no records store" (server/api/sample.py, sessions.py). */
export const NO_RECORDS_CODES: readonly string[] = ["no_sample_store", "no_records"];

export const PLACEHOLDER_NOTICE =
  "Not available with the placeholder engine: this console was started without dino's own sample " +
  "and session records (for example while it is attached to soft-matter-agents). Start it with " +
  "--backend mock, or mm-real at the bench, to use this area.";

/** PLACEHOLDER_NOTICE for a no-records refusal, else null (the caller shows its own error). */
export function placeholderNotice(e: unknown): string | null {
  return e instanceof CommandRefused && e.code !== null && NO_RECORDS_CODES.includes(e.code)
    ? PLACEHOLDER_NOTICE
    : null;
}
