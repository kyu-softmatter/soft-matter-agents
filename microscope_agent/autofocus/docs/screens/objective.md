# Objective screen contract (T-104, stage A)

Area `objective`: objective change with immersion loading (PLAN 2절 F5) and the 100x focus sweep.
Server: `src/dino_autofocus/server/api/objective.py`. Web: `web/src/features/objective/`.

This is the contract between the two, and with the engine. Behaviour is specified elsewhere and is
cited, not restated:

- Screen: `docs/ui-spec.md` 5.1 (operating rules), 5.3 (verdicts and Z), 7.0 (shared rules, disabled
  reasons), 7.5 (this area), 3.1 C6–C11 (confirm points).
- Operations: `docs/operations-spec.md` 4.2 (`objective_change`, seven steps, abort table) and 7
  (`focus_100x`).
- Directions: PLAN 5절 direction basis (v1.2). ZDrive up = toward the sample, 0 µm = retracted.
- Commands and events: `src/dino_autofocus/engine/events.py` (`COMMAND_KINDS`, `EVENT_KINDS`).

Names not yet in engine code are listed under Gaps with their owner task.

## 1. Read endpoints (`GET`, allowed remotely)

All responses are pydantic models. Z values are encoder readbacks unless the field name says `plan_`.

### `GET /api/objective/state`

| Field | Type | Source |
|---|---|---|
| `nosepiece_state`, `label` | int, str | engine snapshot (last `nosepiece_read()`) |
| `pixel_um` | float | backend `info()` |
| `z_um` | float | last `position` event (encoder) |
| `pfs` | `{enabled, locked, in_range}` | last `pfs_read()` |
| `immersion_loaded_this_session` | `{loaded: bool, immersion, at, by} \| null` | the session's last `manual_step load_immersion` record |
| `awaiting_return` | `{since, return_xy_um, objective_before} \| null` | sample record (ops-spec 4.2 abort table) |
| `running` | `{op_id, op, step, n_steps} \| null` | snapshot |
| `pending_confirm` | `{op_id, key, kind, prompt, options, context} \| null` | snapshot (ui-spec 3.0: survives reconnect) |

### `GET /api/objective/lenses`

One row per lens in the engine's lens table (guards data, BACKLOG "Lens table").

| Field | Type | Notes |
|---|---|---|
| `nosepiece_state`, `label`, `registry_key` | int, str, str | e.g. 5, `6-Plan Apo LmbdD0.13 100x Oil`, `100x-Oil` |
| `magnification`, `na`, `immersion` | float, float, `"dry" \| "oil" \| "water"` | |
| `working_distance_um` | float \| null | provisional values are flagged `"unmeasured provisional"` |
| `selectable` | bool | false when any reason applies |
| `disabled_reason` | str \| null | engine preflight text, quoted as is: `"already on that objective"`, `"not in the lens table"`, `"no working distance value"` (40x WI) |

The server asks the engine to evaluate these reasons; it does not compute them itself.

### `GET /api/objective/plan?target_state=<int>&escape=<bool>`

Returns the engine's `planned` payload for `objective_change` without starting it (dry plan):

| Field | Notes |
|---|---|
| `steps[]` | seven rows `{step: 1..7, name, target}`: record; lights off; `Z -> 0`; `Y -> y + dy` (absent when `escape=false`); rotate to `label`; `load_immersion` (manual); `XY -> return_xy`; `Z approach -> approach_target_um` in `approach_step_um` steps |
| `escape` | `{allowed, reason, sign, dy_um, mark, default}` (T-029, from `guards.step_out_target`). The checkbox starts at `default` (on for an immersion lens, off between dry lenses): +Y, 15000 µm, `"unmeasured provisional"` (PLAN v1.3). Shown read-only with the mark; no entry field. When the engine refuses it (e.g. stage Y limit), `allowed: false` and `reason` is the engine text, shown as is, and the screen sends `escape: false` |
| `immersion` | of the target lens |
| `approach_target_um`, `approach_step_um` | 2800 default; step from the target lens's guards row (10 µm, `"unmeasured provisional"`). Both read-only, shown with that mark; no entry field |
| `refusal` | preflight text if the plan itself is refused |

### `GET /api/objective/focus100x/defaults`

| Field | Value / source |
|---|---|
| `z_4x_focus_um` | 4x focus plane of the open sample at the current XY (latest `scan4x_*`), or null. Null until the WP-C helper exists (gap 9) |
| `lab_offset_um` | −60 (2026-09-30 run log), with `"to be re-measured"` |
| `centre_um` | `z_4x_focus_um + lab_offset_um`; null (shown as `"not set"`) when there is no 4x plane |
| `half_um`, `step_um`, `fine_half_um`, `fine_step_um` | 40, 2, 3, 0.2 (ops-spec 7 inputs) |
| `exposure_ms` | 20 (2026-09-30 result, no saturation) |
| `metric` | `"peak"` |
| `ceiling_um` | `min(3200, centre + 0.4 × 130)`, computed by the engine for the given centre |
| `immersion_loaded_this_session` | as in `/state`; false triggers C10 at start |

`GET /api/objective/focus100x/defaults?centre_um=<x>` recomputes `ceiling_um` and an
`above_4x_focus: bool` flag for a centre the operator typed. The screen never raises the range past the
ceiling (ui-spec 5.1).

### Implemented (stage B, `server/api/objective.py`)

- All four routes are `GET` and read the engine only: `snapshot()` (positions, the last
  `status` summary for the lens and PFS, `backend_info.objectives`, `awaiting_return`,
  `running`) and `plan(cmd)` (T-029). Lens and PFS are `null` until a `status` run has read
  them (`read_at`).
- `/lenses` uses the engine's `objective_options()` (T-028) when it exists; until then the same
  facts from `guards.OBJECTIVE_LIMITS` / `FREE_WD_UM`, with the preflight's reason texts.
- `/plan` keeps the engine's escape block and adds `note`: when the engine could not decide yet
  (`allowed: null`, "checked at preflight: ..."), the step-out stays allowed and the text is a
  muted note, not a refusal. Steps that do not run in the chosen mode are left out.
- `/focus100x/defaults` has no 4x focus plane yet (WP-C focus port), so `centre_um` is `null`
  unless the operator types one; the ceiling is `min(3200, centre + 0.4 × 130)`.
- No engine `plan` gives 503 `no_plan`; an engine refusal of the plan gives 409 `plan_refused`.
  Refusals are `{code, message}` with `X-DinoAF-Refusal`.

## 2. Commands (`POST /api/commands`, T-009)

Disabled reasons for these buttons come from the shared `GET /api/permissions?ops=objective_change,focus_100x,confirm,abort` (T-009b, backed by T-011 `check()`); this router never computes role, control, session or remote rules. If `/api/permissions` cannot be read, every control here (including "Loading done") is disabled with "Permission check unavailable"; progress stays visible. Per-lens reasons stay with `objective_options()` (T-028), and the server keeps `"Loading done"` local only. Shape is `engine.events.Command`. `origin="human"`; `user_id` and `session_id` are filled by the server.

| Action | Command | Who |
|---|---|---|
| Rotate | `{kind: "start", op: "objective_change", args: {target_state, escape}}`, `escape` true unless the operator unticks it or the engine refuses it. `approach_step_um` is not sent: it is a per-objective guards value, and the screen only shows the engine's value | local operator with control, session open |
| Loading done | `{kind: "confirm", op_id, args: {key: "load_immersion", ok: true}}` | **local only, always**, whatever D13 allows; the server refuses it from a remote origin |
| Return to sample position | `{kind: "start", op: "objective_change", args: {resume: true}}` (T-011) | as Rotate; the only motion op allowed while `awaiting_return` |
| Re-load immersion | `{kind: "start", op: "objective_change", args: {reload: true}}` (name to be fixed by T-029) | as Rotate; runs steps 2, 3, 5, 6, 7 on the current lens (ops-spec 4.2 item 8) |
| Continue after a dry-lens rotation (C8) | `{kind: "confirm", op_id, args: {key: <event key>, ok: true}}` | local operator |
| Find 100x focus | `{kind: "start", op: "focus_100x", args: {centre_um, half_um, step_um, fine_half_um, fine_step_um, exposure_ms, metric, aura_line, aura_percent, sample_id}}` | as Rotate |
| Answer C9 / C10 / C11 | `{kind: "confirm", op_id, args: {key, ok}}` | local operator |
| Abort | `{kind: "abort", op_id}` | the shell status bar sends it (ui-spec 7.0), not this area; anyone logged in, remote allowed (D13) |
| Lights off | `{kind: "lights_off"}` | anyone logged in, local |

Refusals come back synchronously from `POST /api/commands` (403 remote, permission table) or later as
`preflight_failed`. The screen shows the reason text as is.

## 3. Events read (`/ws/events`)

| Event | Fields used | Drives |
|---|---|---|
| `planned` | `data.steps`, `data.ceiling_um` | plan table, sweep plan |
| `preflight_failed` | `data.why` | reason next to the button |
| `started` | `data.start_state` (`return_xy`, `z_before`, `objective_before`) | step 1 row |
| `progress` | `data.step` (1..7), readbacks per step; for step 7 `{step: 7, z_um, target_um, step_index, n_steps}` (`step` is already the step number); for `focus_100x` `{phase: coarse \| fine, z_readback_um, score, sat}` | step rows, Z approach bar (moves per event, never jumps), sweep curve |
| `position` | `z_um`, `x_um`, `y_um` | current Z, readbacks |
| `light_changed` | the shell's one light shape (T-010-6): `{dialamp: {state, intensity}, aura: {state, lines}, verified, records}` | status bar (the shell's); this area shows no light state of its own |
| `confirm_required` | `data.key`, `data.kind` (`manual_step` for `load_immersion`), `data.prompt`, `data.options`, `data.context` | the loading card (C7) and dialogs C6, C8–C11 |
| `confirmed` | who, when | loading card "done by … at …" |
| `motion` | axis, target, readback | optional detail line |
| `finished` | `data.state` (`done` / `awaiting_return`), `data.summary`, `data.end_state` | result panel, return banner |
| `aborted` | `data.state` (`awaiting_return` or not), `data.why` | step row "stopped", return banner |
| `reading` | `source: "classical"`, `verdict`, `z_encoder_um`, warnings | 100x result badge (T-010 shared component) |

**XY hold (OD-20, the person, 2026-10-05; workplan G-17).** Nothing XY crosses to soft-matter-agents in this merge: the +Y step-out of `objective_change` (`escape`) stay mock/replay only in dino after the merge, and no XY plan shape, exemption or envelope key is requested there. The XY design (`motor_stage` steps, `motor_stage_{x,y}_position_min/max`, the retract-before-long-XY interlock) is soft-matter-agents' work after the bench visit B-03.

The retract-before-long-XY table (`guards.OBJECTIVE_LIMITS.long_xy_um`, Q4) stays in dino; question cards L-019 and L-020 ask the person for its values.

## 4. Gaps and where they went (manager, main 9052f48)

| # | Gap | Owner / answer |
|---|---|---|
| 1 | No `objective` event kind | T-011 adds it. Until then `/state` and `progress` step 4 carry the lens |
| 2 | Confirm shape | Settled: `{key: "load_immersion", ok: true}` (events.Command) |
| 3 | Re-load variant name | T-029 (WP-J) fixes the op names, including `reload`. This contract keeps `args: {reload: true}` until T-029 says otherwise |
| 4 | Plan without starting | T-011 adds a plan-only call (`plan(cmd)`) |
| 5 | Lens rows with reasons | T-028: `objective_options()` returns the rows with the engine's reason per lens |
| 6 | `progress.data` keys for steps 2–7 | T-029 fixes them. Proposed here and used by the web fake: `{step, axis, commanded, readback}`, plus `pfs_in_range` at step 2, `label_read` at step 4, and `{z_um, target_um, step_index, n_steps}` at step 7 |
| 7 | `lights_off` from a remote client | Settled (D2, T-011 text fixed): remote clients send `abort` only |
| 8 | `approach_step_um` | Settled: per-objective guards column, 10 µm, `"unmeasured provisional"`. Read-only on screen; never in the rotate args unless the engine echoes it back |
| 9 | 4x focus plane at the current XY | Goes to the WP-C focus port. Until it exists, `focus100x/defaults` returns `z_4x_focus_um: null` and `centre_um: null`, and the form shows the centre as `"not set"`; the operator types it, and C11 still applies |
