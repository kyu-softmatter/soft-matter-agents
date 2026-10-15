# `map` screen contract (T-102 stage A)

Sample map screen (PLAN.md 2절 F4). This file is the contract between the screen
(`web/src/features/map/`), its router (`server/api/map.py`, mounted at `/api/map` by T-009) and the
engine operations. Behaviour and wording come from `docs/ui-spec.md` 5.1, 5.3, 7.0 and 7.4 (branch
`exec5/T-004-ui-spec`) and `docs/operations-spec.md` 3, 6 and 8절; they are cited here, not restated.
Gap numbers (G1-G9) refer to section 7.

## 1. Rules this screen follows

- Pre-click disabled reasons for every op on this screen come from the shared
  `GET /api/permissions?ops=...` (T-009b, answered by T-011's `check()`). Neither the screen nor
  `map.py` computes role, control, session or remote rules; feature gates stay at
  `/api/hardware/gates`. The only area rule `map.py` adds is the scan box (`allowed_box_um`).
- The screen and the router decide nothing about safety. The box check, the retract decision, the
  stale-fit check and all refusals come from the engine (`preflight_failed`, `confirm_required`). The
  hover hint "outside the scanned area" is display only (ui-spec 7.4, click-move step 1).
- Directions (PLAN.md 5절, v1.2): ZDrive up = toward the sample, 0 µm = retract, so a retract shows
  as Z decreasing. The camera image is mirrored against the stage; the stage position of pixel `p` is
  `stage + inv(M) @ (centre − p)`, with the 2026-09-30 4x `M` as the initial calibration. 4x tiles are
  serpentine.
- The map is drawn in **stage µm**. `M` is applied once, by the engine, when it assembles the mosaic
  and places candidates (operations-spec 6.1 run steps 4–5). The screen never uses `M`: a canvas click
  maps to stage µm through the display transform only.
- Display transform: both axes flipped (joystick direction, ui-spec 1.2 (d)): +x to the left, +y down.
  The scale label says so: `"<span> um across   +stage x ←  +y ↓"`. Every layer uses the same transform.
- Z values shown are encoder readback, entered values or plan values, each labelled (ui-spec 5.3).
  Visited fields are coloured by verdict only. Mosaic images never go into the prompt context (D7).

## 2. Read endpoints (`server/api/map.py`, all GET, everyone incl. remote and viewer)

Storage (manager decision D1, G1): boundary points, flags and candidates are append-only events in
the open experiment session's `records/sample_events.jsonl`. `records.events.fold()` (T-019) is the
only fold; `engine/sample.py` (T-027) projects it into one named view (boundary, flags, candidates,
among others), and `map.py`'s single reader function calls that view. `sample.json` and `map.json` are derived views in the
legacy root `D:\AutoFocus\samples\<sample_id>\`, which also holds the large files the result
endpoints read (`scan4x_*/`, `sample_map_*/`, tiles, `mosaic.npy`). A storage change is then a
one-place change.
Response bodies are pydantic models; the TypeScript types are generated from OpenAPI (PLAN.md 5절).

| Route | Returns |
|---|---|
| `GET /api/map/{sample_id}` | `MapState`: `boundary[] {x_um, y_um, t}`, `hole {centre_um, diameter_mm, fit_rms_um, n_points, arc_deg, fitted_at} \| null`, `expected_diameter_mm \| null`, `visits[] {x_um, y_um, w_um, h_um, verdict, source}`, `scan_box_um` and `allowed_box_um` of the latest scan (`{x0, x1, y0, y1}` or null), `session_started_at` (experiment session start, else engine start; ui-spec 5.1) |
| `GET /api/map/{sample_id}/results` | `ResultSummary[]`: `result_id` (folder name), `kind` (`scan_4x` \| `sample_map`), `started`, `finished`, `light`, `n_tiles`, `grid_n`, `has_mosaic`, `scan_box_um`, `allowed_box_um`. Sources: `scan4x_*/`, `sample_map_*/` |
| `GET /api/map/{sample_id}/results/{result_id}` | `ResultDetail`: the summary + `tiles[] {name, row, col, x_um, y_um, z_focus_um, focus_note, block_z_um[], blocks_per_side, dropout_z_um[]}`, `fov_um`, `um_per_px`, `mosaic {x0, x1, y0, y1, um_per_px, bin} \| null` |
| `GET /api/map/{sample_id}/results/{result_id}/mosaic.png` | `image/png`, 8-bit grey. Contrast from the 0.5 / 99.8 percentiles of non-empty pixels (`plot_scan.py`). Optional `?max_px=` (default 2048, longest side). 404 with a reason if the result has no mosaic |
| `GET /api/map/{sample_id}/flags?include_retired=false` | `Flag[]`: `flag_id, name, note, t, objective, x_um, y_um, z_um (read), replaces \| null, retired_at \| null` |
| `GET /api/map/{sample_id}/candidates?include_rejected=false` | `Candidate[]`: `candidate_id, x_um, y_um, source (classical_candidate \| person_confirmed \| person_rejected), score, result_id, decides \| null, t, by \| null` |

Mosaic orientation: `mosaic.npy` is assembled as in `plot_scan.py`, tiles already flipped by the sign
of `M` and row 0 = `y0`. The server therefore only reverses the row order so that the PNG has +x to
the right and +y up, matching `x0..x1`, `y0..y1`. It does not flip by `M` a second time. To make this
explicit the server requires `mosaic.json` to say so (G4); if the field is missing it refuses
with 409 rather than guess.

The current sample comes from `snapshot()["sample"]` (T-011), i.e. `GET /api/state`; position,
objective and lights come from `/api/state` and `/ws/events` (T-009, T-010), not from `map.py`.

## 3. Commands

### 3.1 Through T-009 `POST /api/commands` (local operator with control and an open session)

| Input (ui-spec 7.4) | Command |
|---|---|
| `"Start tracing"` / `t` | `start edge_trace {sample_id, speed_um_s, hole_diameter_mm, light: "bf"}` |
| `+` / `-` while tracing | `update {op_id, args: {speed_um_s}}` (T-011 adds `update`) |
| `b` / `u` | `start boundary_mark {sample_id}` / `start boundary_undo {sample_id}` |
| `"Re-trace"` | `start edge_trace` (the engine backs up and asks, C4); `"Clear boundary"` = `start boundary_reset {sample_id}` |
| `"Start scan"` | `start scan_4x {...}` or `start sample_map {...}` with the args of operations-spec 3절 1항 / 6.1 1항 |
| map click | `start goto_xy {sample_id, x_um, y_um}` |
| dialog answers | `confirm {op_id, args: {key, ok}}`; `abort {op_id}` |

The live view keys `b`, `u`, `t` belong to the shell (T-010) and send the same commands.

### 3.2 D16 writes go through `map.py`, not the common endpoint

Flag write, flag retire and candidate confirm/reject write the sample record, so PLAN.md D16 allows
them only for an operator on the microscope PC. They are separate POST routes in `map.py` so that the
check sits in one owned, tested place:

| Route | Body | Engine command it submits |
|---|---|---|
| `POST /api/map/{sample_id}/flags` | `{x_um, y_um, name, note, replaces?}` | `start map_flag {sample_id, x_um, y_um, name, note, replaces}` (a note edit is a new flag with `replaces`) |
| `POST /api/map/{sample_id}/flags/{flag_id}/retire` | `{}` | `start map_flag_retire {sample_id, flag_id}` |
| `POST /api/map/{sample_id}/candidates/{candidate_id}/confirm` | `{note?}` | `start candidate_confirm {sample_id, candidate_id}` |
| `POST /api/map/{sample_id}/candidates/{candidate_id}/reject` | `{note?}` | `start candidate_reject {sample_id, candidate_id}` |

Every one of these routes:
1. passes T-009's loopback/origin middleware (remote requests get 403 before the route runs);
2. checks T-018 `auth/roles.py` `WRITE_MAP_FLAG` (operator, local) for the logged-in user; refusal is
   403 `{"detail": "Needs the operator role on the microscope PC"}`;
3. requires an open experiment session (the entry goes into its `records/sample_events.jsonl`, D1);
   without one, 409 `{"detail": "Open an experiment session first"}`;
4. submits the command with `user_id` and `session_id` and returns `CommandAccepted {op_id}`. The
   entry itself is written by the engine; the screen sees it via `map_changed`.

Tests per route: viewer refused, remote operator refused, local operator without an open session
refused, local operator with a session accepted.

None of these overwrite: confirm/reject add an entry with `decides: <candidate_id>`, retire adds
`retired_at`, a note edit adds a flag with `replaces` (ui-spec 7.4, operations-spec 6.2).

Bypass: `/api/commands` refuses these four op names (G2, now in T-009). Assistant proposals for them
pass the same check when a human confirms (G3, now in T-013).

## 4. Events the screen reads (`/ws/events`)

| Event | Used for |
|---|---|
| `map_changed` (G5) | boundary, hole fit, visits, flags, candidates of the open sample; the screen re-reads the matching GET |
| `sample_opened` (G5) | switch `sample_id`, reload all layers |
| `position` | current field rectangle, Z readback, click-target distance |
| objective label (G5) | field-of-view size of the current field rectangle |
| `planned`, `started`, `progress`, `finished`, `aborted`, `error` | edge-trace and scan panels (tile k/n, curve, dropped frames, path length, points), click-move steps, results list refresh on `finished` |
| `preflight_failed` | the `why` text next to the control (ui-spec 7.0 disabled-reason table) |
| `confirm_required` | C1–C5, C12 dialogs; answered with `confirm` |
| `light_changed` | the end-of-operation light line in the panels (status bar is the shell's) |

## 5. Map layers (bottom to top; ui-spec 7.4 layer table)

| Layer | Data |
|---|---|
| Mosaic | `mosaic.png` of the result picked in the results panel, placed at `mosaic {x0..y1}` |
| Scan box | `allowed_box_um` of the picked result (or of the latest, from `MapState`) |
| Visited fields | `MapState.visits`, verdict colour (ui-spec 5.3) |
| Boundary and hole | `MapState.boundary`, `hole`; fit time and "this session / previous session" against `session_started_at` (ui-spec 5.1) |
| Candidates | `/candidates`: hollow circle = computed (`classical_candidate`, labelled "computed" on screen), filled = person confirmed, grey × = rejected (hidden by default) |
| Flags | `/flags`; retired hidden by default |
| Current field | `position` + objective field of view |
| Click target | display only: stage µm under the cursor, distance from `position`, inside/outside `allowed_box_um` |

## 6. Click-to-move (ui-spec 7.4 steps 1–6) as events

| Step | Screen | Events and the fields the screen reads |
|---|---|---|
| 1 hover | target, distance, hint | none |
| 2 click | pin; `start goto_xy` | `planned {distance_um, large_move, retract_needed, z_safe_um, provisional}` |
| 3a outside | pin turns red ×, reason | `preflight_failed {why}`; nothing moves |
| 3b other refusal | reason in the same place | `preflight_failed {why}` |
| 3c retract needed | C12 dialog | `confirm_required {key: "retract_then_move", z_um, z_safe_um, x_um, y_um}` → `confirm` |
| 4 retract | `"Retracting Z <z> -> <z_safe>"`, Z readback going down | `progress {step: "retract"}`, `position` |
| 5 XY move | `"Moving to (x, y)"`, field rectangle moves | `progress {step: "move_xy"}`, `position` |
| 6 done | `"Arrived (x, y read back). Z left retracted at <z>: refocus with a scan tile or focus_100x"` | `finished {x_um, y_um, z_um, retracted}` (readback) |

The screen never raises Z after arrival; it shows only the refocus hint and buttons to the next focus
operation (operations-spec 6.3 run step 4). An `aborted` or `error` at any step clears the pin and
shows the reason. Field names in this table are assumed (G6).

**XY hold (OD-20, the person, 2026-10-05; workplan G-17).** Nothing XY crosses to soft-matter-agents in this merge: `goto_xy` (map click), `scan_4x` and `edge_trace` stay mock/replay only in dino after the merge, and no XY plan shape, exemption or envelope key is requested there. The XY design (`motor_stage` steps, `motor_stage_{x,y}_position_min/max`, the retract-before-long-XY interlock) is soft-matter-agents' work after the bench visit B-03.

## 7. Gaps and their status

| # | Gap | Status |
|---|---|---|
| G1 | Where boundary points, flags and candidates are stored | **Decided (D1)**: append-only events in the open session's `records/sample_events.jsonl`, folded only by `records.events.fold()` (T-019) and projected by `engine/sample.py` (T-027); `sample.json` / `map.json` are derived views. Writes need an open session (section 3.2) |
| G2 | `/api/commands` would bypass D16 | In T-009 (main 176b4c3): refuses `map_flag`, `map_flag_retire`, `candidate_confirm`, `candidate_reject` |
| G3 | Claude proposals for the same ops | In T-013: the proposal-confirm path checks `WRITE_MAP_FLAG` |
| G4 | `mosaic.json` lacks `orientation: "stage"`, `M_px_per_um`, `objective`, `n_tiles`; `scan_4x` writes no mosaic | Future engine card. Until then the server refuses (409) a mosaic without `orientation` |
| G5 | `map_changed`, `sample_opened`, objective event, `update` command | In T-011 (owner of `events.py`) |
| G6 | `goto_xy` payload fields (section 6); `scan_box_um` / `allowed_box_um` in `summary.json` | Future engine card. Field names in sections 2 and 6 are the request |
| G7 | Edge-trace diameter arg name | **Decided**: `hole_diameter_mm` (operations-spec 8절); ui-spec is fixed by its author |
| G8 | Engine-assigned `flag_id` / `candidate_id`; decisions reference them (`decides`, `replaces`); reject = new entry with `source: "person_rejected"` | Future engine card |
| G9 | Op names `map_flag_retire`, `candidate_confirm`, `candidate_reject` | **Fixed in T-011** as written here |
| G10 | Retired flags and decided candidates in the fold | **Closed by T-027c** (b602da5): `flag_remove` keeps the flag with `retired: True`; every flag and particle has a `history` of `{kind, by, at, status}`. `map.py` lists what is in play with `SampleView.active_flags()` / `open_candidates()` and returns the rest on `include_retired` / `include_rejected`, with `retired_by` / `retired_at` and the decision's `by` / `decided_at` taken from history. The screen shows retired flags on the toggle and rejected candidates as a grey × |

Until the engine side merges, stage B tests use a fake engine with these command names and a fixture
session folder with a `records/sample_events.jsonl` (D1) and a `mosaic.json` in the G4 shape.
