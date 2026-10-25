# 014 — Experiments, on the mock store

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, after card 013. If you
are not that seat, take nothing from this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

The person, after running the console from a clone (I-20261024-office-02,
`5f88eab4`):

> 인스투르먼트, 익스퍼리먼트, 라이브러리도 구축해줘.
> 인스투르먼트와 익스퍼리먼트는 목 시스템으로 우선 구현해보자

("Build the Instruments, Experiments and Library too. Let's implement
Instruments and Experiments on a mock system first.")

For Experiments, the runtime holder (architecture-office-20261017-1) says the
console's `--store mock` may serve as the mock. That store reads copied
files with the same reader, so it is data and not an engine (plan.md 15.1
item 6). It stays that under four limits, which this card makes tests:
1. **It stays a reader.** A stop, a live-on, a check-now or a signature never
   makes it produce run events, frames, readings or a run. Whatever answers
   a console action as an instrument would comes only from the runtime on
   `--backend mock`. Where that is not connected, the screen says so.
2. **Everything from it says "example data"** and can name its source,
   `mock_data/SOURCE.md`.
3. **Its copied runs move to the current layout.** Real runs live in
   `microscope_runtime/runs/` since `a36e49d0`, so the screens are built
   against the path the real store reads.
4. Its practice approvals write nothing.

The canvas screens are `PExperiments`, `PSample` and `PSampleMap`, version
58.

## What to do

1. **Refresh the mock sample.**
   - Move the copied microscope runs to
     `mock_data/microscope_runtime/runs/`.
   - Update `SOURCE.md`: what was copied, from which commit, and that it is
     example data.
   - Keep the per-folder rule (card 005) reading both layouts for a real
     tree.
2. **Runs (`PExperiments`).**
   - The run list; each run opens to rows showing:
     - who signed and how: by hand, or through the console under a login;
     - how it ended, in words from `RUN_ENDED_HOW`;
     - a short summary of its events.
   - **A run waiting on a step done by hand**, read from
     `runs/<id>/manual_steps.md` with the sheet still open, shows "Waiting
     for a step at the microscope. Confirm it there." with no button.
   - **A stop on a run that had traps** adds "tweezers laser: software
     cannot switch it; assumed on until you confirm".
   - **Drafts waiting for a signature**: the section says drafts are not
     saved yet, because where a console draft lives is still to be
     designed.
3. **Sample (`PSample`).**
   - "No sample record yet: where a sample's record lives is still being
     designed". Invent no path (architecture-20261007-1).
   - If a run's hand-step sheet holds a loading check, show it as "done at
     the microscope, from <run>'s hand-step sheet".
4. **Sample map (`PSampleMap`).** Each part says "not built yet" and why:
   - no run yet saves frames with the stage's read-back;
   - no hole fitter or candidate finder is built in the runtime;
   - flags and candidate confirmations cannot be recorded yet.

   No moves are drawn. A model's guesses are never drawn as candidates.
5. **Tests, each watched failing first:**
   - every console action leaves the mock store's files byte-identical:
     stop, live-on, check-now, sign;
   - every mock screen carries "example data";
   - the refreshed sample reads from `microscope_runtime/runs/`;
   - an open hand-step sheet shows the waiting line and no confirm button;
   - the trap-stop line;
   - Sample and Sample map show their "not yet" states;
   - no Experiments screen reads anything under `librarian_agent/`.

## What not to do

- No stand-in for a runtime piece, and no run started from the console.
- No write outside `console/`. No retheme yet. Install nothing.

## Done when

- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest` passes.
- The validator ends `0 failed`.
- One commit through `contracts/tools/seat_commit.py`. Report the hash to
  this seat.
