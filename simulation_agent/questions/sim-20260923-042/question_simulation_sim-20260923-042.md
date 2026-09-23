# sim-20260923-042 — system-size dependence of active Brownian dynamics

*S2 output, for people. The record is `goal.json` beside this file (P3), and
the S3.0 verdict is `refusal_s30_sim-20260923-042.json`. Written by seat
simulation-10 (window 4) on 2026-09-23 from the person's question 4-2,
verbatim in `goal.json` `constraint_notes[0]`.*

## Where this stops, and why

**S2 branch (c)** and **S3.0 zero candidates**, as for 041. Two things are
specific to this question and are asked before anything else.

### The two questions only a person can answer

1. **Is the system interacting?** With no pair potential and unwrapped
   coordinates, the box size has strictly no effect on the MSD, D_eff, the
   persistence time or the persistence length: nothing couples a particle to
   its periodic image. A finite-size effect then appears only if the
   estimator reads wrapped positions, which is a defect in the estimator, not
   a property of the system. If the system is non-interacting, this question
   closes at S2 with no run. If it is interacting, it shares 041's
   configuration and differs only in what is varied.

2. **How small an effect counts?** Proposed purpose is `compare` with
   `compare_variable: box_size`, which fits the wording exactly. But under
   `explore` a difference under 10× is a tie, and finite-size effects on a
   diffusivity are typically a fraction of the value — every box would pass
   as size-independent. If the minimum box is wanted at that resolution, the
   intent is `confirm` with an `intent_rationale` and a stated target on
   `effective_translational_diffusivity` (check 32). Confirm is not cheap.

### Also from the person

The same items as 041: dimensionality, the SI anchor, the potential, the
one operating point everything is held at, and the box sizes as arms (or a
range, if `characterize`).

### From `manager-simulation` and the librarian

The same five observables and two configurations requested in 041. Two
`kb_query` calls under this question's S2 id at `kbv-4b981dc870d3` returned
**absent**.

## The lengths the box is compared against

The persistence length v0/D_R (up to a dimension-dependent factor), the
particle diameter, and at high Péclet number and density the size of
motility-induced clusters, which can grow with the box itself. In that part
of the parameter space "independent of size" may have no finite answer, and
A3 needs the ranges before it can say where that part is.

## Relation to 041

041 reads this result as its finite-size premise. Landing 042 first removes
an assumption from 041's A3.

## Revision 2 — the person ruled (2026-09-23)

**2D, WCA, so the system is interacting and this question does not close
at S2.** One operating point held across arms, Pe 10 and φ 0.1, the centre
of 041's grid. Arms at 1, 10 and 100 persistence lengths (50 µm at this
anchor); the largest is expected to exceed the `local` budget, and that
refusal is a result about the reachable range. The P15 tension stands: at
decade resolution a box passes as size-independent unless the regime
changes. Same configuration request as 041.

## Revisions 2 to run (2026-09-23)

S4 kept two arms — one and ten persistence lengths of box, 13 and about a
thousand particles — and refused the hundred-fold arm in numbers (6e11
particle-steps against 7e10; 6e9 stored coordinates against 1e9). The plan
is `v2_plan_simulation_sim-20260923-042.json`. The small arm ran as the
Tier 1 smoke run on the new active backend (`run-20260923-042-small-s1`)
and its result card is beside this file: effective translational
diffusivity 9.9 ± 1.2 µm²/s, persistence time 93.5 s against 100 s
expected, statistics_met false at 11.7 per cent against a 10 per cent
target, and the compare's own criterion waiting on the mid arm. No
trajectory was written because `gsd` is not in the sim environment; the
run's meta says so.
