# 019 — S5 refuses on two fields that are already answered

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Assigned to `microscope-5`.** Read the card file again immediately before
you commit — see the note at the end, which exists because a card changed
hands twice today and the second time the edit did not reach a running
session.

S5 refuses `mic-20260920-001` on **seven** fields. **Two of them are not
gaps**, and closing them is this card. The other five wait on numbers the
person is being asked for.

Run it first and read the refusal yourself:

```bash
python3 microscope_agent/src/plan_card.py --qid mic-20260920-001
```

## 1. `objective_zoom_pair` — the person chose, and S5 cannot see it

S5 says four values satisfy the bound, nothing distinguishes them, and it
goes to the person under §4.5.1(c). **The person already answered: `100x@1x`.**
It is in the goal card, as two numbers:

```
nosepiece_position          5    count   <- 100x oil, MRD71970
intermediate_magnification  1    1
```

**A6 returns one name and the goal card carries two.** S5 looks for a number
called `objective_zoom_pair`, does not find one, and reports an unresolved
tie over a choice that was made.

**Resolve the pair from its parts.** The two numbers name a turret position
and an intermediate magnification, and `objective_zoom_pair`'s values are
exactly that product — `100x@1x` is position 5 with intermediate 1. Map
position to objective through the device table's `nosepiece` element, the
same lookup `operator.resolve_limits` already does for the clearance floor;
do not build a second mapping.

**If the pair the goal names is not in A6's `allowed_set`, refuse.** A
person's choice does not override an axis: A6 excluded eight pairs on
Nyquist grounds and a goal card naming one of those is an error, not an
instruction. Say which pair and which bound refused it.

## 2. `lock_group` — this is not a tie at all

S5 reports two values and sends it to the person. **A4 did not offer a
menu.** Read its reason:

> Exclusivity on this configuration has to be evaluated per element and
> cannot be evaluated per channel. `stand_ti2e` carries two lock groups at
> once — its optical elements in `optical_path`, the motor stage in `stage`,
> because the piezo rides on the motor stage — so a plan that names the
> channel has not said which lock its command takes. **The constraint is
> therefore on the plan's form: a selector this configuration holds is named
> as an element.**

Both values are true **simultaneously**. Nobody picks one. What the bound
asks is that **the plan name elements rather than the channel**, so each
command's lock is determined by what it names.

**The defect is in how S5 reads an `allowed_set`.** It treats every one as a
menu of alternatives. This one is a statement about shape, and the schema
already has the right carrier — `precondition`, which A4 uses for
`verified_selectors` in the same card.

**Two ways to fix it and they are not equivalent.** Either S5 learns to tell
a menu from a form constraint, or A4 emits this as a `precondition`. **Prefer
the second**: the schema distinguishes them already, so the information
belongs at the point where it is known, and a reader of the A4 card then
sees the difference without inferring it. Whichever you choose, **say in the
commit message why** — and if you change A4, the fan-out is re-derived, which
is the re-pin's territory, so it may be cheaper to do it there.

**Do not make S5 treat a two-value set as satisfiable in general.** That
would let a real tie through silently, which is the failure §4.5.1(c) exists
to prevent.

## What this card does not close

Five fields remain and none is yours: `success_criteria`, `actions`,
`stop_criteria`, `cost`, and `conditions[brightness_window]`. **Four of the
five want one thing — how long to record** — and the fifth wants a target.
Both are with the person. When they land, S5 should write the plan.

**So do not force a plan.** If the two above close and five remain, that is
the correct state and the report is the deliverable.

## Before you commit

```bash
python3 contracts/validate.py
```

`0 failed`, and read the tree the run names with it.

**And re-read this file before committing.** Two cards changed hands today
and the mechanism that failed is not the rule — it is that **a running
session holds the card it read at start.** `010` was reassigned in the tree
at 22:47 and the seat it was taken from committed it at 22:50, having never
seen the edit. Editing a card reaches a session that starts afterwards and
nothing else. The cheap guard is to look again at the end.
