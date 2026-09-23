# 026 — first focus in two stages, and what that decision costs

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**The design is the autofocus seat's. I hold the pen only** — that seat
cannot write `tasks/**`, so the judgement below is theirs and the wording is
mine. Where I checked something myself I say so.

**Not assigned.** The person settled two-stage; **§3 makes card 023's items
1 and 2 preconditions**, so this cannot start before they land. Held here
the way 018 is held, and the seat that takes it is the one the person seats
for autofocus — **read your row in `contracts/seats.json` before acting.**

## The scope is narrower than "autofocus"

**Jev is for the FIRST find on an arbitrary mounted sample.** Not focus
hold, not the measurement loop. And Jev has no vision, so the FFT and the
intensity extraction stay deterministic Python; Jev reads the curve.

## 1. The target is the glass interface, not the sample

**An arbitrary sample has nothing in common with the next one** — it may be
fluorescent, it may be phase. **The glass/water interface is there whatever
was mounted.** So: find the interface, then enter the sample by a known
offset.

**What crosses between stages is not "focus" — it is the interface's
absolute encoder Z.** The coverslip does not move when the objective does,
so stage two is not re-finding a surface; it is correcting the parfocality
residual. **A quantity independent of the sample is what makes "arbitrary
sample" hold.**

**Transmitted brightfield** for stage one: assumes no label, bleaches
nothing that has not been measured yet, and works on anything with
refractive contrast. A fluorescent first-find bleaches before the
measurement; confocal sectioning cuts the signal and waits on disk spin-up.

## 2. The sequence

```
1. retract                     (smaller Z -- z_retract_direction_is_measured, E3)
2. 4x or 10x, dry, brightfield, coarse scan to the interface, one-way approach
3. Jev #1  -> verdict + frame  -> encoder Z = the interface
4. full retract
5. ---- PERSON: apply immersion (and rotate) ----
6. target objective, WALK UP from retract toward the handed-over Z,
   clearance comparison live at every step
7. Jev #2  -> fine verdict + how far the handed-over Z missed
```

**Step 6 is the one to read twice: the handed-over Z is a TARGET, not a
destination.** No direct jump. Walk from retract so the limit comparison
stays live — **if the parfocality residual exceeds the margin, a jump is a
collision.**

## 3. This decision made 023 a precondition, and one-stage did not

**A one-stage find has no turret rotation. Two-stage has one, necessarily,
in the middle.** So `nosepiece_write_runs_no_escape` is now on this design's
path, and if the incoming lens is the 100× at 0.13 mm, that is the
collision. **Step 4's full retract is the only defence until 023 item 1
stands.**

**And step 6 exists only on top of 023 item 2.** Without a comparison that
can refuse, a walking approach is a walk with nothing watching. **This card
is unissuable until both land.**

Two more that come with the rotation:

- **PFS off across the change, re-acquired after** (§2.1 interlock 3) —
  card 025
- **`objective_change_invalidates_trap_calibration`** → an **ordering
  rule**: first find, *then* trap calibration. The other order does it twice

## 4. A person stands in the middle, and that is a manual sheet

**Every stage-one lens is dry** (4×, 10×, 20× are air) **and every target is
oil or water.** Applying immersion is not an automated action and has no
read-back. §4.6.6 rule 5 and §6.1: **a manual instruction sheet and an
individual approval**, and while the sheet is open this session issues no
automatic command to that device group.

**So the first find is not one button. It is a procedure a person touches
once.** Once per mount is acceptable; the card has to say so rather than
let someone discover it.

## 5. The 40× WI: the collar is fixed and the number is still missing

The person fixed the collar at **0.17 mm** today, matching
`coverslip_thickness_in_use` 170 µm, so the entry's condition is satisfied.

**I checked the store and the working distance is still 0.16 and 0.20, both
E3, with no value at 0.17.** The catalogue range spans the whole collar
travel and the librarian does not interpolate. **Picking an end is wrong
both ways**: at 0.20 when the truth is 0.16 you stop **40 µm short of
focus**; at 0.16 when it is 0.20 you go **40 µm past, into the glass.** At
40× water, 40 µm is entirely out of focus.

So:

- **preflight resolves by part number (`MRD77400`), not by name** — keyed by
  name, this lens alone gets nothing and the absence looks like a lookup
  that never ran
- **any path targeting the 40× WI is unissuable** until that measurement
- **making the first two-stage target the 100× oil** (0.13, a single value)
  avoids this item entirely
- the collar is a **manual selector with no read-back**, so it is not a
  verified state: the card carries it as a condition and the session
  confirms it by eye at start

## 6. The band differs per stage, and it is one derivation

`objective_change_selects_a_pixel_size_row`: 4× and 100× have different
sample-plane pixel sizes, so the **FFT band differs**. That must be **one
derivation with different inputs, not two sets of constants.**

**And the sample is arbitrary, so the high cutoff cannot come from a
particle size nobody knows.** The band comes from the optics: the top from
the diffraction cutoff and Nyquist, the bottom a fixed block against
illumination non-uniformity. **Pixel size is still an open gap and still
must not be derived.**

## 7. The stage-one lens is not a choice — the bench returns it

4× is safest (WD 20 mm) and its low NA makes the interface peak axially
broad (~λ/NA²). 20× is sharper and its 0.8 mm WD spends the safety margin.
The deciding inequality:

```
stage-2 search range  >=  max(stage-1 focus uncertainty,
                              parfocality residual,
                              coverslip tilt)  +  margin
```

**If that range exceeds the target lens's clearance headroom, two stages
cannot get there safely and the answer is three: 4× → 20× → 100×.** At
0.13 mm it may well be tight. **Two of those terms are unmeasured, so the
stage-one lens is a bench output and not a decision.**

## 8. Refusal conditions, each with its own name

**An arbitrary sample fails in kinds that need different actions, so they
may not be one error.**

| | |
|---|---|
| **no immersion** | never focuses. Detectable as metric-magnitude collapse. **The most common failure on an arbitrary mount** |
| **slide upside down** | the target is outside the working distance. **Refuse, do not search forever** |
| **empty field** | distinct from out-of-range: the action is an XY move, not a Z rescan |
| **out of range** | Jev returns the direction too |
| **travel and time ceilings** | a failed first find ends rather than crawls |

## 9. Jev's place, and five limits

- **The output is a verdict, a frame and a next action — not a Z.** The
  value comes from that frame's encoder reading (§4.6.9). **A
  model-produced number is E6 and enters nothing**
- **It is not in any safety decision (P0).** The clearance comparison is
  Python with Jev or without it
- **A calibrated probability is a self-reported grade**, and §5.3 does not
  take one. **It counts here when the calibration is measured here** — and
  the bare-particle pre-measurement hands over labelled data with encoder
  ground truth, free
- **It is early access, queued** — the same position the librarian was in,
  so the same pattern: `degraded: ["jev"]`, and **a deterministic fallback
  that stands FIRST** (simple maximum plus a prominence threshold). **A path
  nobody walks breaks quietly**, which is why §9.1 made one degraded pass a
  completion condition
- **The abstention threshold is a §11-2 UNDECIDED** — no default may be
  used quietly before the person picks one
- **Calling an external service is the person's decision and is not
  approved.** The design stands; the call does not

## 10. It closes something on the owed list

**Identifying the interface by encoder closes "working height above the
coverslip"** — the owed item in `CLAUDE.md`. A7's wall correction is waiting
on it: **the +16% is true only at 10 µm** and nothing has said what the
height is. Note it when it lands, with a source and a grade.

## Done when

Nothing here can be done until 023 items 1 and 2 land. When they do:

```bash
python3 contracts/validate.py
```

`0 failed`, **and read the tree the run names with it.** A design document
in `questions/` or a plan that S5 will refuse for the reasons above is both
acceptable output — **what is not acceptable is a plan that issues without
them.**
