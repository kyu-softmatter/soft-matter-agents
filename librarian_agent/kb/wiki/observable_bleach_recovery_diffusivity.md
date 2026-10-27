# Observable: bleach_recovery_diffusivity

Every entry in the store about the observable bleach_recovery_diffusivity.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the managers' registry, contracts/observables.json:

> The in-plane translational diffusivity of fluorescent tracers in a dilute suspension, read from how fast fluorescence returns to a uniform disc that was bleached as a column through the whole sample depth. It is the self-diffusivity over the length scale of the disc radius, averaged over the depth of the chamber, so near-wall hindrance enters it in proportion to the fraction of the depth the walls slow. It is not tracer_diffusivity: no particle is followed, and the number comes from a concentration field relaxing rather than from single-particle displacements.

- units: ["um^2/s", "m^2/s"]
- estimator: Geometry, fixed before the run: a uniform disc of radius w bleached through the full depth, so the bleached volume is a column and the depth-integrated signal obeys 2-D diffusion whatever the particles do in z. w is the radius at half the bleach contrast of the azimuthally averaged profile in the first post-bleach frame; the nominal pattern radius is recorded beside it, and when the two differ by more than 2x the column assumption has failed and no value is reported. t = 0 is the end of the bleach. Normalisation, per frame: subtract the background B (a region outside any illumination, or a dark frame), divide the disc's integrated signal by its mean over the pre-bleach frames, and divide that by the same ratio for a reference region at least 5 w from the disc which sees the same imaging light and no bleach. That removes bleaching by the imaging light and source drift. Model: Soumpasis's uniform-disc recovery F(t) = F0 + (Finf - F0) * exp(-2 tau/t) * [I0(2 tau/t) + I1(2 tau/t)], with I0 and I1 the modified Bessel functions. F0, Finf and tau are free; w is not fitted. D = w^2 / (4 tau). Fit by unweighted least squares over every frame from the first post-bleach frame to max_recovery_time. Validity, checked on the fitted tau and refused otherwise, never reported as a value: bleach duration \<= tau/10, frame interval \<= tau/5, max_recovery_time \>= 10 tau. A curve outside any of these bounds D from one side only, and is reported as that bound. Finf \< 1 is reported as a mobile fraction beside D and is not folded into it. The model is declared before the run and is not swapped for a better-fitting one after the curve is seen; a residual showing it wrong is a result. Simulation applies the identical steps to the depth-projected count of unbleached particles inside the disc, sampled at the planned frame interval with the planned bleach duration, so the two sides differ only in where the curve comes from. In the engine there is no background and no bleaching by imaging light, so B is zero and the reference ratio is one by construction; those two steps are identities there and are still applied, not skipped. The engine's box is periodic and at least 10 w across, and its finite reservoir sets the expected plateau Finf = 1 - (disc area / box cross-section), which the free Finf absorbs; the plan states the box so that plateau can be checked rather than read as an immobile fraction.

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
