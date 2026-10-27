# Observable: well_residence_time

Every entry in the store about the observable well_residence_time.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the managers' registry, contracts/observables.json:

> The mean time a single particle spends in one well of a multi-well optical potential between reaching that well and reaching another. Reported per ordered pair of wells, because the time spent in the shallower well before crossing is not the time spent in the deeper one.

- units: ["s", "ms"]
- estimator: Renewal form: the total time assigned to the well by the milestoning rule of well_occupancy, divided by the number of exits from it counted in the same record. Deliberately NOT the arithmetic mean of completed dwell intervals -- the longest dwell in a record is the one most likely to straddle the end of it and be discarded, which biases that mean low by roughly the residence time over the record length.

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
