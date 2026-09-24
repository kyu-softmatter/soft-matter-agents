# plan-sim-20260923-201-r3: the smoke cell of a drag calibration

*Generated from the JSON beside this file, which is authoritative (P3). Status: VALIDATED.*

One sphere in a harmonic trap of 2 pN/um, fluid at 20 um/s, timestep 0.0001 s, startup 0.2 s discarded, then a record of 6 s saved every 0.002 s.

At the conservative per-step cost the run takes 200 s and stores 4e-05 GB.

## Success criteria

- **statistics_met**: the person's target, which is on the UNCERTAINTY: the block standard error of the mean offset, as a fraction of it, at or below one per cent. The recovered stiffness is gamma*v over the offset, so its relative error is the offset's
- **recovered_stiffness_within_target**: the recovered stiffness within one per cent of the declared one. STRICTER THAN THE TARGET AND DECLARED ANYWAY, because it is what `can the known stiffness be recovered` asks in so many words. At the planned error it is met about three runs in four by chance alone; see open_risks

## Open risks

- THE RECOVERED STIFFNESS IS NOT EVIDENCE ABOUT ANY TRAP. gamma and k_t both go in and the estimator inverts the equation the integrator solved (output_independent_of_input false). A pass tests the integrator and the estimator; what carries information is the error model -- whether the block error agrees with sigma*sqrt(2*tau/T), in which the stiffness has cancelled.
- The two success criteria are not the same test. The target is on the uncertainty, and a cell sized for one per cent of uncertainty recovers the stiffness within one per cent only about three times in four. A miss on recovered_stiffness_within_target with statistics_met is expected at that rate and is not the method failing; holding the deviation at 95 per cent would need about four times the record.
- ONE CELL OF TWELVE. The slow row is refused at the conservative cost (S4 refusal card) and the other seven kept cells wait for this run's measured rate. The sweep as a plan also meets a check that cannot read it: check 40 reads only top-level conditions, so a window that varies across a sweep's points -- which varies_with permits -- has nowhere to stand. Raised to manager-simulation.
- This runs on trap_backend, a NumPy Euler-Maruyama integrator, and not on HOOMD. The capability table declares hoomd_backend; that field records which engine ran and moves after the run.
- The trap is harmonic by declaration: no escape and no anharmonicity (A7). This cell's offset is ten thermal widths, about half a micrometre, well inside any real trap's range; the fast row is not.
- The viscosity is E3 and of order one millipascal second, and it cancels out of the recovered over declared ratio because the same gamma imposes and inverts the drag. On the bench it does not cancel, and the sample temperature is neither actuated nor read.
