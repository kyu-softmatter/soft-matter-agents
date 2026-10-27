# 096 — the reading run reads every property a planned run sets

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat**, for the
code and the mock run. It extends card 092's reading run and comes after it,
unless the runtime holder, architecture-office-20261017-1, moves it. The
hardware run happens at the microscope with the person present, as card 092's
does. If you are not that seat, take nothing from this card and report up.

## Why

Read **plan.md 15.1 item 10** (`efbd679a`), the paragraph "What this costs
today". The store holds no binding, so on the instrument a planned run sets
nothing until a binding is E1. The entry has to come from a run here that
read the property's report of itself under the approved configuration: its
value, and the limits or allowed values Micro-Manager reports for it. Card
092 reads each device's identity only. Where the device reports no unit, the
unit has to be established by a measurement here. For the camera's exposure,
that is the exposure a frame's own metadata reports for a value set.

## What to build

In `microscope_runtime/src/`, in card 092's reading run:

1. **Read every property of each device card 092 reads**, not a chosen list.
   For each allow-listed device other than `Core`, and for `Kinetix_blue`,
   log one record per property name the core reports for that label. Each
   record carries:
   - the value as read;
   - the property type;
   - whether it is read-only;
   - its lower and upper limits, where the adapter reports limits;
   - its allowed values, where the adapter reports any;
   - the call that read each one.

   The run binds nothing and judges nothing. Which property a quantity sets
   is the librarian's to enter from these records.
2. **Card 092's rules hold for every record.** A read that raises is logged
   as unread with its error and is called once. A device not loaded is
   logged as not loaded. Nothing is written by this part.
3. **The exposure measurement is a second, separate step, and it writes.**
   It is the one place in this card that commands anything, so it runs only
   when the run is started with it asked for by name. It is logged as its own
   section of the run.
   - **On `Kinetix_red` only**, the one camera on the allow-list, set
     exposure to each of three values and snap one frame at each. Record the
     value set, the value read back, and the exposure the frame's own
     metadata reports. The three values are given as run arguments and
     recorded; none is written into code.
   - **No light.** Before the first snap, read that every light source in
     the configuration is off and its shutter closed, with AutoShutter off
     as card 069 leaves it. On any source that reads on, open, or not read,
     the step refuses before the first write, naming it. Frames are dark
     frames and are kept with the run.
   - Restore the exposure read before the step, and read it back.
   - Every write goes through the motion check and the backend's read-back
     as any planned write does. Nothing bypasses them because this is a
     calibration.
4. **The record names the configuration as card 092's does**: the approved
   original's sha256 and the approval file's path.

## Tests, each watched failing first

1. On mock, a fake core reporting properties with and without limits and
   allowed values: one record per property per device, each field present
   or absent as the fake reports it.
2. Without the exposure step asked for, the fake core records no write of
   any kind (card 092's test 2, unchanged).
3. With it asked for, the only writes are `Kinetix_red`'s exposure, three
   sets and one restore, and three snaps. Each frame's metadata exposure is
   recorded beside the set and read-back values.
4. A light source that reads on, a shutter that reads open, or one not read:
   each refuses the exposure step before its first write, naming the device.
   The reading part still completes and is logged.
5. A property read that raises is logged as unread and called once.
6. The existing suite, card 092's tests included, is unchanged.

## The hardware run

- At the microscope computer, by the seat there that runs the instrument,
  with the person present, under the approved `DMD_dualcam_LUNF.cfg`.
- The reading part emits nothing and moves nothing, as card 092's does. The
  exposure step sets a camera and snaps dark frames, with every source read
  off first. Nothing is pointed at a sample.
- The readings and the exposure records go to the librarian as a finding,
  each citing the run, so the entries are E1 from `measured:`, each with the
  configuration's sha256.
- The person's presence and the time are asked through the intake seat,
  `architecture-office-20261017-2`, together with card 092's. One visit can
  run both.

## Boundaries

- Write `microscope_runtime/src/` and `tests/` only. No `contracts/`, no
  `envelope/`, no `approvals/`, nothing in `librarian_agent/`.
- No write other than part 3's. If another reading needs a write, stop and
  report it to this seat.
- If the run log needs a field for these records, stop and report it to this
  seat. The schema is mine to change.
- Commit through `contracts/tools/seat_commit.py`, naming each path. Never
  `--no-verify`, `--amend` or force.

## What comes back

To this seat, 4 lines at most: the commit; each test, watched failing, then
passing; the suite's counts; and each property field the mock could not
stand for, by device.
