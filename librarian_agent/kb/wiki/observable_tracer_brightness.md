# Observable: tracer_brightness

Every entry in the store about the observable tracer_brightness.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the managers' registry, contracts/observables.json:

> The detected signal rate of a single tracer under stated illumination and exposure: what one particle contributes to a frame, separated from background. Registered so a pre-measurement has an observable to name; it is the input six abstentions across A1 and A3 are waiting on.

- units: ["Hz"]
- estimator: Segment single, well-separated tracers in each frame, integrate the signal over a fixed aperture around each centroid, subtract a local background estimated from an annulus outside it, and divide by the exposure time to give a rate. Report the median over particles and frames within the window, with the inter-particle spread, because the distribution over particles is what A1's detection limit needs and a mean hides it. Particles within one aperture diameter of another are excluded rather than deblended.

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

Generated from the knowledge store at kbv-d027f44dadc0. Do not edit by hand: correct the store and regenerate.
