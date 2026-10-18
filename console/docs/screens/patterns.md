# Patterns: designer and live overlay (card T-20261002-2205, stage 2)

A **pattern** says what the XYZ piezo stage and the tweezer traps do over time. Designing and
showing one moves nothing; running one is stage 4 (an engine operation behind the guards and
both bench locks).

## 1. Shape (`engine/patterns.py`)

```
Pattern = {version: 1, id, name, loop, notes, meta: {created_at, updated_at, by},
           tracks: [{target: "piezo" | "trap:N" (N 0..7), points: [[t_s, x_um, y_um, z_um], ...]}]}
```

- One track per target. Points are linear in between; every track starts at `t = 0` and its
  times go up. The pattern lasts as long as its longest track; a shorter one holds its end.
  With `loop` the time wraps.
- `piezo`: offsets from where the stage is when a run starts. `trap:N`: from the centre of the
  camera field, in the sample plane; `z` is the trap's focus offset.
- Axes: x to the right, y down, as on the camera image (orientation provisional until the
  piezo and the tweezers are measured on the bench).
- Ranges are PROVISIONAL and refused outside: piezo x, y ±100 µm, z ±50 µm; traps x, y ±60 µm,
  z ±10 µm. At most 20 000 points per track, 3600 s.

## 2. API (`server/api/patterns.py`, mounted at `/api/patterns`)

| Route | Who | Does |
|---|---|---|
| `GET /api/patterns` | logged in | `[PatternSummary]` (id, name, duration_s, targets, updated_at) |
| `GET /api/patterns/{id}` | logged in | `PatternOut` |
| `POST /api/patterns/{id}` | operator / admin, microscope PC | `PatternIn` → `PatternOut`; create or replace; `422 invalid_pattern` with the reason |
| `POST /api/patterns/{id}/delete` | operator / admin, microscope PC | `204`; `404 not_found` |

Patterns are designs, not records: one JSON file each in `<settings>/patterns/`, shared by the
mock and the bench.

## 3. Screens

- **Patterns** area (`#/patterns`, `#/patterns/<id>`): saved list, name, loop, one box per
  track (target, shape generator: circle, line, raster, spiral, hold; z start/end ramps z over
  the shape; duration; points per second; points editable as CSV), a preview coloured by time
  (gray `#9e9e9e` at the start to dark green `#1b5e20` at the end) with Play and a time slider,
  each target's x/y/z at that time, Save, Delete (with a confirm) and "Show on live view".
- **Live** area overlay (`#/live?pattern=<id>`): the pattern drawn over every camera panel
  (side by side, merged, one at a time) in the same colours, markers where each target is at
  the slider's time (piezo a square, a trap a numbered circle), a 10 µm scale bar. The scale is
  the frame's `meta.pixel_um` × binning; a frame without it uses 0.1 µm/px and says "assumed".

## 4. Running a pattern (`pattern_run`, stage 4)

- `start("pattern_run", {pattern_id, repeats?: 1..100, rate_hz?: 1..50 (20), return_to_start?:
  true})`. Rule 12 motion class (control and an open session); gate row: the camera.
- Preflight, before anything moves: the pattern exists; a piezo track needs a piezo that may
  move (`guards.PiezoAxis`: only a simulated one; the stand's piezo stays read only until M5)
  and must stay inside its travel from where it is now; a trap track needs tweezers with that
  trap (`guards.TrapAxis`: real ones refused while the bench-motion lock is on); at most 2 h.
- Every tick each track's position at that time is sent (piezo: start + offset; traps: field
  position), read back, without a motion event per move. Progress every 0.5 s carries `t_s`,
  `elapsed_s`, `of_s` and every target's position; the summary carries the pattern's sha256,
  move counts and the largest readback error. At the end the piezo returns to its start
  (`return_to_start`); an abort stops at once with no return. No ramp yet: the first tick
  jumps to the first point and each repeat jumps back to the start (needs a ramp or step limit
  before any real piezo, M5).
- Setup (`server/__main__.py` `simulated_extras`): simulated backends get `MockPiezo` (x, y
  0..200 µm, z 0..100 µm, starting in the middle); the mock's live frames shift with the piezo.
  The bench gets no piezo and no tweezers.
- Screens: "Run on piezo / traps" with repeats and "Abort run" in the designer (saved patterns)
  and in the live view's pattern overlay; the overlay's time follows the run's progress.

## 5. On the stand (merge rules, P-01)

Running a pattern on the real instrument is not this app's job after the merge with
soft-matter-agents (docs/integration-sma.md 7 and 9): the console drafts a plan, the person approves
it, soft-matter-agents' operator executes it. What a pattern can become there today:

- **Trap tracks** become `.tpf` pattern files (`write_pattern` in soft-matter-agents'
  `devices/python_tcp.py`: one point per line, x, y and strength, relative to the trap) loaded with
  `LOAD_PATTERN` and started by `TRAP_ASSIGN_PATTERN`, or a list of `trap_steps` (absolute
  positions, one trap per step, at most 1 um per step, a `hold_for_person` after a step a later one
  relies on). Nothing is streamed at 20 Hz to the tweezers; the device reports nothing back.
- **Piezo tracks** have only the shapes an `operation` plan allows: steps and a host-timed sine on
  X or Y, Z only as a direction-finding step. A circle, spiral or raster (two axes at once), a Z
  track, a loop, a trap z, or piezo and traps in one plan is refused with that reason until
  soft-matter-agents designs a trajectory shape (workplan P-04, a manager decision).
- **Ranges** come from the person's `envelope/safety.json` there, per objective; the provisional
  numbers in `engine/patterns.py` are for the mock only (workplan P-02).
- **The live overlay and the merged or side-by-side camera view are display only.** Frames are
  paired by host arrival time (`WsFrame.time_base: "software"`), not by a hardware trigger: no
  timing, correlation or coincidence analysis may be read off them. Simultaneous capture is a
  hardware-triggered soft-matter-agents plan.
