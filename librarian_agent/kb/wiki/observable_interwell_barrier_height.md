# Observable: interwell_barrier_height

Every entry in the store about the observable interwell_barrier_height.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the managers' registry, contracts/observables.json:

> The potential energy difference between the saddle separating two wells of a static optical potential and the minimum of the origin well. Direction-dependent whenever the wells differ in depth, so it is reported per ordered pair and the two values differ by the tilt.

- units: ["kT", "pJ", "J"]
- estimator: Invert the equilibrium position histogram: U(x) = -kT ln P(x) up to a constant, locate the two minima and the saddle between them, and take the difference from the origin minimum to the saddle. The histogram bin width and the record length both enter, so both travel with the number. In a simulation the potential is known in closed form and the same inversion is still the estimator, so that the two sides are measuring the same thing rather than one reading its own input.

## Values

None.

## Claims

None.

## Disputed and withdrawn

None.

## Reading

None.

## Related

None.

---

Generated from the knowledge store at kbv-058ce14eea72. Do not edit by hand: correct the store and regenerate.
