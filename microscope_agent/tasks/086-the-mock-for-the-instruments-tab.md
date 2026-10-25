# 086 — the mock the console's instruments tab is built against

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat. It comes in
three parts**, in the order that shows the console's screens the most
soonest. The person asked for the Instruments and Experiments screens on a
mock first (`5f88eab4`), and the order is agreed with the runtime holder,
architecture-office-20261017-1:

- **Items 2 to 4 come second, right after card 087.** They reach the screens
  at once through `events.jsonl`, which already exists.
- **Item 1 lands as a pair with card 084.** A second camera's frames reach
  the console only through 084's tap, so item 1 alone shows nothing.
- **Item 5 comes after card 085**, because it exercises 085's check-now run.

Each part is its own commit. If you are not that seat, take nothing from
this card and report up.

## Why

The person's build order for the console is the frontend, then a mock
backend, then the real instruments (plan.md 15.1, `d1068945`). Item 6 settles
what the mock is:

- it is **the runtime on its own mock**, `--backend mock` behind the same
  orchestrator, so the last step changes the backend argument and no console
  code;
- it is **not an engine on the console's side**. dino's `mock` executed
  commands and stays retired, and nothing under `console/` opens a core.

15.1 lists five things the mock lacks for the instruments tab, and this card
adds them. **Read 15.1 items 1 and 6.**

## What to build

In `microscope_runtime/src/devices/mock.py`, plus the orchestrator and live
view where they meet it:

1. **Two cameras framing together.**
   - A mock run whose plan acquires on two cameras produces frames from
     both, each sunk with its own camera name, so card 084's tap answers per
     camera.
   - The two cameras' frames differ visibly, for example with a different
     stripe phase, so a screen that mixes them up is caught.
   - Each frame's metadata names its camera; the tap still keys by the
     orchestrator's call, not by metadata.
2. **A moving piezo trace.** While a mock plan moves the piezo stage, its
   read-back moves along the commanded path at a stated synthetic rate, with
   a small fixed lag. A `snapshot` during the move then shows positions
   between start and target, not a jump.
   - Synthetic and labelled so: it says nothing of the real stage's settling.
   - It is a read-back, so it counts as observed on mock only.
3. **Trap commands echoed.** A mock `optical_tweezers` channel accepts the
   trap commands the registry names and echoes each into the log as sent.
   - It has **no read-back**, as on the instrument: a screen showing a trap
     position shows what was sent, and the mock must not make that look
     observed.
   - Each echoed command carries the trap channel's `verification: none`,
     exactly as the real driver's events do. The mock invents no read-back
     anywhere, or screens built on it learn to show trap positions as
     observed, and that habit carries over to the instrument.
   - A test shows that `read()` on it carries no position, and that every
     trap event in the log says `verification: none`.
4. **The confocal elements.** The confocal unit's elements, as the registry
   lists them, are settable and readable on mock with the registry's names.
   Unknown elements refuse, as on any channel.
5. **The check-now list, on mock.** A mock registry channel set that a
   check-now list in a test's temp folder can name, so the console's "check
   now" can be exercised end to end on mock. Card 085's run does the work;
   this card adds only what the mock needs for it.

Every addition is synthetic, and its docstring says what real behaviour it
does not imply, as `FOCUS_Z_UM`'s does.

## Tests, each watched failing first

1. (With card 084.) A two-camera mock run: each camera's frames reach the
   run's sink under that camera's name, the two cameras' frames differ, and
   the tap returns each camera's own frame.
2. A piezo move on mock: snapshots during the move lie between the start and
   the target, and are monotone along the path.
3. A trap command on mock is logged as sent with `verification: none`, and
   `read()` on the trap channel carries no position.
4. Each confocal element in the registry is settable and readable on mock,
   and an unknown one refuses.
5. (Part two, after card 085.) A check-now run on mock, with a list in the
   temp folder, opens, reads and closes every listed channel, with zero
   `apply`.
6. The existing suite is unchanged.

## Boundaries

- Write `microscope_runtime/src/` and `tests/` only. No `contracts/`, no
  `envelope/` or `approvals/`.
- The mock holds no policy. Whether a value is allowed is the envelope's
  question (4.6.5), so the mock adds no limits of its own.
- Don't edit `console/`.
- Commit and push through `contracts/tools/seat_commit.py`, naming each
  path. Never `--no-verify`, `--amend` or force.

## What comes back

To this seat, 4 lines at most:

- the commits;
- each test, watched failing, then passing;
- the suite's counts;
- anything the registry did not name that the mock needed, with the field.
