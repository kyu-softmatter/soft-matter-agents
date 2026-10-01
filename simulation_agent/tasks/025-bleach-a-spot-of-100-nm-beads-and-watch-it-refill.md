# 025 — bleach a spot of 100 nm beads and watch it refill: how fast they diffuse, and whether that can be seen

**For:** `simulation-kyuhwan-macbook-20260930-4`, the simulation execution seat
of 2026-09-30. Nobody else takes this card.

Written by `manager-simulation-kyuhwan-macbook-20260930-4`. You read this; you
do not edit it (§6.2-2). Report to me by session message at each checkpoint
below and commit at each one.

## The goal, from the person

The person asked, in architecture's window on 2026-09-30, relayed to me as
work and not as a seating:

> Can you check how fast our 100 nm fluorescent beads diffuse? Maybe bleach a
> round spot and watch it come back. Simulate it too.

and then "simulation first", and "and experiment design together". So this is
a **goal card from a person**: open a new question under `questions/` from it,
with `intent: explore` (§5.8). Answers are in decades, and differences under
10x are ties. The microscope side is designing the experiment **at the same
time**, under `manager-microscope-kyuhwan-macbook-20260930-2`. Nothing you need
from that design reaches you by chat (see "What crosses, and how").

## What is already there, and what is not

- **Configuration:** `bd_overdamped` in `contracts/capabilities/simulation.json`.
  It is 3-D, non-interacting, and its one observable is `tracer_diffusivity`.
  Read its entry whole. Its `output_independent_of_input` is **false**: D is
  fixed analytically by the bead size, viscosity and temperature you give it.
  So `values[]` carries the model's prediction and the run's reading goes beside
  it as the comparison. A run here checks the integrator and the estimator. It
  says nothing independent about the beads, and the card must not read as if it
  did.
- **CORRECTED the same evening: the store holds nothing on these beads.** The
  first version of this bullet said the store holds a datasheet for red
  carboxylate polystyrene beads, so the diameter could be taken from it. That
  was wrong, and it came from the relay. The store's `tracer_*` entries
  (`tracer_diameter_measured`, `tracer_diffusivity_expected` and the rest)
  describe **Abvigen AFR-0500-COOH, measured by the operator at 5 µm**. A 5 µm
  diameter would give a D about 50x too small. So:
  - **Diameter:** the person's stated **100 nm**, labelled as the person's
    nominal value. It is not a stored value and not a measurement.
  - **`kb_gaps`:** record the 100 nm beads as absent from the store. Their
    product, diameter spread, dye and dilution are for the person to supply.
  - **The 5 µm entries** go in `kb_refs` only if you actually use them, and then
    labelled as a different bead. They never stand as this bead's size or D.
  - **Viscosity and temperature:** from the store with your caller_id if it has
    them. Otherwise assumed, labelled assumed, and recorded in `kb_gaps`.
- **No registered observable describes a recovery.** `tracer_diffusivity` is
  defined by its estimator, a weighted MSD fit on single-particle positions.
  D read off a bleach recovery is a **different estimator**, so it needs a
  different id (`contracts/observables.json` rule 2). The vocabulary is never
  finished, and an unregistered name is an ordering, not a refusal. So:
  **propose the entry to me** — id(s), definition, estimator, window parameter
  — and I register it **after agreeing the estimator with the microscope
  manager**, because both sides have to extract the number the same way, or
  the comparison has no visible cause when it disagrees. Start Stage 1 while
  that is in flight. It needs no registered name.

## Stage 1 — what needs no simulation (first, and commit it)

Bleach recovery of non-interacting beads has closed forms. Compute these over
the whole range before simulating anything:

1. **D** from Stokes–Einstein with the store's diameter. State the viscosity
   and temperature you used and where each came from. An assumed value is
   labelled assumed.
2. **The recovery time against spot radius**, in seconds, from about 0.3 to
   10 µm. Name the geometry each formula assumes. **A confocal bleach in a 3-D
   suspension is not a 2-D disc.** It is a column through the sample if the
   bleach beam's depth of focus exceeds the chamber, and roughly an ellipsoid
   if not. These refill at different rates. Give both and say which one the
   microscope design has to tell you.
3. **Feasibility, stated plainly — this is the most important result of the
   card.** Compare the recovery time with:
   - **the frame interval**: how many frames fall inside the recovery at each
     spot size, for frame intervals from about 1 ms to 1 s;
   - **the bleach duration**: beads that wander in during the bleach blunt it.
     Find the longest bleach that still leaves a measurable dip at each spot
     size;
   - **the number of beads in the spot**: at low concentration a micrometre
     spot holds a handful of beads, the recovery curve is counting noise, and
     the measurement turns into something closer to correlation spectroscopy
     than bleach recovery. Give the bead count in the bleached volume against
     concentration (number per volume, or volume fraction) over several decades,
     and the concentration below which one recovery curve cannot resolve D.
4. **Concentration and D.** In the non-interacting model, concentration does
   not enter D at all. State the volume fraction at which interactions would
   move D by a tie-breaking factor (10x). If every concentration the bench
   could plausibly use is far below it, concentration is a signal question and
   not a D question, and the card says so.

If Stage 1 shows the measurement cannot be done as asked (the spot refills
faster than a frame, or faster than any bleach), **say so first and propose
what would make it feasible**: a larger spot, a faster line or point scan, a
more viscous medium, or a different measurement of D. That is a result, and a
more useful one than a simulation of an experiment that cannot be taken.

## Stage 2 — the simulation, where it adds something

Use `bd_overdamped` with many independent beads in a box. At t = 0, mark the
beads inside the bleached volume as dark, then count the bright fraction inside
it over time. Run it at two or three points that Stage 1 marks as feasible or
borderline. Simulation adds three things to the closed forms:

- confirm that the integrator reproduces the closed-form recovery, within
  replicate standard errors, at your timestep (show dt and dt/2);
- **the spread one recovery curve shows** at the bead counts of Stage 1 item 3.
  One bleach gives one curve, so the experiment needs the scatter of the fitted
  D over curves, and not just its mean;
- the effect of a finite bleach duration and a finite frame interval on the
  fitted D. Apply the **proposed recovery estimator** to the simulated curve,
  sampled as a camera would sample it.

Time a smoke point first and write the two-term cost down (task 023). This
machine is the person's MacBook. Keep it modest and say how many cores you
used.

## What crosses, and how

- **Nothing from the microscope design by chat.** Spot sizes, frame rates,
  bleach durations and concentrations the microscope side is weighing reach you
  only as a card the bridge carries. Until one does, use the ranges above as
  **stated assumptions**, labelled assumed, and say what you will re-predict
  once real values arrive.
- **Your result goes to the microscope side the same way:** as a card in
  `questions/`, which the bridge reads and carries. If what you need to send has
  no field in the schema, **tell me** rather than inventing one.
- Architecture sent a back-of-envelope number with the relay, marked "not a
  source and not for any card". I have left it out on purpose. Compute your own.

## Added the same evening: one vocabulary, and the hand-over

- **This seat is the one writer of the recovery observable.** Architecture
  settled that on 2026-09-30. The microscope seat is drafting an entry too
  (`microscope_agent/tasks/051`). I merge the two drafts with
  `manager-microscope-kyuhwan-macbook-20260930-2` and register one id in
  `contracts/observables.json`. I then add it to `bd_overdamped`'s
  observables in `contracts/capabilities/simulation.json`. The microscope
  manager adds only the microscope capability. **Use the name I send you in
  the goal card and in nothing else.** `comparable` stays false until the
  same estimator has run on both sides.
- **The result crosses to the microscope side only when the person hands it
  over.** Commit the result card, then tell me **it is ready for hand-over**.
  Don't tell the bridge. I tell the person.

## Added later the same evening: what the result card must answer

The microscope manager sent me by message the three things its design
waits on. Each one is a result you were already producing. The result card
must answer each by name:

1. **tau against w** over the whole assumed range.
2. **The scatter of fitted D against the number of beads in the disc**, which
   sets the concentration and the number of repeats.
3. **The finite-bleach and finite-frame bias of D_fit/D**, at bleach tau/10 and
   tau/30 and at frame intervals up to tau/5. Edge softness is the third bias
   already in the observable's note.

**Widen the assumed disc range to 0.3–100 µm.** The same message said the
design is weighing discs much larger than this card's 10 µm ceiling. Its
values are a chat number. They enter no card, and the rule against taking
microscope numbers by chat stands. What the message changes is only the
**width of your own assumed range**: up to 100 µm, a decade-level assumption
labelled assumed, so that whatever radius the plan eventually carries falls
inside it. At large discs, say what starts to bind as tau grows: record
length, imaging bleach over the record, drift. The real radii, objective and
brightness arrive only in the microscope plan that the bridge carries, which
is not emitted yet.

## Standing instruction from the person: commit and push when done

The person gave this in architecture's window on 2026-09-30 ("완료시 커밋
푸시", commit and push when done), and it reached me as relayed work. It
applies to you. When a piece of work is finished and `contracts/validate.py`
ends `0 failed`:

1. Commit **only your own paths**. Check `git diff HEAD -- <paths>` first.
   Then run `git commit -F <message file> -- <paths>` under your seat's
   committer identity, and confirm it with `git log -1`. Do not filter the
   commit's output down to FAIL lines: a held `.git/index.lock` prints
   `fatal:`, and the commit is not made.
2. Push. Run `git fetch`, merge if origin moved, then
   `git -c credential.helper=manager push origin main`. **Never force, and
   never `--amend`.**

Unfinished or failing work stays uncommitted. Another seat's paths are never
yours to commit, even when they are what keeps the tree dirty.

## Done when

Stage 1 is committed with feasibility stated first. The observable proposal has
reached me. Stage 2 has run at the points Stage 1 picked, or the card says why
it was not worth running. The result card is committed for the bridge to carry.
Then send me **a report of about ten lines**: D with its unit and where every
input came from (store, computed, or assumed), the recovery time against spot
size, and whether the measurement is feasible as asked, and if not, what would
make it feasible.
