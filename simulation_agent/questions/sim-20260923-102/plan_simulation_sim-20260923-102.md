# plan-sim-20260923-102: one trap at rest, the width a camera should see

*Generated from the JSON beside this file, which is authoritative (P3). Status: VALIDATED.*

One sphere of 5 um in a harmonic trap of 0.5 pN/um, fluid at rest. Timestep 0.0004 s, start-up 0.9 s discarded, then a record of 20 s saved every 0.009 s.

Predicted in-plane width: 0.09 um. Longest bench exposure without correction: 0.009 s.

## Success criteria

- **width_within_decade**: the goal's target: both in-plane widths within one decade of the prediction
- **width_within_three_scatters**: each in-plane width within three of this record's own standard errors of sqrt(k_B*T/k_t), after allowing for the expected low bias of one relaxation time over the record. Stricter than the target and declared anyway, because it is what tests the estimator rather than only the integrator

## Open risks

- THE WIDTH IS NOT EVIDENCE ABOUT ANY TRAP: k_t goes in and sqrt(k_B*T/k_t) comes out by construction (output_independent_of_input false). A pass tests the integrator and the estimator. What the run carries to the bench is the record length and the expected bias and scatter at that length.
- A CAMERA FRAME IS NOT AN INSTANT. The run's positions are instantaneous; a frame averages over its exposure and narrows the variance. The bench exposure must stay under camera_exposure_max_op, or the comparison must apply the exposure correction to the simulated width.
- The trap is harmonic by declaration and a real trap goes to zero far from its focus. Where the bench trap stops being harmonic is unknown -- the store holds no trap width -- and only the measured histogram's tails can say.
- The width's low bias from a finite record has a sign and scatter does not. The three-scatter criterion allows for it; a comparison that ignores it reads a one-relaxation-time-over-the-record shortfall as a stiffer trap.
- The sample temperature is neither actuated nor read, and the width goes as its square root. On the bench a kelvin of drift moves the width by a sixth of a per cent, far inside the target; in a confirm revision it will not be.
