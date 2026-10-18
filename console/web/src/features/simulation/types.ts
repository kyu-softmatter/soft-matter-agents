/**
 * What the simulation API sends: the models of server/api/simulation.py, from the generated
 * `src/api/schema.ts` (`npm run gen:api`). The names here are the screen's.
 */
import type { components } from "../../api/schema";

import type { FrameJson } from "./frame";

type S = components["schemas"];

export type RunProgressJson = S["ProgressOut"];
export type ProgressState = RunProgressJson["state"];
export type SimRunInfoJson = S["RunInfoOut"];
export type FileInfoJson = SimRunInfoJson["files"][number];
export type CurveJson = S["CurveOut"];
export type RunSeriesJson = S["SeriesOut"];
export type ZipEntryJson = S["ZipEntryOut"];

/**
 * frame.ts keeps its own FrameJson (the seam T-022's 3D viewer builds on); this fails to compile
 * if the server's FrameOut stops fitting it.
 */
export type FrameOutFitsFrameJson = S["FrameOut"] extends FrameJson ? true : never;
export const FRAME_OUT_FITS: FrameOutFitsFrameJson = true;
