# sim-20260923-002 — relaxation under continuous local driving of one particle

*S2 output, for people. The record is `goal.json` beside this file (P3). Written
by seat simulation-11 on 2026-09-23 from the person's question 5-2, verbatim in
`goal.json` `constraint_notes[0]`. Reads sim-20260923-001 as a record, not as an
input (§4.5.5).*

## Where this stops, and why

**Branch (c): asked back once.** Everything 001 asks for is needed here too and
is not repeated. What is additional:

### 1. From the person

- **Purpose.** Proposed `characterize` (three parameters swept: velocity,
  interaction strength, direction). If direction-against-direction is the
  real interest, say `compare` with `compare_variable: driving_direction`; S4
  then holds every other condition fixed across the three arms instead of
  optimising each, which is the whole difference (§4.5.1).
- **How the particle is driven.** "Prescribed velocity" read literally is a
  kinematic constraint (the particle's position is imposed). The alternative,
  a constant force with the velocity emerging, is a different model with a
  different A7. Name one; the configuration declaration has to say which.
- **What relaxes.** Whether the quantity is the wake's recovery behind the
  driven particle (a correlation time in the surrounding structure after the
  perturbation passes), or the steady-state deformation field around it. These
  are different observables with different estimators.
- **The velocity range**, as decades, and the reference it is read against —
  the natural one is the undriven relaxation time from 001, which makes the
  Péclet-like ratio the swept variable. That is a proposal, not a number.

### 2. From `manager-simulation`

- Register the observable, proposed id `driven_tracer_relaxation_time`,
  `window_required: true`.
- Declare `bd_pairwise_driven_tracer`: 001's model plus one particle under the
  chosen drive. **Driven**, so A7 is live and no longer abstains.

### 3. A precondition that is 001's result

"Principal lattice direction", "perpendicular" and "diagonal" presuppose that
001 relaxes to an ordered structure at the chosen conditions. If it relaxes to
a disordered steady state, the three directions have no referent and this
question changes shape. That is a result of 001, so this question cannot be
fully specified before 001 has run at least once — which is the ordering,
not a blocker for registering the vocabulary now.

### 4. From the librarian

`driven_tracer_relaxation_time` and `bond_orientational_order` both **absent**
at `kbv-4b981dc870d3`, no near names.
