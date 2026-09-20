# 021 — the objective ceiling is a lookup, and the store holds the values

status: open · issued 2026-09-20 by manager-librarian · **ruling from the person**

## THE RULING

The person wrote `objective_clearance_min = 130 µm` into
`microscope_agent/envelope/safety.json` this morning and was then asked what it
is for. Their answer:

> Rising from the sample's bottom surface up to the working distance is fine,
> and beyond that it should not rise.

Asked whether that is one guard or two, they ruled **both**, and asked for the
names to be split.

**They are two guards because they catch different events:**

| | binds | when |
|---|---|---|
| a constant backstop | once, whatever lens is in | only when something has already gone wrong |
| the focus ceiling | at the working distance of the lens in use | **in ordinary operation, every time** |

One number cannot be both. The six objectives run **20 mm to 130 µm, a factor
of 150**:

```
4X       20000 um        40X WI    160-200 um
10X       4000           60X Oil       150
20X        800           100X Oil      130
```

`130 µm` is the 100× Oil's working distance. As a backstop it is sound for all
six — the 4× focuses 20 mm away and never approaches it. As a focus ceiling it
is right for one lens out of six.

## What is already done, and what is yours

**`contracts/schemas/envelope_safety.schema.json` now takes a lookup-shaped
limit** (this seat, this commit). A limit is **either** a constant
(`value`+`unit`) **or** a `resolved_from` naming the quantity and what keys it
— never both, never neither, and `confirmation` required either way. Verified
by construction six ways.

**This does not move knowledge into `envelope/safety`.** §10.3 rule 4 stands:
the person writes the **policy** — that focus is the ceiling — which is a
decision only they can make. The **numbers** stay here as graded vendor facts
and resolve at preflight. Nothing crosses; the limit says where to look rather
than copying what is found, which is the same reason an envelope holds a
snapshot rather than the store.

## TASK

1. **Make `working_distance` resolvable by the objective in use.** The store
   already holds it per part number, and 009 made `identifiers.part_number`
   addressable precisely so a lens could be named without inventing a device
   id. Check that a preflight can get from *"MRD71970 is in position"* to
   *"130 µm"* with what exists, and say what is missing if it cannot.
2. **The 40× WI answers with a range, not a point** — `working_distance_min`
   0.16 mm and `working_distance_max` 0.2 mm, because a correction collar moves
   it. A ceiling resolved against a range is a different question from one
   resolved against a point, and it is **not this seat's to decide which end
   binds**. Say what the store can honestly supply and leave the choice.
3. Record what the reference plane is, if the catalogue says. See below — it is
   not needed for the ceiling, and it is needed for anything that computes an
   absolute Z.

## What I got wrong, so the file does not repeat it

I argued at length that the ceiling could not be written until the store
recorded **what the working distance is measured from** — front element to the
coverslip surface, or to the sample plane. The person's answer: *either way it
is all working distance.*

**They are right and the argument was over-built.** A lens is at its working
distance when it is in focus, by definition. *Do not pass the working distance*
means *do not pass focus*, and that holds whichever surface the catalogue
measured from. The convention would matter to something computing an absolute
Z in stage coordinates from the coverslip geometry; it does not matter to the
rule.

**One arithmetic from it is still worth keeping**, as a fact and not as a
blocker: three objectives have a working distance **shorter than the 170 µm
coverslip in use** — 60× Oil at 150, 100× Oil at 130, 40× WI from 160. If the
catalogue measured to the sample plane, focusing those lenses would put the
front element inside the glass. So the catalogue measures to the coverslip
surface. That is an inference from two facts the store already holds, not a
reading of any document, and it should be recorded as an inference or not at
all.

## CONSTRAINTS

- `envelope/safety.json` is the person's file and **no seat may write it**
  (§2.1 rule 7, §6.1). Nothing in this task edits it. What you produce is the
  resolution path the policy points at.
- Do not put a working distance into `envelope/`. The limit names the quantity;
  the value stays here.
- The backstop keeps its single number and is not yours.

## REPORT

Whether a preflight can resolve part number → working distance with what is on
disk today, and what the 40× range does to that. Then the one thing I expect to
be missing: **nothing has confirmed that the catalogue working distance is
where these lenses actually focus on this bench.** The schema can now say
`carried_over` for that, and until someone checks, that is the honest value.
