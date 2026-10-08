# 026 — the microscope finds its own focus, so the plane it found is a condition of every comparison

**For:** `simulation-20261007-1`, the simulation execution seat on the Office
computer. Nobody else takes this card.

Written by `manager-simulation-20261007-1`. You read this; you do not edit it
(§6.2-2). Report to me by session message at each checkpoint below and commit
at each one.

## Why this card exists

The person asked this seat on 2026-10-07, in its own window, to find what the
simulation side can do and improve once dino-autofocus's focus search is in the
workflow. `plan.md` §14 is the merge; §11-24 is where the search lives; §13.2 is
the trial that will compare a decision model against the classical metric
maximum. Read all three before starting.

What changes for this side is one thing: **the focal plane stops being an
unrecorded hand setting and becomes an encoder read on the run** -- the plane a
focus search found, with its verdict (`in_focus | step_up | step_down |
no_sample_here | unsure`). Every comparison this agent's predictions enter has
been silently assuming a plane. Once the plane is recorded, that assumption is
checkable, and an unchecked one becomes a defect.

Three places in this agent's own record already depend on it:

- `questions/sim-20260930-401/stage1_closed_forms.md` assumes the bleach is
  **a column through the whole chamber**, refilling by 2-D diffusion, and finds
  that **a soft-edged disc reads D two to four times low and the fit's radius
  check does not catch it** -- naming defocus as the cause and leaving it out of
  the model.
- `stage2_runs.md` lists "drift of the stage and focus" among the things that
  bind on long records and are not in the model, and "no walls" among what the
  model camera leaves out.
- The double-well configurations hold a 5 µm bead in a trap at some height
  above the coverslip, in a bulk-drag model, so every timescale they predict
  (residence time, transition rate) carries a drag the wall changes.

## What this card does not do

- **No focus number goes toward the instrument.** Not a Z target, not a range,
  not a coverslip position, not a limit. The person writes the per-lens limits
  and the upper limit is written, never derived (§11-24, 2026-10-04); a
  coverslip position computed here would be a derived safety number by another
  route. What this card produces are *predictions about the sample and the
  measurement*, which a microscope plan may cite through the store like any
  other graded number, and only after the person hands the result over.
- **No imaging model.** Rendering synthetic defocus stacks to test the focus
  core or §13.2's trial would be a new declared configuration -- a change of
  physical model, which is the person's decision (`What this agent does not do`
  in this agent's `CLAUDE.md`). If your work shows it would be worth having,
  say so in the report as a proposal with its cost. Do not build it.
- **No change to the declared models.** None has walls and none has optics.
  Closed forms and analysis of existing runs only, unless Stage 2 below is
  agreed first.

## The question

Open a new question under `questions/` from the person's request, `intent:
explore` (§5.8): answers in decades, differences under 10x are ties. It asks,
for the two samples this repository has worked on -- the **100 nm fluorescent
beads** of `sim-20260930-401` and the **5 µm beads** of the double well:
*which plane does an observation depend on, how much does a wrong plane move
the answer, and which plane will a sharpness-maximum focus search actually
find?*

Every input comes from the store with its source, or goes on the card as
assumed and names the gap (check 39). Ask the librarian for: each objective's
NA and immersion index, the chamber depth, the bead diameters and densities,
the medium's viscosity and density, the DMD pattern's projection path (which
objective, and whether the pattern is conjugate to the camera's image plane).
**The last one decides item 2 and may well be absent**; if it is, say what the
answer would be under each case and name the gap.

## Stage 1 — closed forms (first, and commit it)

1. **The bleach column is not a column.** A widefield-projected disc is sharp
   only near the focal plane and blurs with distance from it, roughly as
   `|z - z_f| * tan(asin(NA/n))` in geometric optics -- name the approximation
   and where it fails (near focus, diffraction sets the width). Through a
   chamber of depth `L` with the focal plane at `z_f`:
   - the edge width at each depth, and its depth average, per objective and
     disc radius from 1 to 30 µm;
   - feed that average into the soft-edge table already in
     `stage1_closed_forms.md` (D fitted / D against edge softness), and give
     **the D bias per (objective, disc radius, z_f)**;
   - **where to focus for a bleach**: the `z_f` that minimises the bias
     (expect mid-chamber, and check it), and the bias when `z_f` is instead at
     the coverslip;
   - **the focus tolerance**: how far `z_f` may sit from the best plane before
     the bias reaches a factor 2, and before it reaches 10. That is the number
     the microscope's focus-search success criterion for a bleach plan should
     be held against, beside §13.2's depth-of-field fraction.

   If the result is that at high NA the pattern is blurred across most of the
   chamber, so the "column" premise of `sim-20260930-401` fails outright for
   that objective, **say that first**: it is a correction to a committed
   result, and the card names the result it corrects.

2. **Which plane a sharpness maximum will find.** Not by rendering images --
   by counting. For each sample:
   - the bead density profile in z from sedimentation (gravitational length
     `k_B T / (Δρ V g)`; the 401 card already found about 20 mm for the 100 nm
     beads, so they fill the chamber, while 5 µm beads sit within a fraction of
     their own diameter of the coverslip);
   - the number of beads per area inside one depth of field in the bulk,
     against a surface density of beads stuck to the coverslip, which the store
     will not hold -- leave it as a parameter over decades and name the gap;
   - **the conclusion stated plainly**: for the 100 nm suspension, does the
     focus search's metric maximum find the plane the bleach wants (item 1) or
     the coverslip, and above what stuck-bead density does it find the
     coverslip? For the 5 µm beads, is the coverslip plane the particle plane?
     Where two planes compete, say so: the copied core reports a double peak,
     and a sample that produces one by construction is a fact the microscope
     plan's branches should know about before the search runs.

3. **The wall.** The declared models have bulk drag. Give the parallel and
   perpendicular drag corrections against height above a flat wall
   (Faxén near the wall, the method-of-reflections series further out; name
   which formula holds where), and then:
   - for the 100 nm beads, the fraction of a chamber of depth `L` in which D
     is reduced by more than 10 per cent, and whether it moves the
     depth-integrated bleach recovery by more than a tie;
   - for the trapped 5 µm bead, D∥(h)/D₀ over trap heights of a few hundred nm
     to tens of µm, and what it does to `well_residence_time` and
     `interwell_transition_rate`, which scale with the drag. **The bead height
     is the experiment's**: a trap height, or the focus search's plane plus a
     known offset. State the height below which the bulk model's timescales
     are off by a factor 2 and by a factor 10.

4. **Holding focus over the record.** `stage2_runs.md` gives the shortest
   record the bleach fit allows against disc radius. Against item 1's
   tolerance, give the focus drift *rate* that would use up the tolerance over
   that record, per disc radius. The real drift rate is the microscope's to
   measure and is a gap here; the card gives the rate the measurement must
   beat, which is what decides whether a bleach run needs the focus re-checked
   during the record.

**Checkpoint 1:** commit Stage 1 as `stage1_*.json` and its generated `.md`
with figures, and message me the four conclusions in one line each.

## Stage 2 — only if Stage 1 leaves a question, and only after I agree

The candidate is item 1's depth averaging. `sim-20260930-401`'s Stage 2 runs
start from a sharp column. If the bias Stage 1 predicts is large enough to
matter, re-running the same configuration with a bleach that is blurred as a
function of depth tests whether the depth average is the right reduction --
the same question `manager-simulation-20260924-1` asked of the 1-D double well,
where the reduction moved the rate by 40 per cent. That is a change to the
bleach initial condition and not to the model; propose it with its cost and
wait for my answer.

## What crosses, and how

- Nothing reaches the microscope side by chat. Results go to `questions/` as
  cards; the bridge carries them **only when the person hands the result over**,
  the rule 025 recorded. Don't tell the bridge. I tell the person.
- What the microscope side might cite from this -- the bleach focal plane and
  its tolerance, the competing-plane warning, the wall threshold -- enters a
  microscope plan only through the store, as a `simulated:` or computed entry
  the librarian makes from your result card. You write the card; the librarian
  decides the entry.
- If the projection-path question in "The question" comes back absent, that gap
  is the most useful thing this card can send up. Name it on the result card.

## Done when

The result card answers, in decades: where to focus for a bleach and how
precisely; which plane the focus search will find on each sample and when it
finds the wrong one; the height below which wall drag breaks each prediction;
and the drift rate a bleach record must beat. Each number is graded from its
source, every assumed input names its gap, and the card says plainly which
committed result it corrects, if any. A Stage 1 that finds the focus plane
matters less than a tie everywhere is a result too: say so and stop.

## Corrected 2026-10-08: a findings file, not a result card

"Done when" above asked for a result card, and **that was my error, not the
seat's**. A result card is the record that a run happened. It requires a plan, a
plan hash, an approval and a run directory, and Stage 1 is closed forms with no
run. `simulation-20261007-1` stopped rather than mint a plan and an empty run to
satisfy the checks, which is the right call. The answers go in
`findings/simulation-20261007-1-20261008.json` under `findings.schema.json`,
the route that exists for facts established without a plan. They go to the
librarian, not the bridge. The readable record for the person is
`questions/sim-20261008-001/stage1_focus_planes.md`. Everything else in "Done
when" holds. **Writing a card for closed-form answers is not wrong**, and the
same gap will come back: if closed-form answers ever need to travel through the
bridge as cards, that is a contract change and the manager's to design.
