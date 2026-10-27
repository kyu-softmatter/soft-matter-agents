# Observable: trapped_position_distribution

Every entry in the store about the observable trapped_position_distribution.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the managers' registry, contracts/observables.json:

> The in-plane distribution of a trapped particle's centre about the trap. The scalar reported is the per-axis standard deviation of that position relative to the trap centre; the full histogram stays with the raw data.

- units: ["um", "nm"]
- estimator: Track the particle centre in every frame, take the mean position as the trap centre and subtract it, and report the per-axis standard deviation over the declared record length. A particle counts as trapped when the distribution stays bounded about that centre for the whole record; drifting away is not trapped.

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
