# 030 — the planner keeps its own copy of the retract hints

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Assigned to `microscope-1`.** Found by probing for the shape §2.1's new rule
names, after architecture ruled it (`0746bfb`).

**The inventory of four was an inventory of `orchestrator.py`.** `plan_card.py`
decides the same things again, on its own, and nobody counted it.

## What is actually there

```python
# orchestrator.py:443   the interlock
RETRACT_HINTS = ("focus", "z_drive", "z_axis", "objective_z", "z")

# plan_card.py:588      the planner, written out inline
retract = next((e for e in ("z_drive", "focus", "z_axis", "objective_z", "z")
                if e in elements), None)
```

**Two lists, two files, same five members, different order.** And
`"pfs" in elements` at `plan_card.py:584` and `:630` is `STABILISER = "pfs"`
again, and `"nosepiece"` is hardcoded at `:83` and `:389`.

## Why the duplication is worse than either copy

**Identical today is the dangerous state, not the safe one.** Nothing compares
them, so the first edit to one is silent drift — and the edit is coming: the
`role` field lands and somebody fixes the interlock. **If only
`orchestrator.py` is migrated, the planner still guesses**, and the plan it
emits names an element the interlock then approves on different grounds.

**And the two do not even select the same way.** `next(...)` returns the
FIRST match in the planner's order; `retract_elements()` returns `sorted()`
of every match. With both `z_drive` and `focus` in the registry the planner
picks `z_drive` and the interlock sees two. Same data, different semantics,
and the difference is invisible while only one element matches.

## What §2.1 now says, and which half this is

> **An enumerated field is compared by equality; an identifier is never
> tested by substring.**

`"pfs" in elements` is membership in a list of ids, so it is **equality, not
substring** — the second clause does not reach it. What it breaks is the
first: it decides a device's role without an enumerated field to compare
against. **So do not read this card as four more substring bugs.** Three
shapes are in play and only one of them is the substring one:

| shape | where | the rule it breaks |
|---|---|---|
| `"shutter" in element_id` | `orchestrator.py:404` | substring on an identifier |
| `"pfs" in elements`, `e == "nosepiece"` | both files | role decided without a declared field |
| a hint tuple, written twice | both files | the above, and no single source |

## What to do, and what not to

**Not now**: do not unify the two lists by importing one from the other. That
makes the wrong thing shared instead of removing it, and you would then
migrate a shared wrong thing. The tuple's whole future is deletion.

**Now**: one line where each copy lives, saying the other exists and that
both die with the `role` field. A comment is a poor guard and it is the
honest one here — **nothing at commit time can compare two literals in two
files**, and the next reader of either file currently has no way to learn
that the other exists.

**When `role` lands**: both sites read it, and the migration is not done when
the interlock passes. **It is done when `plan_card.py` has no device name in
it.** `grep -nE '"(pfs|nosepiece|z_drive|focus)"' microscope_agent/src/plan_card.py`
returning nothing is the test.

## REPORT

Whether `plan_card.py` has anything else deciding a role by identifier that
my probe's shapes would not catch — it looks for substring, `startswith`,
`endswith` and membership, and **equality against a bare literal is a shape I
did not search for** beyond the two `"nosepiece"` lines I happened to see.

And whether `screening.py` or the axis modules do the same. I probed
`microscope_agent/src/` as a whole and read only what matched; I did not read
those files.
