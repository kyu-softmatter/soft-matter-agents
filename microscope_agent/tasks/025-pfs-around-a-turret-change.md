# 025 — the plan never releases PFS, and §2.1 requires it

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Assigned to `microscope-1`**, who found it while doing 023 and asked for
the card. Small, and it is the second P0 gap in the same plan — **023 did
not name it and should have.**

## What is missing

§2.1: **PFS is disabled across turret and path changes, and re-acquired
after.** The plan rotates the nosepiece and carries no such action:

```
act_set_nosepiece_position
act_set_intermediate_magnification
act_acquire
```

**Unlike the retract, this one can be written today.** `pfs` is an element
of `stand_ti2e` in the registry, so an action can name it and check 38 will
accept it. The retract cannot be written because the registry has no focus
element — that is with the librarian and is not this card.

## What to write

**Release before, re-acquire after, and verify both.** `stand_ti2e` is
`read_back: true`, so both are verifiable and neither may be assumed —
**the same rule the turret interlock already applies.** A `verification:
none` on a channel that can answer is a claim this plan is not entitled to.

**And re-acquiring is not the same as confirming it re-acquired.** Issue,
read, compare. If the read says it did not, that is a refusal and not a
retry.

**Order it against the interlock rather than beside it.** The release has
to precede the rotation the interlock guards, so `check_turret_rotation_allowed`
should be the thing that knows PFS is released — otherwise two mechanisms
each hold half of one rule and the second is free to drift.

## The sign is unmeasured, and that bounds what this card may do

`pfs_offset_sign_unmeasured` is an open gap and the store is blunt about
what it is:

> a collision device alongside the Z drive and the nosepiece, and **the one
> remaining direction on one that has never been measured. A direction
> written into a configuration without being measured reads as verified.**

**So release and re-acquire only. Do not command an offset.** Releasing does
not need the sign; moving by an offset does. Anything that needs the sign
waits for the bench — card 018 §6d.

If the re-acquire needs a target offset to be meaningful, **say so and stop**
rather than choosing one. That would be a fourth thing the plan needs and it
is the person's, not this seat's.

## Two things this card does not ask for

**Not the retract.** No focus element exists to name, and inventing one is
refused by check 38. Your interlock already looks it up from the registry
rather than hardcoding, so the day that row lands the retract passes without
touching your code — that is the right shape and it stays.

**Not the `bounds` field's consumer.** I added `bounds` to `$defs/limit`
this morning at your request, so the direction a limit binds is now readable
instead of hand-mapped. **It is optional**, because requiring it would
refuse the person's existing envelope. When you read it, **say in the code
when you are falling back to the suffix**, so the fallback is visible rather
than assumed — that is the whole reason the field exists.

## Done when

```bash
python3 contracts/validate.py
python3 microscope_agent/src/plan_card.py --qid mic-20260920-001
```

`0 failed`, and **read the tree the run names with it** — a run right now
shows one failure that is the simulation side's.

A third mock run. **Report what it refuses on**: if the turret interlock now
refuses for the focus element and PFS both, say both, because the count of
reasons is the progress.

**Re-read this card immediately before committing.**
