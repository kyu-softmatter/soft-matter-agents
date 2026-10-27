# 093 — a live view that fails says which channel failed, and how

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat.** It is
small and comes after card 092, unless the runtime holder,
architecture-office-20261017-1, moves it. If you are not that seat, take
nothing from this card and report up.

## Why

The console's connection page shows a live view's end as its status file has
it, `last_run.outcome`, and it shows that text verbatim (manager-console,
2026-10-26). A live view whose camera cannot open never becomes a run, and
the host refuses it with the error. But a live view that **started** can
still fail mid-run: the camera goes away, or a read would wait. Read at
`32e7f044`:

- `operator.run_live_view` catches the error, records `live_view_failed`
  with `error`, aborts, and calls `o.end_run("failed")`;
- `idle_status` writes `outcome` as `str(how)`, which gives `"failed"`.

So the page says "failed" and cannot say which camera, or whether it was
absent or busy. The log has the error, and the status file does not. No
schema change is wanted: `outcome` is already a free string, described as
"run_ended's reason, as the log has it".

## What to build

In `microscope_runtime/src/`:

1. When a started live view fails, `run_ended` names the channel that raised
   and what happened to it, in words. One of:
   - absent: the channel did not answer;
   - busy: a read would wait (`ReadWouldWait`);
   - error: anything else, with the caught text.
2. The status file's `last_run.outcome` carries that same text, for example
   `failed: kinetix_red busy: <message>`, so the page needs no other field.
3. The run log's `ended` stays one of its four values. Only the reason
   carries the detail.
4. Where the channel cannot be told from the error, the outcome says
   "unknown channel" with the caught text. It never names a guessed one.

Plan runs and check-now runs are out of scope. Check-now already writes a
per-channel `error`.

## Tests, each watched failing first

1. On mock, with card 086's test-only connection states, a live view whose
   camera goes absent after it starts ends `failed`, and its status file's
   outcome names that camera and says absent.
2. The same with busy.
3. An error raised from no channel gives "unknown channel" and the text.
4. A completed live view's outcome is unchanged.
5. The existing suite is unchanged.

## Boundaries

- Write `microscope_runtime/src/` and `tests/` only. No `contracts/`, no
  `envelope/` or `approvals/`, no `console/`.
- Commit through `contracts/tools/seat_commit.py`, naming each path. Never
  `--no-verify`, `--amend` or force.

## What comes back

To this seat, 3 lines at most: the commit, each test watched failing then
passing, and the suite's counts.
