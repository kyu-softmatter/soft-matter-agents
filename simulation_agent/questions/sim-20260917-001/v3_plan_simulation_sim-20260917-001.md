# Plan plan-sim-20260917-001-r3

*Generated from `plan_simulation_sim-20260917-001.json`. The JSON is authoritative;
editing this file changes nothing (P3).*

- **question** `sim-20260917-001`, revision 3, status `VALIDATED`
- **purpose** characterize · **intent** explore
- **from** goal `goal-sim-20260917-001-r3` via synthesis `synthesis-sim-20260917-001-r3`
- **degraded** librarian_agent — see the open risks

## What is computed

**tracer_diffusivity** — The short-time translational self-diffusion coefficient of dilute spherical tracers in the sample: the proportionality between mean squared displacement and lag time in the free regime, before hindrance by walls or by neighbouring particles sets in.

*Estimator (from `contracts/observables.json`, which no card can carry):* Weighted least-squares fit of the mean squared displacement of single-particle positions against lag time, with the intercept left free so that localisation error stays out of the slope. D = slope / (2 * spatial_dimensions). Fit range: lags from one save interval up to max_lag_time, which must satisfy both bounds -- below the diffusive time tau_d, so the tracer is still free, and short enough against the record that every lag in the fit is determined. The plan declares the value and shows both. Weighting: by the number of independent displacements at each lag. A record of length T yields about T/tau of them at lag tau, so the variance of the MSD estimate grows sharply with lag, and equal weights hand the slope to the points that have the fewest samples. This is not a refinement: measured on the simulation side, equal weights over whole-record lags gave a 7 percent bias at 0.16 percent relative standard error -- a number that looks precise and is wrong, which is the failure a shared estimator exists to prevent.

Configuration `bd_overdamped` on `hoomd_backend`.
Model: overdamped Brownian dynamics of spherical tracers in an implicit solvent, no pair interactions, periodic boundaries in all three directions.

## Conditions

| parameter | value | source | grade |
|---|---|---|---|
| `integration_timestep` | 0.3 s | `computed:thousandth_of_a_diffusive_time` | E4 |
| `total_simulated_time` | 3000 s | `computed:ten_diffusive_times` | E4 |
| `save_interval` | 0.3 s | `computed:two_decades_below_the_window` | E5 |
| `box_length` | 300 um | `computed:spacing_times_particles_per_edge` | E5 |
| `max_lag_time` | 30 s | `assumed:a_window` | E5 |
| `n_particles` | 1000 count | `assumed:a_ensemble` | E5 |
| `temperature` | 293 K | `kb:lab_ambient_temperature` | E3 |
| `viscosity` | 0.001 Pa*s | `kb:water_viscosity_293k` | E3 |
| `bead_diameter` | 5 um | `kb:tracer_diameter_measured` | E2 |

## Declared before the run

Stop and success criteria are fixed now. Chosen afterwards they would be narration,
not results (5.4).

**Stop**

- `simulated_time` >= 3000 s — stop when the run reaches the planned duration; running longer would be a different plan
- `max_single_step_displacement` > 300 um — a tracer moving more than the box in one step is a diverged integration; stop and keep the run, because divergence is a result

**Success**

- `log10_ratio_of_measured_to_expected_diffusivity` <= the target for `tracer_diffusivity`: 1 decade — the fitted diffusivity sits within the target decade of the free Stokes-Einstein expectation
- `relative_standard_error_of_fitted_diffusivity` <= 0.1 1 — the spread across tracers is small enough that the decade is decided by the physics and not by the sampling
- `msd_fit_intercept_in_block_sigma` <= 3 1 — the MSD fit's intercept is consistent with zero against the block-resampled error, so the lags that were fitted are in the free regime the estimator assumes. This backend has no localisation error for a free intercept to absorb, so a nonzero one means the window and not the physics
- `log10_ratio_of_first_half_to_second_half_diffusivity` <= the target for `tracer_diffusivity`: 1 decade — the fit agrees with itself across the window: D over the first half of the lag range against D over the second. This is what separates converged from precise -- a fit reaching past the free regime disagrees with itself across the window while each half stays tight, and no error bar reports that

## The window, and both of its bounds

`tracer_diffusivity` is window-dependent, so the fit window is a condition and not a
detail. The vocabulary requires it to clear two bounds at once:

- **physical** — below the diffusive time, so the tracer is still free: window 30 s against `tau_d` 300 s
- **statistical** — short enough against the record that every lag in the fit is
  determined: ratio 0.01 1 against a ceiling of 0.1 1

At a ratio of one the longest lag carries a single displacement per tracer, and an
equally weighted fit then hands the slope to its noisiest point.

## Envelope

Status **inside**, checked against `simulation_agent/envelope/budget.json`.

target local: every cost number of this plan that lines up with a ceiling is under it: wall_clock_estimate against wall_clock_max, storage_estimate against storage_max. Re-confirmed at run time (4.6 O1).

## Cost

- `wall_clock_estimate` 0.0001 core_h
- `storage_estimate` 0.02 GB

estimates of an unrun job, from A5. The smoke run's own log replaces them with measured values

## Rejected

- **integration_timestep at A1's ceiling** — A1 allows a far coarser step, set from the diffusive time, but a saved frame would then fall between steps; the step is set a decade below the save interval instead (`integration_timestep_max` 3 s, `save_interval_max` 0.3 s)
- **box_length at the periodic-image bound** — the image bound is cleared by a much smaller box, but that box puts a thousand tracers about a diameter apart, which is not the dilute limit the observable is defined in; the dilution bound binds instead (`box_length_min_images` 20 um, `box_length_min_dilution` 300 um)

## Open risks

- A5 abstains, so no interval in this plan is constrained by the budget. The ceilings exist in envelope/budget.json and the operator compares against them at run time, but at plan time the cost side stands alone -- a cheap run is not the same fact as a run inside a known allowance.
- The intercept guard cannot detect a systematic short-lag artifact. A bias shows in the mean intercept over an ensemble and a fluctuation shows in a single run, and no threshold on one run's intercept separates them. What catches an artifact is a campaign whose mean intercept is consistent with zero, and that is not a criterion one plan can carry.
- The fit's own standard errors understate the spread by roughly 36x for the diffusivity and 7x for the intercept, measured across 32 seeds: the weighted least squares treats correlated MSD points as independent. The criteria here read the block-resampled error instead, and any reader comparing against relative_standard_error is comparing against a number far too small.
- The expected diffusivity is what the run is checked against, and it was derived from the same Stokes-Einstein relation the engine is expected to reproduce. Agreement therefore tests the integration and the sampling, not the physical model.
- Nothing here is fitted to experimental data, and no experimental counterpart has been measured. A bridge round would be the first comparison, and comparable is still false for this observable. The store was asked at this revision and holds no measured tracer_diffusivity -- only the Stokes-Einstein prediction, which is the same relation this run is checked against.
- The temperature is the same number on both sides and not the same kind of number. Here the thermostat realises it exactly: it is a coordinate of the model, carrying no uncertainty of its own. The entry it was chosen from is an operator reading whose validity leaves the thermometer's position open, and nothing on the instrument actuates the sample temperature. So in a comparison the whole temperature uncertainty sits on the experimental side, and treating the two as equally certain -- or equally uncertain -- would misplace it.

## Assumptions

- **`a_ensemble`** One thousand tracers is a round ensemble that makes the statistics cheap and keeps the cube root exact at ten per edge. Nothing physical picks this number.
  - retired by: a statistics interval this ensemble cannot satisfy inside budget replaces it
- **`a_window`** The fit window sits below the diffusive time so the free regime is what is sampled, at the same tenth of it revision 1 chose. The exact upper end is an estimate until A4 constrains it.
  - retired by: an A4 interval that excludes this value replaces it
- **`a_window_statistics`** A lag may span at most about a tenth of the record, so that every lag in the fit is determined by many displacements rather than by one. The vocabulary requires the window to satisfy this statistical bound as well as the physical one but deliberately fixes no fraction -- a number chosen in the contract would be a threshold nobody measured -- so the value is declared here and carried into the plan.
  - retired by: a weighted fit whose slope is unchanged when the longest lag is shortened retires this fraction
- **`a_statistics`** A ten per cent statistical error needs of order one hundred independent samples, from the square-root scaling of an ensemble mean. The target is set at ten per cent rather than at the goal's full decade so that the statistical error is not what decides the decade.
  - retired by: a seed-to-seed spread wider than ten per cent at this sample count retires the prefactor and raises the floor
- **`a_intercept_guard`** Three standard errors is a guard against a gross short-lag failure, not a test of bias, and it is set from the asymmetry rather than from any observation: a false refusal costs one re-run of a job sitting far under budget, while a false acceptance puts a biased number into a graded card. IT CANNOT DETECT AN ARTIFACT, and saying so is the point -- a systematic short-lag error shows in the MEAN over runs while a fluctuation shows in a single one, and no threshold on a single run's intercept separates them. Tight refuses good runs at the fluctuation rate; loose misses a small artifact. The test that catches an artifact is that the mean intercept over an ensemble of runs is consistent with zero, which needs a campaign and is not a criterion one plan can carry.
  - retired by: a campaign whose mean intercept is inconsistent with zero, which would show this guard passing runs it cannot judge
- **`a_cost_reference`** Cost is estimated at a reference step of ten milliseconds over a window of a few seconds, with one interaction-free force evaluation per particle per step. Two mock runs have happened on this machine and neither benchmarks this job: 93 per cent of their wall clock fell outside the monitored window, in process start and a poll interval the mock outruns, and the mock writes no trajectory at all, so the size of its run directory measures four cards. Both figures stay order-of-magnitude estimates of an unrun job.
  - retired by: a smoke run on the backend this configuration declares -- hoomd_backend, not mock_backend -- replaces both estimates with measured values. The earlier form said 'a smoke run's own log' and named an EVENT that would happen rather than a STATE that has to obtain, so two mock runs satisfied it in letter while measuring the harness; substituting their numbers would have produced figures that look measured and are about a different thing. It does not fire today: hoomd_backend.py is written and HOOMD is not installed.

