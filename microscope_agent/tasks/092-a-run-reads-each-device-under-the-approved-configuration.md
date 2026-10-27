# 092 — a run reads each device's report of itself under the approved configuration

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat**, for the
code and the mock run. It comes after card 091, unless the runtime holder,
architecture-office-20261017-1, moves it. The hardware run happens at the
microscope, with the person present (see "The hardware run"). If you are not
that seat, take nothing from this card and report up.

## Why

Read **plan.md 15.1 item 9, the bullet added at `344d115a`**. A label lets
software command its device only when its entry is E1, read here, under the
configuration that is loaded, compared by sha256. Read off the files at that
commit:

- the person approved `DMD_dualcam_LUNF.cfg` on 2026-10-19 (`80135a4e…`);
- the store's E1 labels (`Kinetix_red`, `DiaLamp`, and the Aura's report of
  its five lines) were read on 2026-09-24 under
  `single_cam_red_noDMD_nocom10.cfg` (`8184073e…`);
- the 2026-10-13 bench readings saw the labels in the property browser, and
  none of them is a store entry.

So once card 091 lands, nothing on the instrument outside the three
exemptions runs. This card produces the readings that change that. It
commands no device. The librarian enters what it reads.

## What to build

In `microscope_runtime/src/`:

1. **A preparatory run that loads the approved configuration and reads, and
   writes nothing.** It uses the shape the live view already uses (plan.md
   11-21): `plan_id` null, `no_plan_because`, one run lock, one core, the
   configuration through `mm_config_gate` exactly as card 069 does it, with
   the AutoShutter stop and the derived copy in the run folder. **No
   setProperty, no snap, no sequence, no position write.** Loading the
   configuration is the run's only effect on the stand, and it is already
   approved.
2. **For each device `SOFTWARE_MAY_COMMAND` names, other than `Core`, it reads
   the device's report of itself** under its label, and logs one event per
   device. The event carries:
   - the label;
   - the library and device name Micro-Manager reports for it;
   - every read-only identity property the adapter exposes (for a camera:
     serial number, chip, firmware; for a light engine: its line report);
   - each value as read, with the call that read it.

   Today that is `Aura`, `Kinetix_red` and `DiaLamp`. Read the list from
   `micromanager.py`; do not copy it into this run.
3. **`Kinetix_blue` is read as well**, and logged the same way. It is not on
   the allow-list, and this card does not put it there. Card 084's tap takes
   frames from both cameras, and the two bodies are one model, so only a
   serial read under this configuration tells their frames apart. Reading is
   not commanding, and the record costs nothing.
4. **The log names the configuration as the check will compare it:** the
   approved original's sha256 from `mm_config_gate.check`, and its approval
   file. A device the configuration did not load is logged as not loaded,
   with its label, and the run still completes. A read that raises is logged
   as unread, with the error, and is never retried as if it had succeeded.
5. **A device whose report names a different device than the store expects
   is not judged here.** The run records what was read. The comparison with
   the store's serials is the librarian's, at entry.

## Tests, each watched failing first

1. On mock, with a fake core that loads a fake configuration and reports
   identity properties, the run logs one event per allow-listed device
   except `Core`, plus `Kinetix_blue`, each with library, device name and
   identity properties.
2. The fake core records every call. No write call of any kind appears: no
   setProperty, setConfig, snap, startSequenceAcquisition, setPosition or
   setXYPosition.
3. The run log carries the approved original's sha256, not the derived
   copy's, and the approval file's path, written with forward slashes.
4. A device the fake configuration did not load is logged as not loaded, and
   the run completes. A property read that raises is logged as unread, and
   is called once.
5. Without an approved configuration, on hardware, the run is refused before
   the lock, as card 069 refuses it.
6. Adding a device to `SOFTWARE_MAY_COMMAND` in a test adds it to the run
   with no other change.
7. The existing suite is unchanged.

## The hardware run

- It is run at the microscope computer, by the seat there that runs the
  instrument, with the person present, under the approved
  `DMD_dualcam_LUNF.cfg`.
- Nothing is pointed at the sample, and nothing emits. Loading the
  configuration is the whole effect on the stand.
- The run record is committed like any run.
- The readings go to the librarian as a finding, each citing the run, so the
  entries are E1 from `measured:` with the configuration's sha256 on each.
  The digest field is the one manager-librarian adds to card 061's form.

The person's presence and the time are asked through the intake seat,
`architecture-office-20261017-2`, not in this window.

## Boundaries

- Write `microscope_runtime/src/` and `tests/` only. No `contracts/`, no
  `envelope/`, no `approvals/`, nothing in `librarian_agent/`.
- This run reads. If a reading needs a write to be taken, stop and report;
  that is a different run and a different card.
- Commit through `contracts/tools/seat_commit.py`, naming each path. Never
  `--no-verify`, `--amend` or force.

## What comes back

To this seat, 4 lines at most:

- the commit;
- each test, watched failing, then passing;
- the suite's counts;
- each identity property the mock could not stand for, by device.
