# 040 — the dispatcher runs an operation plan, and reaches the two blind wrappers

Written by `manager-microscope-20260924-1`. You read this; you do not edit it
(§6.2-2).

**Assigned to `microscope-20260924-2`.** This card is what stands between
the person's approved sine and a moving axis. The person approved it in
your window: 290 µm around 300 µm, 1 Hz, 5 cycles, with a result of
position against time.

## Why the dispatcher, and not a session script

`plan.md` at `66e3d83`: **a planned run goes through the dispatcher**,
because what makes a run planned is that its commands are derived from the
plan mechanically rather than written beside it by hand. An operation
plan's findings leave as a result card, so it is a planned run. **A stand-in
script is for a preparatory run only.**

The operation-plan shape landed at `cd2d5b7`: `plan.schema.json`'s
`operation`, and check 86. Read both before starting.

## When you may start: not while a run imports these files

This card edits **`src/orchestrator.py` and `src/operator.py`**, which
`microscope-20260924-1`'s session scripts import. **Start only after `-1`
has released the bench after card 038, and no run is in progress.** Ask
that seat, and check `git status` for its uncommitted work in these files.
`-1` has card 041 queued on the same files after you. **Land yours first,
commit it, and tell `-1` and me.** Two seats in one file at once is how a
goal card got overwritten on 2026-09-21.

## What to build

1. **`derive_commands` derives an operation plan's moves**, mechanically,
   from `operation.moves`:
   - a step becomes one absolute position write, and a ramped step
     (`ramp_um_per_s`) becomes writes paced from the integer index
   - a sine becomes `cycles × points_per_period` absolute writes. The
     position of point `i` is computed from `i`, never from an accumulated
     phase, starting at its `start`. The time of point `i` is `t0 + i × dt`,
     from the integer, and late points are logged as late, never re-timed
   - **every derived point is checked against the envelope's limits
     before the first is sent.** This is condition 2 at run time: check 86
     checks the plan statically, and the dispatcher checks what it actually
     derived. They must agree, and a disagreement refuses
2. **Position is read back before and after each move** (condition 4),
   logged as `readback` only when it matched within the plan's own
   `targets` tolerance, and the run stops on the stop criterion otherwise
3. **The router reaches the two blind wrappers by the person's named
   exception only** (`plan.md` 4.6.6 rule 5 at `66e3d83`). `laser_combiner`
   and `optical_tweezers` route to their wrappers, with `verification:
   none`. **Any other `read_back: false` channel still goes to the manual
   sheet, whatever the registry says.** Name the two in code, and say why.
   `lunf.py`'s module name waits on the librarian fixing the registry's
   `driver` head, so the laser may stay unreachable after this card, which
   is correct
4. **`check_software_motion`, `SOFTWARE_MAY_COMMAND` and `GuardedCore` stay
   byte-identical.** What changes is what the check is applied to, and
   **this card is the decision to change it.** The allow-list's own comment
   says lifting it is a card's decision, not an edit made in passing, and
   this is that card. Ruled 2026-09-24 on `microscope-20260924-2`'s
   question, option (a), narrowed:
   - **exempt only commands derived from `operation.moves` of a plan with
     `operation` present, `operation.device == "piezo_stage"`, and a move
     axis of `x` or `y`.** Everything else goes through the allow-list
     exactly as today, **including piezo Z**. That covers a Micro-Manager
     command inside an operation plan, and any plan without `operation`
   - **piezo Z stays refused by the allow-list** until the wrapper compares a
     Z target against `objective_clearance_min` at the moment of the move.
     `plan.md` makes that binding and nothing enforces it yet. Lifting Z is
     a later card
   - **the exemption is decided from the plan's structure, never from a
     flag**, and the derived-point envelope check of item 1 replaces the
     allow-list for exactly those commands. If the derived points and the
     plan disagree, it refuses
   - **every exemption is logged as its own event**, naming the plan field
     it came from (`operation.moves[i]`), so the log shows where the
     allow-list did not bind and why
   - a test watched failing for each: a piezo Z move from an operation plan
     is refused; a piezo X move from a plan without `operation` is refused;
     a Micro-Manager command inside an operation plan still meets the
     allow-list

   Card 033's "software moves nothing" still binds everything this does not
   name. It was the rule for a day with no designed motion. This card
   designs one motion, bounded four ways: the envelope, check 86, the
   person's approval, and the bench

Each of 1 to 3 gets a test in `microscope_agent/tests/`, watched failing
with the behaviour switched off.

## Then the person's sine

Write the operation plan against the shape: approach step to 10 µm, the sine
starting at its `minimum`, X only, 5 cycles at 1 s. **Show the person the
peak speed** check 86 reports (about 1.8 mm/s) **before approval, in
words**: it is about 29 times the fastest the prior project drove, and no
envelope limit bounds a piezo's speed. **Whether to cap it is the
person's.** Then the ordinary plan approval, the bench handed over in your
window, and the controller powered on by the person. The run and its result
card are a planned run's, through the dispatcher.

## Constraints

- **Z is not in this card's run.** It rests 1.7 nm below the person's 0 µm
  floor, so the wrapper correctly refuses every Z command. Whether the floor
  should admit the controller's rest position is the person's question
- commit with `git commit -- <paths>` after `git diff HEAD -- <paths>`.
  Hooks are not installed; say so. Run
  `PYTHONUTF8=1 python contracts/validate.py` and read the tree line

**Re-read this card immediately before committing.**
