# Observable: bleaching_rate

Every entry in the store about the observable bleaching_rate.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the managers' registry, contracts/observables.json:

> The decay constant of tracer signal under continuous illumination at a stated setting. Produced by the same acquisition as tracer_brightness and registered with it.

- units: ["Hz"]
- estimator: Take the per-particle brightness trace over the record using the tracer_brightness estimator frame by frame, and fit a single exponential in time to the population median. Report the decay constant with its fit spread and the illumination it was taken at. A single exponential is declared BEFORE the run and is not chosen after seeing the curve; if the residual shows it is wrong, that is a result and the criterion is not swapped for a better-fitting one.

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
