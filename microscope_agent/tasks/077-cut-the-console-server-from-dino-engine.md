# 077 — cut the console's server from dino's engine, before the console moves

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261015-1` (Microscope 3)**, from
2026-10-18. It was first written for `microscope-office-20261015-2`, whose
session closed before the card reached it, so nothing of this card has
started. Card 064 gives both dino seats `microscope_agent/autofocus/`, so
this card needs no handover of paths. Card 069, also yours, stays paused
until plan.md 15's move and touches no file this card does. If you are not
`microscope-office-20261015-1`, take nothing from this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window** (plan.md 6 at
`7d48af21`). A decision said there counts once its line is committed, and
you cite that commit.

## Why

plan.md 15 (`a8995280`) moves the console to its own top-level folder,
`console/`, in two commits. The console seat adds its part of `autofocus/`
under `console/`, and then a microscope seat deletes the originals. **This
card comes before both.**

The server dino brought with it carries dino's own engine:

- it can open a real Micro-Manager core (`--backend mm-real`);
- it passes light, stage, objective and trap commands through
  `/api/commands`;
- only dino's own lock holds that back today: `BENCH_MOTION = "LOCKED"` at
  `src/dino_autofocus/engine/backends/mm_real.py:90`.

That engine is a second execution path and a second core, which this
repository forbids, and it must not arrive in a folder whose rules say the
console commands nothing.

The imports run both ways, as the console seat measured at `2f0d6f3b`,
read only:

- **The server reaches into the engine.** Twelve server modules import
  dino's engine, focus, live or records code. A grep at `78e25f5b` finds
  these files under `src/dino_autofocus/server/`: `__main__.py`, `app.py`,
  `ws.py`, `schemas/contract.py`, and `api/__init__.py`, `hardware.py`,
  `map.py`, `objective.py`, `patterns.py`, `sample.py`, `sessions.py`. Your
  test, below, is the count of record, not this list.
- **The engine reaches into the server side.**
  `src/dino_autofocus/engine/backends/mm_real.py:255` imports
  `auth.config`.

## What to do

1. **Draw the line, file by file, and report it before cutting.** The
   console-design draft gives the split at `667f2c71`, in
   `docs/drafts/console-top-level-move-20261017.md`. What reads and shows
   crosses: the web app, the server's placeholder and mock backends, this
   repository's run interface, the assistant that only proposes, and the
   screen documents. What measures, moves or lights stays. Send the list of
   what crosses and what stays to this seat and to the console's manager,
   `manager-console-office-20261017-1`, and wait for both to answer.
2. **Sever every import from something that crosses into something that
   stays.**
   - Routes and backends that need the engine stay with the engine, behind
     dino's lock: the `mm-demo`, `replay` and `mm-real` backends,
     `/api/commands`, and the engine-backed routes. Do not move them, and do
     not unlock them.
   - Move `mm_real.py:255`'s dependency on `auth.config` to the engine's
     side, or pass the value in. **Nothing that stays may import anything
     that crosses.**
3. **Then retire dino's engine command path. This is the target, not an
   option** (revised 2026-10-17). plan.md 15 settles it, in the sentence
   architecture-office-20261017-1 gave for its console paragraph: "dino's
   engine command path is retired, not re-placed beside the orchestrator:
   every command goes through the orchestrator (11-25 rule 3) on the one
   execution path (4.6.8), so a second command path survives nowhere here,
   whatever dino's own plan said about deleting its motion only later.
   Until the cut card retires it, it stays locked where it is and moves into
   neither new folder."
   - **The lock stays in force until the retirement lands.** Never unlock
     it, not even to test.
   - Retire the path in its own commit, after the cut in step 2 and its
     import test. That covers what lets dino's engine send a command to a
     device: `/api/commands` and its handlers, and the `mm-demo`, `replay`
     and `mm-real` backends' command and motion paths. List each file and
     function removed.
   - **What it could do that is still wanted is not re-built here.** A light
     setting, a stage move, an objective change, a trap step, a sample map
     or a pattern re-enters only as the orchestrator's, inside
     `microscope_runtime/`, through plans the person approves, each by its
     own card.
   - **The console's command buttons are not this card's.** Section 15
     orders them: each console area that sent commands to the engine gets
     its draft-a-plan or run-interface replacement first, and its buttons
     go after that, on the console manager's cards. If a console test that
     crosses still calls a path you retire, report it to this seat and to
     `manager-console-office-20261017-1` rather than keeping the path
     alive.
   - Measuring code the engine also holds (focus, models, configuration
     files, scripts) is not a command path. It stays in `autofocus/`.
4. **The console's reader of the run interface follows
   `contracts/schemas/run_interface.schema.json`** (`78e25f5b`). Its
   `run_ended` `how` must accept `refused`, which the operator writes and
   `sma_run.py`'s `RUN_ENDED_HOW` does not list. Change only what you need
   to keep its tests green. The rest is the console manager's to card.

## Done when

- **A test inside `microscope_agent/autofocus/` shows that nothing which
  crosses imports anything which stays**, by walking the import graph over
  the two path lists, not by grepping names. Watch it fail on a planted
  import first, then remove the plant.
- With the cut, the console's own tests, run on the placeholder and mock
  backends with `--store sma`, are as green as they were before it. Card
  063 shows how to run them that way.
- dino's engine-side tests are as green as they were before the cut. Card
  072's suite is the baseline.
- No backend that opens a core is reachable from anything that crosses.
- dino's engine command path is retired, in its own commit, and its tests
  are removed with it, or changed to assert that the path is gone.

## Boundaries

- Write inside `microscope_agent/autofocus/` only. No change to
  `microscope_agent/src/`, `envelope/`, `approvals/` or `inbox/`, and none
  to `contracts/`.
- Move nothing to `console/`. That folder does not exist until the console
  seat's commit, and the move is not this card's.
- Run nothing that opens a Micro-Manager core, and never set the lock to
  unlocked. Removing the path the lock guards is step 3.
- Through the gate, naming each path. Never `--no-verify`, `--amend` or
  force.

## What comes back

To this seat, 6 lines at most:

- the commits;
- the two path lists, crossing and staying;
- each severed import, and what it now does instead;
- the import test, watched failing, then passing;
- the suites' counts before and after;
- the engine command path retired: files and functions removed, and any
  console test that still called it.
