# First motion on the stand (after the T-036 unlock)

This is the order for the first time the app moves the Ti2 through `mm-real`. The rules come from the
director (T-038); the code already refuses steps 4 and 5 on its own. Do the steps in order, and do not
skip one because the code would catch it.

Until the commit that sets `BENCH_MOTION = "UNLOCKED"` in `engine/backends/mm_real.py` is on main, every
`mm-real` move is refused with "bench motion locked until clearance guards land (T-027, T-011)". Only
step 1 can be done then. This lock is T-036 (card in the private internal notes, `dino-autofocus-internal/tasks/T-036-mm-real-motion-lock.md`).

Values marked *provisional* are "unmeasured provisional" in the code and the records. None of them has
been measured on this stand yet.

Every step is done by the user at the microscope PC, watching the stand. Nobody runs these steps from
another PC.

**Never move the stand with an old bench script.** The old scripts (`change_objective.py`, `scan_4x.py`,
`focus_100x.py`, `live_focus.py`, ...) bypassed the guards and the T-036 lock and were deleted in R-05
(they are in git history; do not restore one to move the stand). Motion goes through the app, or by
hand at the stand.

## How to stop, at any step

| What | Where | Effect |
|---|---|---|
| **Abort** button | common status bar, every screen (ui-spec 4) | aborts every running operation; lights go off on the exit path |
| `Esc` | any screen of the app | same as Abort ("stopped by Esc"); the live stream keeps running |
| **Lights off** button | common status bar | pre-empts: aborts the running operation, then switches all light off and reads it back |
| Close every app tab on the microscope PC | browser | a watched operation aborts 10 s later (D14) |
| Hardware stop | Ti2 controller / joystick at the stand | always available; use it if the screen does not respond |

On the microscope PC, Abort and Lights off work without a login (PLAN 6 rule 12, the T-009b contract:
loopback stops always work). A remote screen can only send Abort, and it needs a login (PLAN D13).

Each move is checked against its readback. A move that reads back more than 0.25 um off in Z or 5 um
off in XY (both tolerances *provisional*) stops the operation by itself. The record shows a `motion`
event with `target_um`, `read_um` and the tolerance.

## Step 1. Check the configuration on the microscope PC

Who: the user, before any motion. Nothing moves in this step.

1. Run the two read-only checks in `docs/microscope-pc-checklist.md`, section "실제 장비 백엔드 (T-033)":
   - the `Select-String` line for `System/Startup` and `System/Shutdown`;
   - the `check_load_settings` line.

   Both read the file only. Neither opens the stand.
2. Open and close the real backend once. Opening loads the configuration; with the lock on, it cannot
   move anything:

   ```powershell
   uv run python -c "from dino_autofocus.engine.backends.mm_real import MmRealBackend; b = MmRealBackend(r'C:\agentic_microscope\config\micromanager\single_cam_red_noDMD_nocom10.cfg'); i = b.open(); print(i.notes); print(b.config_record()); b.close()"
   ```

What you should see:
- The checklist's `check_load_settings` line prints `OK`. It passes `BENCH_DEVICES`, so it also refuses a
  Core role mismatch (T-036d). This is the pre-check: it reads the file without loading Micro-Manager.
- `open()` returns without `UnsafeConfig`. This is the binding check: only a clean `open()` counts as
  "passed". `UnsafeConfig` means one of two things:
  - a preset or a post-init line would set ZDrive, XYStage, Nosepiece or PFS;
  - the config's Core role labels differ from the backend's `DeviceNames`.
  If you see it, stop and tell the director's session. Do not edit the check to get past.
- `notes["bench_motion"]` reads `LOCKED` before the unlock commit and `UNLOCKED` after it.
- `notes["stage_limits"]` reads "not read: user check needed".

Write down:
- whether a `ConfigGroup,System,Shutdown` line exists, and what it sets;
- whether Micro-Manager applies it when the backend closes. The record does not say. To see it, give
  Shutdown a harmless visible value (a light path) and watch it change on close (checklist row
  "설정의 종료 프리셋").

Enforced by: T-036b (Startup / post-init lines), T-036c (Shutdown), T-036d (device and role labels).
Code: `mm_real.check_load_settings`, run in `open()` before anything is loaded.

## Step 2. 4x only: Z to 0, then small XY moves

Who: the user, watching the stand, with the Abort button and the hardware stop within reach.

Only after the unlock commit. The Z retract (2a or 2b) is safe on any lens. The XY moves (2c) need the 4x
(`1-Plan Apo LmbdD20 4x`, nosepiece State 0) in place.

Before you start, read where the stand is. The hardware screen "지금 상태 (Step 0)" or a `status` read
shows the lens, Z and PFS, and the status bar shows the position.
- PFS must read off. Software never enables it.

### 2a. The first engine motion: `z_retract`

The first move the app makes on the stand is `z_retract` (T-039, on main). It moves Z to `z_safe`
(0 um, *provisional*), away from the sample: the safest direction. It tests the lock lift, the readback
and the records before any XY move.

It is on main, but the motion lock (T-036) still refuses it on `mm-real` until the unlock commit
merges. Its preflight shows that as the `bench_motion` check, and `mm-real`'s own move refuses as well.

1. Start `z_retract` (no arguments) from the app. Rule 12 applies: a local operator with the control
   grant and an open experiment session. It is also allowed while a sample awaits return.
2. It switches PFS off first (never on), then retracts. Driving ZDrive against an engaged PFS fights
   the focus lock; PFS was on in the 2026-09-30 session. Preflight refuses if the PFS state cannot be
   read.
3. The status bar and the hardware screen show ZDrive 0.0 (+- 0.25, *provisional*), and PFS off.
4. In the log:
   - a `motion` event with `how: "retract"` and `sent: true`;
   - a `finished` event whose summary has `commanded_um`, `readback_um`, `verified: true`, `moved`,
     `from_um`, and `pfs` (`enabled_before` and `in_range_before` as found, `enabled` and `in_range`
     after the move).
5. If Z already reads 0, the op finishes with no move (`moved: false`) and records the readback.

A read Z off by more than the tolerance fails the op, naming the commanded and read values. So does a
PFS that stays enabled. Stop there and tell the director's session.

If `z_retract` is refused, check the refusal before anything else:
- `bench_motion` ("bench motion is locked") means the unlock commit is not on main;
- `pfs` means the PFS state is unreadable;
- no control grant or no open session is rule 12.

Enforced by: T-039 (the op: PFS off, then `FocusAxis.retract()`), T-036 (the lock), T-011 (rule 12).

### 2b. The fallback, by hand at the stand (the user)

Use this if `z_retract` is refused for a reason you cannot fix, or the screen does not respond:
1. Retract Z to 0 with the Ti2 controller. The hardware screen must then show ZDrive 0.0 (+- 0.25).
2. If the 4x is not in place, turn the nosepiece to the 4x by hand. The hardware screen must then show
   nosepiece State 0 and `1-Plan Apo LmbdD20 4x`. The 2026-09-30 session ended on the **100x Oil** with
   ZDrive at 498 um; if the stand is still like that, clean the oil off the 100x after turning.

The turn to 4x is always by hand for now. Do not use the app's `objective_change` for it: the code would
let it run, but it must not be used on the stand yet (2c, "Do not use the other operations instead").

### 2c. Small XY moves

**Through the app (engine XY moves with `goto_xy`), with Z at 0. All values are stage um:**

| # | Move | Expected readback | Rule that applies |
|---|---|---|---|
| a | (Z is at 0 from 2a or 2b) | ZDrive 0.0 +- 0.25 | Z already retracted, so no long-move rule can stop the moves below |
| b | XY +100 in X from where it is | X +100 +- 5, Y unchanged | inside the XY box; short move |
| c | XY -100 in X (back) | the start XY +- 5 | |
| d | XY +100 in Y, then -100 in Y | the start XY +- 5 | |
| e | XY +1000 in X, then back | the start XY +- 5 | under the 4x long-move row (10 mm, *provisional*), so Z may stay where it is; with Z at 0 it is retracted anyway |

What each move must show:
- The status bar position after every move.
- A `motion` event in the log with `sent: true` and `read_um` within the tolerance.
- The light stays off. These moves need no light.

Keep every move well inside the stage. The real stage limits are unknown (`StageLimits` all None), so
the backend cannot catch a move past the travel.

**`goto_xy` is on main (T-032 stage 2, `engine/operations/sample_map.py`).** A move longer than the
lens's long-move row with Z above the retracted height retracts Z first (`park_at` to the safe height,
PFS switched off before the retract and refused in preflight when its state cannot be read, the retract
confirmed by readback) and leaves Z retracted; a short move goes straight. With Z at 0 from 2a or 2b every
move in the table is short in that sense, so nothing retracts here. Like every motion operation it stays
behind `BENCH_MOTION` until the user's unlock commit. Do the XY moves above only after 2a has passed once
on the stand.

Do not use the other operations instead:
- **`objective_change`: do not run it on the stand**, including a turn to a dry lens without `escape`.
  Since the partial unlock (2026-10-02, "Bench approach lock" below) the code refuses only its climbs above
  2800 µm on a lens other than the 4x, 10x and 20x; the climb 0 -> 2800 is no longer refused. Keep this as
  a user rule until Q13 and Q20 are measured.
  - Its "clearance" callback is software bounds (Z window and cap, lens readback, abort), not a contact
    or oil sensor. The runner's bench check does not refuse it, because it has that callback.
  - A turn to the 4x that climbs back only to 2800 µm on the 4x is not above 2800. Do that turn by hand
    (2b).
- `scan_4x` is refused on `mm-real`:
  - by the runner, because it approaches with no clearance callback (T-011b `approach_clearance`);
  - no longer by T-029d: since the partial unlock the 4x may sweep above 2800.
  Any step that sweeps or scans stays blocked by the runner's check.

**Bench approach lock (T-029d), partially unlocked.** The user unlocked it on 2026-10-02
(`BENCH_APPROACH = "MEASURED"`), before Q13, Q20 and the stage limits were measured. It was planned as a
reviewed commit after those measurements.

Now the guards refuse on the stand any upward Z move (`approach`, `move_to` and sweeps) above the lens's
approach ceiling:
- 3200 µm for the 4x, 10x and 20x, whose free working distance covers the 400 µm window;
- 2800 µm for the 40x WI, 60x Oil, 100x Oil and an unreadable lens.

A sweep climbs to its start in one move with no clearance check, so this rule covers sweeps and `move_to`
too, not only `approach`. Downward moves and `z_retract` stay allowed.

What that leaves possible on the stand (once the motion lock is off):
- every lens may climb 0 -> 2800 µm, the move Q13 is about;
- the 4x, 10x and 20x may sweep and approach up to 3200 µm;
- `focus_100x` and the 100x approach above 2800 are still refused.

Until Q13 and Q20 are measured, the old rules stay user rules: no upward Z on a lens other than the 4x.
- Old bench scripts from git history: never (see the top of this runbook).

Enforced by:
- T-036, the lock;
- T-032 stage 2: `goto_xy`;
- T-027b: `approach` caps, and `is_bench`, which makes every non-mock backend count as the bench;
- T-011b: the bench clearance check in the runner's preflight (refuses `scan_4x`, not
  `objective_change`);
- `guards.XYAxis`: box, long-move rule, readback;
- T-029d: `BENCH_APPROACH`. Partially unlocked on 2026-10-02: it refuses upward Z above the lens's
  approach ceiling on the stand (2800 µm except the 4x, 10x and 20x). The "no `objective_change` on the
  stand" rule is this runbook only.

## Step 3. No 100x Oil approach yet

Who: the user. This is a rule to keep, not a move.

Do not raise Z under the 100x Oil (0 -> 2800 -> sample window) until two questions in
`docs/operations-spec.md` 10 are answered on this stand:
- **Q13**: the safe approach step and its timing. The default `approach_step_um` is 10 um (*provisional*).
- **Q20**: how long an XY move may be on the 100x before Z must retract (the oil film), and `z_safe`. Today
  `Z_SAFE_UM` is 0 for every lens and the 100x long-move row is 156 um (*provisional*).

Since the partial unlock (T-029d, "Bench approach lock" in step 2) the code refuses only the part above
2800 µm under the 100x: its approach above 2800 and `focus_100x`. The climb 0 -> 2800 µm under the 100x is
no longer refused by the code, so this step is a user rule. The clearance callbacks are software bounds (Z window and cap, lens readback, abort), not a
contact or oil sensor.

Treat the rest as a user rule until then.

Enforced by:
- T-029d (`BENCH_APPROACH`);
- T-027b and T-029: the approach cap above 2800 µm;
- `guards.OBJECTIVE_LIMITS` (*provisional*).

## Step 4. No F5 objective change on the stand yet

Who: the user. This is a rule to keep, not a move.

Do not run an objective change with the F5 step-out (`escape`) on the stand until:
- the stage X and Y travel limits are measured or read (checklist row "재물대 이동 한계", Q12);
- the +Y 15 mm step-out (`ESCAPE_DY_UM = +15000`, *provisional*) is checked against them at the stand.

What the screen shows: the objective change is refused in preflight with "the backend reports no stage
Y limit; refusing the step-out". `mm-real` reports no stage limits today, so this already holds. Keep it
that way: do not enter guessed limits to get past it.

Note: by default the step-out runs only for a change *to* an immersion lens (oil or water). An explicit
`escape: true` still forces one.

A turn to a dry lens (e.g. 100x Oil -> 4x) has no step-out by default, so the missing limits do not stop
it. It still needs Z retracted and PFS off and Out of Range. Step 2 says when `objective_change` may be
used on the stand at all.

Enforced by:
- T-027 and T-029: the step-out as data, and the preflight Y-limit check;
- T-029c: `objective_stepped_out` is written before the move, and `objective_stepped_back` only after the
  readback confirms the stage is back;
- `guards.step_out_target`.

## Step 5. Lenses without a measured working distance stay refused

Who: the user. This is a rule to keep, not a move.

Only the 4x (20 mm) and the 100x Oil (130 um) have a `FREE_WD_UM` entry. 10x, 20x, 40x WI and 60x Oil are
not rotation targets. Do not add an entry until the lens's free working distance is measured on this
stand.

What the screen shows: the objective change is refused with "free working distance not measured
(<lens>; guards.FREE_WD_UM)".

Enforced by: T-029, the `target_working_distance` preflight check, and `guards.FREE_WD_UM`.

## After the session

- Lights: the exit path switches them off. The status bar should read DiaLamp off and Aura off.
- Leave Z retracted if you are not continuing.
- Write down in the session record:
  - which steps were done;
  - every readback that was off;
  - the Shutdown answer from step 1;
  - any stop you had to use.
