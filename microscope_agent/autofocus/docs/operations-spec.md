# Engine operation specification (T-006, draft)

- Author: AF execution 4 · development (2026-10-01). Owns: this one file (T-006).
- Purpose: break what the bench scripts do into an engine operation's `plan → preflight → run → abort`, so that the
  WP-C port becomes mechanical. It is an input to T-002 (guards, backend contract) and T-004 (UI spec).
- Source code: `scripts/*.py` (main `6ba1bc1`) (deleted in R-05; in history). Run record: `docs/runs/2026-09-30_substrate-scan.md`
  (hereafter "the 9/30 record"), and the `.yaml` of the same name. Plan: `docs/PLAN.md` v0.2.
- **Inference** marking: `C:\agentic_microscope\hardware\focus.py` (FocusAxis) is not on this PC.
  Behaviour guessed from how the scripts use it is marked "**inference**", and the questions to check are collected in the last section.

Progress (the writing order is the manager's instruction, T-006 "v0.2 adjustment")

| § | Operation | Status |
|---|---|---|
| 1 | `lights_off` | draft |
| 2 | `status` | draft |
| 3 | `scan_4x` | draft |
| 4 | `objective_change` (including the 7 steps of PLAN §2 F5) | draft |
| 5 | `hardware_scan` (F2) | draft |
| 6 | `sample_map`, `map_flag`, `goto_xy` (F4) | draft |
| 7 | `focus_100x` | draft |
| 8 | `edge_trace` | draft |
| 9 | Deferred and out of scope: `find_particle_z`, `focus_servo` | draft |
| 10 | Questions to check on the microscope PC | Q1–Q21 |

Manager decisions applied (T-002 Appendix 3, main `69e6ba5`): keep the `scan4x_<stamp>/` folder + write `scan.json` alongside,
`lights_off` is a preempting command, the status display uses `position` events, `hole.fitted_at`, and three gaps in the original.

T-024 (execution 17): the call names in 0.1 and in each section were aligned with `backend.py` (T-002-1, T-015), `events.py` and `guards.py` (T-002-2) at main `543c5ee`.
The direction convention is PLAN v1.2 (§5, the 9/30 record): a larger ZDrive value is toward the sample and 0 is retracted, sweeps go upward, the image is a mirror image of the stage,
and 4x tiles are serpentine. What this document says agrees with this convention.

## 0. Common conventions

### 0.1 Call-name table

The **engine call** column of the "run" tables uses the names below. Backend names follow main's
`src/dino_autofocus/engine/backend.py` (T-002-1 protocol + T-015 extension), and guard names follow `engine/guards.py` (T-002-2)
(main `543c5ee`). "(T-015)" marks a method that T-015 added.

| Kind | Name | Script original |
|---|---|---|
| Backend lifetime | `open()` → `BackendInfo`, `close()` | `mm_grab.open_core` (config load, AutoShutter 0, exposure, ROI) |
| Backend info | `info()` → `BackendInfo`: kind, config, camera, sensor, roi, exposure_ms, pixel_um, objective, intermediate_mag, bit_depth, `ceiling_adu` (= 2^bit_depth − 1), `objectives[]` (`ObjectiveInfo`: state, label, magnification, pixel_um, free_wd_um), `stage_limits` (`StageLimits`: x_um, y_um, z_um, None if unknown), `notes{}` (e.g. `aura.CYAN` = "unmeasured provisional"), `bench` (True on the real microscope, mm-real) | `info` from `open_core`, `core.getImageBitDepth()` |
| Frame | `snap()` → `Frame` (image uint16, t_read, exposure_ms, x_um, y_um, z_um) | `core.snapImage(); core.getImage()` |
| Settings | `set_exposure(ms)` → the exposure read back, `set_roi(size)` → the ROI read back (0 = full sensor) | `core.setExposure`, `core.setROI / clearROI` |
| Position | `positions()` → `Positions`: x_um, y_um, z_um, piezo_um{}. A failure is not an exception but None + `errors{}` | `mm_grab.positions` |
| Property | `read_property(dev, prop)` → string, `set_property(dev, prop, v, token=None)` → `Readback` (device, prop, wanted, read, verified, t, notes). Allow list `check_set_property`: motion devices are always refused, light properties need a token, a few camera properties go without a token, everything else is refused | `core.getProperty`, `mm_grab.set_and_read` |
| Lights | Turning on, `lamp_on(token=)` and `aura_line_on(line, percent, token=)` (turns DiaLamp off first), needs a token (PLAN D15). Turning off, `lamp_off()`, `aura_off()`, `all_off()`, needs no token (a stopping action). All return `list[Readback]`. Reading is `light_state()` → `{"DiaLamp": .., "Aura": ..}`. Operations turn lights on only through `scope.lamp_on()`, `scope.aura_line_on(line, percent)` | `set_and_read(DiaLamp, State, ·)`, `mm_grab.aura_on / aura_off` |
| Z | `move_z(z_um, token=)` → the z read back. **Only the guard calls it** | `core.setPosition("ZDrive", ·)` (inside FocusAxis) |
| XY | `move_xy(x_um, y_um, token=, timeout_s=None)` → the (x, y) read back. **Only the guard calls it**. Reading is `positions()` | `core.setXYPosition; waitForDevice` |
| Objective | `nosepiece()` → label (e.g. `1-Plan Apo LmbdD20 4x`). The State is looked up by label in `info().objectives`. `set_nosepiece(state, token=)` → `Readback`. **Only the guard calls it** | `getProperty / setProperty("Nosepiece", ...)` |
| PFS | `pfs()` → `PfsState` (enabled, locked, in_range string, `.out_of_range`). `pfs_off(token=)` → `Readback`. **Only the guard calls it** | `isContinuousFocusEnabled / Locked`, `PFS in Range` |
| Detection (T-015) | `describe_devices(include_properties)`, `nosepiece_labels()`, `piezo_read(port)`, `config_record()` | §5 |
| XY relative move (T-015) | `move_xy_rel(dx_um, dy_um, token=, timeout_s=None)` → the (x, y) read back. The guard `XYAxis.goto_rel` does not call this; it converts to an absolute move and goes through `goto` | `setRelativeXYPosition` (§8) |
| Continuous acquisition (T-015) | `start_stream(interval_ms)`, `next_frame(timeout_s)`, `stop_stream()`, `streaming()`. Frame metadata is the same as `snap()`'s. `snap()` during a stream raises `StreamActive`. The stream is owned by the engine (T-011) | `startContinuousSequenceAcquisition`, `popNextImageAndMD` (§8) |
| Guarded Z axis | `axis = FocusAxis(backend, objective, allow_motion=, dry_run=, sink=, op_id=)`. `objective` is a label or a registry key | `FocusAxis(core, key, allow_motion=, dry_run=)` |
| | `axis.plan(c, half, step)`, `.describe()` | Same |
| | `axis.sweep(plan, grab, score=, settle_s=)` → `.points[i].{z_um, z_readback_um, score, diagnostics}`, `.argmax_index`, `.peak_z_um`, `.peak_interior`, `.at_top` (peak on the top plane) | Same. `at_top` is a new name |
| | `axis.move_to(z, allow_ascent_um=)` (target inside the window 2800–3200), `axis.park_at(z)` (descent only, down to 0) → landing z readback, `axis.position_um()` | Same |
| | `axis.require_pfs_quiet(disable=True)` | Same |
| | `axis.approach(target_um, step_um=None, clearance=None)`: if below 2800 µm, once up to 2800, then steps of at most `OBJECTIVE_LIMITS[key].approach_step_um`. At every step a readback, an ascent check, `clearance(z)`. If `info().bench` is True (the real microscope), `clearance` must be given (`backend.py`) | New name (F5 step 7). Not in the original |
| | `best_z_um(coarse, fine)` → `(z \| None, why)`, `registry_key(label)`, `limits_for(label)` → (`ObjectiveLimits`, row name) | Same. `limits_for` is a new name |
| Objective rotation | `rotate_nosepiece(backend, axis, state)` → new label. Only when Z ≤ `RETRACTED_MAX_Z_UM` (1 µm) and PFS is off and Out of Range | `setProperty("Nosepiece", "State", N)` |
| Guarded XY | `xy = XYAxis(backend, XYBox.around(centre, half_um), allow_motion=, dry_run=, timeout_s=)`. The box is + 1 mm (`XY_BOX_MARGIN_UM`) | the `box` check inside `scan_4x.goto_xy` |
| | `xy.goto(x, y)`, `xy.goto_rel(dx, dy)` → the (x, y) read back. Refuses outside the box, compares the readback (`XY_TOL_UM` 5 µm, provisional) | `goto_xy`, `setRelativeXYPosition` |
| | A large XY move (over `OBJECTIVE_LIMITS[key].long_xy_um`; the objective is re-read on every move) only when Z ≤ `RETRACTED_MAX_Z_UM` is read back | New guard (F4 click move, F5 escape and return). Not in the original |
| Operation scope | `with operation(backend, parent, op, sink, args=, prefix=, user_id=, session_id=) as scope:` record folder, `started`, lights-off on every exit path, and `finished` / `aborted` / `error`. `scope.result` goes to summary.json | a different `finally` in each script |
| | `scope.lamp_on()`, `scope.aura_line_on(line, percent)`: turns on and emits `light_changed`; `GuardError` if `verified` is false | `set_and_read`, `aura_on` |
| | `scope.ask(key, text, **data)` → bool: `confirm_required` → a `confirm` with the same `key` → `confirmed`. Accepts abort while waiting | launcher dialog, a person's approval in chat |
| | `exclusive(backend)` (sole ownership of the core), `lights_off(backend)` (preempting lights-off, returns a result dict without raising) | `hardware_users()`, `lights_off.py` |
| Pure functions | `vollath4`, `parabola_peak`, 4×4 peak, `block_scores` | `mm_grab.vollath4`, `scan_4x.*`, `focus_100x.peak` |

Pure functions (focus metric, parabola) are treated as owned by `focus/` (WP-E, T-003); operations only import them.

- **Motion and light-on methods** (`move_z`, `move_xy`, `move_xy_rel`, `set_nosepiece`, `pfs_off`, `lamp_on`,
  `aura_line_on`, `set_property` on light properties) take the guard's `MotionToken` as `token=`; without it the backend
  refuses with `UnguardedMotion`. Operations do not call these methods directly but go through `FocusAxis`, `XYAxis`, `rotate_nosepiece`,
  `scope.lamp_on()` / `scope.aura_line_on()`. `axis.require_pfs_quiet(disable=True)` is a guard method that reads with `pfs()` and
  turns off with `pfs_off()`.
- Provisional guard values (`guards.py`, all "unmeasured provisional", also marked in the record of any motion that used them): `Z_SAFE_UM` 0,
  `RETRACTED_MAX_Z_UM` 1, `Z_TOL_UM` 0.25, `XY_TOL_UM` 5.0, `ESCAPE_DY_UM` +15000 (F5 escape +Y 15 mm, PLAN v1.3), per-objective `OBJECTIVE_LIMITS`
  (`long_xy_um`: 4x 10 mm, 100x Oil 156 µm, `approach_step_um`: 10 µm). The items to check are in `docs/microscope-pc-checklist.md`.
- The backend's z is always in bench coordinates (ZDrive µm, window 2800–3200). A device with a different origin, such as the demo Z, is offset inside the backend.
- Light methods and writes all return a `Readback` (or a list of them). "Readback check" means checking that every `verified` is true.

### 0.2 Events and records

- Event kinds are T-002 `events.py`'s `EVENT_KINDS`: `planned`, `preflight_ok / preflight_failed`,
  `started`, `progress`, `frame_ready`, `reading`, `finished`, `aborted`, `error`, `position`,
  `light_changed`, `property_set`, `motion`, `confirm_required`, `confirmed`; for commands,
  `proposed`, `approved`, `rejected`, `refused`, `updated`; for screen state, `map_changed`, `sample_opened`,
  `objective`, `session_changed`; and `log`. Every event has `kind`, `op_id`, `data` (JSON primitives) and `t`.
- Command kinds are `COMMAND_KINDS`: `start` (`op`, `args`), `abort` (`op_id`), `confirm` (`op_id`,
  `args = {"key": <data["key"] of the confirm_required>, "ok": bool}`), `lights_off` (preempting), `update`
  (`op_id`; changes, while running, only the arguments the operation declared), `approve` / `reject` (the decision on an assistant proposal). Every command
  carries `origin` (`human` / `assistant`), `user_id` and `session_id` (None if not yet available).
  The kinds of `confirm_required` are `CONFIRM_KINDS`: `question` and `manual_step` (F5 "Loading done"; kept in the summary's
  `manual_steps`). All are in main's `events.py` (T-011).
- `confirm_required("...")` in the sections below is the question text of `scope.ask(key, text)`. The answer comes as a `confirm`
  command with the same `key`, and the engine records that answer as a `confirmed` event.
- The record folder is, per T-002, `<sample_dir>/<op>_<stamp>/log.jsonl` + `summary.json`.
  Operations with no sample (`status`, `lights_off`) use T-002's default record location
  (corresponding to the launcher's `outputs/launcher_logs`).
- Each section's "Records" item states (a) the files and fields the script writes now, and (b) where they go in the engine record.

### 0.3 What every operation shares

| Item | Script today | In the engine |
|---|---|---|
| Opening the core | Each script reloads the config with `open_core()`. Loading applies the System/Startup preset (`LappMainBranch1 State 1`, `mm_grab.py` header) and changes the exposure and ROI | The engine opens the backend once (sole ownership of the core). Operations do not call `open()` |
| Another program holding it | The launcher's `hardware_users()` checks process command lines and only warns | The same check, once at engine start. Per engine, not per operation |
| stdout log | The launcher copies it into `launcher_<label>_<stamp>.log` via `run_logged.py` | As `log` events. In files, together in `log.jsonl` |
| Ctrl+C | `KeyboardInterrupt` → each script's `finally` | An `abort` command. The operation stops between frames and moves and takes the guard's exit path |
| Lights off | Differs per script (each section's abort item) | The `operation()` scope does `all_off()` + readback on every path (T-002) |

## 1. `lights_off`

Original: `scripts/lights_off.py` (deleted in R-05; in history). Launcher button "Lights off (Aura + DiaLamp)" (`hw=True`).

**1) Input arguments**: none. The original opens the core with `open_core(10.0, 0)` (exposure 10 ms, full sensor). No engine arguments.

**2) plan**: nothing to compute. Text to show: "Aura State → 0, DiaLamp State → 0. Nothing moves."

**3) preflight**: none in the original. In the engine, read the current light state and keep it as a `reading`
(`light_state()`). A failed read does not block. Lights-off is always attempted.

**4) run**

| # | Script call | Engine call | Note |
|---|---|---|---|
| 1 | `open_core(10.0, 0)` | (the backend the engine already opened) | In the original, a config reload and an exposure change come with it |
| 2 | `aura_off(core)` = `set_and_read("Aura", "State", 0)` | `aura_off()` | Turns off only the master State. The line (`GREEN 1`) and the intensity (`GREEN_Intensity 10`) stay as they are |
| 3 | `set_and_read("DiaLamp", "State", 0)` | `lamp_off()` | |
| 4 | Print each item whose `verified` is false as `WARNING` | If false, an `error` event and the result `finished(ok=False)` | The original still exits with code 0 |

In the engine, 2–3 are combined into a single `all_off()`. It must be the same function the guard's exit path calls.

**5) abort / finally**: no `finally` in the original. The engine's `lights_off` is itself an exit path.

Decision: `lights_off` is **accepted even while another operation is running** (a preempting command in `events.py`'s `COMMAND_KINDS`). On receipt it sends `abort` to the running operation,
and after that operation's exit path has finished it checks `all_off()` once more. Today the launcher refuses
`lights_off` too while a hardware operation is running. Yet an operation that stopped with the lights on is the moment this button is needed most.

**6) Records**

| Now | Engine |
|---|---|
| stdout: two JSON lines from `set_and_read` (`device, property, wanted, read, verified`) + one summary line | `property_set` events (one per `Readback` of `all_off()`: device, prop, wanted, read, verified), `light_changed`, `summary.json`: `{aura_state, dialamp_state, verified}` |

**7) Confirmation points**: none (the safe direction).

**8) Against the 9/30 record**: end state "Aura OFF, DiaLamp OFF (both read back)". This button exists because of known problem 4
(`live_focus.py` does not turn off DiaLamp when its window closes). In the engine,
the exit paths of `edge_trace` and the live view turn the lights off, so this button becomes one for checking and for emergencies.

## 2. `status`

Original: `scripts/change_objective.py --status` (the `state()` function) (deleted in R-05; in history). Launcher Step 0 "Show objective / Z / PFS".

**1) Input arguments**: `--status` alone. The original opens the core with `open_core(30.0, 0)`. No engine arguments.

**2) plan**: none. It only reads.

**3) preflight**: none.

**4) run**

| # | Script call | Engine call | Values read |
|---|---|---|---|
| 1 | `open_core(30.0, 0)` → print `info` | `info()`, `positions()` | config, camera, autoshutter, exposure_ms, sensor, roi, pixel_um, objective, intermediate_mag, position (x_um, y_um, z_um) |
| 2 | `getProperty("Nosepiece", "State")`, `getProperty("Nosepiece", "Label")` | `nosepiece()`, the State by label from `info().objectives` | `nosepiece_state`, `nosepiece_label` |
| 3 | `getPosition("ZDrive")` | `positions().z_um` | `z_um` (3 decimal places) |
| 4 | `isContinuousFocusEnabled()`, `isContinuousFocusLocked()` | `pfs()` | `pfs_enabled`, `pfs_locked`. On failure the original gives the string `"unreadable: <exc>"`, `PfsState` gives None |
| 5 | `getProperty("PFS", "PFS in Range")` | `pfs()` | `pfs_in_range` (`"In Range"` or `"Out of Range"`). On failure, the same string |
| 6 | (none) | `light_state()` | **Proposed addition**: the light state. Needed for checking the end state and for the status bar |
| 7 | (none) | `info().bit_depth`, `info().ceiling_adu` | **Proposed addition**: the camera ceiling. It caused the failure of the first scan_4x attempt (§3 item 8) |

- Nosepiece numbering: `State` starts at 0, the number in front of `Label` starts at 1. 4x is State 0 / `1-Plan Apo LmbdD20 4x`,
  100x Oil is State 5 / `6-Plan Apo LmbdD0.13 100x Oil`. The UI shows the Label and sends the command as a State.
- The original says "Read only", but `open_core` reloads the config and with it applies the Startup preset, exposure 30 ms,
  and ROI clear. The engine's `status` only reads from the backend that is already open, so it has none of these side effects.

**5) abort / finally**: none. It turns nothing on and moves nothing.

**6) Records**

| Now | Engine |
|---|---|
| One `info` JSON line and one `state` JSON line on stdout. The only file is the launcher log | One `reading` event (every field in the table above). `status_<stamp>/summary.json` only when the user ran it explicitly |

Proposal: the status bar's periodic refresh uses `position` events, not the `status` operation. Otherwise a record folder
would be created every few seconds. The decision is left to T-002 and T-004.

**7) Confirmation points**: none.

**8) Against the 9/30 record**: Step 0. Result `Nosepiece 0 = 1-Plan Apo LmbdD20 4x`, ZDrive 62.9 µm,
PFS off / "Out of Range". No failures. ZDrive 62.9 µm is outside the Z window (2800–3200).
How scan_4x's `z_guess` rule handles this value is in §3 item 3.

## 3. `scan_4x`

Original: `scripts/scan_4x.py` (deleted in R-05; in history). Launcher Step 2 "Start 4x scan" (runs after a confirmation dialog), "Dry run" checkbox.

**1) Input arguments**

| Command line | Default | Engine argument name | Note |
|---|---|---|---|
| `--sample` | (required) | `sample_id` | `sample.json` must have a `hole` |
| `--margin` | 500.0 µm | `margin_um` | margin added around the hole |
| `--overlap` | 0.15 | `overlap` | tile overlap fraction |
| `--exposure` | None (auto) | `exposure_ms` (None = auto) | auto exposure is run step 10 |
| `--aura LINE PERCENT` | GREEN 1 | `aura_line`, `aura_percent` | the per-mille conversion (`GREEN_Intensity = 10`) is the backend's job |
| `--z-guess` | None | `z_guess_um` | If None: the current Z when the current Z is inside 2800–3200, otherwise 2960 |
| `--first-half-range` | 160.0 µm | `first_half_um` | half-width of the first tile's coarse sweep |
| `--tile-half-range` | 50.0 µm | `tile_half_um` | half-width of later tiles' coarse sweeps |
| `--dry-run` | False | `dry_run` | Prints the plan only. The original shows only the plan of the first sweep |
| `--no-preview` | False | (none) | The preview is the UI's job. The engine always emits `frame_ready` |

Fixed values in the code (in the engine, kept as named constants or hidden arguments):

| Value | Where in the original | Proposed name |
|---|---|---|
| coarse step 10 µm (first tile), 6 µm (after) | `sweep_pair(z_ref, hr, 10.0 if first else 6.0, 12.0, 2.0)` | `coarse_step_first_um`, `coarse_step_um` |
| fine sweep ±12 µm, 2 µm spacing | same | `fine_half_um`, `fine_step_um` |
| settle 0.1 s (coarse), 0.2 s (fine) | `sweep_pair` | `settle_coarse_s`, `settle_fine_s` |
| blocks 6 × 6 | `BLOCKS` | `blocks_per_side` |
| dropout test ±2 % (against the sweep's median brightness) | tile loop | `dropout_frac` |
| auto exposure: p99.9 to 50 % of the ceiling. The factor is clipped to 0.25–4 and it stops at 0.7–1.4. At most 6 times, exposure 1–2000 ms, starting at 30 ms | auto-exposure loop, `open_core(args.exposure or 30.0, 0)` | `auto_exposure_*` |
| 0.2 s wait after an XY move | `goto_xy` | `xy_settle_s` |
| XY box margin 1000 µm | `box` | guard constant |
| parking upper limit 3200 µm | `axis.park_at(min(z_img, 3200.0))` | Z window upper limit (guard) |
| objective label `1-Plan Apo LmbdD20 4x`, registry key `"4x"` | `OBJECTIVE_4X`, `FocusAxis(core, "4x", ...)` | objective table (`info().objectives`; the registry key is the guard's) |

**2) plan** (computable without motion. Emitted as a `planned` event)

- Inputs: `sample.json`'s `hole.centre_um`, `hole.diameter_mm`, `stage_camera_calibration.um_per_px`
  (1.625 if absent), `info().sensor` (or the ROI).
- `half = diameter_mm × 500 + margin_um`, `fov = min(w, h) × um_per_px`, `pitch = fov × (1 − overlap)`,
  `n = max(1, ceil((2·half − fov) / pitch) + 1)`. Tile centres lie on a `(i − (n−1)/2) × pitch` grid, in a serpentine order
  that reverses direction on every row (`grid()`).
- XY box: `centre ± (half + 1000)`.
- First sweep: `axis.plan(z_guess, first_half_um, 10).describe()`. The original dry-run shows only this far.
  The engine's plan also states the sweep widths of later tiles (±50 @6, fine ±12 @2) and the rule "on failure, widen once to the first tile's width".
- Check values (usable as WP-C test vectors): on 9/30, `diameter_mm 6.1438`, margin 500, overlap 0.15,
  2400 px × 1.6252 µm give fov 3901, pitch 3315, n = 2 (2 × 2 tiles). This matches the 9/30 record.

**3) preflight**

| Check | Original | Engine proposal |
|---|---|---|
| `sample.json` exists | The launcher only looks at `sample_id(required=True)`. The script raises if it is absent | `preflight_failed("no sample.json")` |
| a `hole` fit exists | None. If `hole` is null, `TypeError` | `preflight_failed("hole not fitted: run edge_trace")` |
| is the fit from this session | Only the launcher dialog's question ("Hole traced in brightfield this session?") | `sample.json` has no fit time, only `updated`. Put `hole.fitted_at` in T-002 `sample.py`, and if it is not after engine start, `confirm_required` (operating rule: re-trace every session) |
| objective label = 4x | Present. But it is checked **after** the grid has been printed | Move it to the very front. Otherwise `preflight_failed` |
| PFS | Run's `require_pfs_quiet(disable=True)` turns it off | Read it and keep it as a `reading`. Turning it off is run step 7 |
| current Z | Used only to compute `z_guess` | If the current Z is outside the window (62.9 µm at the start on 9/30), the first move climbs about 2.9 mm to 2960 µm. Proposed: ask with `confirm_required`. The original does not ask |
| camera bit depth | `getImageBitDepth()` during the run | Read in preflight to set the ceiling. It must be 4095 (12-bit) to match the 9/30 settings |
| another operation running | launcher `hardware_users()` | sole ownership by the engine (0.3) |

**4) run**

| # | Script call | Engine call | Note |
|---|---|---|---|
| 1 | `open_core(args.exposure or 30.0, 0)` | `set_exposure(exposure_ms or 30)`, `set_roi(0)`, `info()` | |
| 2 | `getProperty("Nosepiece", "Label")` | `nosepiece()` | moved to preflight |
| 3 | `FocusAxis(core, "4x", allow_motion=True, dry_run=)` | create the guarded Z axis. The original hard-codes `"4x"` instead of `registry_key` | |
| 4 | `axis.position_um()` | same | computing `z_guess` |
| 5 | if dry-run, print `axis.plan(...).describe()` and exit | ends at the plan stage. `finished(dry_run=True)` | creates no record folder |
| 6 | `out.mkdir`, `getImageBitDepth()` | create the record folder, `info().ceiling_adu` | |
| 7 | `axis.require_pfs_quiet(disable=True)` | same | **Inference**: turns off the PFS servo and reads that it is off |
| 8 | `aura_on(core, line, pct)` = DiaLamp State 0 → `{LINE}_Intensity` (per mille) → `{LINE} 1` → Aura State 1, each with a readback | `scope.aura_line_on(line, percent)` | The original continues even with `verified=False`. The engine stops (`GuardError`) |
| 9 | `goto_xy(x0, y0)`: box check → `setXYPosition` → `waitForDevice` → 0.2 s → `getXYPosition` | `xy.goto(x, y)` (box, large move, readback comparison) | The original does not compare the XY readback against the commanded value |
| 10 | if auto exposure, `axis.move_to(min(z_guess, 3200), allow_ascent_um=max(0, z_guess − z) + 0.5)`, then up to 6 times `snap` → p99.9 → `setExposure` | `axis.move_to(...)`, `snap()`, `set_exposure()` | The original only prints p99.9 |
| 11 | `goto_xy(x, y)` for each tile | same as step 9 | `progress(tile k/n)` |
| 12 | `sweep_pair`: `axis.sweep(axis.plan(z_ref, hr, step), grab, score=, settle_s=0.1)`. If `coarse.peak_interior`, `axis.sweep(axis.plan(coarse.peak_z_um, 12, 2), grab, score=, settle_s=0.2)` | same | `grab` = `snap()`. For the preview the original also calls `axis.position_um()`, `vollath4`. The engine emits `frame_ready` + `progress` per point |
| 13 | `best_z_um(coarse, fine)` | same | result `(zf, why)` |
| 14 | if not the first tile and `zf` is None, one more `sweep_pair` at the first tile's width (±160 @10) | same | |
| 15 | Dropout filter: drop points more than 2 % away from the median of `diagnostics.mean` over the coarse+fine points. If any were dropped and there is a fine sweep, redo `parabola_peak` with the remaining fine points (3 or more) | pure function (`focus/`) | `why` becomes `"fine pass without light-dropout frames at [...]"` |
| 16 | `parabola_peak(zs, blocks[b])` for each of the 36 blocks | pure function | `block_z_um` |
| 17 | `axis.park_at(min(zf or z_ref, 3200))` | same | the landing z is `z_image_um` |
| 18 | `grab()` → save `tile_rXcY.npy`, save `scan.json` | `snap()`, record | Saved per tile. Earlier tiles survive an interruption |
| 19 | if `zf` exists, `z_ref = zf`, `first = False` | same | A failed tile does not change the next tile's reference |
| 20 | `rec["finished"]` | `finished` | |

The `score` function (shared by coarse and fine): `sharp = vollath4`, `blocks = block_scores` (6×6 vollath4), `mean`, `p999`,
`saturated_frac = mean(frame ≥ ceiling)`. The deciding metric is Vollath F4 alone.

**5) abort / finally**

| Order | Original `finally` | Engine proposal |
|---|---|---|
| 1 | if `lights` is not empty, `aura_off()` (Aura State 0 only) | `all_off()` on the guard's exit path (Aura + DiaLamp, readback) |
| 2 | `rec["z_end_um"] = axis.position_um()` | all of `positions()` as the end state |
| 3 | save `scan.json` | `summary.json` + `aborted` or `finished` |
| Z | left where it is (not retracted) | left the same way. The 4x has a working distance of 20 mm, so retracting is not needed for safety |
| XY | where it is | where it is |

Gaps in the original (to fix when porting):
- If `aura_on()` stops with an exception before its fourth write, `lights` is an empty list, so `finally` does not turn the lights off.
  The engine must enter the `operation()` scope **before** turning lights on.
- It does not check `aura_on`'s `verified=False`.
- It does not compare the XY readback against the commanded value. On 9/30 a person moved the stage during a run (record §4 item 3).
  The tolerance is a §10 question.
- What happens when Ctrl+C arrives during a move inside `axis.sweep` is unknown. **Inference**: `KeyboardInterrupt` propagates as is
  and goes to `finally`. The engine checks for abort only between moves.

**6) Records**

Now: `<sample>/scan4x_<stamp>/`

| File | Contents |
|---|---|
| `scan.json` | `sample, started, header (=info), objective, um_per_px, fov_um, pitch_um, grid_n, hole, margin_um, coordinates, camera_ceiling_adu, light (4 aura_on records), exposure_ms, tiles[], finished, light_off, z_end_um` |
| `tiles[]` in `scan.json` | `name, row, col, x_cmd_um, y_cmd_um, x_um, y_um, z_focus_um, focus_note, z_image_um, block_z_um[36], blocks_per_side, dropout_z_um[], curve[{z, sharp, mean, sat}], frame_mean, frame_max, seconds` |
| `tile_r{r}c{c}.npy` | uint16 frame taken at the focus position |
| `launcher_scan4x_<stamp>.log` (sample folder) | stdout |

Fields `scripts/plot_scan.py` reads: `um_per_px`, `fov_um`, `hole`, `tiles[].{x_um, y_um, name, z_focus_um,
blocks_per_side, block_z_um}`, and `stage_camera_calibration` from `sample.json` in the parent folder.

Mapping onto the engine record:

| Now | Engine |
|---|---|
| top-level fields of `scan.json` | under the same names in `summary.json`. Names are not changed, for plot_scan compatibility |
| `tiles[]` | `tiles[]` in `summary.json` (same fields). Also emitted as a `reading` event per tile |
| `curve[]` | `progress` events in `log.jsonl` (per point: the commanded `z_um`, `z_readback_um`, `score`, `diagnostics`). `summary.json` keeps a summary curve as now |
| `light`, `light_off` | `property_set` events and the end state |
| `header` | the start state of the `started` event (`info()` + `positions()`) |
| `.npy` | as is, in the same folder |

What needs a decision (for the manager):
- Folder name: it is `scan4x_<stamp>` now, and under T-002's rule it becomes `scan_4x_<stamp>`. The launcher's `plot()` and
  `plot_scan.py` look for `scan4x_*/scan.json`. Proposal: keep the operation name `scan_4x` but keep the folder as `scan4x_<stamp>`,
  and also write a `scan.json` with the same content as `summary.json`. Merge them into one once the port is finished.
- `z_focus_um` is a value from a classical metric (Vollath) and the encoder readback. It is not a model value, so
  it is not subject to the `grade: model` marking.

**7) Confirmation points** (`confirm_required`)

| Point | Original | Engine |
|---|---|---|
| before start | launcher dialog: "moves the XY stage and ZDrive and switches on Aura GREEN 1 %", "Nosepiece on 4x?", "Hole traced in brightfield this session?" | `confirm_required("start scan_4x", plan)` once. Preflight replaces the objective check |
| the fit is not from this session | the dialog question above | `confirm_required("hole fit is from <time>; re-trace?")` |
| the first move comes in from outside the Z window | none | `confirm_required("ZDrive <z> -> <z_guess>")` (proposed) |
| during the run | none | none |

**8) Against the 9/30 record**: Step 2.

| Case | What happened | Where the spec reflects it |
|---|---|---|
| first attempt `scan4x_20260930-194928/` is an empty folder | Auto exposure aimed at a 16-bit ceiling and stalled on a 12-bit camera. Fixed with `getImageBitDepth` | the bit-depth read in preflight. Mock tests use 12-bit |
| light dropout | In the second run's r1c1 fine sweep, two frames at −23 % read 2.7 times sharper and became the peak. 3053.99 → 3051.2 µm | run step 15 dropout filter, `dropout_z_um` |
| a person moved the stage during the run | XY changed between records | XY readback comparison (gap in item 5), start position in the `started` event |
| exposure | automatically 994 ms (p99.9 2043 ADU) | the auto-exposure fixed values |
| first tile's reference Z | ±160 around the current Z of 3012 µm, set in brightfield | the `z_guess` rule |
| repeatability | 0.4–3.4 µm between runs (4x depth of field about 14 µm) | basis for the mock-test tolerance |

Results (serpentine order): r0c0 (6368.3, −1086.0), r0c1 (9683.7, −1086.0), r1c1 (9683.6, 2229.2),
r1c0 (6368.3, 2229.5). Focal plane: 3048.7 µm at the hole centre, tilt x −1.66, y −3.62 µm/mm.

## 4. `objective_change` (including F5)

Original: `scripts/change_objective.py` (deleted in R-05; in history). On 9/30 it was used as `--to 5 --park` → a person applies oil → `--return-only`.
The launcher has no button for it ("The objective change and 100x steps stay manual"). In the engine it is rebuilt in the order of the
7 steps of PLAN §2 F5. Below, the original comes first, then the F5 engine operation.

### 4.1 What the original does

**Input arguments**

| Command line | Default | Meaning |
|---|---|---|
| `--to N` | None | target Nosepiece **State** (0 = 4x, 5 = 100x Oil) |
| `--status` | False | read only (§2) |
| `--park` | False | leaves Z at 0 after the rotation (to apply oil) |
| `--return-only` | False | Z 0 → 2800 without a rotation |

Fixed values: `RETRACT_Z_UM = 0.0`, `RETURN_Z_UM = 2800.0`, the core is `open_core(30.0, 0)`.
If `--status` is present, it is handled before the other arguments and the script ends. With neither `--to` nor `--return-only`, it only reads.

**The original's call order** (`--to N`, with or without `--park`)

| # | Script call | Engine call | Note |
|---|---|---|---|
| 1 | `state(core)` | `nosepiece()`, `positions()`, `pfs()` | start state `s0` |
| 2 | if `s0.nosepiece_state == N`, "already on that objective" and exit | preflight | nothing moves |
| 3 | `FocusAxis(core, registry_key(s0.label), allow_motion=True)` | guarded Z axis (current objective's key) | |
| 4 | `axis.require_pfs_quiet(disable=True)` | same | |
| 5 | `axis.move_to(0.0)` | `axis.park_at(0.0)` | Retract. The guard's `move_to` refuses a target outside the window (2800–3200); below the window, `park_at`, which only descends, does it |
| 6 | `state(core)` → if `pfs_in_range` is `"in range"`, refuse and exit | `pfs()` | Z stays at 0 |
| 7 | `setProperty("Nosepiece", "State", N)`, `waitForDevice("Nosepiece")` | `rotate_nosepiece(backend, axis, N)` | a call refused in soft-matter-agents (Nosepiece is in `NAMED_REFUSALS`) |
| 8 | `state(core)` → if the State is not N, exit ("ZDrive left retracted") | `rotate_nosepiece` refuses (`GuardError`) | |
| 9 | if `--park`, exit | | Z is 0 |
| 10 | `FocusAxis(core, registry_key(s2.label), allow_motion=True)` | guarded Z axis (new objective's key) | |
| 11 | `axis.move_to(2800.0, allow_ascent_um=2800.5)` | same | **A 2800 µm climb in one go.** F5 step 7 replaces this with a stepped approach |
| 12 | print `state(core)`, `getPixelSizeUm()` | `nosepiece()`, `info().pixel_um` | |

`--return-only`: `FocusAxis(current objective)` → `require_pfs_quiet(disable=True)` → refuse if Z is over 1.0 µm →
`axis.move_to(2800, allow_ascent_um=2800 − z + 0.5)` → `state`. It does not re-check the objective, PFS or oil.

What the original does not do: XY moves (on 9/30, XY was moved to the hole centre separately before the rotation), lights, record files, the oil check.

### 4.2 Engine operation `objective_change` (the 7 steps of F5)

**1) Input arguments**

| Engine argument | Default | Note |
|---|---|---|
| `target_state` | (required) | Nosepiece State. The UI picks by Label and sends the State |
| `escape_dy_um` | +15000 µm | Not an operation argument but the guard constant `guards.ESCAPE_DY_UM`. **Set to +Y, 15 mm** (the user, PLAN v1.3: the shorter end of 15–20 mm). It is "unmeasured provisional" and recorded as such. Before the move, the stage's Y limit is read and the move is refused if it would cross it (`step_out_target`) |
| `escape` | True | If False, steps 3 and 6 are skipped (when changing between dry objectives) |
| `approach_target_um` | 2800 | the target of step 7's stepped approach. The original's `RETURN_Z_UM` |
| `approach_step_um` | undecided | one stride of step 7. A §10 question |
| `park_only` | False | the original's `--park`. Stops after step 5 (6 and 7 done separately later) |

**2) plan** (what to show)

- Start state: current objective, XY, Z, PFS.
- The order and each step's target: Z → 0, Y → `y + ESCAPE_DY_UM` (+15 mm), Nosepiece → `target_state`, manual loading, XY → the start XY,
  Z → up to `approach_target_um` in strides of `approach_step_um`.
- The new objective's immersion type (objective table: 4x dry, 100x Oil oil, 40x WI water) and working distance.

**3) preflight**

| Check | Result |
|---|---|
| `target_state` equals the current State | `preflight_failed("already on that objective")` (original step 2) |
| the target objective is in the objective table (state and `free_wd_um` in `info().objectives`, registry key) | If absent or `free_wd_um` is None, `preflight_failed`. **40x WI is refused because it has no working-distance value** (PLAN §10, soft-matter-agents task 026 §5) |
| `escape=True` | The escape distance is `ESCAPE_DY_UM` (+Y 15 mm, provisional). The escape position must pass the Y-limit check in the next row |
| the escape position is inside the stage limits | The limit is `info().stage_limits.y_um` (filled from the F2 configuration file). If None, `preflight_failed` |
| other running operations, lights | There must be no other operation. Lights that are on are turned off in step 1 (`all_off()`) |
| a previous `objective_change` ended as "awaiting return" | See item 5 of 4.2. `preflight_failed`, saying to do the return (6 and 7) first instead of a new rotation |

**4) run**

| F5 step | Engine call | Guard / check | Original counterpart |
|---|---|---|---|
| 1 record the current XY, Z, objective | `positions()`, `nosepiece()`, `pfs()` | store `return_xy`, `z_before`, `objective_before` in the `started` start state | original step 1 |
| (1b) lights off | `all_off()` | readback | not in the original |
| 2 PFS off → retract Z → confirm PFS Out of Range | `axis.require_pfs_quiet(disable=True)`, `axis.park_at(0.0)`, `positions()`, `pfs()` | Check the Z readback is the retract value ± tolerance. If not `pfs().out_of_range` (In Range or a failed read), stop (Z is 0) | original steps 4–6 |
| 3 Y escape | `xy.goto(*step_out_target(backend, x, y)[:2])` (= `y + ESCAPE_DY_UM`) | **Large-XY-move guard: only when the Z retract is confirmed by readback.** Z is read again right before the move. XY readback comparison | not in the original |
| 4 rotate the objective, confirm by reading | `rotate_nosepiece(backend, axis, target_state)` → label, rebuild `FocusAxis` for the new objective, `info()` | `rotate_nosepiece` checks Z retract, PFS off and Out of Range, and the readback. If the label differs from the target objective, stop. Z is left at 0, XY at the escape position | original steps 7–8, 10 |
| 5 the user: load immersion liquid → "Loading done" | wait with `scope.ask("load_immersion", "Loading done", immersion=<oil\|water>)` (the kind `manual_step` is T-011) | While waiting, this operation sends no command to Z, XY or the Nosepiece. The answer is kept as a `manual_step` record | after the original's `--park`, a person applies oil |
| (5b) if `park_only`, `finished(state="awaiting_return")` here | | | the original's `--park` exit |
| 6 return XY to the position from step 1 | `xy.goto(*return_xy)` (the guard reads Z again) | the same guard as step 3. XY readback comparison | not in the original |
| 7 stepped Z approach | `axis.approach(approach_target_um, approach_step_um)` | Once up to 2800, then a readback and an ascent check at every stride of at most the objective's `approach_step_um`. It does not jump to the target | replaces original step 11 (`move_to(2800)` in one go) |
| end | `nosepiece()`, `positions()`, `info().pixel_um` | | original step 12 |

- Step 7's target is "a target, not a destination" (soft-matter-agents task 026 §2 item 6). The approach starts from the retracted position, and
  the comparison must be live at every stride. What it compares against is, for now, the Z window's upper limit and the per-objective upper limit. Once F3's coverslip thickness and
  sample thickness are set, those values go in (PLAN F3).
- **Inference**: original step 11, `move_to(2800, allow_ascent_um=2800.5)`, appears to have FocusAxis send this climb as a single command.
  2800 µm is about 190 µm below the 100x focus (about 2989), so there was no problem on 9/30. The stepped approach is for objectives without this
  margin (objectives with a short working distance, cases with a large parfocal error).
- 2800 µm is the Z window's lower limit. The approach path 0 → 2800 lies outside the window. The guard treats "an `approach` started from the retracted state" as
  the permitted path for a move outside the window (the same place as T-002's objective-change exception).

**5) abort / finally**

| When stopped | Z | XY | State left |
|---|---|---|---|
| between 1 and 2 | where it is (not raised) | where it is | `aborted` |
| after the retract in 2, before 3 | retracted | where it is | `aborted` |
| 3–5 (escape, rotation, waiting for loading) | retracted | escape position | `aborted(state="awaiting_return", return_xy=...)` |
| during the return in 6 | retracted | where it stopped | `awaiting_return` |
| during the approach in 7 | where it stopped. **No stop ever raises Z** | the start XY | `aborted` |

- `all_off()` on every path (a readback check even when nothing is on).
- `awaiting_return` is kept in the sample record, so that the next time the engine starts the UI can show "Return to sample position".
  In this state other motion operations are blocked in preflight.

**6) Records**

| Now | Engine |
|---|---|
| `state` JSON lines on stdout (`nosepiece_state, nosepiece_label, z_um, pfs_enabled, pfs_locked, pfs_in_range`) and guidance text. No file | `<sample>/objective_change_<stamp>/`: `log.jsonl` (`progress(step=1..7)` per step, `property_set`, `position`), `summary.json`: start state, readback per step, `manual_step: {step: load_immersion, immersion, confirmed_at, by: user}`, end state, `state` (`done` / `awaiting_return` / `aborted`) |
| `objectives_used` in `sample.json` is updated by the live view | updated by the engine when step 4 succeeds |

**7) Confirmation points**

| Point | `confirm_required` |
|---|---|
| before start | `"rotate <label_now> -> <label_target>: retract Z, move Y <dy>, rotate"` + plan. On 9/30 a person explicitly approved the rotation in chat |
| step 5 | `manual_step: load_immersion` (the "Loading done" button). This answer is also the approval to start steps 6 and 7 |
| when changing to a dry objective (`escape=False`) | instead of step 5, `"objective rotated; continue to approach Z?"` (proposed). Whether to wipe the oil when going from 100x to 4x is the user's decision |

**8) Against the 9/30 record**: Step 3.

| Case | What happened | Reflected in |
|---|---|---|
| XY before the rotation | moved first to the hole centre (8026, 572) (`xy_before_um [8025.7, 571.4]`) | step 1 `return_xy` |
| order | PFS off → Z 0 → confirm PFS Out of Range → Nosepiece 5 → park → oil → Z 2800 | steps 2, 4, 5, 7 |
| result | `6-Plan Apo LmbdD0.13 100x Oil`, Z 2800.0 | step 4 readback |
| too little oil | a false rise near 3005 µm on the first 100x curve after the rotation. After more oil was applied, a clean peak (§7) | Re-applying oil means redoing steps 2, 3, 5, 6 and 7 of this operation. Proposed: a variant that allows "re-load immersion" with `target_state = current` |
| lab record | on 2026-09-07 a high-NA objective nearly touched the coverslip because of a wrong centre (`focus_100x.py` header) | step 7's stepped approach, the ceiling in §7 |

Gate (F2): Nosepiece read and write, ZDrive, PFS read, XYStage (when `escape=True`), the target objective's working distance in the objective table.

## 5. `hardware_scan` (F2)

No original (a new operation). Basis: `info` from `mm_grab.open_core`, `mm_grab.positions`, `mm_grab.PiezoReader.read`,
`change_objective.state`, and `load_configuration` and `preflight` in soft-matter-agents `devices/micromanager.py`.
**It only detects. It moves nothing and turns nothing on.**

**1) Input arguments**

| Engine argument | Default | Note |
|---|---|---|
| `include_properties` | True | Whether to read every property of every device. If off, only the device list and the key values |
| `piezo_port` | `"COM4"` | If `""`, the piezo is not opened (the same convention as live_focus `--piezo`) |
| `out` | default record location | where to write `hardware_profile.json`. Not the sample folder (it is per instrument) |

**2) plan**: shows only the list of what will be read. "Reads devices, properties, objectives, camera, positions, PFS, lights, piezo.
Nothing moves or turns on."

**3) preflight**

| Check | Result |
|---|---|
| another operation running | Blocked. Detection does not run alongside another operation |
| the backend is open | The one opened at engine start. Loading the config applies the Startup preset (0.3), so that fact is kept in the record |
| piezo port | If the NanoBench program holds the port, `PiezoReader` raises `OSError`. A failure does not block; it is kept as `piezo.error` |

**4) run** (all reads)

| # | What is read | Engine call | Basis in the original |
|---|---|---|---|
| 1 | config path, sha256, whether it changed during load, AutoShutter readback | `info()` + `config_record()` (T-015) | the return value of soft-matter-agents `load_configuration` |
| 2 | list of loaded devices; each device's type, library, description | `describe_devices(include_properties)` (T-015) → `getLoadedDevices`, `getDeviceType`, `getDeviceLibrary`, `getDeviceDescription` | none. T-015 adds it to the backend |
| 3 | per-device properties: value, whether read-only, allowed values, limits, whether the read succeeded | the same method → `getDevicePropertyNames`, `getProperty`, `isPropertyReadOnly`, `getAllowedPropertyValues`, `getPropertyLowerLimit/UpperLimit` | none |
| 4 | objective list: State, Label, pixel size | `nosepiece()`, `info().objectives` (state, label, pixel_um) + `nosepiece_labels()` (T-015) → `getStateLabels("Nosepiece")` | `change_objective.state`, `pixel_um` from `open_core` |
| 5 | camera: name, sensor, ROI, bit depth, ceiling, PixelType | `info()` | `open_core`, `getImageBitDepth` |
| 6 | position: XY, Z | `positions()` | `mm_grab.positions` |
| 7 | PFS: enabled, locked, in range | `pfs()` | `change_objective.state` |
| 8 | light state: Aura State and line, DiaLamp State | `light_state()`, the line by `read_property("Aura", ...)` | none |
| 9 | piezo: connected or not, x/y/z µm | `piezo_read(port)` (T-015) → `PiezoReader(port).read()` then `close()` | `mm_grab.PiezoReader`. `read()` does not write. A security-level change happens only in `move_z`, so detection does not cause one |
| 10 | cross-check against the objective table: registry key, working distance, immersion | pure function | The objective table holds values a person entered, not detected ones (§10 Q8) |
| 11 | gate verdict | `gates.py` (WP-G) | PLAN F2.2 |

- At the detection stage, "whether it can be confirmed by reading" is known only as far as **whether it can be read**. Whether a readback after a write matches cannot be
  known without writing. So each device carries `read_back: true/false` and `write_verified: null` (not tested yet) separately.
  The names match the `read_back` and `automatable` fields of soft-matter-agents `preflight`.

**5) abort / finally**: there is nothing to undo. If a piezo session was opened, `close()` (it closes as it was, since the security level was never changed).
`all_off()` is not called (a read-only operation does not change the lights). But if the light state read is on, a `log` warning.

**6) Records**

Proposed fields of `hardware_profile.json` (working name, PLAN F2.1):

| Field | Contents |
|---|---|
| `detected_at`, `backend` (`mock` / `mm-demo` / `mm-real`), `host` | |
| `config` | `path, sha256, changed_during_load, autoshutter_verified, startup_preset_applied` |
| `devices[]` | `label, type, library, description, read_back, write_verified, properties{name: {value, read_only, allowed, limits, read_ok}}` |
| `objectives[]` | `state, label, pixel_um, registry_key, working_distance_um, immersion` (the last three from the objective table) |
| `camera` | `name, sensor, roi, bit_depth, ceiling_adu, pixel_type` |
| `positions`, `pfs`, `lights` | values at detection time |
| `piezo` | `port, connected, x_um, y_um, z_um, error` |
| `human_confirmed{}` | items a person confirms. E.g. DiaLamp intensity (608 at the stand), CondenserTurret, the 40x WI correction collar. UI input, not detection |
| `gates{}` | per operation, on/off and the reason it is off |

Engine record: `hardware_scan_<stamp>/log.jsonl` (`reading` per read), `summary.json` = the profile above. Where the latest profile lives is
decided by T-002/WP-G.

Draft gate table (input to WP-G):

| Operation | Devices and conditions needed |
|---|---|
| `status`, `lights_off` | even without a camera. Aura and DiaLamp read |
| `edge_trace` | camera, XYStage read and write, DiaLamp, the 4x objective, an image that allows the stage-camera calibration for this objective |
| `scan_4x` | the above + ZDrive, PFS read, Aura line, camera bit depth, the sample's `hole` |
| `sample_map` | same as `scan_4x` (the light is DiaLamp) |
| `objective_change` | Nosepiece read and write, ZDrive, PFS read, XYStage (`escape=True`), the target objective's working distance |
| `focus_100x` | 100x Oil on the Nosepiece, ZDrive, PFS, Aura, a `load_immersion` record from this session |

**7) Confirmation points**: none. The `human_confirmed` items are an input form, not a confirmation dialog.

**8) Against the 9/30 record**: the §3 "Settings reference" table (MM config, camera 12-bit ceiling 4095, pixel size 4x 1.625 /
100x 0.065, Z window, DiaLamp 608, CondenserTurret `3-`, LightPath `4-L100`, PFS off, piezo read-only z 9.94 µm) is
the first example of this profile. Related failure: auto exposure that assumed 16-bit for a 12-bit camera (§3 item 8) is prevented by the profile's `bit_depth`.

## 6. `sample_map` (F4)

No original (a new operation). It reuses `edge_trace` (§8) and `scan_4x` (§3), and the mosaic uses the assembly method of
`scripts/plot_scan.py`. PLAN F4: transmitted light (DiaLamp) recommended.

F4 is split into three operations, not one. Only the scan has long motion, the flag has no motion, and the click move is short.

| Name | What it does | Motion |
|---|---|---|
| `sample_map` | transmitted-light 4x tile scan, mosaic, particle candidates | XY, Z |
| `map_flag` | a flag at a point on the map (F4.4) | none (record only) |
| `goto_xy` | move to the clicked map position (F4.3) | XY (Z retract first if needed) |

### 6.1 `sample_map`

**1) Input arguments**: the `scan_4x` arguments (§3 item 1) with only the lighting changed.

| Engine argument | Default | Note |
|---|---|---|
| `sample_id`, `margin_um`, `overlap`, `z_guess_um`, `first_half_um`, `tile_half_um`, `dry_run` | same as `scan_4x` | |
| `light` | `"bf"` | `"bf"` = DiaLamp (Aura State 0, DiaLamp State 1). `"aura"` is the same as `scan_4x` |
| `exposure_ms` | 12 | the 9/30 brightfield 4x value. With auto exposure, the 50 % of ceiling target may be too bright in brightfield (§10 question) |
| `focus` | `"per_tile"` | `"per_tile"`: a sweep per tile (same as `scan_4x`). `"plane"`: use the focal plane of the latest `scan_4x` and do not sweep |
| `candidates` | True | particle candidate detection |

**2) plan**: the same as `scan_4x`'s plan (grid, box, sweeps). If `focus="plane"`, it shows each tile's Z computed from the plane.

**3) preflight**: all of `scan_4x`'s preflight (4x objective, `hole`, whether the fit is from this session, bit depth, current Z).
In addition: if `focus="plane"`, a `scan4x_*/scan.json` for the same sample must exist.

**4) run**

| # | Engine call | Basis in the original |
|---|---|---|
| 1 | enter the `operation()` scope → `axis.require_pfs_quiet(disable=True)` | `scan_4x` step 7 |
| 2 | `light="bf"`: `aura_off()`, `scope.lamp_on()` (readback). `"aura"`: `scope.aura_line_on()` | `live_focus --set Aura State 0 --set DiaLamp State 1`, `scan_4x` step 8 |
| 3 | tile loop: the same as `scan_4x` steps 9–19 (XY box guard, sweeps, `best_z_um`, dropout filter, block z, `park_at`, tile save) | `scan_4x` |
| 4 | mosaic: bin tiles 8×8, flip left-right and up-down by the signs of the stage-camera calibration `M_px_per_um`, place at the tile centres `x_um, y_um` | the `mosaic` assembly in `plot_scan.py` (`flip_lr = M[0,0] > 0`, `rows_up = M[1,1] < 0`) |
| 5 | particle candidates: find spots with classical image processing → pixels → stage coordinates (`stage + inv(M) @ (centre − p)`) | the coordinate transform of the 9/30 record Step 1. The detection method is to be settled with WP-E (T-003) |
| 6 | `finished`. The `operation()` scope does `all_off()` | |

- The 9/30 particles are about 6.7 µm (FWHM) and a 4x pixel is 1.625 µm, so one particle is a little over 4 pixels. Whether they are visible in brightfield 4x
  has not been confirmed (§10 question). Candidates are recorded only as "candidates" and kept distinct from what a person confirmed (PLAN F4).
- Whether a brightfield Vollath sweep finds focus at 4x has not been confirmed either. The 9/30 4x scan was done under Aura GREEN 1 %.
  That is why the `focus="plane"` option exists.

**5) abort / finally**: the same as `scan_4x`. Z and XY stay where they are. The `operation()` scope turns off DiaLamp and Aura.
It does not leave DiaLamp on the way `live_focus.py` does.

**6) Records**

| File | Contents |
|---|---|
| `<sample>/sample_map_<stamp>/` | `log.jsonl`, `summary.json` (= the `scan.json` fields of `scan_4x` + `light`, `focus`), tile `.npy` |
| `mosaic.npy` + `mosaic.json` in the same folder | the binned mosaic and its extent (`x0, x1, y0, y1, um_per_px, bin`). The UI uses it to draw |
| `<sample>/map.json` (existing) or a new `features.json` | particle candidates `{x_um, y_um, source: "classical_candidate", score, map_id}`. When a person confirms one, a new entry with `source: "person_confirmed"` is added (nothing is overwritten) |

There are no model values. If DINO comes to be used for candidate scores, those numbers are marked `grade: model` (PLAN §6 item 3).

**7) Confirmation points**: the same as `scan_4x` (once before start, the fit time, a first move from outside the window).

**8) Against the 9/30 record**: Step 1 (brightfield exposure 12 ms, median 2766 ADU at 10 ms, saturated at 30 ms and above), Step 2
(grid, mosaic, `plot_scan.py`). The mosaic's left-right flip: the image is a mirror image of the stage (the calibration result of Step 1).

### 6.2 `map_flag`

- Arguments: `sample_id`, `x_um`, `y_um`, `name`, `note`. Filled in by the engine: `t`, the current objective, the current Z.
- No motion; preflight only checks that the sample folder exists. Record: `<sample>/flags.json` (or `kind: flag` in `features.json`).
  The fields of PLAN F4.4: name, note, time, objective, coordinates.
- Deleting does not erase; it adds `retired_at` (the record stays).

### 6.3 `goto_xy` (click move, F4.3)

**1) Arguments**: `x_um`, `y_um`, `sample_id`. Optional: `retract_first` (default automatic).

**2) plan**: the distance from the current XY to the target XY, whether it is a large move, whether a Z retract is needed, the Z value to retract to.

**3) preflight**

| Check | Result |
|---|---|
| the target is inside the sample's map extent + margin | Refused if outside (PLAN F4 "Outside the scan box it is refused"). The extent is the box of the latest `sample_map` or `scan_4x` |
| another operation running | Blocked |
| `awaiting_return` state (4.2 item 5) | Blocked |

**4) run**

| # | Engine call | Guard |
|---|---|---|
| 1 | `positions()` | |
| 2 | if a large move: if Z is not retracted, first retract with `axis.park_at(Z_SAFE_UM)` and confirm with `positions()` | **A large XY move only when the Z retract is confirmed by readback** |
| 3 | `xy.goto(x, y)` | XY box, XY readback comparison |
| 4 | Z is left retracted. Raising it again is the next operation the user chooses (one tile sweep of `scan_4x`, the approach of `objective_change`, `focus_100x`) | It does not jump to the target |

Provisional values set (`guards.py`, unmeasured provisional, see 0.1):
- The threshold for a "large move": `OBJECTIVE_LIMITS[key].long_xy_um`. 10 mm for working distance 10 mm or more (4x), otherwise min(field of view, 1 mm)
  (100x Oil 156 µm). If the objective cannot be read, the strictest value (retract for every move). `edge_trace`'s single stride (at most 200 µm) and
  calibration move (200 µm) are below the 4x threshold.
- `z_safe`: `Z_SAFE_UM` = 0 µm, for all objectives. Per-objective values after measurement on the microscope PC (Q20).

**5) abort**: stops between moves. Z is not raised. This operation turns no light on.

**6) Records**: `<sample>/goto_xy_<stamp>/summary.json` (start, whether it retracted, target, landing readback). Since it is a short operation,
one line in a per-sample `moves.jsonl` may replace it if T-002 allows.

**7) Confirmation points**: for a move that needs a Z retract, `confirm_required("retract Z <z> -> <z_safe>, then move to (x, y)")`.
A small move that needs no retract goes without confirmation (the click itself is the command).

**8) Against the 9/30 record**: the original has no click move. The 9/30 case of a person moving the stage by hand (record §4 item 3) and
the case of `find_particle_z` stopping on the readback guard during a person's move (3037/3036) are the same problem. A readback comparison after the move is needed.

## 7. `focus_100x`

Original: `scripts/focus_100x.py` (deleted in R-05; in history). No button in the launcher (a manual step).

**1) Input arguments**

| Command line | Default | Engine argument | Note |
|---|---|---|---|
| `--centre` | 2930.0 µm | `centre_um` | sweep centre. **Not set to the 4x focus** (item 8 below) |
| `--half` | 40.0 µm | `half_um` | coarse sweep half-width |
| `--step` | 2.0 µm | `step_um` | |
| `--fine-half` | 3.0 µm | `fine_half_um` | |
| `--fine-step` | 0.2 µm | `fine_step_um` | |
| `--exposure` | 30.0 ms | `exposure_ms` | **The engine default is 20 ms** (`focus_100x.DEFAULT_EXPOSURE_MS`, unmeasured provisional: one run on 9/30, no saturation) |
| `--aura LINE PERCENT` | GREEN 1 | `aura_line`, `aura_percent` | |
| `--metric` | `peak` | `metric` (`peak` / `vollath`) | `peak`: 4×4-binned maximum − median. For sparse-particle fields |
| `--out` | `D:\AutoFocus\samples\20260930_1849_1` (a fixed sample!) | `sample_id` | The original default is the 9/30 sample folder. The engine uses the current sample |

Fixed values: objective label `6-Plan Apo LmbdD0.13 100x Oil`, registry key `"100x-Oil"`, settle 0.1 s (coarse) / 0.15 s (fine).

**2) plan**

- Coarse sweep `axis.plan(centre, half, step)`; the fine sweep is the coarse peak ± `fine_half` @ `fine_step`.
- Ceiling: the header says `min(3200, centre + 0.4 × 130 µm)`. **The code has no such calculation.** **Inference**: FocusAxis
  computes it from the working distance of the registry key `"100x-Oil"`. The engine's plan shows this ceiling as a number (§10 Q8, Q15).
- Proposed centre: the Z at the current XY from the same sample's 4x focal plane, plus the parfocal offset (about −60 µm, measured 9/30).
  It is a proposal derived from measurements, not a model value. The run uses the value as corrected by a person.

**3) preflight**

| Check | Original | Engine |
|---|---|---|
| objective label = 100x Oil | present (`refusing`) | `preflight_failed` |
| oil loading | none | There must be a `load_immersion` record from `objective_change` in this session. If not, `confirm_required` |
| `centre_um` near the 4x focus | none (only a header warning) | If above the 4x focal-plane value, a warning and `confirm_required` |
| within the ceiling | **Inference**: FocusAxis refuses at the plan stage | A sweep that crosses the plan's ceiling is `preflight_failed` |
| signal | none | Take one frame at the start Z; if the maximum is near the dark offset (about 102 ADU), warn. The 9/30 30 ms Vollath failure case |

**4) run**

| # | Script call | Engine call | Note |
|---|---|---|---|
| 1 | `open_core(exposure, 0)` | `set_exposure()`, `info()` | |
| 2 | `getProperty("Nosepiece", "Label")` | `nosepiece()` | preflight |
| 3 | `FocusAxis(core, "100x-Oil", allow_motion=True)` | guarded Z axis | |
| 4 | `ceiling = 2 ** getImageBitDepth() − 1` | `info().ceiling_adu` | for the saturation test |
| 5 | `axis.require_pfs_quiet(disable=True)` | same | |
| 6 | `aura_on(core, line, pct)` | `scope.aura_line_on(line, pct)` | inside the `operation()` scope |
| 7 | `axis.sweep(axis.plan(centre, half, step), grab, score=, settle_s=0.1)` | same | `score`: `sharp` (peak or vollath), `vollath`, `mean`, `max`, `sat` |
| 8a | peak at the **top end** (`argmax_index == last`): "PEAK AT THE TOP END", `axis.move_to(coarse.points[0].z_um)` (goes down to the bottom end), no fine sweep | the same move, then `confirm_required("peak at the top end; extend upward?")` | The original ends here. A person reruns with a new centre |
| 8b | peak at the **bottom end** (`argmax_index == 0`): prints "re-centre lower", no fine sweep | `reading(peak_at="low_end")` | Rerunning lower is the safe direction. Proposed without confirmation |
| 8c | interior peak: `axis.sweep(axis.plan(coarse.peak_z_um, fine_half, fine_step), grab, score=, settle_s=0.15)` | same | |
| 9 | `best_z_um(coarse, fine)` | same | |
| 10 | if `zf` exists, `axis.park_at(zf)` | same | |
| 11 | `positions(core)` | `positions()` | |

**5) abort / finally**

| Original `finally` | Engine |
|---|---|
| if `lights` exists, `aura_off()` | `all_off()` of the `operation()` scope |
| save `focus100x_<stamp>.json` (even if interrupted) | `summary.json` + `aborted` |
| Z where it is | where it is. With a top-end peak, in the state of having gone down to the bottom end, as in the original |

Gap: the same `aura_on` partial-failure problem as `scan_4x` (§3 item 5).

**6) Records**

| Now `focus100x_<stamp>.json` | Engine |
|---|---|
| `started, header (=info), coarse [(z_readback, score, mean, max)], fine [...], z_focus_um, why, z_parked_um, position` | the same fields in `summary.json` + **run arguments missing from the original** (`centre_um, half_um, step_um, exposure_ms, metric, aura`) and `sat`. The 9/30 yaml had to reconstruct the exposure and metric from notes |
| it writes to `--out` (default fixed to the 9/30 sample) | `focus100x_<stamp>/` of the current sample (keeping the existing prefix, the same way as `scan4x`) |

**7) Confirmation points**

| Point | `confirm_required` |
|---|---|
| extending upward after a top-end peak | `"peak at the top end of <lo>-<hi>; extend upward to <new_hi>?"`. The new range does not cross the ceiling. Operating rule `no_climb_without_ok` |
| no oil record | `"no immersion loading recorded this session; oil applied?"` |
| centre above the 4x focus | `"centre <c> is above the 4x focus <z4>; 100x focus is usually 60-100 um below"` |

**8) Against the 9/30 record**: Step 4.

| File | Exposure | Range | Result | Reflected in the spec |
|---|---|---|---|---|
| `focus100x_20260930-201702` | 30 ms, vollath | | only the dark offset (about 102 ADU) → no focus | preflight signal check, `metric=peak` default |
| `-202011` | 200 ms | 2890–2980 | top-end peak, not climbed | 8a, the upward-extension confirmation |
| `-202226` | 50 ms | 2965–3005 | 2982.0, saturated, false rise near 3005 (oil) | `sat` record, double-peak warning (below) |
| `-202507` | 30 ms | 2955–3015 | 2988.45 at (8164.7, 523.4), a clean peak after adding oil | |
| `-202813` | 20 ms | 2968–3008 | 2989.42 at (7811.0, 1529.0), no saturation, maximum 3435 ADU | engine default 20 ms (provisional) |

- Double peak: if the coarse curve has two separated local maxima, emit a "check immersion oil" warning (a classical verdict, not a model).
  This warning leads to the re-loading variant of 4.2.
- Saturation: if any point has `sat > 0`, a warning to reduce the exposure.
- 100x − 4x ≈ −60 µm (the lab's 2026-09-07 note says about −100 µm). Re-measuring on a reference sample is PLAN §10.

## 8. `edge_trace`

Original: `EdgeTracker` in `scripts/edge_track.py` and the `t` key (`toggle_track`) in `scripts/live_focus.py` (deleted in R-05; in history).
Launcher Step 1 "Start live view" (brightfield), then `t` in the window. The offline simulation is `scripts/sim_edge_track.py`.

**1) Input arguments**

| Original | Default | Engine argument | Note |
|---|---|---|---|
| live_focus `--exposure` | 30 ms (launcher brightfield default 12) | `exposure_ms` | 9/30: 12 ms |
| live_focus `--hole-diameter` | None | `hole_diameter_mm` | the tracker's `expect_diameter_um` |
| live_focus `--track-speed` | 100 µm/s | `speed_um_s` | clipped to 10–1000. During the run `+`/`-` set it to 2 times / half |
| live_focus `--set Aura State 0 --set DiaLamp State 1` | (the launcher adds it) | `light="bf"` | |
| live_focus `--sample` | new id | `sample_id` | |
| `EdgeTracker(step_um=50, cal_um=200, point_every_um=250, max_radius_um=7000, max_path_um=25000, max_time_s=360, min_radius_um=1000)` | | same names | the stride is `speed × 0.5 s` clipped to 20–200 µm |
| `min_blob_um = 500`, settle `2 × exposure + 0.08 s` | | constants | |

**2) plan**: the start XY, the maximum-radius circle (7 mm from the start point), the maximum path 25 mm, the maximum time 360 s, the speed and the stride.
The calibration moves (out and back +x 200 µm, out and back +y 200 µm) are shown in advance.

**3) preflight**

| Check | Original | Engine |
|---|---|---|
| demo mode | refused with `"edge tracking needs the real stage"` | The mock backend must support tracking (M1 mock first). `sim_edge_track.py` is the basis |
| objective | no check | 4x recommended. A warning for any other objective (the calibration is stored per objective: `stage_camera_calibration.objective`) |
| lighting | the launcher turns on brightfield | if `light="bf"`, turned on in run step 1 |
| previous boundary | none. On 9/30 the agent backed it up and cleared it by hand | If the sample has a `boundary`, back up to `map_before_rescan_<stamp>.json` and `sample_before_rescan_<stamp>.json` and clear only `boundary` (the visit fields stay). `confirm_required` |
| another operation | original: refused if a servo or sweep is running | single operation in the engine |

**4) run**

| # | Original call | Engine call | Note |
|---|---|---|---|
| 1 | Aura State 0, DiaLamp State 1 with `set_and_read` | enter `operation()` → `aura_off()`, `scope.lamp_on()` | |
| 2 | `startContinuousSequenceAcquisition`, `popNextImageAndMD` every tick → `tracker.feed(img)` | `start_stream(interval_ms)`, `next_frame(timeout_s)`, `stop_stream()` (T-015). `snap()` cannot be used during a stream (`StreamActive`). T-002's `snap()` alone would also work, but sharing with the live view needs continuous acquisition | `feed` uses only frames taken after the settle time since the last move |
| 3 | calibration: `getXYPosition` → `setRelativeXYPosition(+200, 0)` → frame → phase correlation → `(−200, 0)` → the same for y | `positions()`, `xy.goto_rel(dx_um, dy_um)` | stops with "too little structure" if the peak sharpness is < 8. Stops if `um_per_px / pixel_um` is outside 0.7–1.4 |
| 4 | tracking loop: `find_edge` → circle fit (`robust_circle`, fixed diameter `fixed_radius_centre`) → one stride of `setRelativeXYPosition` → `waitForDevice` | pure functions (the image functions of `edge_track`) + `xy.goto_rel` + `positions()` | XY only. Z does not move |
| 5 | stop conditions: more than 7 mm from the start point, path or time limit, boundary lost (if there is a circle, coast along it for up to about 2 mm, otherwise 3 frames), one full lap (path > 3 mm and back at the first point seen), a key (`t`, `Esc`), an exception | the same conditions. The key is an `abort` command | |
| 6 | `edge_point` (every 250 µm) → `map.mark_boundary(Ti2 + piezo)` | `progress(edge_point)` + appended to the sample's `boundary` | coordinates are the Ti2 + piezo sum |
| 7 | `cal_result` → `sample.calibration = {um_per_px, angle_deg, M_px_per_um, objective}` | the sample's `stage_camera_calibration` | read by `scan_4x` and `plot_scan` |
| 8 | the live view's `Sample.save()` every 10 seconds → `hole` fit (`XYMap.circle`) | at the end, write the `hole` fit into `sample.json` and add `fitted_at` | the fit is a circle over all boundary points, not the tracker's internal circle |
| 9 | speed change during the run, `set_speed` | the run-time argument-change command `update` (`COMMAND_KINDS`, T-011). The operation declares its changeable arguments as `updatable` | applied in T-011 |

Motion limits: one stride is at most 200 µm, the calibration is 200 µm. The range of motion is held by the "7 mm circle around the start point". Both are below
`goto_xy`'s "large move" threshold (6.3), so they do not trip the Z-retract condition.

**5) abort / finally**

| Original | Engine |
|---|---|
| tracker `stop(why)` → `track_stop` record. A stride in progress finishes (`waitForDevice`) | same |
| live_focus `finally`: stop tracking, servo and sweep, stop continuous acquisition, `aura_off` if it was `--aura`, `Sample.close()` (save), close the piezo | same + **DiaLamp is turned off too** (`all_off()`). The original does not turn off the lamp it turned on with `--set DiaLamp State 1` (9/30 known problem 4) |
| XY where it stopped | same. Z is not touched |

**6) Records**

| Now | Engine |
|---|---|
| `<sample>/track_<stamp>.jsonl`: first line `{header, sample}`, then `track_start, cal, cal_result, move (why, d_um, at_um), edge_point (um, contrast), track_speed, track_stop (why)` and the live view's events | the same event names in `<sample>/edge_trace_<stamp>/log.jsonl` (subkinds of `progress`). Separated from the live view's events |
| `<sample>/map.json`: `boundary` (sum coordinates), `visits` | as is (T-002 `sample.py`) |
| `<sample>/sample.json`: `hole {centre_um, diameter_mm, fit_rms_um, n_points, arc_deg}`, `boundary_limits_um`, `stage_camera_calibration` | same + `hole.fitted_at` (the manager's answer: applied in T-002) |
| backup `*_before_rescan_<stamp>.json` | the automatic backup in preflight |

**7) Confirmation points**

| Point | `confirm_required` |
|---|---|
| there is a previous boundary | `"replace the hole fit from <fitted_at>? (backed up)"` |
| start | `"trace the edge: XY moves only, within 7 mm of here"` |
| after the end | none. The result (diameter, rms, arc angle) is shown. A warning if the diameter differs from `hole_diameter_mm` by more than 20 % |

**8) Against the 9/30 record**: Step 1.

| Item | Value |
|---|---|
| start | (8833.4, −2354.1), speed 400 µm/s, stride 200 µm (raised by a person), stopped on one full lap |
| result | centre (8026.0, 571.6), diameter 6.1438 mm, rms 42.5 µm, 49 points, 352° |
| previous fit | (9361.1, 1272.2), 5.9919 mm. Moved 1.5 mm between 18:49 → 19:57 → the "re-trace every session" rule |
| calibration | 1.6252 µm/px, 0.117°, `M = [[0.6160, 0.0024], [0.0013, −0.6146]]`. The image is a mirror image of the stage |
| brightfield | DiaLamp intensity 608/2100 (stand), median 2766 ADU at 10 ms, saturated at 30 ms and above, 12 ms used |
| failure | DiaLamp stays on after the window is closed (known problem 4) → item 5 |

## 9. Deferred and out of scope

### 9.1 `find_particle_z` (deferred)

`scripts/find_particle_z.py` (deleted in R-05; in history): moves the 100x field of view in a spiral (150 µm spacing), takes an upward Z stack at 1 µm spacing in each field,
and takes as a particle a point whose brightness peaks **inside** a given Z band. Per the 9/30 record §4 item 1 it is **not usable**.

- The spot test is wrong. Real particles are about 6.7 µm (FWHM), but in the 9/30 run the test assumed 2.5 µm. The current code's
  default is `--particle-um 7.0`. At 7 µm it finds the particle a person found (3010.0 µm) in the saved stack, but it also passes 24
  synthesized fragments of defocus rings.
- 4 runs, 46 fields of view, nothing found. The last run stopped on the readback guard (3037.0 commanded /
  3036.0 read) while a person was moving the stage.
- Not ported. The spec will be written again once the test problem is solved. F4.2 (finding a lost particle) is handled for now by `sample_map`'s candidates and
  flags.

### 9.2 `focus_servo` (out of scope)

`scripts/focus_servo.py` (deleted in R-05; in history) is three routines that fine-focus inside the live view with the **piezo Z** (NanoBench, 0–600 µm).
`FocusServo` (the `f` key) measures the slope and sign with a +0.5 µm probe to drive the DINO head's signed score to 0,
and moves at most 0.5 µm per stride, within ±5 µm of the start point. `AutoFocusZ` (`w`) looks for the Vollath peak over ±1 µm at 0.25 µm spacing,
widens up to ±5 µm if the peak sits at an end, and picks the direction by the DINO score if the curve is flat. `ZSweep` (`W`) is a ±5 µm diagnostic sweep.
All write with `PiezoReader.move_z`, switching the controller's security level to User before the first write and restoring it on close.

Judgement: **out of the M1–M3 scope** (by the PLAN v0.2 milestones, a candidate for M5 "focus verdict").
- The DINO score becomes an input to a motion command. To agree with PLAN §6 items 2 and 3 (the model gives a verdict, not a Z), it must be redesigned so that instead of a servo the T-003 verdict
  (`step_up` / `step_down`) moves one stride only after a classical metric has confirmed it.
- Piezo writes change the controller's security level. The T-002 protocol has no piezo write (reading is `positions().piezo_um`). A piezo write method and a separate gate must come first.
- Taking only the Vollath part of `AutoFocusZ` would give a classical fine focus. That part overlaps with `focus_100x`'s fine sweep.

### 9.3 What this document does not cover

- The live view (`live`) itself: frame display, the score panel and map drawing belong to T-004 (UI) and T-002 (frame events).
  This document covers only `edge_trace`, which issues motion inside the live view.
- The `b` / `u` keys (marking and erasing boundary points by hand): record commands with no motion. They can be handled the same way as `map_flag`.

## 10. Questions to check on the microscope PC

Reading FocusAxis (`C:\agentic_microscope\hardware\focus.py`) or running it once on the bench answers them.

| # | Question | Why it is needed |
|---|---|---|
| Q1 | When the current Z is above the plan's start point, how does `sweep(plan, ...)` get to the start point (does it go down and come back up, or refuse) | the exact meaning of the "upward only" guard and of `allow_ascent_um` |
| Q2 | What is the readback tolerance? On 9/30 it stopped at 3037.0 commanded / 3036.0 read | default of the T-002 guard |
| Q3 | `park_at(z)`'s approach direction and return value (the landing readback or the commanded value) | the meaning of `z_image_um` |
| Q4 | the rules of `best_z_um(coarse, fine)` and the list of `why` strings | expected values for the port and the mock tests |
| Q5 | what `require_pfs_quiet(disable=True)` reads and writes | the boundary between preflight and run |
| Q6 | what `move_to` and `sweep` do when `dry_run=True` | the definition of the engine's `dry_run` |
| Q7 | if `KeyboardInterrupt` arrives during a move, does the ZDrive stop or go on to the commanded position | recording the Z position on abort |
| Q8 | where are the upper-limit and working-distance values per registry key (`"4x"`, `"100x-Oil"`) | ownership of the objective table (T-002 or the F2 configuration file) |
| Q9 | does `open_core`'s Startup preset (`LappMainBranch1 State 1`) cause any visible change | whether the engine may load the config only once |
| Q10 | does the Aura master State 0 alone turn off every line | the definition of `all_off()` |
| Q11 | the normal error range of the XYStage readback | the tolerance of the XY readback comparison |
| Q12 | F5's Y escape direction and distance (provisionally +Y 15 mm for now, PLAN v1.3), the stage's Y limit, the direction of the sample's 24 mm side | the value of `escape_dy_um` and the limit check in preflight (PLAN §10) |
| Q13 | a safe `approach` stride, and the time taken, when raising the 100x Oil from 0 to 2800 µm. May it go up to 2800 in one go as in the original | the `approach_step_um` default |
| Q14 | does `waitForDevice("Nosepiece")` return after the rotation has mechanically finished | the meaning of the step 4 readback |
| Q15 | where is the 100x ceiling `min(3200, centre + 0.4 × 130)` computed (FocusAxis, the registry)? Is its reference the plan's centre | the ceiling shown in the `focus_100x` plan and the upward-extension range |
| Q16 | does a per-tile Vollath sweep find focus in brightfield 4x (the 9/30 scan was done in Aura fluorescence) | the `focus` default of `sample_map` |
| Q17 | the target of brightfield auto exposure (50 % of the ceiling is a fluorescence target) | `sample_map`'s `exposure_ms` |
| Q18 | are particles of about 6.7 µm visible in a brightfield 4x (1.625 µm/px) mosaic | whether particle candidate detection is possible |
| Q19 | does merely opening `PiezoReader` change anything on the controller? What happens if the port collides with the NanoBench program | whether `hardware_scan` keeps to "changes nothing" |
| Q20 | before an XY move of how many mm does the 100x Oil need a Z retract (oil film) | `goto_xy`'s "large move" threshold and `z_safe` |
| Q21 | does FocusAxis already have a function similar to the stepped approach | whether to write `approach` new or port it |
