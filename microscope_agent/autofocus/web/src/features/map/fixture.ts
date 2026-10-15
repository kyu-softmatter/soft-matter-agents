/** Test data for the map screen: the 2026-09-30 sample, shaped as docs/screens/map.md section 2. */

import type { Candidate, Flag, MapState, Permissions, ResultDetail, ResultSummary } from "./api";

/** What the fake server knows (tests/map world). */
export interface FakeData {
  /** raw GET /api/state */
  snapshot: Record<string, unknown>;
  /** ops not listed here are allowed */
  permissions: Permissions;
  /** make GET /api/permissions fail */
  permissionsFail?: boolean;
  /** ops left out of the answer */
  permissionsOmit?: string[];
  maps: Record<string, MapState>;
  results: Record<string, ResultSummary[]>;
  details: Record<string, ResultDetail>;
  flags: Record<string, Flag[]>;
  candidates: Record<string, Candidate[]>;
}

export const SAMPLE = "20260930_1849_1";
/** the experiment session opened at 19:30 local; the fit below is from 19:57 */
const SESSION_START = new Date(2026, 8, 30, 19, 30).getTime() / 1000;
const FIT_AT = new Date(2026, 8, 30, 19, 57).getTime() / 1000;

export function fixture(over: Partial<FakeData> = {}): FakeData {
  return {
    snapshot: {
      sample: SAMPLE,
      positions: { x_um: 8026, y_um: 571.6, z_um: 3048.7 },
      objective: "1-Plan Apo LmbdD20 4x",
      running: [],
    },
    permissions: {},
    maps: {
      [SAMPLE]: {
        sample_id: SAMPLE,
        boundary: [
          { x_um: 8833.4, y_um: -2354.1 },
          { x_um: 11097, y_um: 571.6 },
        ],
        hole: {
          centre_um: [8026.0, 571.6],
          diameter_mm: 6.1438,
          fit_rms_um: 42.5,
          n_points: 49,
          arc_deg: 352,
          fitted_at: FIT_AT,
          closed_loop: true,
          loop_why: "edge_trace: closed loop",
        },
        expected_diameter_mm: 6.0,
        visits: [{ x_um: 8026, y_um: 571.6, w_um: 3900, h_um: 3900, verdict: "in_focus" }],
        scan_box_um: { x0: 4554, x1: 11498, y0: -2900, y1: 4043 },
        allowed_box_um: { x0: 3554, x1: 12498, y0: -3900, y1: 5043 },
        session_started_at: SESSION_START,
      },
    },
    results: {
      [SAMPLE]: [
        {
          result_id: "sample_map_20260930-200100",
          kind: "sample_map",
          started: FIT_AT + 60,
          finished: FIT_AT + 400,
          light: "bf",
          n_tiles: 4,
          grid_n: 2,
          has_mosaic: true,
          scan_box_um: { x0: 4554, x1: 11498, y0: -2900, y1: 4043 },
          allowed_box_um: { x0: 3554, x1: 12498, y0: -3900, y1: 5043 },
        },
      ],
    },
    details: {
      "sample_map_20260930-200100": {
        result_id: "sample_map_20260930-200100",
        kind: "sample_map",
        started: FIT_AT + 60,
        finished: FIT_AT + 400,
        light: "bf",
        n_tiles: 1,
        grid_n: 1,
        has_mosaic: true,
        scan_box_um: null,
        allowed_box_um: { x0: 3554, x1: 12498, y0: -3900, y1: 5043 },
        tiles: [
          {
            name: "r0c0",
            row: 0,
            col: 0,
            x_um: 6368.3,
            y_um: -1086.0,
            z_focus_um: 3053.99,
            focus_note: "fine pass",
            block_z_um: [],
            blocks_per_side: 6,
            dropout_z_um: [],
          },
        ],
        fov_um: 3901,
        um_per_px: 1.6252,
        mosaic: { x0: 4418, x1: 11634, y0: -3036, y1: 4180, um_per_px: 13, bin: 8 },
      },
    },
    flags: {
      [SAMPLE]: [
        { flag_id: "f1", name: "good field", note: "dense", t: FIT_AT + 500, objective: "4x", x_um: 8164.7, y_um: 523.4, z_um: 2988.45, replaces: null, retired: false, retired_at: null },
        { flag_id: "f0", name: "old", note: "", t: FIT_AT + 100, objective: "4x", x_um: 7000, y_um: 0, z_um: null, replaces: null, retired: true, retired_at: FIT_AT + 200, retired_by: "op@example.test" },
      ],
    },
    candidates: {
      [SAMPLE]: [
        { candidate_id: "c1", x_um: 7811, y_um: 1529, source: "classical_candidate", score: 0.7, result_id: "sample_map_20260930-200100", decides: null, t: FIT_AT + 400, by: null },
        { candidate_id: "c2", x_um: 8100, y_um: 600, source: "classical_candidate", score: 0.5, result_id: "sample_map_20260930-200100", decides: null, t: FIT_AT + 400, by: null },
        { candidate_id: "c3", x_um: 8100, y_um: 600, source: "person_confirmed", score: null, result_id: null, decides: "c2", t: FIT_AT + 600, by: "op@example.test", decided_at: FIT_AT + 600 },
        { candidate_id: "c4", x_um: 9000, y_um: 900, source: "person_rejected", score: null, result_id: null, decides: "c5", t: FIT_AT + 600, by: "op@example.test", decided_at: FIT_AT + 660 },
      ],
    },
    ...over,
  };
}
