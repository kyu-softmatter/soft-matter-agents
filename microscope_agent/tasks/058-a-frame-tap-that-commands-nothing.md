# 058 — a frame tap that commands nothing

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-20261003-1`**, after card 057, whose `run_started`
event this card's address joins. If you are not that seat, take nothing from
this card and report up. This is plan.md 11-25 (c).

## Why

`dino-autofocus`'s console wants live frames. **It must never open a second
Micro-Manager core**: two cores on one instrument is two places commanding it,
and 4.6.8's single entry point ends there (11-25 item 3). So the frames come
from the core the orchestrator already holds, in the orchestrator's process.

## Where it lives, read at 3ba8733

`devices/micromanager.py` already hands every frame to a callback as it
arrives (`sequence(n, sink, ...)` calls `sink(i, image, metadata)`), and
`snap()` returns one frame. **The tap sits on that path:** the orchestrator
wraps the sink a run passes and keeps a copy of the most recent frame. It
makes no camera call of its own.

## What to build

- **A latest-frame buffer in the orchestrator**, filled by a tee on the run's
  own sink and its own `snap()` results. It holds one frame, its metadata
  (camera, exposure, `ImageNumber`) and the event time. A new frame replaces
  the old one, and nothing queues.
- **Served on its own loopback socket**, bound to `127.0.0.1` on a port the
  OS chooses, announced in `run_started`. It is separate from card 057's stop
  channel, which accepts a stop and nothing else, and that stays true. It
  closes when the run ends.
- **One request: the latest frame.** The reply is the frame and its metadata,
  or *no frame yet*. Nothing else is accepted.

**It must not start, stop or configure acquisition. Ever:**

- it calls nothing on the core, not even a read; the buffer is all it touches;
- when no frame is arriving, it says so. It never snaps to have something to
  show;
- **a slow or vanished reader never slows the run.** The sink copies into the
  buffer and returns; serving happens on another thread; acquisition never
  waits on the console. If copying a full frame would cost the sink measurable
  time, say so with a number and report up rather than dropping frames from
  the run;
- the frame is a copy. Nothing the reader does reaches the run's data.

**Outside this card:** frames when no plan is running. That would mean
something acquiring outside a plan, which is the question below. Do not build
a live view.

## Tests, mock first and on a fake core, each watched failing first

1. During a mock sequence of N frames, the tap's last frame equals the sink's
   last frame, `ImageNumber` included.
2. **The fake core records zero calls caused by the tap**: compare a run with
   a reader polling as fast as it can against a run with none, and the call
   lists are identical.
3. A reader that blocks forever does not change the sequence's duration
   beyond a stated tolerance, and every frame still reaches the run's sink.
4. Before the first frame, the reply is *no frame yet*; after the run, the
   socket is closed.
5. Any request but the one is refused and changes nothing.
6. The socket is bound to `127.0.0.1`.

## Boundaries

Write in `microscope_agent/src/` and `microscope_agent/tests/` only. Never
write `envelope/` or `approvals/`. No change to `SOFTWARE_MAY_COMMAND` or
`NAMED_REFUSALS`. **Open no device**: mock and a fake core.

Run the validator to `0 failed` under the interpreter `CLAUDE.md` names for
this computer, and read its `tree:` line. Then `git diff HEAD -- <paths>`,
then `git commit -F <file> -- <paths>` under your seat. Confirm with
`git log -1`, and push with
`git -c credential.helper=manager push origin feature/autofocus-ui`. Never
force, never amend.

## Question only the person can answer

- **Should the console show live frames only while a plan you approved is
  running, or also when nothing is running?** The second would need the
  camera running outside any plan, which needs a plan of its own. Until the
  person answers, it is only while a plan runs.

## What comes back

To this seat, 8 lines at most: the commit, the six tests' failing and then
passing output, what one frame copy costs the sink in time, and the
validator's `verdict:` and `tree:` lines.
