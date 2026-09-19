# 007 — the operator set a target, and a standing preference

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**This card is `microscope-1`'s**, because it revises the goal card and re-runs
A2, both of which are that seat's.

## The number — and whose number it is

**Revised 2026-09-19, before anything acted on the first version.** That
version said `target_relative_error = 0.5`, written `operator_set:` at E5.
Two things were wrong with it.

**What the person decided is the decade, not a relative error.** Asked in this
seat's window they chose the option whose label read *50%* and whose body read
*enough to tell whether D is 10⁻¹³ or 10⁻¹²*; the same decision reached the
bridge seat as **one decade**. The decade is the statement, and `0.5` was a
gloss this seat put on it. So what changes on the goal card is small and
exact: `target_decade_resolution = 1` is already there as `assumed:a_target`,
noted *"Screening only needs to place the diffusivity within one decade; the
question is which regime the sample is in"*. **The assumption becomes a stated
goal.** No new number is added.

**A relative error is an axis's margin, not the person's target.** The
simulation side already shows the shape: its A2 carries
`target_relative_error 0.1` as `assumed:a_statistics`, noted *"well inside the
one decade the goal asks for"*. If A2 here derives a statistical requirement,
**keep the two halves separable in the card** — which half a person stated and
which half the axis chose. Statistics go as 1/ε², so the margin is the
expensive half and it is the axis's to justify.

**The shape is ruled and the schema cannot yet express it.** Architecture has
settled that a target is carried with **neither source nor grade**, the way a
ceiling in `envelope/safety.json` is. A `decision:` source kind was rejected,
and the reason is worth carrying: `SOURCE_GRADE` is a function from source to
grade and P2 derives the grade from the source, so a source that yields no
grade is a hole in that invariant — and its content would be *this is not a
source*, written as a source kind.

But `targets[]` is `{metric, number, kind}` where `number` names an entry in
`numbers[]`, and those require source and grade. **The only slot that exists
for a target guarantees what the ruling forbids.** An inline form is proposed
and architecture has not answered.

**So write nothing into the schema-shaped fields yet.** Record in prose that
the person stated one decade on 2026-09-19 and that the encoding awaits
§5.3. This seat added `operator_set:` at `b47dc3d` for exactly this and the
ruling supersedes it; do not use it.

**And the split is not between target-ish and not.** If A2 derives a
statistical requirement from the decade, **that derived number stays a
graded, sourced `numbers[]` entry.** It is a claim about what the statistics
need, not a decision. The line runs between the person's goal and everything
computed from it — not between numbers that feel like targets and numbers
that do not.

**The value is not confirmed to architecture yet.** It reached them relayed,
and they will not write *the person decided* into `plan.md` on a relayed
answer — §6.2.2 applied to themselves. Treat the **shape** as ruled and the
**value** as pending.

## What it unblocks, and what it does not

Half of A2. `frame_count` was missing `target_relative_error` **and**
`localisation_error`, and only the first arrives here — no localisation error
has been measured on this instrument and it cannot be derived without the
pixel size and the SNR actually achieved. So re-run A2 and expect
`frame_count` to stay `no_input` with a **shorter** `missing` list. That is
progress and it must show as progress: one input arriving is not an interval.

`repeat_count` is blocked twice and the second block does not move at all —
the goal says the sample is consumed and cannot be remounted, so repeats are
capped at one whatever the target is. Say so rather than letting the target
look like it helped.

At 50%, roughly four independent displacements carry the estimate. If that
turns out to make A3's dose and A5's duration non-binding, say that too — a
target chosen to be cheap should visibly be cheap.

## The standing preference

The person also stated, the same day: **where relative motion is needed,
prefer moving the piezo stage over steering the trap**, so the object stays
fixed on the sensor for image analysis. It is in
`microscope_agent/CLAUDE.md` now; read it there rather than from this card.

It does not belong in this goal card. It is standing and not per-question, and
`configuration_preference` is for choosing a configuration, not an actuator
inside one.

Two things it does **not** do, both easy to get backwards and both worth a
sentence in A7 when A7 is next written:

- The escape condition `v_max ~ k·x_max/γ` still binds. It is about relative
  velocity, so driving it from the stage produces the same drag.
- What changes is which limits enter: piezo travel, bandwidth and settling
  rather than trap steering rate. `stage_velocity` becomes the binding bound.

## What holds

The pin does not move: `kbv-49feb73662b7`.

A goal revision bumps `goal_revision`, and `configs.json` names
`goal-mic-20260918-001-r6`. Carry it forward so the two do not disagree.

`degraded` stays `[]` on the re-run and stays honest.

## Done when

`goal.json` carries the target at the new revision, `configs.json` agrees on
the revision, A2 is re-run and committed, `python3 contracts/validate.py` ends
`0 failed`, and one commit as `seat:microscope-1`.

Then one sentence up: what A2's `missing` lists say now.

## Not this task

**Card 006**, the `near_names` migration, which still waits on the first E2.
If that E2 lands before you start here, do 006 first and fold this re-run into
it — A2 is in both, and running it twice is the thing to avoid.
