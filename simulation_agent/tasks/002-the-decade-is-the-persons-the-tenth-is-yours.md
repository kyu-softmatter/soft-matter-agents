# 002 — move the target inline, and keep the axis's margin beside it

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).

**Startable now.** This card said *do not start* until 2026-09-19 and the two
things it was waiting on have landed. Both halves of that wait are gone, and
the rest of this card is the procedure.

`goal.schema.json` now carries the inline target, and its `$comment` on the
superseded branch names **this agent's `goal.json`** as one of exactly two
cards keeping that branch alive. So this is not tidying: a shape the contract
wants deleted stays in the schema until this card moves.

## What the contract decided

A target is a **decision**, so it carries no source and no grade — the same
reason a ceiling in `envelope/safety.json` carries none. A grade says how far a
claim can be trusted; a decision is correct by being made, and grading a
person's own goal E5 says they might be misremembering what they want.

It is **inline rather than by reference** so that a grade is not merely absent
but *inexpressible*. `common.schema.json#/$defs/target` is `{metric, kind,
value, unit}` with an optional `note` and `additionalProperties: false`. That
last word is the mechanism: §2.1 rule 9 — an opt-in guard is not a chokepoint.

A `decision:` source kind was proposed and **rejected**, because `SOURCE_GRADE`
is a function from source to grade and a source yielding no grade punches a
hole in P2.

## Why this card may move when an approved one may not

`3646fb7` found the wall: a card pinned by a signed `plan_approval` can neither
gain nor lose a field (§5.5), so the `plan_hash` moves and the approval stops
covering it. **That is not should-not, it is cannot** — short of asking a
person to re-approve work they already approved. So the contract migrates
forward: new cards inline, pinned cards keep the legacy form while their
approval stands.

**Checked, and this card is on the free side of that wall**:
`sim-20260917-001/goal.json` has `approval_id: null` and `status: VALIDATED`.
Nothing pins it. The plan card beside it is the one to check the same way
before touching — do not take this paragraph as covering it.

## The four places, and the one that is a judgement

1. **`goal.json` → `targets[]`.** `{"metric": "tracer_diffusivity", "number":
   "target_decade_resolution", "kind": "decade_resolution"}` becomes
   `{"metric": "tracer_diffusivity", "kind": "decade_resolution", "value": 1,
   "unit": "count"}`, carrying the existing note.
2. **`plan_simulation_sim-20260917-001.json`** carries its own copy — pinned,
   not referenced, because a `plan_approval` fixes the plan and not the goal.
   Check 52 compares the copy against the goal's.
3. **`plan_simulation_sim-20260917-001.md`** is generated (P3). Regenerate; do
   not hand-edit.
4. **`src/plan_card.py`** names `target_decade_resolution` as a literal in four
   places. Fix the code before the data, for the reason `003` gives at length.

**The judgement is `a_target`, and it is the interesting part.** Its statement
is *"Screening accuracy is one decade"* and its falsifier is *"a question
needing the coefficient rather than its decade restates this target and
switches the intent to confirm."*

Read that falsifier again. It does not say what observation would show the
assumption **false**. It says when somebody would **change their mind**. That
is not an assumption with a weak falsifier; it is a decision that had nowhere
else to live, so it was dressed as an assumption because `assumptions[]` was
the only container that would take it. Now there is a container. When the
target moves inline, `a_target` and `target_decade_resolution` should go with
it — but check what still cites them first, and say what you found.

A success criterion that compared against this number now has `target:
<metric>` as its alternative to `number`; check 6 resolves either, so the
guarantee moved containers rather than being dropped.

## Do not delete the `0.1`

`axis_bd_overdamped_a2.json` carries `target_relative_error = 0.1`,
`assumed:a_statistics`, E5, noted *"ten per cent, which is well inside the one
decade the goal asks for"*. That note puts **two facts in one number**: the
decade is the person's goal, the ten per cent is this axis's own tightening.

The tempting edit, once the person's target is properly recorded, is to replace
the axis's number with the person's because one is more authoritative. That
collapses the fact that costs money. **`0.1` stays, as the axis's margin, and
it stays an assumption** — unlike the target, it *is* one, and a falsifier can
be written for it.

Statistical error goes as `1/sqrt(N)`, so sampling goes as `1/ε²`: ten per cent
against thirty is **nine times the sampling**. It is free today only because A5
says this job is far too small for the budget axis to bind. **Record why it is
free, not just that it is.** The day a real budget exists, a `0.1` chosen while
no target existed at all is where the compute goes, and by then nobody will
know it was never examined.

## One thing still open, and it does not block this

§11-14 — recording in `plan.md` that *the person decided one decade* — is still
open, because the answer reached the architecture seat through another seat's
user and §6.2.2 does not let a relayed answer stand as the person's. **That is
about the record, not about the shape.** The contract's ruling that a target
carries no grade holds for every target, confirmed or not, and the value here
does not change: `1 count`, `decade_resolution`, exactly as it reads today. So
nothing in this card waits on §11-14.
