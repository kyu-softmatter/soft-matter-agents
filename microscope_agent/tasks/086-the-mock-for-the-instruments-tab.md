# 086 — the mock the console's instruments tab is built against

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat. It comes in
three parts**, in the order that shows the console's screens the most
soonest. The person asked for the Instruments and Experiments screens on a
mock first (`5f88eab4`), and the order is agreed with the runtime holder,
architecture-office-20261017-1:

- **Items 2 to 4 and 6 come next, right after cards 087 and 089.** They reach the screens
  at once through `events.jsonl`, which already exists.
- **Item 1 lands as a pair with card 084.** A second camera's frames reach
  the console only through 084's tap, so item 1 alone shows nothing.
- **Items 5 and 7 come after card 085**: 5 exercises its check-now run, and
  7 writes its status file.

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
   lists them, are readable on mock with the registry's names.
   - The ones in `micromanager.NAMED_REFUSALS` (CSUW1-Filter_Red and _Blue,
     CSUW1-Dichroic, CSUW1-Port, CSUW1-Bright, CSUW1-Shutter) are state the
     mock reports. A test-only parameter sets them, standing for the
     person's hand, as item 7 sets connection states.
   - A plan that commands one is refused on mock with the instrument's own
     refusal, because `check_software_motion` loads that one list on every
     backend.
   - Unknown elements refuse, as on any channel.
5. **The check-now list, on mock.** A mock registry channel set that a
   check-now list in a test's temp folder can name, so the console's "check
   now" can be exercised end to end on mock. Card 085's run does the work;
   this card adds only what the mock needs for it.
6. **The optical path's elements** (added for the person's Instruments page,
   `1641323a`).
   - The registry's light-path selectors are readable on mock, by the
     registry's names: the filter turrets, the two emission wheels, the
     LightPath and port, and the confocal dichroic.
   - **None of them can be set by a plan, on mock or on the instrument.**
     All are in `micromanager.NAMED_REFUSALS` or are moved by hand, and
     `orchestrator.check_software_motion` loads that list on every backend,
     so a plan refuses on mock exactly as on the instrument. On the mock
     they are state it reports, set by a test-only parameter standing for
     the person's hand. They are never set by `apply` (ruled by
     architecture-office-20261017-1, 2026-10-25).
   - "Control" from the console's optical-path page is a drafted plan run on
     mock, never a set-point path, since hand control is deferred
     (Q-20261022-office-07). A draft can change only what
     `SOFTWARE_MAY_COMMAND` allows: Aura, the DiaLamp's State and Intensity,
     and Kinetix_red, with the Core roles pinned. A draft touching any
     light-path element is refused with the instrument's refusal, and the
     mock's state does not change.
   - If the person ever opens one of these elements to software, as the
     trap-step and focus-search exemptions opened theirs, this item changes
     then, by a plan exemption written into the design first.
   - The orchestrator's ordering interlocks (Z retracts before a turret
     rotates, PFS disabled across a path change) are tested at the
     orchestrator level, not through a page: no plan can reach them while
     the Nosepiece and PFS are refused.
   - The registry's known traps stay visible: the turret label that names
     the wrong position, and the splitter states that send no light to one
     camera. A position read back from the mock is the mock's, and does not
     establish which element is in the beam.
7. **Connection states to show.** For the console's connection-state page,
   each mock channel can be set, by a test-only parameter and never from the
   console, to answer its preflight, to be absent, or to be busy
   (`ReadWouldWait`). A plan run, a live view or a check-now run on mock then
   writes card 085's status file with each state as it is, so the page reads
   only that file.

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
4. Each confocal element in the registry is readable on mock. Setting one
   by the test-only parameter changes what the mock reports. A plan
   commanding a refused one is refused on mock with the instrument's
   refusal, the state unchanged. An unknown one refuses.
5. (Part two, after card 085.) A check-now run on mock, with a list in the
   temp folder, opens, reads and closes every listed channel, with zero
   `apply`.
6. A mock plan touching any light-path element is refused before any
   command, with the same refusal the instrument gives, and the mock's state
   is unchanged. A plan using only what SOFTWARE_MAY_COMMAND allows runs. At
   the orchestrator level, an interlock test shows Z retracting before a
   turret rotates and PFS disabled across a path change.
7. With channels set answering, absent and busy, a mock plan run writes a
   status file that validates and shows each state, and no absent or busy
   channel carries a value.
8. The existing suite is unchanged.

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
