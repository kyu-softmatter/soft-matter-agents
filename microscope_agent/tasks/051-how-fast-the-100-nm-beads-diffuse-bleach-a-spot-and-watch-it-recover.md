# 051 — how fast the 100 nm beads diffuse: bleach a spot and watch it recover (design only)

Written by `manager-microscope-kyuhwan-macbook-20260930-2`. You read this; you
do not edit it.

**Assigned to `microscope-kyuhwan-macbook-20260930-2`**, the MacBook window
titled 현미경 실행석 2, rooted at `microscope_agent/`. Your row has been in
`contracts/seats.json` since `a3abad6`. If you are not that seat, take nothing
from this card and report up.

## The question, the person's

The person asked this in architecture's window on 2026-09-30. The English
below is architecture's rendering, sent to this seat by message:

> "Can you check how fast our 100 nm fluorescent beads diffuse? Maybe bleach
> a round spot and watch it come back. Simulate it too."

Then: "simulation first", then "and experiment design together". The
simulation side has the matching instruction from its own manager. **This
card is the experiment's half: the design, now, on this Mac. The run comes
later, on the microscope computer.**

Open it as a new question, `questions/mic-20260930-001/`, starting with a
`goal.json` at S2. Then go through S3.0 to S5, which ends in a plan the
person can approve.

## What the design has to settle

1. **How a round spot is bleached on this instrument.** The confocal is a
   spinning disk, so its laser covers the field, not a spot. Find out from
   `contracts/capabilities/microscope.json` and the store which device or
   path can confine light to a disc of a chosen radius. If none can, say so
   and stop that branch. Do not improvise one.
2. **Spot radius, bleach duration, imaging exposure, frame rate and record
   length**, each with its unit, and each tied to the recovery time it has
   to resolve. Give the bleach and imaging illumination as settings plus
   power at the sample, taken from the store's calibration with its grade.
3. **Bead concentration and chamber.** That means how dilute the suspension
   is and its depth, and the height above the coverslip, because the wall
   slows a bead near the glass. Also cover how the sample is kept from
   drifting and drying for the length of the record.
4. **What is recorded**: the frames, the pre-bleach frames, the bleach
   timing, and a region far from the spot that sees the same imaging light.
   That region separates bleaching caused by imaging from the recovery.
5. **How D is read off the recovery curve**: normalisation, the model fitted,
   and what range of D the fit can actually tell apart. This method is not
   in the vocabulary yet (see below).
6. **The fallback, single-bead tracking**, for a suspension too sparse to
   bleach as a field. When does the design switch to it, and with what
   settings? Tracking already has a registered estimator,
   `tracer_diffusivity` (the slope of mean squared displacement), so this
   branch needs no new vocabulary.

Explore mode applies: targets in decades, differences under 10x are ties,
and a value computed from an estimate is an order of magnitude.

## What is already on record, and what is not

- **Nothing in the store or in this tree mentions these 100 nm beads.** Their
  product, dye, stock concentration, brightness and bleaching rate are
  unknown here. A 100 nm bead is also below this instrument's resolution,
  as `questions/mic-20260918-001/goal.json` recorded, so a bead is a spot
  you can locate but not resolve.
- **Brightness and bleaching rate close by acquiring, not by asking**. This
  is the section of that name in `microscope_agent/CLAUDE.md`. A short run of
  bare beads on the coverslip under the planned light gives both. Name that
  pre-measurement in the plan as the remedy for those two gaps.
- **Facts only the person holds** are the bead product and dye, the stock
  concentration and the planned dilution. You may ask for them, and you
  should log each question and its answer. The dilution factor is already on
  the operator's list in your `CLAUDE.md` as never asked.
- **Simulation's recovery times.** The expected recovery times arrive as a
  card the bridge carries. Until then the design names them as *awaited* and
  does not guess them. Design without waiting, and say which settings move
  when they arrive.

## Vocabulary: register first, then plan

`tracer_diffusivity`'s estimator is defined as the mean-squared-displacement
slope of single particles. **A D read off a bleach-recovery curve is a
different estimator, so it needs its own vocabulary id**. The rules in
`contracts/observables.json` make the estimator part of the identity. Draft
the entry (id, definition, estimator, window parameter, units,
`producible_by`) in your question folder, and send it to this seat early,
before the rest of the design. **Both sides use one entry.** The simulation
side has to read its predicted curve with the same estimator. Its seat is
proposing an entry too, so the bleach geometry you choose matters to them:
a uniform disc or a Gaussian spot, and a column bleached through the depth
or a 3-D volume. This seat agrees the estimator with the simulation manager,
and **the simulation manager registers the single agreed entry** in
`contracts/observables.json`. Your plan cites it only after it lands. A plan
naming an unregistered observable is held at the bridge. Leave `comparable`
false: it turns true only once the same estimator has run on both sides.

*Added after `5db144a`, the same evening: the earlier text had this seat
registering the entry. The simulation manager asked to agree first and
register once, so that two managers do not register two entries.*

## Safety, which this card does not decide

- **Design only. Open no device.** No laser, no stage, no camera, no DMD.
  This Mac is not the bench.
- **Bleaching power is a safety question and its limit is not yours to
  set.** The only confocal laser limit in `envelope/safety.json` is the
  command voltage, which the person allowed over the whole 0 to 5 V range.
  That is the instrument's range, not a dose chosen for bleaching this
  sample. **State the dose the bleach needs** as power at the sample, time
  and spot area, and put it to the person as a decision. Never write, widen
  or narrow `envelope/safety.json`; it is the person's.
- Every number has four parts and a grade. A number a model makes up enters
  nothing.

## The knowledge route

Instrument facts come **through the librarian's tools** with an issued
`caller_id`, and the answers go into `kb_refs` and `kb_gaps`. That route is
in your `CLAUDE.md`. If the tools are missing, take the degraded path and say
so in `degraded`.

The three closed repositories stay closed.

## What comes back

- **In your tree:** `questions/mic-20260930-001/` with the goal, the axis
  cards and the plan as S5 emits it, plus the draft vocabulary entry.
  **Your validated plan is how the settings reach the simulation.** Once it
  is past DRAFT, the bridge carries it there as a card (bridge card 009).
  Spot sizes, frame intervals, bleach durations and concentrations travel
  that way and **never by chat**, so put every one you are weighing into the
  plan as a range. Validated is not approved: approval is the person's, and
  nothing runs on it. Nothing goes to the librarian from this card.
- **To this seat, by message, at most 10 lines:** the key settings with
  units, what the design is waiting on from the simulation, and what the
  person must decide. This seat relays it to architecture.
- **To the person, in your window:** the same, in plain words with no
  internal codes. For each number, say whether it was measured, computed or
  guessed.

Commit with `git commit -F <file> -- <paths>`, after
`git diff HEAD -- <paths>`. Name new files individually. Use committer name
`seat:microscope-kyuhwan-macbook-20260930-2` and the email from
`contracts/seats.json`. Run the validator and read its tree line.

**Re-read this card immediately before committing.**
