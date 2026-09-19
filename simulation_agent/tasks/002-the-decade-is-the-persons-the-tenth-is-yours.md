# 002 — keep the person's target and the axis's margin as two facts

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).

**Do not start this yet.** It is carded now so that it is on disk rather than
in a chat window, which is the whole reason this directory exists. Two things
have to land first and neither is yours. What you can do today is read it and
not do the tempting thing.

## The thing not to do

`axis_bd_overdamped_a2.json` carries `target_relative_error = 0.1`,
`assumed:a_statistics`, E5, with the note *"ten per cent, which is well inside
the one decade the goal asks for"*.

That note is the important sentence in the card, because it puts **two
different facts in one number**:

- **one decade** is what the person wants — placing the value within a factor
  of ten answers the question
- **ten per cent** is this axis's own tightening, chosen by A2

When the person's target is recorded properly, **do not delete the `0.1`.**
The tempting edit is to replace the axis's number with the person's, since one
is "more authoritative". That collapses two facts into one and loses the one
that costs money.

## Why it costs money, which is the part worth keeping

Statistical error goes as `1/sqrt(N)`, so sampling goes as `1/ε²`. Ten per cent
against thirty per cent is **nine times the sampling**. The margin is not a
rounding-down of the target; it is a decision to spend nine times as much.

It is free today, and that is the trap. A5 says this job is far too small for
the budget axis to bind, so nothing refuses the `0.1` and nothing draws
attention to it. **Record why it is free, not just that it is** — the day a
real budget exists, an unexamined `0.1` chosen while no target existed at all
is where the compute goes, and by then nobody will know it was never examined.

## What has to land first, and neither is this seat's

**The person's answer has to reach the architecture seat directly.** It arrived
through another seat's user, and architecture will not write *the person
decided* into `plan.md` on a relayed answer — §6.2.2, the same rule that says a
tier assignment cannot be relayed. §11-14 stays open until then. Do not treat
this card as the answer having landed.

**And the schema cannot express the target yet.** Architecture ruled the shape:
a person's target rides on the card with **neither source nor grade**, the way
`envelope/safety.json` carries a ceiling — a policy is a decision, not a claim
about the world. A `decision:` source kind was proposed and **rejected**,
because `SOURCE_GRADE` is a function from source to grade and a source that
yields no grade punches a hole in P2.

The gap is that `goal.schema.json`'s `targets[]` is `{metric, number, kind}`
where `number` names an entry in `numbers[]` — and a `numbers[]` entry is
four-part by P2, so source and grade are required. **The only slot a target has
today guarantees the thing the ruling forbids.** An inline form is with
architecture. `manager-bridge` found this after sending the opposite advice and
corrected it inside the hour; the correction is the useful half.

## What is already true, so do not redo it

`goal.json` already carries `target_decade_resolution = 1 count`,
`assumed:a_target`, E5, noted *"one decade is enough: the question is whether
the engine reproduces the free value at all"*. **The person's answer confirms
that assumption rather than supplying a new number.** So when this lands,
**nothing numeric moves in any card.** What changes is that the person's goal
stops being recorded as this agent's assumption — which is the whole point:
`assumed:` says we guessed, and we did not guess, we asked.

## When you do it

It is a revision, not a patch (§4.5.5). The cards of `sim-20260917-001` are
`revision: 1` and stay there; a target changing what the question is asking is
revision 2's business, alongside the librarian run. Revision 2 may cite
revision 1 as a record and may not take it as input.
