# Tweezers: traps, the live stream and Tweez300 (card T-20261002-2205, stage 3)

## 1. Engine

- `engine/tweezers.py`: the `Tweezers` interface (`info`, `traps`, `move_trap`, `set_trap`,
  `close`), `TrapState {index, on, x_um, y_um, z_um, power_pct}`, `MockTweezers` (4 traps,
  in memory) and `state_of` (the `snapshot()["tweezers"]` block, null with no tweezers).
- Coordinates: um in the sample plane from the centre of the camera field, x right, y down as
  on the image (orientation provisional); z is the trap's focus offset. Range PROVISIONAL:
  x, y ±60 µm, z ±10 µm (`engine/patterns.py` `TRAP_RANGE_UM`).
- `guards.TrapAxis`: the only caller of the write methods (the guards' token). Checks the range,
  reads every move back (0.05 µm, provisional) and records a `motion` event. Real tweezers
  (`info().bench` not exactly False) are refused while the stand's bench-motion lock is on.
- Operations `trap_move {trap, x_um, y_um, z_um?}` and `trap_set {trap, on}`: rule 12 motion
  class (the operator's control and an open experiment session); hardware gate: the camera
  (the profile has no tweezers role yet); preflight: tweezers present, trap number, range.
- `engine/stream.py` `BackendStream`: the live stream for simulated backends. It renders only
  while someone has `/ws/frames` open, pauses for operations that snap, and stops at shutdown.
  It refuses the bench.

## 2. What runs where (`server/__main__.py` `simulated_extras`)

| Backend | Tweezers | Live stream |
|---|---|---|
| mock | `MockTweezers` | yes: the mock frame with a bead in every trap that is on, plus a second camera `Kinetix_blue` with only the trap laser spots |
| mm-demo, replay | `MockTweezers` | no (mm-demo shares one Micro-Manager core between threads) |
| mm-real | none | no (a separate decision) |

Mock trap spots are at least 3 camera pixels wide so they stay visible at low magnification
(a picture aid, not optics). Trapping is a high-magnification job: at 4x the ±60 µm range is
about ±12 displayed pixels.

## 3. Tweez300 (`engine/backends/tweez300.py`): a refusing stub, not a driver

Tweez300 stays running on the microscope PC; the app never starts or closes it. The real
driver is soft-matter-agents' `microscope_agent/src/devices/python_tcp.py` (the GUI's TCP text
interface; wrapped verbs with `LASER_ON` left out; `.tpf` pattern files via `write_pattern`,
`LOAD_PATTERN`, `TRAP_ASSIGN_PATTERN`; a silence is never retried; every dispatch is
`verification: none` because the device reports nothing back) with its live checklist
`microscope_agent/src/tweezers_live_checklist.md`. The merge decisions (integration-sma.md 7 and
9; integration-sma-workplan.md P-01, P-03, D-05) make that the only path to the real tweezers:
trap moves on the stand happen only as soft-matter-agents plans the person approves
(`trap_steps`, absolute positions, one trap per step, a `hold_for_person` after any step a later
one relies on), and the console's trap tracks become `.tpf` pattern files carried by such a plan.
So this stub is not wired here and is deleted once that path is in use on the bench (D-05); until
then it refuses every call and opens nothing, and `bench=True` keeps it behind the bench-motion
lock. What the console shows for real traps is therefore what was commanded, never a read-back
(the Tweez300 has none), and a trap's `z_um` exists only in the mock.

## 4. Screens

- **Tweezers** area (`#/tweezers`): source (mock or Tweez300), a row per trap (laser on/off,
  x/y/z, Move, power when reported), the reason when moves are not allowed (control, session,
  remote, role), and the live view (all cameras, side by side / merged / one) with a ring per
  trap (filled when on, the chosen one thicker). A click on a frame moves the chosen trap
  there; outside the provisional range it is refused in the browser.
- **Live** area: a "Traps" checkbox draws the same rings (display only).
- `WsFrame.t` now falls back to the runner frame's `t_read`.
