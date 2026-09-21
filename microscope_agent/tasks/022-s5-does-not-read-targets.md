# 022 — S5 never reads `targets[]`, and its criterion is one question's

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Assigned to the seat holding `020`/`021`.** This is the last of S5's five
that is not waiting on a person, and it is two defects in one place.

## What S5 actually does

```python
# plan_card.py:327
target = next((n for n in goal.get("numbers") or []
               if n.get("name") == "target_decade_resolution"), None)
```

**It reads `goal["numbers"]` and looks for one literal name.** It never
reads `goal["targets"]`. The one place that mentions `targets` uses the old
reference shape:

```python
# plan_card.py:242
named_by_target = {t.get("number") for t in goal.get("targets", []) or []}
```

So when S5 says *"the goal card carries no target to compare against"*, the
statement is **false about the card in front of it** — `mic-20260920-001`'s
goal carries two targets, at revision 4, with their reasoning written out.

## The contract moved and the reader did not

`common.schema.json`'s `$defs/target` is explicit about why:

> **Inline rather than by reference into `numbers[]`, so a grade is not
> merely absent but inexpressible**: an opt-in guard is not a chokepoint
> (§2.1 rule 9). A target is a DECISION and carries no source and no grade
> — a grade says how far a claim can be trusted, and **a decision is correct
> by being made.**

And check 52 is counting the migration as it runs: *9 targets stated as
decisions, 4 carried unchanged, **4 still by reference while the migration
runs***. The old `mic-20260918-001` goal is one of the four; the
pre-measurement's is in the new shape and **correct**. S5 can only see the
old one.

**This is the same shape `manager-simulation` fixed in check 6 this
morning** — the contract says `target:`, the reader implemented half — and
they named it before I found it here. Worth saying because it means the
migration has at least two readers behind it and there may be more.

## The second defect, which a shape fix alone leaves

```python
success.append({"id": "ok_decade", "metric": "diffusivity_decades_resolved",
                "comparator": ">=", "number": "target_decade_resolution",
                "statement": "the diffusivity is placed within one decade"})
```

**The criterion is hardcoded to one question.** Metric, statement and the
number's name are all `mic-20260918-001`'s diffusivity. This question's
targets are `tracer_brightness` and `bleaching_rate`, so even after S5 reads
`targets[]`, it would emit a criterion about a quantity this run does not
measure — **and it would pass check 6, because check 6 recomputes a verdict
against its own stated criterion and does not ask whether the criterion is
about the right thing.**

So: **build one criterion per target, from the target.** `metric` comes from
the target's `metric`, and the statement is generated rather than written.

## What a target is, and what that forbids

A target is inline and carries **no source and no grade**. So:

- **Do not copy it into `numbers[]`** to make `conditions` point at it.
  That is the shape the contract just left, and it would make a grade
  expressible again on something that must not have one.
- **Carry it unchanged.** §5.2 and check 52: the plan pins the goal's target
  rather than referencing it, for the same reason `kb_version` is pinned —
  an approval fixes the plan and not the goal, so a pin that resolves to
  whatever the goal says now is not a pin.
- **Do not invent a target for `bleaching_rate` if the goal states one** —
  it does, both at `decade_resolution 1`, and the goal's note says why each.

## Done when

```bash
python3 microscope_agent/src/plan_card.py --qid mic-20260920-001
python3 contracts/validate.py
```

`success_criteria` leaves the unfillable list, and the count drops from five
to four. **Read the count off the run.** The remaining four wait on the
record length from card `021` and on the window, and they are not yours to
force.

Check 52 should still pass and should say **one fewer by reference** once the
plan carries its targets in the new shape.

**Re-read this card immediately before committing** — cards changed hands
twice on 2026-09-20 and a running session holds the copy it started with.
