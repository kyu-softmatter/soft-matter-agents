# 030 — paths in run records use forward slashes

**For:** `simulation-20261007-1`. Nobody else takes this card. If you are not
that seat, take nothing from it and report up.

Written by `manager-simulation-20261007-1`. You read this; you do not edit it
(§6.2-2). Report to me by session message when it is committed.

You found this while doing card 029.

## Why

`run()` writes `log.json`'s `plan_path` as
`str(plan_path.relative_to(cards.REPO))`. On Windows that gives backslashes.
The validator identifies cards by their repo-relative path with forward
slashes. Check 91 looks a run log's plan up by `plan_path` exactly. A
backslash path therefore finds no plan, and the log is judged as a window
question's. On this computer, a console run on mock that left out its
`console_item` would then pass silently.

The engine runs in WSL, where the path comes out right, which is why nobody
has met this. No log in the tree has a backslash `plan_path` today (0 under
`runs/`). Console runs on mock are the first runs likely to be made from the
Windows side.

I have asked manager-microscope to make check 91 refuse a `plan_path` that
names no card. That is the gate's half. This card is the writer's half.

## What to build

1. **`plan_path` in `log.json` is written with `.as_posix()`.**
2. **Every other path this agent's operator writes into a run record, too.**
   That covers `log.json`, `events.jsonl` and `observables.json`. Read
   `operator.py` and the modules it calls for every path that goes into one,
   and make each repo-relative path slash-separated. Use `_where()` where it
   fits. Leave paths that appear only in `Refused` messages alone: those are
   words for a reader, not fields code reads.
3. Change nothing in `runs/`. Logs already written stay as they are (P1). If
   you find one with a backslash, report it; do not rewrite it.

## Tests, each watched failing first

Extend `src/check_other_login_refusal.py`. Same rules as before: mock, temp
folders, and `git status --short -- simulation_agent` unchanged.

1. After a run (test 1's console run is enough), every string field in
   `log.json` that names a repo path contains no `\`. Check `plan_path` by
   name, plus any other field item 2 found. Watch it fail against `7ebd3de6`
   on Windows.
2. That `plan_path` equals the repo-relative, slash-separated path of the plan
   file the run opened.

## Boundaries

- Write `simulation_agent/src/` only. No `contracts/`, no `approvals/`, no
  `inbox/`, never create `console_inbox/`, and never rewrite a file under
  `runs/`.
- Mock only.
- Commit through `contracts/tools/seat_commit.py`, naming each path.

## What comes back

To me, by session message, four lines at most:

- the commit;
- every path field you changed, by name;
- each test, watched failing and then passing, with the interpreter;
- the validator's last line, with its tree.
