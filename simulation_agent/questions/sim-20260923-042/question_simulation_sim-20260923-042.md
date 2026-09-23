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
   `effective_diffusivity` (check 32). Confirm is not cheap.

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
