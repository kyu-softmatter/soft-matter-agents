# Observable: effective_translational_diffusivity

Every entry in the store about the observable effective_translational_diffusivity.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the managers' registry, contracts/observables.json:

> The long-time translational diffusivity of a persistently self-propelled particle: the plateau of MSD/(2*d*t) once the motion has lost memory of its orientation. NOT the bare translational diffusivity D_T, which is the same curve read at short lag.

- units: ["um^2/s", "m^2/s"]
- estimator: Fit the slope of the mean squared displacement against lag time over a range whose LOWER bound lies well above the persistence time, and divide by 2*d. The lower bound is the condition that matters and it is the opposite direction from `tracer_diffusivity`, whose window is an UPPER bound protecting the free regime. A value read too early is D_T under this name.

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

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
