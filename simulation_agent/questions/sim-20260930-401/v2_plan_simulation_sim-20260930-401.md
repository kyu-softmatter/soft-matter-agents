# plan-sim-20260930-401-r2 — bleach recovery of 100 nm beads, on the model

*Generated from the JSON card beside this file. If the two disagree the JSON wins.*

**Status** VALIDATED  ·  **Configuration** bd_overdamped

## The model

non-interacting spheres in overdamped Brownian motion in a periodic box, three-dimensional, no pair potential, no wall. A uniform disc is bleached as a column through the whole depth by labelling beads, not by any force: the label changes nothing about how a bead moves. The depth-projected count of unbleached beads inside the disc is read as a camera would read it

## What every point shares

| parameter | value |
|---|---|
| `temperature` | 293 K |
| `viscosity` | 0.001 Pa*s |
| `bead_diameter` | 100 nm |
| `bleach_radius` | 3 um |
| `box_length` | 30 um |
| `chamber_depth` | 10 um |
| `bleach_rate` | 50 1/s |
| `max_recovery_time` | 9 s |
| `pre_bleach_frames` | 10 1 |
| `record_length` | 1000 s |
| `curve_period` | 20 s |

## The points that run

| point | beads in disc | step | frame | bleach |
|---|---|---|---|---|
| n10_dt_f12_b30 | 10 | 0.005 s | 0.05 s | 0.02 s |
| n30_dt_f12_b30 | 30 | 0.005 s | 0.05 s | 0.02 s |
| n100_dt_f12_b30 | 100 | 0.005 s | 0.05 s | 0.02 s |
| n300_dt_f30_b30 | 300 | 0.005 s | 0.02 s | 0.02 s |
| n300_dt_f12_b30 | 300 | 0.005 s | 0.05 s | 0.02 s |
| n300_dt_f12_b12 | 300 | 0.005 s | 0.05 s | 0.05 s |
| n300_dt_f6_b30 | 300 | 0.005 s | 0.1 s | 0.02 s |
| n300_dt_f6_b12 | 300 | 0.005 s | 0.1 s | 0.05 s |
| n300_dt2_f12_b30 | 300 | 0.002 s | 0.05 s | 0.02 s |
| n1000_dt_f12_b30 | 1000 | 0.005 s | 0.05 s | 0.02 s |

50 further cells of the grid are listed as skipped, each with its reason.

## What would make this a failure

- **agrees_with_solver** — the point's mean fitted D lies within three standard errors of what the diffusion equation predicts for the same bleach, camera and fit; this is the integrator check, and it is against the solver and not against Stokes-Einstein
- **dt_halving_unchanged** — halving the engine step moves the mean fitted D by no more than three combined standard errors

## What was considered and dropped

- **a full product grid of bead count x timestep x frame x bleach** — sixty cells for questions that each move one factor; the base point and one move per factor answer them, and the corner tests the two allowed extremes together
- **frame and bleach lengths beyond A4's ceilings** — the estimator refuses such curves as one-sided bounds; a point there measures the refusal and not the bias, and A4's interval excludes it
- **a disc larger than 3 um** — in units of tau and w the problem is scale-free: at a fixed bleach/tau, frame/tau, k*tau and beads per disc the curve and its bias are the same at any w, so a larger disc needs no run of its own; the first stage's closed form gives tau at any w

## What this run cannot settle

- The run's D is fixed by its inputs (the configuration says so): it checks the integrator, the bleach and the estimator, and says nothing independent about the beads.
- The bleach rate is a guess. It sets how deep the dip is, which sets how noisy one curve is; a slower real bleach makes every point here an optimistic case.
- No imaging bleach, no background, no drift and no walls are modelled. The reference ratio and background the estimator applies are identities here. At large discs, where the record runs for minutes, these are what bind first, and none of them is in this model.
- The camera is ideal: it counts beads, with no point-spread function, no shot noise from photons and no pixel grid. Counting noise is the only noise.
