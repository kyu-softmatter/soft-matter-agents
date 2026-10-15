/**
 * What the map draws, as plain data (ui-spec 7.4 layer table, bottom to top). The canvas painter
 * turns this into pixels; tests read it directly.
 */

import type { Box, Candidate, Flag, MapState, MosaicExtent } from "./api";
import { isRetired, pointBox, visibleCandidates, visibleFlags } from "./geometry";

export const LAYERS = ["mosaic", "scanBox", "visits", "boundary", "candidates", "flags", "field", "target"] as const;
export type Layer = (typeof LAYERS)[number];

export const LAYER_LABEL: Record<Layer, string> = {
  mosaic: "Mosaic",
  scanBox: "Scan box",
  visits: "Visited fields",
  boundary: "Boundary and hole",
  candidates: "Particle candidates",
  flags: "Flags",
  field: "Current field",
  target: "Click target",
};

export type LayerSet = Record<Layer, boolean>;

export const ALL_LAYERS_ON: LayerSet = Object.fromEntries(LAYERS.map((l) => [l, true])) as LayerSet;

/** hollow = classical candidate, filled = person confirmed, cross = rejected (ui-spec 7.4) */
export type CandidateMark = "hollow" | "filled" | "cross";

export function candidateMark(c: Candidate): CandidateMark {
  if (c.source === "person_confirmed") return "filled";
  if (c.source === "person_rejected") return "cross";
  return "hollow";
}

export type Item =
  | { layer: "mosaic"; kind: "image"; url: string; extent: MosaicExtent }
  | { layer: Layer; kind: "rect"; box: Box; style: "scan" | "visit" | "visit_in_focus" | "field" }
  | { layer: "boundary"; kind: "point"; x: number; y: number }
  | { layer: "boundary"; kind: "circle"; x: number; y: number; r_um: number; stale: boolean }
  | { layer: "candidates"; kind: "candidate"; x: number; y: number; id: string; mark: CandidateMark }
  | { layer: "flags"; kind: "flag"; x: number; y: number; id: string; label: string; retired: boolean }
  | { layer: "target"; kind: "pin"; x: number; y: number; refused: boolean };

export interface SceneInput {
  state: MapState | null;
  mosaic: { url: string; extent: MosaicExtent } | null;
  scanBox: Box | null;
  flags: Flag[];
  candidates: Candidate[];
  showRetired: boolean;
  showRejected: boolean;
  field: { x_um: number; y_um: number; fov_um: number } | null;
  pin: { x: number; y: number; refused: boolean } | null;
  staleFit: boolean;
}

export function buildScene(inp: SceneInput, on: LayerSet): Item[] {
  const items: Item[] = [];
  const s = inp.state;
  if (on.mosaic && inp.mosaic) items.push({ layer: "mosaic", kind: "image", ...inp.mosaic });
  if (on.scanBox && inp.scanBox) items.push({ layer: "scanBox", kind: "rect", box: inp.scanBox, style: "scan" });
  if (on.visits && s) {
    for (const v of s.visits) {
      items.push({
        layer: "visits",
        kind: "rect",
        box: { x0: v.x_um - v.w_um / 2, x1: v.x_um + v.w_um / 2, y0: v.y_um - v.h_um / 2, y1: v.y_um + v.h_um / 2 },
        style: v.verdict === "in_focus" ? "visit_in_focus" : "visit",
      });
    }
  }
  if (on.boundary && s) {
    for (const p of s.boundary) items.push({ layer: "boundary", kind: "point", x: p.x_um, y: p.y_um });
    if (s.hole) {
      items.push({
        layer: "boundary",
        kind: "circle",
        x: s.hole.centre_um[0],
        y: s.hole.centre_um[1],
        r_um: s.hole.diameter_mm * 500,
        stale: inp.staleFit,
      });
    }
  }
  if (on.candidates) {
    for (const c of visibleCandidates(inp.candidates, inp.showRejected)) {
      items.push({ layer: "candidates", kind: "candidate", x: c.x_um, y: c.y_um, id: c.candidate_id, mark: candidateMark(c) });
    }
  }
  if (on.flags) {
    for (const f of visibleFlags(inp.flags, inp.showRetired)) {
      items.push({ layer: "flags", kind: "flag", x: f.x_um, y: f.y_um, id: f.flag_id, label: f.name, retired: isRetired(f) });
    }
  }
  if (on.field && inp.field) {
    items.push({
      layer: "field",
      kind: "rect",
      box: pointBox(inp.field.x_um, inp.field.y_um, inp.field.fov_um / 2),
      style: "field",
    });
  }
  if (on.target && inp.pin) items.push({ layer: "target", kind: "pin", ...inp.pin });
  return items;
}
