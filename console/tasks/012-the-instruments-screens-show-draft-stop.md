# 012 — the instruments screens: show, draft and stop

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, from 2026-10-24, after
card 011 landed at `e9601b31`. If you are not that seat, take nothing from
this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

This is card 007's fifth app card. It covers the Instruments area's six
sub-tabs, which do three things only: show, draft and stop. Hands-on control
is decided after the reduction (`cd9dcb57`). The canvas screens are
`PInstStatus`, `POptics`, `PCameras`, `PTweezers`, `PConfocal` and
`PPiezo`, version 58. The runtime holder read them at versions 42 and 43,
and card 006 records the corrections.

Several live pieces are the runtime's and not built yet:
- the idle status file's writer (card 085);
- check now;
- latest frames per camera (card 084).

A missing piece shows "not built yet", and **the console builds no stand-in
for it** (007; plan.md 15).

## What to do

0. **A fix to card 011's dialog first.** Its "Light" row is derived from
   device names (lamp, led, laser and the like). That is deciding a device's
   role from how its name is written, which check 80 counts against the
   code. A light named another way would be left out, and leaving it out is
   the unsafe direction. Remove the derived row. List instead **every device
   the plan touches, with the value the plan sets**, and keep "cannot be
   undone" as it is. A light row comes back only when the registry gives a
   device a role to read.
1. **Status (`PInstStatus`).**
   - Read `microscope_runtime/.runtime_status/idle_status.json` as data,
     validated against `contracts/schemas/idle_status.schema.json` read from
     the repository.
   - Absent, the tab says "No status yet". That is not "nothing connected".
   - Present, show "As of <written_at>, from <written_by_run>" and each
     reading's name, value, how it was read and when:
     - `read_back` reads "read back";
     - `not_readable` reads "sent, cannot be read";
     - `not_read` reads "not read", with a null value shown as unknown.
   - "Which program holds which instrument" shows "not checked yet" while
     ownership is `not_built`.
   - **One row always**, whatever the file says: "Tweezers laser · set by
     hand · not known · assumed on". The trap strength last sent, if any, is
     labelled "sent through the tweezers program".
   - **Check now** shows for `person_login` only. Until the runtime has it,
     and the person has connected the console to the live-view host,
     pressing it answers "not built yet" and sends nothing.
2. **Optics and control (`POptics`).**
   - The light path is drawn as on the canvas: three rows of parts, labelled
     as a picture of the stand.
   - Each part shows its state from the status file by channel id when one
     is there, and "unknown" otherwise.
   - Double-clicking a part opens its tab: Light source, Filters,
     Magnification, Camera.
   - **Drafts only where software may command**, as the runtime's
     `SOFTWARE_MAY_COMMAND` names: the Aura LED, the transmitted lamp
     (DiaLamp state and intensity), and the red camera's exposure. Each
     carries "refused until you write a limit". Every other part reads "set
     by hand; software may not move it", with no draft.
   - The laser combiner reads "close was sent; assumed open until a shutter
     that reads back shows it blocked".
   - **A draft is an ordinary `operation` plan card**, validated against
     `contracts/schemas/plan.schema.json` read from the repository. It is
     shown in full and **saved nowhere**. The screen says where a console
     draft goes before the person signs it is still to be designed.
3. **Cameras (`PCameras`).**
   - Four panels.
   - Panel 1 is the red camera, through today's live-view code, only while
     a signed run is acquiring. Live view on is offered to `person_login`
     only.
   - Panels 2 and 3 say the blue camera is not opened by software yet.
   - Panel 4 draws no traps: "mapping onto the camera is not measured".
   - The exposure draft is as in Optics.
4. **Tweezers (`PTweezers`).**
   - The laser row as in Status.
   - Traps and their strengths come from the latest run's events, labelled
     "sent". With no run, "no trap sent".
   - The t-x, t-y and x-y plots come from the same events, labelled "sent".
     No click-to-hold, no dragging.
   - **A pattern is a `trap_steps` plan draft**, validated and saved
     nowhere, as in Optics. Beside it: allowed only at 40x within ±100 µm,
     60x within ±67 µm and 100x within ±40 µm, at most 1 µm per step; trap
     count and flicker rate are refused until a limit exists.
5. **Confocal (`PConfocal`).** State only, from the status file's spinning
   disk channels. The shutter reads "read back; which value means closed is
   not recorded".
6. **Piezo stage (`PPiezo`).**
   - x, y and z come from a run's snapshots in its events, with time, in
     micrometres and seconds. Outside a run: "as of <time>, from <run>".
   - The time window and refresh are screen-only, and the screen says the
     read rate is a plan field.
   - The range is read from `microscope_runtime/envelope/safety.json` and
     shown as "from your safety file". It is never written into code.
   - The pattern generator shows "designed later".
7. **Tests, each watched failing first:**
   - check now sends no request, and shows for `person_login` only;
   - the laser row is always there and always "assumed on";
   - the three `how` words;
   - a missing status file reads "No status yet";
   - only the three drafts are offered, and each validates against
     `plan.schema.json`;
   - no draft is written anywhere;
   - the dialog's device list includes a light whose name contains none of
     the old words;
   - the piezo range comes from the safety file.

## What not to do

- No command to any instrument, no live-host connection, and no stand-in
  for a runtime piece.
- No write outside `console/`, and no draft saved.
- No retheme yet. Install nothing.

## Done when

- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest` passes.
- The validator ends `0 failed`.
- One commit through `contracts/tools/seat_commit.py`. Report the hash to
  this seat.
