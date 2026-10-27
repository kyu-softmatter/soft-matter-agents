# Observable: dynamical_crossover_time

Every entry in the store about the observable dynamical_crossover_time.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the managers' registry, contracts/observables.json:

> The lag at which a mean squared displacement stops being ballistic and starts being diffusive, defined by its log-log slope passing a stated value between 2 and 1.

- units: ["s"]
- estimator: Take `msd_loglog_slope` on a rolling lag window and report the lag at which it first crosses a DECLARED threshold between 2 and 1. The threshold is the window: 1.5 and 1.1 give different numbers from one run.

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
