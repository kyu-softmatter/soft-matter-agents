# 017 — the live optical path, labelled as the runtime reports it

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, after card 014.
**Start it only once runtime card 086 item 6 is committed** (the mock's
light-path read). Until then card 015's panel stands as built. If you are
not that seat, take nothing from this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

Card 015 built the live optical path on page 2 before the runtime reported
any selector. So every element reads "not built yet", and the names are the
orchestrator's refusal labels. plan.md 15.1 item 8 (`2ea04557`, after the
person's `4582f29d`) now says what the page reads and how each element is
labelled. This card brings the panel to it. It is not a new screen.

## Where it reads, and nothing else

- **During a run, the run's `events.jsonl`.** The latest `snapshot` gives
  what was read. The `apply` events since it give what was sent.
- **Outside a run, card 085's status file**, with its time, once it lands.
  Until then, the last run's last snapshot, marked "as of <time>, from
  <run>", as 015 does.
- **Never a request of its own.** Nothing goes to a device, the host or the
  frame tap. The page is as fresh as the run's read cadence and cannot be
  made fresher by asking.
- **Element names come from the read-back.**
  - Never from the snapshot's device table or anything under
    `librarian_agent/`. That is the knowledge store, and the console shows
    only its wiki pages.
  - Drop 015's hard-coded label list once the read-back carries the names.
- **The read-back's shape is the one card 086 lands with.** Read it off the
  runtime's own tests at that commit, and cite the commit in your report.
  Build nothing to a draft seen uncommitted in the working copy.

## What the page shows

The elements the read-back carries, and nothing it does not:
- the filter turrets and their shutters;
- the confocal unit's filters, dichroic and port;
- the LightPath;
- the objective (the Nosepiece);
- the lamp and the LED;
- the laser combiner.

Each element carries exactly one label:
- **read back**, with the snapshot's time.
  - Beside the path, say that a position read back is the stand's report.
    By itself it does not say which element is in the beam.
  - Name the registry's two known traps there: the turret label that names
    the wrong position, and the splitter states that send no light to one
    camera.
- **sent**: the laser combiner, which cannot be read back.
  - A blind laser is shown at the most dangerous state its commands allow,
    until something readable shows the beam blocked.
  - It is never shown off on the strength of what was sent.
  - A laser channel the run did not open reads "not open", never "off".
- **not open**: a channel the run did not open.
- **not read**: a channel busy at the read, or, on the mock, an element no
  test has set. The mock reports no position for it, and the page invents
  none.
- **moved by hand**: every light-path selector and the objective. No
  control and no draft link.
- **drafted**: on this page, only the Aura and the transmitted lamp's state
  and intensity, through the page's draft link. The draft is refused
  wherever the safety file names no limit.

On the mock every state is labelled the mock's. A value is never carried
forward without its time. "Not built yet" stays only for a source that has
not landed, such as 085's status file.

## Tests, each watched failing first

Use recorded fixtures inside `tests/`: an events file with a snapshot and
later applies, and, once 085 lands, a status file in its landed shape.
- Each label above appears for an element of its kind, one label per
  element.
- A blind laser whose sent commands end in "off" is not shown off.
- An apply later than the latest snapshot shows as "sent", not "read back".
- An element the read-back omits does not appear. An element the mock
  reports as unset reads "not read".
- Element names follow the fixture: rename one in the fixture and the page
  follows.
- No request leaves the page while it renders or refreshes: no frame tap,
  host or device call.
- No "moved by hand" element offers a control.

## What not to do

- No read of the snapshot or the knowledge store.
- No request to a device, the host or the frame tap.
- No stand-in for a runtime piece.
- No write outside `console/`. Install nothing.

## Done when

- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest` passes.
- The validator ends `0 failed`.
- One commit through `contracts/tools/seat_commit.py`. Report the hash to
  this seat, with the runtime commit whose read-back shape you built to.
