# plan-sim-20260923-003-r4 — mean_squared_displacement for a free active particle

*Generated from the JSON card beside this file. If the two disagree the JSON wins.*

**Status** VALIDATED  ·  **Configuration** abp_free  ·  **Engine** hoomd_backend

## The model

a free active Brownian particle in two dimensions: one orientation diffusing at D_R, self-propulsion at a fixed speed v0 along it, translational noise D_T, no pair interaction, no wall, no obstacle, periodic in both directions with unwrapped coordinates

## The operating point

| parameter | value |
|---|---|
| `integration_timestep` | 0.01 s |
| `total_simulated_time` | 40000 s |
| `save_interval` | 0.1 s |
| `box_length` | 3000 um |
| `max_lag_time` | 3000 s |
| `n_particles` | 100 1 |
| `self_propulsion_speed` | 3 um/s |
| `rotational_diffusivity` | 0.01 1/s |
| `temperature` | 293 K |
| `viscosity` | 0.001 Pa*s |
| `bead_diameter` | 5 um |
| `fit_lag_range_lower_bound` | 1000.0 s |

## The three scales this run sits between

- the early crossover, where thermal motion gives way to propulsion: 0.01 s
- the persistence time, where propulsion gives way to effective diffusion: 100 s
- the window the long-time answer is read over: from 1000.0 s to 3000 s, a share 0.08 1 of the record

## What would make this run a failure

- **ballistic_regime_present** — the maximum log-log slope reaches at least 1.9. It cannot reach 2: the limit is a function of v0^2/((d-1) D_R D_T) alone and is 1.98 at this operating point, so a run below 1.9 means the sweep does not reach the regime it was chosen to reach. This is the falsifier of a_peclet_point
- **long_time_diffusive** — the slope returns to 1 within a tenth at the longest lags, which is what says the plateau was entered rather than approached. If it has not, the effective diffusivity read from this record is a lower bound and not a value
- **statistics_met** — the spread on the effective diffusivity is inside A2's target, read from a block resample rather than from the fit's own standard error

## What was considered and dropped

- **a save interval fine enough to resolve the thermal regime** — the MSD has THREE regimes and this plan resolves two of them. Below tau_1 = D_T/v0^2 the translational noise beats the propulsion and the slope returns to 1; seeing that needs a save interval a decade under tau_1, which at this record length is 4e9 stored coordinates against A5's ceiling of 1e9. The window is bounded here and not resolved, and the short-lag end is a second plan rather than a finer version of this one
- **the integration timestep at A1's ceiling** — A1 allows a step three decades coarser, because for a free active particle the only discretisation error is holding the orientation fixed across a step. A saved frame would then fall between steps, so the step follows the save interval instead
- **the record at A2's own floor of a hundred persistence times** — A2's floor and A4's window floor cannot both be met at that record: 3000 s of window in 10000 s of record is a ratio of 0.3 against A2's own ceiling of 0.1. Two axes that never see each other conflict, and S4 resolves it by lengthening the record rather than shortening the window

## What this run cannot settle

- This run measures no dependence, and the capability table says so: the mean squared displacement of a non-interacting active Brownian particle is a closed form in v0, D_R and D_T, so the run confirms the integrator, the estimator and the crossover machinery and cannot be cited as evidence about the dependence itself. Interaction or confinement would change that.
- The plan resolves two of the three regimes. Below the thermal crossover the translational noise beats the propulsion and the slope returns to 1; the save interval sits AT that crossover, so the run bounds that regime and does not resolve it. A finer save interval at this record length exceeds A5's storage ceiling by a factor of four, which is why it is a second plan.
- The rotational diffusivity is a chosen value and not a measured one. The store holds no rotational diffusivity for this tracer; the value used is the Stokes-Einstein-Debye figure for a sphere of the measured diameter, so it is a prediction from the same relation that produced the translational diffusivity, not an independent input.
- The temperature is a coordinate of this model and not a measurement of it. The integrator represents no velocity, so there is nothing to thermostat and the declared value enters as a noise amplitude. Citing the laboratory reading records why the number was chosen; it is not evidence about the model.
- Nothing here is fitted to experimental data and no experimental counterpart exists. The observables this plan produces are declared producible by simulation only, so there is no bridge round to compare against and comparability is not claimed.
