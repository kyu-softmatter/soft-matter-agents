# 015 — Instruments, on the runtime's mock

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, after card 014. If you
are not that seat, take nothing from this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

The person asked for Instruments to be implemented on a mock system first
(I-20261024-office-02, `5f88eab4`). For the instruments, the mock is **the
runtime on `--backend mock`**, behind the same orchestrator (plan.md 15).
The live views come from it: frames, snapshots and the stop. **The console
builds no stand-in for a runtime piece** (007). Card 012 built the screens.
This card connects them to a mock run the runtime is running.

The runtime holder's list of what is not built yet, each on manager-microscope's
cards for the runtime seat (plan.md 15.1, "Who takes what"):
- the idle status file's writer;
- check now;
- latest frames per camera;
- the mock's additions: two cameras, a moving piezo trace, trap commands
  echoed back, the confocal elements.

Each stays "not built yet" on the screen until its card lands.

## What to do

1. **Attach to a running mock run.**
   - A run started by the runtime seat or the person on `--backend mock`
     appears in the runs folder with its `run_started` event.
   - The Instruments tabs follow the newest running run.
   - **The console starts no run.** It reads `runs/<id>/events.jsonl` as it
     grows, and uses only what the run interface offers: the stop on the
     stop channel (card 004), and the frame tap's `get` for live view.
2. **What each tab takes from the run.**
   - **Piezo**: x, y and z from the run's snapshots, with times, as read
     back.
   - **Tweezers**: trap positions and strengths from apply events, labelled
     "sent".
   - **Cameras, panel 1**: frames from the frame tap while the run acquires,
     offered to `person_login` only. Panels 2 to 4 keep card 012's
     wording.
   - **Status**: still reads the idle status file, "No status yet" while
     its writer is not built.
   - A run that has ended leaves its last values marked "as of <time>, from
     <run>".
3. **Not connected, not built.**
   - With no running run, each live tab says no run is running.
   - A piece the runtime has not built says "not built yet". Neither state
     is ever filled from the console's own side.
4. **Tests, each watched failing first.** Use events files and a recorded
   frame-tap exchange as fixtures inside `tests/`, never in the app:
   - the piezo plot reads snapshots;
   - trap positions are labelled "sent";
   - an ended run shows "as of";
   - no run means no values;
   - the console never starts a run or writes an event;
   - the frame tap is asked only for `person_login`;
   - each runtime piece that is not built shows "not built yet".

## What not to do

- No stand-in engine, frame source or status writer in the app.
- No start, command or set-point. Only the stop and the frame tap's `get`
  leave the console.
- No live-host connection beyond what card 004's and the live view's code
  already make, and that only when the person presses it.
- No write outside `console/`. Install nothing.

## Done when

- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest` passes.
- The validator ends `0 failed`.
- One commit through `contracts/tools/seat_commit.py`. Report the hash to
  this seat, with which runtime pieces still read "not built yet".
