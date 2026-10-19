# 004 — a stop on the lock screen that needs no login

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, from 2026-10-18. If
you are not that seat, take nothing from this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

Card 003 removed the lock screen's Abort button, because it posted to the
retired `/api/commands` and so stopped nothing. That left a locked console
with no stop. The person asked for one, committed at `cee4f8c1`,
`docs/ideas/20261018.md`, Q-20261018-03, in the intake seat's window:
"콘솔 잠금 화면에 로그인 없이도 이 프로젝트의 실행을 멈추는 정지 버튼을
두고, 첫 실제 실행 전에 끝내." ("Put a stop button on the console's lock
screen that stops this project's runs without logging in, and finish it
before the first real run.")

**The words ask for a way to stop and for nothing else.** No other command
becomes reachable without a login, and nothing this card adds can start,
light or move anything.

## What is already there, and what is missing

- **The crossing exists and does not change.** A run this project executes
  announces its stop channel in `run_started`. The console sends one line on
  it, `{"stop": <run_id>, "reason": <text>}`, exactly as
  `contracts/schemas/run_interface.schema.json` pins `stop_request`
  (`agents/sma_run.py`, `send_stop`). Nothing in `microscope_runtime/` or
  `microscope_agent/` changes for this card.
- **The server already lets the microscope computer stop without a login.**
  `server/api/__init__.py` `command_why`: on loopback, a stop "always, with
  or without a login". `POST /api/console/runs/{agent}/{run_id}/stop` is
  matched as a stop at the edge (`SMA_STOP_PATH`).
- **What is missing**:
  - the button;
  - a way for a locked or logged-out screen to stop runs it cannot list,
    because every read but `/api/health`, `/api/auth/setup` and, while
    locked, `/api/auth/me` needs a login.

## What to do

1. **One write route that stops every running run this project executes:**
   `POST /api/console/runs/stop`. The name is yours to adjust, if the
   message says why.
   - The server finds the microscope runs whose `events.jsonl` says they are
     running and whose stop channel was announced, and sends one stop line
     to each through `send_stop`.
   - It answers with each run's id and outcome. It runs nothing else, and
     it reads no file outside the store's runs.
   - **It is the only new thing reachable without a login, and only on
     the microscope computer (loopback).** A remote viewer keeps today's
     rule: it may stop only when logged in and when remote abort is on.
   - The edge treats it as a stop, alongside `SMA_STOP_PATH`. Every stop is
     written to the audit log as `stop_run` writes it, with who asked, "the
     microscope PC (no login)" when there is no login.
   - With no run running, it says so and sends nothing.
2. **No new open read.** The button does not list runs before stopping.
   It asks the server to stop whatever is running and shows what came back.
   A read that worked without a login would show a stranger the run list,
   which the person did not ask for.
3. **The button.**
   - The lock screen and the logged-out screen show one control, "Stop all
     runs", whenever the console is connected to this project's files
     (`--store sma`).
   - Pressing it sends the one request and shows each run's outcome in
     plain words, or that nothing was running.
   - No confirmation step, because a stop that waits for a second click is
     slower to stop. It cannot be pressed twice in flight.
   - With the mock store, it says it is not connected and sends nothing.
4. **Tests, each watched failing first:**
   - Without a login, on loopback, two fake followed runs, one ended: two
     stop lines go out, one to each running run, and each validates against
     the schema's `stop_request`. The ended run gets none.
   - Without a login, from a remote address: refused.
   - With a login, from a remote address: allowed only with remote abort
     on.
   - **The guard on the person's words.** A test lists every write route the
     app mounts. It asserts that without a login each one refuses, except
     the login and setup paths that already work that way, `/api/shutdown`
     on loopback, and the two stop routes. A new write that works without a
     login then fails this test.
   - Web: the locked and logged-out screens render the button, and a press
     makes exactly one request, to the new route.
5. **Run everything and report the counts**: the Python tests, typecheck,
   the web tests, the build and the validator (0 failed).
6. **Commit through `contracts/tools/seat_commit.py`**, paths under
   `console/` only, and send me the hash. I send it to the intake seat for
   the person's record.

## What you must not do

- Make anything other than a stop reachable without a login, or make a stop
  reachable without a login from another computer.
- Add a confirmation step that delays the stop.
- Touch `microscope_runtime/`, `microscope_agent/` or `contracts/`. If the
  pinned stop line is not enough, stop and report; the schema is not this
  folder's.
- Start the server with anything but `--backend placeholder`, or point it at
  a live host. The tests use the fake runs, not a real one.
- Write outside `console/`, or edit `console/CLAUDE.md`, `console/README.md`,
  `console/tasks/` or `console/.claude/`.
