# Plan plan-sim-20260923-001-r3 -- structural_relaxation_time on bd_pairwise

*Generated from `plan-sim-20260923-001-r3` (revision 3); the JSON is authoritative. Status: VALIDATED.*

## Model

overdamped Brownian dynamics of N identical particles in two dimensions in a periodic box, purely repulsive Yukawa pair potential u(r) = U0 (a/r) exp(-kappa (r - a)) with U0 = Gamma k_B T and kappa = kappa_a / a, no hydrodynamic interactions, no attraction, no wall, no drive; positions start uniformly random; temperature enters as the noise amplitude only

## Sweep

- `gamma`: 10, 100
- `kappa_a`: 1, 3

4 cells, every cell at the same integrator settings.

## Conditions shared by every cell

| parameter | value | provenance |
|---|---|---|
| integration_timestep | 0.005 s | computed:factor_times_curvature_time (E5) |
| total_simulated_time | 10000 s | computed:cap_times_brownian_time (E5) |
| save_interval | 100 s | computed:factor_times_brownian_time (E5) |
| box_length | 300 um | computed:rows_times_lattice_constant (E5) |
| mean_spacing | 10 um | computed:spacing_times_diameter (E5) |
| plateau_window_start | 9000 s | computed:record_minus_window (E5) |
| relaxation_fit_window | 1000 s | computed:frames_times_save_interval (E5) |
| plateau_fraction | 0.9 | assumed:a_plateau (E5) |
| lattice_constant | 10 um | computed:triangular_lattice_constant_at_density (E5) |
| rows_x | 30 | computed:rows_from_finite_size_factor (E5) |
| rows_y | 30 | computed:rows_from_finite_size_factor (E5) |
| n_particles | 900 | computed:rows_product (E5) |
| n_seeds | 9 | computed:seeds_at_the_floor (E5) |
| temperature | 293 K | kb:lab_ambient_temperature (E3) |
| viscosity | 0.001 Pa*s | kb:water_viscosity_293k (E3) |
| bead_diameter | 5 um | kb:tracer_diameter_measured (E2) |

## Stop criteria, declared before the run

- **planned_duration_reached** (complete): `simulated_time` >= 10000 s. the run ends at the planned record length, ten Brownian times; the relaxation time is read from the saved psi6 curve afterwards, because the plateau it is read against is not knowable during the run
- **step_displacement_diverged** (fault): `max_single_step_displacement` > 10 um. a particle moving more than a lattice constant in one step is a diverged integration; stop and keep the run, because divergence is a result

## Success criteria

- **converged_before_window**: `time_of_plateau_crossing` < 9000 s. in every seed of a cell psi6 reached the declared fraction of its plateau before the plateau window began, so the plateau was a plateau; a cell where it did not is reported not converged and its time is a lower bound, not a value
- **statistics_met**: `relative_standard_error_of_relaxation_time` <= 0.1. the seed-to-seed spread of the relaxation time, as a standard error of the cell mean, is inside the ten per cent the design asked for

## Cost

Wall clock 6000 s against 70000000000 particle-steps allowed; storage 0.06 GB. Envelope: inside -- target local: every cost number of this plan that lines up with a ceiling is under it: wall_clock_estimate against wall_clock_max, storage_estimate against storage_max. Re-confirmed at run time (4.6 O1).

## Rejected

- a timestep per sweep cell (the bounds carry varies_with): one step at the stiffest cell's bound keeps every cell under the same integrator settings, so a difference between cells cannot be an integrator difference; the cost of that choice is a factor of a few at the weak cells and the total still sits under the ceiling (grounds: particle_steps_total, particle_steps_max)
- the noise-step and Brownian-time bounds on the timestep: both are looser than the curvature bound at every cell of this sweep, so the curvature bound is the one that binds (grounds: dt_max_curvature, dt_max_noise, dt_max_brownian)
- more seeds than the statistics floor: ten per cent statistical error is met at nine seeds and the budget margin does not allow a decade more (grounds: n_seeds_min, particle_steps_total, particle_steps_max)
- bd_pairwise_driven_tracer: bd_pairwise_driven_tracer imposes a drive and this goal carries no `drive` selector; bd_pairwise is the configuration for an undriven question (grounds: drive_selectors_on_goal)

## Open risks

- The record is ten Brownian times. A 100-particle trial of the NumPy backend at the stiff corner ordered in three hundredths of a Brownian time, so the record is likely long rather than short; a cell whose crossing falls inside the plateau window is a lower bound and the first thing the result reports.
- The particle-step rate under the cost estimate is a guess about this workstation; the smoke run measures it, and the full sweep is not submitted until that measurement is in a card.
- Finite size is never absent here: the psi6 correlation length grows toward the box as the structure orders. The design margin is thirty spacings and its falsifier is a second box a factor of two larger giving the same time, which is a separate plan.
- The plateau fraction 0.9 is the design stage's convention until a person chooses one; the vocabulary's window field holds only the fit window, so this card carries the fraction as a condition.
- Nothing here is fitted to experimental data and no experimental counterpart exists for this observable; the anchor on the lab's particles is what would make one comparable.
- Temperature is a coordinate of the model and not a measurement of it: the integrator represents no velocity, so the declared value enters as the noise amplitude and cannot fail to be realised.
