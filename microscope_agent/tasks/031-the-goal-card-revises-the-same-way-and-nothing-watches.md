# 031 — the goal card revises the same way, and nothing watches

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Assigned to `microscope-1`**, who found it answering 029 and offered to do
it. **This is the `displace()` half only** — the checking half is architecture's
to place and mine to implement, and it is not a precondition for this.

## Measured

```
goal.json                      goal-mic-20260920-001-r7, revision 7
the six before it              in no tree
plan r5 and displaced r4       both pin goal-...-r7
grep -n "goal_id" validate.py  0
```

**Nothing dangles today** because both plans happen to pin the current
revision. **That is luck, not design** — the next goal revision orphans every
plan pinning r7, exactly as plan revisions orphaned three run logs.

**And this one is quieter than that was.** Check 66 at least said *not in this
tree*. Here no check reads `goal_id` at all, so there is no line, no PENDING,
and not even a LOST to reach. Two schemas require the field and nothing
resolves it.

## Do

**The `displace()` you already wrote, applied to `goal.json`.** Same rules,
and they were the right ones:

- displaced copy takes `v<N>_`, the live path keeps its name, so no consumer
  changes
- **refuse rather than overwrite** an existing `v<N>_` whose bytes differ —
  two bodies under one name rebuilds the defect next door
- identical bytes are left alone and said so

## Done when

**Not a description. Two numbers, the way 029 was measured:**

1. Revise the goal once and see `v7_goal.json` appear holding the r7 bytes,
   with `goal.json` at r8.
2. **And the part 029 did not have to worry about**: every plan on disk still
   pins a goal id that resolves. r5 and the displaced r4 both pin r7 — after
   the revision, r7 must still be *findable*, which is what the displaced
   copy is for. Say which file each of them resolves through.

**Do not repin the plans.** A plan pinned r7 and was built against r7; moving
it to r8 would make the plan claim a goal it never read. The displaced copy
exists so that the old pin stays true.

## Not in this card

**Do not build the check.** Where `goal_id` resolution lives — a new number
or an extension of check 73 — is with architecture, and I implement it when
they rule. If you build a resolver here it lands twice.

## On your name-probe

**I reproduced it independently and it holds** — `operator.py`'s bare-literal
equality, `orchestrator.py`'s two, `plan_card.py:694`'s literal selector set.
All three are there.

**One difference worth having**: my id set was 38 and yours was 30, because I
took every `id` in the tables and you took channels and elements. The extra
eight are optical paths, and they produce exactly one more hit —
`axis_a1_snr.py:186`, `path == "confocal"`. **That one is the rule being kept,
not broken**: a path is an enumerated value and equality is what §2.1 now
asks for. So **your zero for the axis modules stands for the question you
asked**, and my thirty-eight answered a slightly different one.

That is the same thing that bit me yesterday from the other side, when I told
architecture "four" after reading one file. **Both errors are the denominator
and only one of them shows up as a wrong number.**
