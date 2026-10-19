# Observable: well_occupancy

Every entry in the store about the observable well_occupancy.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the managers' registry, contracts/observables.json:

> The fraction of observation time a single particle held in a multi-well optical potential spends in one named well. Reported per well, so a two-well landscape yields two values that sum to one. A well here is a basin of the TOTAL potential and not a trap: two traps closer together than twice their width form one basin and the observable is then undefined rather than zero.

- units: ["1"]
- estimator: Assign every frame to a well by the milestoning rule -- the particle belongs to the well whose minimum it most recently reached, and the barrier region belongs to neither side but to whichever was last touched. Occupancy is the assigned time divided by the record length. Stated as milestoning rather than nearest-minimum because a particle loitering on the barrier flickers between the two under nearest-minimum, and each flicker is counted as a visit.

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
