# 080 — move the runtime's code, tests and runs into `microscope_runtime/` (plan.md 15 step 5)

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat**, which the
person opened in `microscope_runtime/` and seated there (plan.md 15 step 4).
If you are not that seat, take nothing from this card and report up.

Questions for the person go to the intake seat,
`architecture-office-20261017-2`, not to your own window (plan.md 6).

## Why

On 2026-10-17 the person decided that execution leaves `microscope_agent/`
for its own folder (plan.md 15, `a8995280`). Everything before this step
has landed:

- the registry narrowed (`df579182`);
- the validator knows the folder (`df11b44b`);
- the run interface is pinned (`78e25f5b`);
- the folder's guards and standing orders are in (`004da816`, `eec87b5e`);
- the console has moved (`908e55c8`, `8e9d8d9`).

**This card is the move itself: one commit, as renames git detects, so
`git log --follow` crosses it.**

## Before anything moves

1. **Your row must cover the paths you move, for this commit only.** Today
   it holds `microscope_runtime/`. Ask `architecture-20261007-1` to add
   `microscope_agent/src/`, `microscope_agent/tests/` and
   `microscope_agent/runs/` until the move lands, and to narrow the row back
   right after (plan.md 15 step 4). Check 41 refuses the commit otherwise.
2. **Nobody may hold an edit in the moving files.** Card 069 is paused
   (`c6f0be0`) and its seat has nothing uncommitted. Confirm `git status`
   is clean for `microscope_agent/src/`, `tests/` and `runs/` at the moment
   you commit. If it isn't, stop and report, and never stash, reset or check
   out another seat's work.
3. **Classify every file and report the list to this seat before moving.**
   Use plan.md 15's table:
   - **Runtime, moving:** the operator, the orchestrator, `devices/`, live
     view, the run lock, the focus search's gate and decider and the copied
     focus core (`focus_classical`, `focus_verdict`, `focus_search`,
     `focus_decider`), and their tests.
   - **Design, staying:** screening, the seven axes and `axis_common`,
     synthesis, `plan_card`, `card_revision`, and their tests.
   - **The rest** of `src/` and `tests/`: the dated session, analysis,
     record and checklist files from the bench days. Each goes where its
     imports and its purpose say. List each with one line of why, and mark
     any you cannot place.

   **Check the import graph both ways**, with an AST walk as card 077 did.
   Nothing staying may import anything moving, and the reverse. A
   cross-import is a finding: report it and do not move around it. Wait for
   this seat's answer before step 4.

## The move

4. **One commit: `git mv` of the runtime's `src/` files, their tests, and
   `runs/`** into `microscope_runtime/src/`, `tests/` and `runs/`. Change
   only what the move itself requires, so git sees renames:
   - **The person's files are read from the runtime's folder.** The policy
     and the approvals are read at `microscope_runtime/envelope/safety.json`
     and `microscope_runtime/approvals/`.
     - **Nothing falls back to the old path.** A missing policy or
       approval refuses, as `operator.py` already does ("Nothing executes
       without a safety policy").
     - `devices/lunf.py` and `devices/python_serial.py` find the policy by
       a path relative to their own file. Confirm they resolve to the new
       folder.
   - **The knowledge snapshot stays where it is.** It is read by its
     explicit path, `microscope_agent/envelope/snapshot.json`, one copy for
     both folders.
   - **Runs are written to `microscope_runtime/runs/`.**
5. **In the same commit, a test, watched failing first, that the moved
   operator refuses when the policy is absent at the new path**, even while
   one still sits at the old path. Watch it fail against a planted fallback.
6. **Between this commit and the person moving their files (step 6),
   nothing can run.** The runtime finds no policy in its folder and refuses.
   That is the direction a late step has to fail in. Say so in the message.

## Done when

- `git log --follow` on a moved file crosses the move, shown on one file in
  your report.
- The runtime's tests pass from `microscope_runtime/`, and the design's
  from `microscope_agent/`, with counts for each and the total equal to
  before, apart from the new test.
- The validator ends 0 failed, and `--expect-fail` holds its counts.
- The message carries the full old-to-new path list and states that nothing
  can run until step 6.

## Boundaries

- **Never `envelope/safety.json` or `approvals/`.** Moving them is the
  person's own act, step 6, byte for byte with sha256 shown.
- No change to `contracts/`. If a check names an old path wrongly, report
  it to this seat.
- `microscope_runtime/CLAUDE.md`, `.claude/` and `tasks/` are this seat's,
  not yours.
- No hardware. Mock only.
- Commit and push through `contracts/tools/seat_commit.py`, naming every
  path. Never `--no-verify`, `--amend` or force.

## What comes back

To this seat, 6 lines at most:

- the classification list, before the move;
- the commit;
- the `--follow` check;
- the absent-policy test, watched failing, then passing;
- both suites' counts;
- anything that named an old path and was not yours to change.
