// The /api/patterns routes (server/api/patterns.py); types from gen:api via app/patterns.
// Reads and writes go through the shell's shared client; writes are POST like the rest of the API.

import type { Client } from "../../app/client";
import type { PatternIn, PatternOut, PatternSummary } from "../../app/patterns";

const at = (id: string) => `/api/patterns/${encodeURIComponent(id)}`;

export function patternsApi(client: Client) {
  return {
    list: () => client.get<PatternSummary[]>("/api/patterns"),
    get: (id: string) => client.get<PatternOut>(at(id)),
    save: (id: string, body: PatternIn) => client.post<PatternOut>(at(id), body),
    remove: (id: string) => client.post<null>(`${at(id)}/delete`),
  };
}

export type PatternsApi = ReturnType<typeof patternsApi>;

/** Lower-case letters, digits, '-' and '_' (the server's rule), from a name. */
export function idFromName(name: string): string {
  const s = name
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
  return s || "pattern";
}
