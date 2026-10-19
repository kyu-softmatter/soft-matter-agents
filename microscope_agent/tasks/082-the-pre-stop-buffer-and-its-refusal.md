# 082 — the rolling pre-stop buffer, and the refusal of a plan without one

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat. Start after
card 076, before card 081.** Card 081's DM-4 reads what this card saves, and
all three cards edit the same files, one at a time. If you are not that seat,
take nothing from this card and report up.

## Why

The person's answer Q5 of 2026-10-19 (`04e3985f`): **a stop keeps a rolling
buffer of the last seconds before it and saves it**, with lamps off and
shutters closed first as the abort order says. Nothing emits light after a
stop. plan.md 4.6.1 (`578a20ee`, by architecture-20261007-1) settles its
shape:

- its length is a plan field with no default;
- there is no rate field, because it holds only copies of frames the run
  already acquires;
- a plan that can reach a device without the field is refused ("unstated is
  a stop"), while simulation and replay plans are exempt;
- zero is allowed only if it is written.

**Read 4.6.1 before starting.**

## What is in `contracts/` (this card's commit)

- **plan:** a top-level `pre_stop_buffer` block with `length_s`, a number
  of at least 0. It has no default and no rate field.
- **run log:** a `pre_stop_buffer_saved` event, `from: "pre_stop_buffer"`,
  with `buffer`: `length_s`, `frames`, `recorded_rate_hz` (null when fewer
  than two frames), `first_frame_index`, `last_frame_index`, `path` and
  `sha256`. It carries none of a command's keys.
- **Examples:** three of the four example device plans carry the block. The
  fourth, `plan_microscope_mic-20260917-001`, does not, because an example
  approval naming the person signs its hash. It stands as a record from
  before the rule.

## What to build

In `microscope_runtime/src/`:

1. **The buffer.** A ring of copies taken from the frame tap's tee. Card
   058's rules apply: the run's sink first, a copy, nothing queued that can
   delay the run. It holds the last `length_s` seconds by the frames'
   `t_mono`, not by a frame count, because the rate is the run's own.
   - **It never triggers an acquisition, a snap or a light.** It only keeps
     what the run already made.
   - With `length_s: 0` it keeps nothing and says so.
2. **On a stop**, every kind (abort, stop from outside, monitor):
   - **after the abort has completed**, lamps off and shutters closed and
     read back, save the ring whole into the run folder as one file;
   - then write `pre_stop_buffer_saved`, with the measured rate and the
     sha256 of exactly the saved bytes;
   - **saving never delays or weakens the abort**, and a failed save is
     recorded and never retried with light.
   - A run that ends normally saves nothing.
3. **The refusal.** The operator refuses to run any plan authored by
   `microscope_agent` that has no `pre_stop_buffer` block, before any
   command, with a reason naming plan.md 4.6.1. Simulation and replay plans
   are exempt. The eleven committed microscope plans then refuse until
   revised, which is intended. List them in your report.

## Tests, each watched failing first

1. A device plan without the block is refused before any command, with the
   reason, and a mock run log shows no device call.
2. With the block, a mock run stopped from outside saves exactly the frames
   of the last `length_s` seconds, and the event's sha256 matches the file.
3. The save happens after the abort's read-backs, never before, shown by
   the events' order.
4. The buffer causes no device call: with it on, the only device calls a
   run makes are those it made without it. Card 058's tap test is the
   pattern.
5. `length_s: 0` saves nothing and records it.
6. A normal end saves nothing.

## Boundaries

- Write `microscope_runtime/src/` and `tests/` only.
- No `contracts/`, and no `envelope/` or `approvals/`. Mock only.
- Commit and push through `contracts/tools/seat_commit.py`, naming each
  path. Never `--no-verify`, `--amend` or force.

## What comes back

To this seat, 5 lines at most:

- the commits;
- each test, watched failing, then passing;
- the plans now refused for lacking the block;
- the suite's counts;
- every place the schema did not fit, with the field.
