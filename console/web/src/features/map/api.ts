/**
 * The map router's calls (docs/screens/map.md section 2). Response types are the generated ones
 * in src/api/schema.ts (gen:api from server/api/map.py); only names and the source values the
 * router sends are added here. Engine commands and events go through the shell's client.
 */

import type { Client } from "../../app/client";
import type { components } from "../../api/schema";

type S = components["schemas"];

export type Box = S["Box"];
export type BoundaryPoint = S["BoundaryPoint"];
export type HoleFit = S["HoleFit"];
export type Visit = S["Visit"];
export type MapState = S["MapState"];
export type ResultSummary = S["ResultSummary"];
export type Tile = S["Tile"];
export type MosaicExtent = S["MosaicExtent"];
export type ResultDetail = S["ResultDetail"];
export type HistoryEntry = S["HistoryEntry"];
export type Flag = S["Flag"];
export type Candidate = S["Candidate"];
export type FlagIn = S["FlagIn"];

/** `ResultSummary.kind` values (a plain string in the schema) */
export type ResultKind = "scan_4x" | "sample_map";
/** `Candidate.source` values (a plain string in the schema) */
export type CandidateSource = "classical_candidate" | "person_confirmed" | "person_rejected";

/**
 * One entry of the shared `GET /api/permissions?ops=a,b` (T-009b, backed by T-011's check()):
 * whether the op may be sent now and, if not, why. The screen only shows these reasons; the
 * server and engine enforce them again on every request.
 */
export type Permission = S["PermissionOut"];
export type Permissions = Record<string, Permission>;

/** The parts of GET /api/state (engine snapshot, T-011) this screen reads. */
export interface Snapshot {
  sample: string | null;
  position: { x_um: number | null; y_um: number | null; z_um: number | null } | null;
  objective: string | null;
}

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const str = (v: unknown): string | null => (typeof v === "string" ? v : null);

export function readSnapshot(snap: Record<string, unknown>): Snapshot {
  const p = (snap.positions ?? snap.position ?? null) as Record<string, unknown> | null;
  return {
    sample: str(snap.sample) ?? str((snap.sample as { sample_id?: unknown } | null)?.sample_id),
    position: p && typeof p === "object" ? { x_um: num(p.x_um), y_um: num(p.y_um), z_um: num(p.z_um) } : null,
    objective: str(snap.objective) ?? str(p?.objective),
  };
}

const enc = encodeURIComponent;
const base = (sampleId: string) => `/api/map/${enc(sampleId)}`;

export const PATHS = {
  map: base,
  results: (id: string) => `${base(id)}/results`,
  result: (id: string, rid: string) => `${base(id)}/results/${enc(rid)}`,
  mosaic: (id: string, rid: string) => `${base(id)}/results/${enc(rid)}/mosaic.png`,
  flags: (id: string, all: boolean) => `${base(id)}/flags?include_retired=${all}`,
  candidates: (id: string, all: boolean) => `${base(id)}/candidates?include_rejected=${all}`,
  addFlag: (id: string) => `${base(id)}/flags`,
  retireFlag: (id: string, fid: string) => `${base(id)}/flags/${enc(fid)}/retire`,
  decide: (id: string, cid: string, d: "confirm" | "reject") => `${base(id)}/candidates/${enc(cid)}/${d}`,
  permissions: (ops: readonly string[]) => `/api/permissions?ops=${ops.map(enc).join(",")}`,
};

const opIdOf = (r: { op_id?: string } | null): string => r?.op_id ?? "";

export interface MapRoutes {
  mapState(sampleId: string): Promise<MapState>;
  results(sampleId: string): Promise<ResultSummary[]>;
  result(sampleId: string, resultId: string): Promise<ResultDetail>;
  mosaicUrl(sampleId: string, resultId: string): string;
  flags(sampleId: string, includeRetired: boolean): Promise<Flag[]>;
  candidates(sampleId: string, includeRejected: boolean): Promise<Candidate[]>;
  /** the one permissions call; a failure disables the controls ("Permission check unavailable") */
  permissions(ops: readonly string[]): Promise<Permissions>;
  addFlag(sampleId: string, body: FlagIn): Promise<string>;
  retireFlag(sampleId: string, flagId: string): Promise<string>;
  decideCandidate(sampleId: string, candidateId: string, decision: "confirm" | "reject"): Promise<string>;
}

export function mapRoutes(client: Client): MapRoutes {
  return {
    mapState: (id) => client.get<MapState>(PATHS.map(id)),
    results: (id) => client.get<ResultSummary[]>(PATHS.results(id)),
    result: (id, rid) => client.get<ResultDetail>(PATHS.result(id, rid)),
    mosaicUrl: PATHS.mosaic,
    flags: (id, all) => client.get<Flag[]>(PATHS.flags(id, all)),
    candidates: (id, all) => client.get<Candidate[]>(PATHS.candidates(id, all)),
    permissions: (ops) => client.get<Permissions>(PATHS.permissions(ops)),
    addFlag: (id, body) => client.post<{ op_id?: string }>(PATHS.addFlag(id), body).then(opIdOf),
    retireFlag: (id, fid) => client.post<{ op_id?: string }>(PATHS.retireFlag(id, fid), {}).then(opIdOf),
    decideCandidate: (id, cid, d) => client.post<{ op_id?: string }>(PATHS.decide(id, cid, d), {}).then(opIdOf),
  };
}
