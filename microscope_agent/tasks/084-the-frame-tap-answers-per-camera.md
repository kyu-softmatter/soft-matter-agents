# 084 — the frame tap answers per camera

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat. Start after
card 087**, which gates the console's approval writer and comes first
(plan.md 15.1 item 4 at `0607b848`), **and after card 086's items 1 to 4**,
the mock the console's screens are built against (the person, `5f88eab4`). If you are not that seat, take nothing
from this card and report up.

## Why

The redesigned console shows the latest frame of each camera a run takes
(plan.md 15.1 item 1, the person's Q-20261022-office-06 to -09, `231f0c76`
to `55a635b6`). Today the tap answers one request, and with only the latest
frame of whichever camera produced last. 11-25 says that request changes only
by agreement with the console. manager-console-office-20261017-1 agreed the
shape on 2026-10-22, and it is pinned in `contracts/` in this card's commit.

## What is in `contracts/` (this card's commit)

In `contracts/schemas/run_interface.schema.json`:

- **`frame_tap_request`** has two forms, and only these:
  - the bare `{"get": "latest_frame"}`, which answers for the first camera in
    `tap_cameras`, exactly as today;
  - `{"get": "latest_frame", "camera": "<name>"}`, naming one camera from
    `tap_cameras`.

  No other key is allowed.
- **`frame_tap_header`**: a frame reply requires `camera`. A `frame: false`
  reply may carry `camera`, and does when one was asked about.
- **`run_started`** requires `tap_cameras`: the cameras the tap answers for,
  in order, with no duplicates. The list may be empty.
- `$defs/camera_name`: `^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$`.
- Each `$defs` entry's `examples` validate and its `x_refused` are refused.
  The console's tests read them. Read them as your tests' table too.

## What to build

In `microscope_runtime/src/` (the tap, the orchestrator, `live_view.py`):

1. **`tap_cameras`.** Derive it before `run_started` from what the run will
   acquire: the cameras the plan's acquisition fields name, or, for live
   view, the list's `camera.device`. Never derive it from a frame's metadata
   text. A plan that acquires nothing writes `[]`.
2. **One latest frame per camera.** The tee knows which camera it serves
   because the orchestrator made the call, so key the copy by that camera.
   Card 058's rules still hold:
   - the run's sink first, then a copy;
   - nothing queued that can delay the run;
   - the tap holds no core and no device, and never acquires.
3. **The two request forms.**
   - Bare: answer for `tap_cameras[0]`. With an empty list, answer
     `frame: false`.
   - Named: answer that camera's latest. A name not in `tap_cameras` gets
     `frame: false`, naming the camera and saying the run does not take it,
     and is recorded as `frame_tap_refused`, as other refusals are.
   - Anything else is refused as today.
4. **Every frame reply names its camera.**

## Tests, each watched failing first

1. A two-camera mock run: each named request returns that camera's frame,
   and the bare request returns the first camera's.
2. An unknown camera is refused by name and recorded, and makes no device
   call. Card 058's tap test is the pattern.
3. `run_started` carries `tap_cameras` derived from the plan, and `[]` for a
   plan that acquires nothing.
4. Every request and reply in the schema's `examples` is accepted and every
   `x_refused` request is refused, read from the schema file, not copied.
5. A slow reader of one camera delays neither the run nor the other camera.

## Boundaries

- Write `microscope_runtime/src/` and `tests/` only. No `contracts/`, no
  `envelope/` or `approvals/`. Mock only.
- The console's side is manager-console's. Don't edit `console/`.
- Commit and push through `contracts/tools/seat_commit.py`, naming each
  path. Never `--no-verify`, `--amend` or force.

## What comes back

To this seat, 4 lines at most:

- the commit;
- each test, watched failing, then passing;
- the suite's counts;
- every place the schema did not fit, with the field.
