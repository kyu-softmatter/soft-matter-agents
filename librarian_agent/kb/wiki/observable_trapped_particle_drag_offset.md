# Observable: trapped_particle_drag_offset

Every entry in the store about the observable trapped_particle_drag_offset.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the managers' registry, contracts/observables.json:

> The steady-state MEAN displacement of a trapped particle from its trap centre along the flow axis, while the surrounding fluid moves at constant velocity relative to the trap. The trap centre here is the geometric centre of the confining potential and not the time-averaged particle position.

- units: ["um", "nm"]
- estimator: Track the particle centre over a declared record length under steady flow and report the mean displacement from the DECLARED trap centre, resolved along the flow direction. The record length is the window: the standard error of a mean falls as sqrt(1/T), so a displacement quoted without it is not one number.

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
