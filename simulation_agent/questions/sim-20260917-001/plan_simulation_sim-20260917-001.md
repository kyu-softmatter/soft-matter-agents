# Plan plan-sim-20260917-001

*Generated from `plan_simulation_sim-20260917-001.json`. The JSON is authoritative;
editing this file changes nothing (P3).*

- **question** `sim-20260917-001`, revision 1, status `VALIDATED`
- **purpose** characterize · **intent** explore
- **from** goal `goal-sim-20260917-001-r1` via synthesis `synthesis-sim-20260917-001`
- **degraded** librarian_agent — see the open risks

## What is computed

**tracer_diffusivity** — The short-time translational self-diffusion coefficient of dilute spherical tracers in the sample: the proportionality between mean squared displacement and lag time in the free regime, before hindrance by walls or by neighbouring particles sets in.

*Estimator (from `contracts/observables.json`, which no card can carry):* Weighted least-squares fit of the mean squared displacement of single-particle positions against lag time, with the intercept left free so that localisation error stays out of the slope. D = slope / (2 * spatial_dimensions). Fit range: lags from one save interval up to max_lag_time, which must satisfy both bounds -- below the diffusive time tau_d, so the tracer is still free, and short enough against the record that every lag in the fit is determined. The plan declares the value and shows both. Weighting: by the number of independent displacements at each lag. A record of length T yields about T/tau of them at lag tau, so the variance of the MSD estimate grows sharply with lag, and equal weights hand the slope to the points that have the fewest samples. This is not a refinement: measured on the simulation side, equal weights over whole-record lags gave a 7 percent bias at 0.16 percent relative standard error -- a number that looks precise and is wrong, which is the failure a shared estimator exists to prevent.

Configuration `bd_overdamped` on `hoomd_backend`.
Model: overdamped Brownian dynamics of spherical tracers in an implicit solvent, no pair interactions, periodic boundaries in all three directions.

## Conditions

| parameter | value | source | grade |
|---|---|---|---|
| `integration_timestep` | 0.002 s | `computed:operating_point_of_bd_overdamped` | E5 |
| `total_simulated_time` | 20 s | `computed:operating_point_of_bd_overdamped` | E5 |
| `save_interval` | 0.02 s | `computed:two_decades_below_the_window` | E5 |
| `box_length` | 100 um | `computed:spacing_times_particles_per_edge` | E5 |
| `max_lag_time` | 2 s | `assumed:a_window` | E5 |
| `n_particles` | 1000 count | `assumed:a_ensemble` | E5 |
| `temperature` | 293 K | `kb:lab_ambient_temperature` | E3 |
| `viscosity` | 0.001 Pa*s | `kb:water_viscosity_293k` | E3 |
| `bead_diameter` | 2 um | `assumed:a_sample` | E5 |

## Declared before the run

Stop and success criteria are fixed now. Chosen afterwards they would be narration,
not results (5.4).

**Stop**

- `simulated_time` >= 20 s — stop when the run reaches the planned duration; running longer would be a different plan
- `max_single_step_displacement` > 100 um — a tracer moving more than the box in one step is a diverged integration; stop and keep the run, because divergence is a result

**Success**

- `log10_ratio_of_measured_to_expected_diffusivity` <= 1 count — the fitted diffusivity sits within the target decade of the free Stokes-Einstein expectation
- `relative_standard_error_of_fitted_diffusivity` <= 0.1 1 — the spread across tracers is small enough that the decade is decided by the physics and not by the sampling

## The window, and both of its bounds

`tracer_diffusivity` is window-dependent, so the fit window is a condition and not a
detail. The vocabulary requires it to clear two bounds at once:

- **physical** — below the diffusive time, so the tracer is still free: window 2 s against `tau_d` 20 s
- **statistical** — short enough against the record that every lag in the fit is
  determined: ratio 0.1 1 against a ceiling of 0.1 1

At a ratio of one the longest lag carries a single displacement per tracer, and an
equally weighted fit then hands the slope to its noisiest point.

## Envelope

Status **unavailable**, checked against `simulation_agent/envelope/safety.json`.

The file is absent and no schema in contracts/schemas/ declares its shape, so there is no allowance to compare the estimated cost against. A5 abstained for the same reason. This is not a claim that the run is inside budget; it is the record that nothing was available to check it against.

## Cost

- `wall_clock_estimate` 0.0001 core_h
- `storage_estimate` 0.02 GB

estimates of an unrun job, from A5. The smoke run's own log replaces them with measured values

## Rejected

- **integration_timestep at A1's ceiling** — A1 allows a far coarser step, set from the diffusive time, but a saved frame would then fall between steps; the step is set a decade below the save interval instead (`integration_timestep_max` 0.2 s, `save_interval_max` 0.02 s)
- **box_length at the periodic-image bound** — the image bound is cleared by a much smaller box, but that box puts a thousand tracers about a diameter apart, which is not the dilute limit the observable is defined in; the dilution bound binds instead (`box_length_min_images` 9 um, `box_length_min_dilution` 100 um)

## Open risks

- No resource envelope exists, so nothing in this plan says the run is affordable. A5 abstained rather than passing, and the envelope check reports unavailable.
- The librarian was never reached, so temperature, viscosity and the expected diffusivity are all estimates. Every interval in this plan rests on them, and one estimate in the chain makes the answer an order of magnitude (P15).
- The expected diffusivity is what the run is checked against, and it was derived from the same Stokes-Einstein relation the engine is expected to reproduce. Agreement therefore tests the integration and the sampling, not the physical model.
- Nothing here is fitted to experimental data, and no experimental counterpart has been measured. A bridge round would be the first comparison, and comparable is still false for this observable.
- The temperature is the same number on both sides and not the same kind of number. Here the thermostat realises it exactly: it is a coordinate of the model, carrying no uncertainty of its own. The entry it was chosen from is an operator reading whose validity leaves the thermometer's position open, and nothing on the instrument actuates the sample temperature. So in a comparison the whole temperature uncertainty sits on the experimental side, and treating the two as equally certain -- or equally uncertain -- would misplace it.

## Assumptions

- **`a_sample`** The tracer size is a property of the question rather than a result. No bead lot exists to quote, so a micron-scale sphere is the intended size and not a specification.
  - retired by: a bead lot specification replaces this with an E3 value and every interval resting on it moves
- **`a_ensemble`** One thousand tracers is a round ensemble that makes the statistics cheap and keeps the cube root exact at ten per edge. Nothing physical picks this number.
  - retired by: a statistics interval this ensemble cannot satisfy inside budget replaces it
- **`a_window`** The fit window sits below the diffusive time so the free regime is what is sampled. The exact upper end is an estimate until A4 constrains it.
  - retired by: an A4 interval that excludes this value replaces it
- **`a_window_statistics`** A lag may span at most about a tenth of the record, so that every lag in the fit is determined by many displacements rather than by one. The vocabulary requires the window to satisfy this statistical bound as well as the physical one but deliberately fixes no fraction -- a number chosen in the contract would be a threshold nobody measured -- so the value is declared here and carried into the plan.
  - retired by: a weighted fit whose slope is unchanged when the longest lag is shortened retires this fraction
- **`a_target`** Screening accuracy is one decade. The run answers whether the engine reproduces free diffusion, not what the coefficient is to three figures.
  - retired by: a question needing the coefficient rather than its decade restates this target and switches the intent to confirm
- **`a_statistics`** A ten per cent statistical error needs of order one hundred independent samples, from the square-root scaling of an ensemble mean. The target is set at ten per cent rather than at the goal's full decade so that the statistical error is not what decides the decade.
  - retired by: a seed-to-seed spread wider than ten per cent at this sample count retires the prefactor and raises the floor
- **`a_cost_reference`** Cost is estimated at a reference step of ten milliseconds over a window of a few seconds, with one interaction-free force evaluation per particle per step. Nothing has been benchmarked on this machine, so both figures are order-of-magnitude estimates of an unrun job.
  - retired by: a smoke run's own log replaces both estimates with measured values

