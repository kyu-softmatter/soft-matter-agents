# plan-sim-20260923-101-r2 -- the double well, one bead and two traps

*Generated from the JSON card beside this file. If the two disagree the JSON wins.*

**Status** VALIDATED  ·  **Configuration** bd_overdamped_gaussian_double_well_2d

## The model

one overdamped bead in two dimensions, in fluid at rest, in two optical traps modelled as two Gaussian wells that add: U = -eps_1 exp(-|r-r_1|^2/2w_1^2) - eps_2 exp(-|r-r_2|^2/2w_2^2), each 0.5*k_i*dr^2 at its centre with k_i = eps_i/w_i^2. Many independent single-bead records in one engine run; no pair interaction

## The operating point

| parameter | value |
|---|---|
| `integration_timestep` | 0.001 s |
| `save_interval` | 0.01 s |
| `record_length` | 600 s |
| `startup_discard` | 10 s |
| `box_length` | 0.0001 m |
| `walkers` | 200 1 |
| `trap_stiffness_1` | 1e-06 N/m |
| `trap_stiffness_2` | 1e-06 N/m |
| `trap_width_1` | 1e-06 m |
| `trap_width_2` | 1e-06 m |
| `barrier_target` | 4 1 |
| `milestone_core_fraction` | 0.2 1 |
| `temperature` | 293 K |
| `viscosity` | 0.001 Pa*s |
| `bead_diameter` | 5 um |

## What would make this run a failure

- **hops_counted** -- the median record holds at least ten hops; below that a record bounds the rate and the barrier target is lowered in the next revision
- **occupancy_symmetric** -- for equal wells the mean occupancy over records is one half within its standard error; a departure is the estimator or the engine, since the potential fixes it

## What was considered and dropped

- **a stiffness ratio anywhere in the person's 1 to 100** -- computed from the potential: with wells hundreds of kT deep, any k2/k1 of 0.5 or below makes the shallow well vanish while the barrier from the deeper one is still tens to thousands of kT, so no separation gives a barrier in 1-10 kT. Equal stiffnesses are the operating point; asymmetry is a depth difference of a few kT, a trim of a few per cent
- **the separation as a plan number** -- the barrier moves by about half a kT per ten nanometres at this stiffness, so a separation to one figure is a different experiment. The plan carries the barrier and the engine solves the separation from it

## What this run cannot settle

- Only the rates and residence times are results about the model. The occupancy and the barrier are fixed by the potential in the long-record limit, so for those two this run establishes only what a finite record returns -- its spread and its bias -- and must not be read as discovering them.
- The separation is solved from the barrier and is not a number the bench can set: near merging the barrier moves by about half a kT per ten nanometres, so the bench reaches this point by watching its histogram, and the comparison runs at the calibrated values it returns.
- Bulk Stokes drag. Near the coverslip the bead's drag is larger and every time here stretches with it; the bench's in-situ diffusivity replaces the drag in the re-prediction.
- Simulated positions are instantaneous and a camera frame averages over its exposure, which narrows each peak and can hide a short visit. The exposure is a condition of any comparison.
- The axis along the beam is not modelled. A real trap is weaker there; the in-plane observables are unaffected only while nothing reads that axis.
