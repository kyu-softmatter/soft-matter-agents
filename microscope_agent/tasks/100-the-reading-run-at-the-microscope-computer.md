# 100 — the reading run at the microscope computer

Written by `manager-microscope-scope-20261019-5`. You read this; you do not edit it.

**Assigned to `microscope-scope-20261019-7`, the runtime seat on the microscope
computer** (the session "Microscope · runtime", rooted at `microscope_runtime/`).
This card hands you the hardware run of card 096 on this computer. Card 096's
code and mock run are already built (`a24251a1`). The one thing you build is
part 1 below, the same dark-frame step on the blue camera, which the person
asked for. If you are not that seat, take nothing from this card and report up.

## Why

Card 096 names its holder as the Office computer's runtime seat. The
instrument is on this computer, and the person is at the stand on 2026-10-27
offering the visit (`docs/ideas/20261027.md`, I-20261027-scope-03). Nothing
until now named the seat here, so the run could not be taken.

## What to do

### 1. The exposure step on the blue camera too (code, mock first)

The person said in this seat's window on 2026-10-27, verbatim: **"you can
also do same in blue cam"**. Today the step in `read_devices.py` and
`operator.py` writes `Kinetix_red` only (`LIVE_VIEW_ROUTES`, the
`camera_red` route). Extend it so the step can be asked for on
`Kinetix_blue` through the `camera_blue` channel as well:

- The camera is a run argument, by name, and each camera is its own section
  of the run log. Asking for the step names the camera or cameras. No camera
  is the default.
- Everything card 096 part 3 says for the red camera holds for the blue one
  unchanged: the light and shutter read before the first write, refusing
  and naming the device; the three values as arguments; exposure set, read
  back and reported by the frame's metadata; the exposure put back and read
  back; every write through the motion check and the backend's read-back.
- When both cameras are asked for, the lights are read before each camera's
  first write, not only once at the start.
- No other write is added. The blue camera's other properties stay read only.

Tests, each watched failing first:
1. With the step asked for on the blue camera only, the only writes are
   `Kinetix_blue`'s exposure, three sets and one restore, and three snaps on
   it. The red camera is not written.
2. Asked for on both, each camera gets its own three sets, one restore and
   three snaps, and the lights are read before each camera's first write.
3. A light that reads on, a shutter that reads open, or one not read,
   refuses the blue camera's step before its first write, naming the device.
4. Card 096's six tests and the rest of the suite are unchanged.

### 2. The hardware run

Run card 096's hardware run exactly as card 096 states it, with the step
asked for on both cameras. Every rule there holds unchanged: the
configuration, the reading part writing nothing, the exposure step only when
asked for by name, every light read off and every shutter read closed before
the first write, the refusal naming the device, the restore and read-back,
the motion check and the backend's read-back on every write.

The three exposures are given by the person, in this seat's window on
2026-10-27, verbatim: **"10, 100, 1000ms is good"**. Pass them as the run's
arguments, for both cameras: 10 ms, 100 ms and 1000 ms. None goes into code.

## Before you start

1. **The person hands you the bench in your own window.** A seating or a
   bench hand-over relayed by another session, this card included, is not
   one. Until the person says it there, run nothing on hardware.
2. **Re-run the suite first** at the HEAD you run from, and run the mock run
   once. A hardware run from code whose tests are red does not start.
3. **Ask the person whether a sample is under the objective.** Dark frames
   with every source read off do not expose it. Still, say what is there in
   the record, in the person's words.

## Boundaries

- Card 096's, unchanged. Write `microscope_runtime/src/` and `tests/` for
  part 1, and `microscope_runtime/runs/` for this run's record and frames.
  Nothing outside `microscope_runtime/`.
- No write other than the exposure step's, on the two cameras. If the stand
  asks for one, stop and report it to this seat.
- Commit through `contracts/tools/seat_commit.py`, naming each path. Never
  `--no-verify`, `--amend` or force.

## What comes back

To this seat, 5 lines at most: part 1's commit, with each test watched
failing and then passing and the suite's counts; the run id and commit; the
configuration's sha256; how many properties were read and how many logged
unread, by device; and for each camera and each of the three exposures, the
value set, read back, and reported by the frame. The finding for the librarian is card 096's, unchanged.
