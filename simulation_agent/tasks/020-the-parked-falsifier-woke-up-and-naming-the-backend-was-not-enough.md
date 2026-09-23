# 020 — the parked falsifier woke up, and naming the backend was not enough

**For:** simulation-2 (the cards and `src/axis_a5_budget.py`)
**Depends on:** `013` (write the trajectory). Half of this card cannot close before it.

## What changed

`a_cost_reference`'s falsifier in `v3_axis_bd_overdamped_a5.json` (and the same
text in `v3_plan_simulation_sim-20260917-001.json`) ends:

> It does not fire today: `hoomd_backend.py` is written and HOOMD is not installed.

**HOOMD was installed on 2026-09-23.** `pixi install -e sim` stands, the sim
environment holds hoomd 7.2.0, and six runs under `runs/` carry
`backend: hoomd_backend` -- `run-20260922-001`, `-003`, `-005`, `-006`, `-007`,
`-008`. The last clause is false, and read literally the falsifier has fired:
a smoke run on the declared backend exists, so both estimates should be
replaced with measured values.

**Do not replace them.** Doing that would repeat, one level down, the exact
defect this falsifier was rewritten to fix.

## Why the literal reading is wrong

The falsifier records its own history: the earlier form said *a smoke run's own
log*, which named an event rather than a state, so two mock runs satisfied it
in letter while measuring the harness. The fix was to name the backend.

But which quantity a run measures is decided by **the artifact it produces**,
not by the engine that produced it. `storage_estimate` costs a written
trajectory and says so in its own note -- *a thousand frames of a thousand
tracers at three double coordinates each, a few tens of megabytes*. No run
writes one. Every run directory holds `config.json`, `log.json`,
`trajectory_meta.json`, `observables.json` and nothing else, because `013` is
open.

    storage_estimate   0.02 GB      E5   assumed:a_cost_reference
    measured dir       0.000036 GB       run-20260922-001

That is a factor of about 550, and **it is not evidence the estimate is
wrong.** It is evidence the runs measure a different thing. Substituting it
would produce a figure that looks measured and is about something else --
which is the sentence already in the falsifier, aimed one level higher.

The run logs carry no size field at all, so there is not even a number to
substitute; the 36 KB above is the directory measured from outside.

`wall_clock_estimate` (0.0001 core_h) is in the same position for a weaker
reason. Elapsed time is derivable from the log, but a run that writes no
trajectory does no trajectory I/O, so what is derivable is not the costed
quantity either.

## What to do

1. **Fix the stale clause now.** It asserts a fact about this machine that
   stopped being true on 2026-09-23. Replace it with what actually holds:
   the engine is installed and the declared backend has run, and the
   falsifier still has not fired because no run writes the trajectory.

2. **Name the state, not the backend.** The condition should be *a run that
   writes the trajectory this plan declares*, which is checkable against the
   run directory rather than against a field the run fills in about itself.
   The backend clause can stay as a necessary part; it is not the sufficient
   one, and the current text reads as though it were.

3. **Then it fires, and it fires for real.** When `013` lands and a
   hoomd_backend run writes a trajectory, both estimates are replaced with
   measured values and both grades rise off E5. Landing `013` is therefore
   what closes this card's second half; the first half closes today.

## Considered and not proposed: a check

A number was weighed for *a card's justification asserts an environment fact
that has flipped*. It is not mechanisable in the general case -- the assertion
is prose and the fact is the world. The one narrow form that would work here,
comparing `engine_check`'s answer against cards claiming the engine is absent,
guards a single string and would go stale the moment the sentence is reworded.
What actually generalises is item 2: **a condition that names an artifact can
be tested; a condition that names an intention cannot.** That belongs in the
card, not in the validator.
