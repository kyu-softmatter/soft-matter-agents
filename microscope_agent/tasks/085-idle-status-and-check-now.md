# 085 — the idle status file, and "check now"

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat. Start after
card 084.** Both touch the live-view host and the orchestrator, one at a
time. If you are not that seat, take nothing from this card and report up.

## Why

The redesigned console shows the instruments' state when nothing runs, and
has a "check now" button. The person's word, Q-20261022-office-08
(`471ef2df`), is that it "opens, reads and closes from a list approved once,
with no light and no motion". plan.md 15.1 item 3 says how:

- outside a run the runtime holds nothing open, so idle status is **a file
  the runtime writes**, never a device the console asks;
- "check now" is a **preparatory run** under 11-21's conditions, in the
  live-view pattern.

**Read 15.1 item 3 and 11-21 before starting.**

## What is in `contracts/` (this card's commit)

- **`check_now_list.schema.json`.** The list the person writes in
  `microscope_runtime/approvals/`. Each entry is `{channel,
  opening_is_inert_because}`, and the closed shape admits no setting, value
  or action, so the file cannot express a command. Check 85 refuses a list
  naming anything in the motion set. `contracts/examples/check_now_list.json`
  is an accepted example. No real list exists yet: the person writes one.
- **`idle_status.schema.json`**, the file you write. Its fields:
  - `written_at` and `written_by_run`, so the view can say "as of this time,
    from this run";
  - `last_run`: kind, outcome, the last preflight rows and the last
    snapshot;
  - `check_now`: the last check-now run, per channel `opened`, `closed` and
    an optional `error`;
  - every channel, in both, is a **reading**: `channel`, `name` (the
    registry's display name as the run read it, because the console opens
    no store), `how` (`read_back`, `not_readable` or `not_read`), `t_wall`
    and `value`. `not_read` has a null time and a null value. A channel with
    no read-back is `not_readable`, and its value is what this run sent.
    These are the console's three asks of 2026-10-22;
  - `ownership`: `{"status": "not_built"}` until 4.6.10's ownership check
    exists;
  - `registry`: the path and sha256 of the registry you read, pointed to,
    not copied.
- **`run_interface.schema.json`**: `check_now_request`
  `{"check_now": "<sha256>"}` and `check_now_reply` (`started` with
  `run_id`, or `refused` with `reason`), each with `examples` and
  `x_refused`.
- **Where the file lives**: `microscope_runtime/.runtime_status/idle_status.json`.
  - The validator's walk skips `.runtime_status`, and architecture adds the
    `.gitignore` line.
  - Check 79 now fails any tracked file inside a skipped directory, so a
    forced add is refused at commit. Never commit the file. It is volatile,
    and everything in it is already in a run's own log.

## What to build

In `microscope_runtime/src/`:

1. **Write the status file at the end of every run**, check-now runs
   included, from that run's own log:
   - written atomically: a temporary file in the same folder, then renamed
     over the old one;
   - **nothing carried forward**: a channel the last run did not open is
     absent, never given an older value, and every value keeps the time it
     was read. A busy read (`ReadWouldWait`) is `not_read`, never its last
     value;
   - a failed write is recorded in the run's log and never fails or delays
     the run's end;
   - create `.runtime_status/` when it is missing.
2. **"Check now" in the live-view host.** It accepts a second one-line
   message, `{"check_now": "<sha256>"}`, alongside `live_on`, and nothing
   else.
   - Find the list under `--approvals` by the sha256 of its raw bytes, and
     validate it against the schema. An unknown hash or an invalid list is
     refused with the reason.
   - Run it as a preparatory run: `plan_id` null, `no_plan_because`, and
     `approved_commands` naming the list's path and sha256. Take the run
     lock as every run does.
   - For each listed channel, in order: preflight, open, `read()`, close.
     Record each step. A step that fails is recorded and the next channel is
     tried, and a channel is always closed if it was opened.
   - **Nothing in the motion set, and no command to anything.** There is no
     `apply`. Use `orchestrator.is_light_command` in the tests to show that
     no light command and no motion dispatch appear in the log.
   - A channel not in the registry refuses the whole run before anything is
     opened.
   - When the run ends, write the status file.
3. **Live view and check now never run at once.** The run lock already
   says so. A `check_now` while a run holds the lock is refused with that
   reason.

## Tests, each watched failing first

1. A mock check-now run opens, reads and closes each listed channel in
   order. Its log has no `apply`, no light command and no motion dispatch.
2. Check 85's conditions hold on that log: a preparatory run that names its
   list, dispatches nothing to the motion set and has no result of its own.
3. An unknown hash, an invalid list, a channel not in the registry and a
   held run lock are each refused with the reason, and none opens anything.
4. The status file validates against `idle_status.schema.json` after a plan
   run, a live view and a check-now run. A channel opened in an earlier run
   and not in the last one is absent from `check_now`, never carried
   forward.
5. A failed status write leaves the run's outcome unchanged and is recorded.
6. A reader that reads the file while it is being written sees either the
   old file or the new one, never half of either.
7. Every `examples` and `x_refused` entry of `check_now_request` and
   `check_now_reply` is accepted or refused as the schema says, read from
   the schema file.

## Boundaries

- Write `microscope_runtime/src/` and `tests/` only. No `contracts/`, no
  `envelope/` or `approvals/`. Mock only.
- **Do not write a real check-now list.** The person writes it, and decides
  which channels are inert to open (a serial open can assert DTR). Tests use
  lists in their temp folder.
- The console's button is manager-console's. Don't edit `console/`.
- Commit and push through `contracts/tools/seat_commit.py`, naming each
  path. Never `--no-verify`, `--amend` or force.

## What comes back

To this seat, 5 lines at most:

- the commits;
- each test, watched failing, then passing;
- one mock check-now run's log, in counts: channels opened, read and closed,
  and zero `apply`;
- the suite's counts;
- every place the schema did not fit, with the field.
