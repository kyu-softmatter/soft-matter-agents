# 094 — a census of the scripts that reach a device outside the operator

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat.** It writes
one Markdown file and changes no code. It comes after card 093, unless the
runtime holder, architecture-office-20261017-1, moves it. If you are not
that seat, take nothing from this card and report up.

## Why

The runtime's orders say there is one execution path: every command goes
through the orchestrator, from an approved plan, and "there is no second
command path anywhere in this repository" (plan.md 15). The gates that a
console question passes through run only on that path: the approval reader,
the other-login refusal, the run lock and the status file.

`microscope_runtime/src/` also holds the bench scripts of September, each
written for one session the person watched: `session_033.py`,
`session_036_blink.py`, `session_036_laser.py`, `session_036_readonly.py`,
`session_038.py`, `record_20260925.py`, `live_view_20260925.py`,
`run_trap_plan_20260925.py`, `shutdown_20260925.py` and others. A rough
count at `04e5264f` finds several that build a backend or open a core
without calling the operator's run. Some still have a `__main__`. A run
started from one of them passes none of the gates above.

The simulation side was asked for the same count (simulation card 028,
item 6). This card is the microscope's.

## What to do

Write `microscope_runtime/src/scripts_outside_the_operator.md`, beside the
bench checklists already there (`findings/` takes only the librarian's JSON
findings), read at a named commit, with one row per file in `microscope_runtime/src/`
that has a `__main__` or is imported by one. Each row gives:

1. **Does it reach a device**, and how: builds a backend, opens a core,
   imports a driver, or none.
2. **Through the operator or not**: `operator.run`, `run_live_view`, the
   check-now run, or its own path.
3. **Can it still run today?** Does it import, and does it find what it
   needs: the moved policy and approvals, a configuration, a driver? Answer
   by importing it and reading its arguments, never by running it against
   the instrument.
4. **Does it take the run lock?**
5. **What it was**: the card and run it served, read off its docstring and
   `runs/`.

End with the count, split three ways:
- reaches a device outside the operator and can still run;
- reaches a device outside the operator and cannot run;
- does not reach a device.

**Propose nothing in the file.** Whether a script is retired, made to
refuse, or kept as a record is decided after the count, by this seat with
the runtime holder, and anything that touches the person's bench is put to
the person.

## Boundaries

- Write that one file only. No code change, and no run of
  any script against the instrument or the mock.
- Commit through `contracts/tools/seat_commit.py`, naming the path. Never
  `--no-verify`, `--amend` or force.

## What comes back

To this seat, 3 lines at most: the commit, the three counts, and any script
that can still run outside the operator and takes no run lock, named.
