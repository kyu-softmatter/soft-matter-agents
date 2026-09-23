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

## Correction: this card parked the firing, and parking it is not allowed

Architecture is right and the section above is short by one step. It ruled
correctly on the *card* -- do not edit v3 -- and wrongly on the *item*.

**A falsifier whose condition became true has fired, and a fired falsifier is
an event that calls for something.** P16 attaches a falsifier to every lesson
precisely so that something happens when the condition is met. If the answer
is "the generator was fixed and the record waits", then this one fired and
produced nothing, and a condition that produces nothing when met is
decoration -- which is the failure P16 exists to prevent.

So the answer is neither *edit* nor *leave*. It is **leave the record and put
the firing into it.**

### Where the firing can land, measured rather than assumed

An axis card has no light way to be marked superseded. `supersedes` and
`superseded_by` exist in `observable.schema.json` and `ask.schema.json` -- the
KB's entries and the bridge's rounds -- and in **no card schema**. For a card,
superseding means cutting a revision, which means a fan-out with caller_ids
and librarian queries. That is a heavy instrument for a corrected sentence
with no number behind it.

The third place is `failures.jsonl`. It is append-only, it carries `qid`, and
it already holds `deviation` and `abandoned_attempt` entries against this
question. **It does not touch v3 and it does not need a revision.**

### What actually fired, and why that decides the kind

This falsifier did not fire because the world moved the way it anticipated.
It fired because **it was mis-specified**: the condition it names -- a smoke
run on hoomd_backend -- is not the condition that makes the two estimates
measurable, which is a run that writes a trajectory. The world moving merely
exposed that.

That makes the event a defect in the falsifier rather than a result about the
system, and `failures.jsonl` is exactly where this agent records that kind.

### Revised instruction

Item 1 of the section above stands (the generator is fixed, `ec6fbfe`). Items
2 and 3 stand. **Added:** append one entry to `failures.jsonl` against
`sim-20260917-001` recording that `a_cost_reference`'s falsifier fired on
2026-09-23 when the engine was installed, that it was judged spurious because
the condition named the backend and not the artifact, and that the corrected
condition is in the generator and reaches the record at the next revision.
Then `013` cuts that revision and the corrected condition fires for real.

### The shape that was missed twice

On 2026-09-22 the same seat wrote, about the mock: *"I saw only delete or
keep, and keep but remove the silence was the third."* Here it saw only fix
or leave, and **leave and record that it fired** was the third. Both times the
missing option had the same shape -- *the artifact stays and its silence
goes* -- so the lesson is not "look for a third option", which is advice
nobody can act on. It is: **when a two-option frame appears and both options
are about the artifact, the one being skipped is usually about the record.**
