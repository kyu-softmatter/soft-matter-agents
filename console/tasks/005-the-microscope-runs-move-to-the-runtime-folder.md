# 005 — the console follows the microscope's runs and approvals to microscope_runtime/

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, from 2026-10-19. If
you are not that seat, take nothing from this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

`plan.md` 15 moves the microscope's run-side folders out of
`microscope_agent/`, in two steps:
- **`runs/`** goes to `microscope_runtime/runs/` in card 080's commit, by the
  runtime seat. manager-microscope-20261003-1 reported on 2026-10-18 that it
  lands shortly.
- **`approvals/`** (and `envelope/safety.json`) go to
  `microscope_runtime/approvals/` later, in the person's own commit (step 6).

The shapes do not change; `contracts/schemas/run_interface.schema.json` is
untouched. Only the folders move. The questions, the plan cards and the
knowledge snapshot stay in `microscope_agent/`.

The console reads three places that move:
- `agents/sma_files.py` reads runs at lines 299, 302 and 344
  (`<root>/microscope_agent/runs/...`);
- the same file reads approvals at line 416;
- `agents/sma_live.py` reads live-view lists at line 107, which are files in
  approvals.

After the move, run-following finds no runs. **The lock-screen stop then
answers "nothing was running" while a run is running.** That is the one
outcome a stop button must never give, so this card comes before the first
real run, like card 004.

## What to do

1. **One rule, in one place, for where the microscope's run-side folders
   are.** For the microscope seat, each of `runs/` and `approvals/` is read
   from `microscope_runtime/<folder>/` if that folder exists, and otherwise
   from `microscope_agent/<folder>/`. Decide each folder on its own, so the
   time between the two steps reads correctly: runs moved, approvals not
   yet. The simulation seat keeps `simulation_agent/` for both. The
   questions stay in `microscope_agent/questions/`.
   - Every reader goes through that rule: runs, run following, the stop,
     approvals, and live-view lists. No reader keeps a path of its own.
   - The old-path branch is for a tree from before the move, such as a
     scratch copy made earlier. It is display-side only, and no reader
     that enforces anything is involved. Once step 6 has landed, a later card
     removes it.
2. **The stop never mistakes "cannot see the runs" for "nothing running".**
   If neither folder exists, `POST /api/console/runs/stop` answers a
   distinct outcome, that this project's runs folder was not found, and
   the lock screen says so in plain words. The same holds for any screen
   that lists runs.
3. **Tests, each watched failing first:**
   - A tree with only `microscope_runtime/runs/`: runs are found, followed
     and stopped, and the stop lines are as card 004 pinned them.
   - A tree with only `microscope_agent/runs/`: the same, through the
     old-path branch.
   - A tree with runs moved and approvals not yet: the runs come from the
     runtime folder, and the approvals and live-view lists from the agent
     folder.
   - A tree with neither runs folder: the stop answers "not found",
     never "nothing running".
   - Card 004's guard and its stop tests still pass, unchanged except for
     where their fake runs are written.
4. **Run everything and report the counts**: Python tests, typecheck, web
   tests, build, validator (0 failed).
5. **Commit through `contracts/tools/seat_commit.py`**, paths under
   `console/` only, and send me the hash.

## What you must not do

- Touch `microscope_runtime/`, `microscope_agent/` or `contracts/`.
- Read both locations for one folder and merge them. Read one, by the rule.
- Write anything into a runs or approvals folder, in either place.
- Start the server with anything but `--backend placeholder`, or point it at
  a live host.
- Write outside `console/`, or edit `console/CLAUDE.md`, `console/README.md`,
  `console/tasks/` or `console/.claude/`.
