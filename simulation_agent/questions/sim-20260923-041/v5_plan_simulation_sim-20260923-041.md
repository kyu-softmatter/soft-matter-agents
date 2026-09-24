# Plan plan-sim-20260923-041-r5

*Generated from `v5_plan_simulation_sim-20260923-041.json`. The JSON is authoritative; editing this file changes nothing (P3).*

- **question** `sim-20260923-041`, revision 5, status `VALIDATED`
- **purpose** characterize · **intent** explore · **sweep** over `peclet_number_steric` and `packing_fraction`
- **from** goal `goal-sim-20260923-041-r5` via synthesis `synthesis-sim-20260923-041-r5`
- **degraded** librarian_agent — S4 and S5 make no lookup; the axis cards did

## What is computed

**mean_squared_displacement** — The ensemble- and time-origin-averaged squared displacement of a particle centre as a function of lag time. The reported object is the curve on a declared lag grid; a single number is never this quantity.

*Estimator (from `contracts/observables.json`):* Unwrapped coordinates, so periodic images do not truncate the displacement. Average over particles and over time origins on a DECLARED lag grid. Overlapping time origins are NOT independent samples and an uncertainty that treats them as such is wrong; the count of independent origins is a declared condition. Report the curve, not a fitted scalar -- quantities derived from it are separate ids.

Configuration `abp_wca_2d` on `hoomd_backend`. Model: interacting active Brownian dynamics in two dimensions: one orientation per particle diffusing at D_R, self-propulsion v0 along it, translational noise D_T, WCA pair repulsion, periodic box, undriven.

## The grid

| cell | Pe | packing fraction | step | box | particles | particle-steps | run? |
|---|---|---|---|---|---|---|---|
| min_min | 1 1 | 0.01 1 | 0.005 s | 50 um | 1 1 | 6,000,000 1 | yes |
| min_mid | 1 1 | 0.1 1 | 0.005 s | 50 um | 10 1 | 60,000,000 1 | yes |
| min_max | 1 1 | 0.5 1 | 0.005 s | 50 um | 60 1 | 400,000,000 1 | yes |
| mid_min | 10 1 | 0.01 1 | 0.005 s | 500 um | 100 1 | 600,000,000 1 | yes |
| mid_mid | 10 1 | 0.1 1 | 0.005 s | 500 um | 1000 1 | 6,000,000,000 1 | yes |
| mid_max | 10 1 | 0.5 1 | 0.005 s | 50 um | 60 1 | 400,000,000 1 | yes |
| max_min | 100 1 | 0.01 1 | 0.01 s | 500 um | 100 1 | 300,000,000 1 | yes |
| max_mid | 100 1 | 0.1 1 | 0.001 s | 5000 um | 100000 1 | 3,000,000,000,000 1 | skipped |
| max_max | 100 1 | 0.5 1 | 0.001 s | 5000 um | 600000 1 | 20,000,000,000,000 1 | skipped |

Skipped cells exceed A5's ceilings at their own step and box; the S4 refusal card carries the counterexample and the alternatives.

## Conditions held across the grid

| parameter | value | source | grade |
|---|---|---|---|
| `temperature` | 293 K | `kb:lab_ambient_temperature` | E3 |
| `viscosity` | 0.001 Pa*s | `kb:water_viscosity_293k` | E3 |
| `bead_diameter` | 5 um | `kb:tracer_diameter_measured` | E2 |
| `translational_diffusivity` | 0.09 um^2/s | `computed:stokes_einstein` | E4 |
| `rotational_diffusivity` | 0.01 1/s | `computed:stokes_einstein_debye` | E4 |
| `wca_epsilon` | 4e-21 J | `assumed:a_wca_stiffness` | E5 |
| `total_simulated_time` | 30000 s | `computed:window_over_record_ratio` | E5 |
| `save_interval` | 1 s | `computed:a4_ceiling` | E5 |
| `max_lag_time` | 3000 s | `computed:a4_floor` | E5 |
| `fit_lag_range_lower_bound` | 1000 s | `computed:a4_floor` | E5 |

## The free expectation each cell is read against

- Pe 1 1: D_T + v0²/(2 D_R) = 0.2 um^2/s
- Pe 10 1: D_T + v0²/(2 D_R) = 10 um^2/s
- Pe 100 1: D_T + v0²/(2 D_R) = 1000 um^2/s

## Declared before the run

**Stop**

- `simulated_time` >= 30000 s — stop when the run reaches the planned duration; running longer would be a different plan
- `max_single_step_displacement` > 5 um — a particle moving more than its own diameter in one step has passed through a neighbour's core; stop and keep the run, because divergence is a result

**Success**

- `relative_block_error_of_effective_translational_diffusivity` <= 0.1 1 — in each cell the block-resampled error on the long-time slope is small enough that the decade is decided by the physics
- `log10_ratio_of_effective_translational_diffusivity_to_free_expectation_at_this_peclet` <= the target for `effective_translational_diffusivity`: 1 decade — the question's own criterion: the interacting cell agrees with the free active particle's closed-form long-time diffusivity at its Peclet number within the goal's decade. Meeting it says interactions do not change the decade there; failing it is the qualitatively different regime the question asked whether density produces, and either is the result
- `log10_ratio_of_first_half_to_second_half_effective_translational_diffusivity` <= the target for `effective_translational_diffusivity`: 1 decade — the long-time slope agrees with itself across the fit range; if not, the lower bound sits inside the crossover and the number is not the plateau

## Envelope

Status **inside**, checked against `simulation_agent/envelope/budget.json`. target local: every cost number of this plan that lines up with a ceiling is under it: wall_clock_estimate against wall_clock_max, storage_estimate against storage_max. Re-confirmed at run time (4.6 O1).

Cost: 800 s of wall clock and 0.6 GB of disk for the kept cells, at an assumed rate of ten million particle-steps per second (`particle_step_rate`).

## Rejected

- **configuration abp_free** — the person ruled on 2026-09-23 that the repulsion is WCA; the free configuration is the closed-form reference the interacting results are read against and belongs in the store, not in this run. Its cards stand as the record of what a free arm would need (grounds: `wca_epsilon`)
- **grid cell max_mid** — exceeds A5's ceiling on particle_steps and coordinates_stored at the cell's own step and box; skipped, and the plan's sweep records the empty cell with this reason (grounds: `particle_steps_max_mid`, `particle_steps_max`, `coordinates_stored_max_mid`, `coordinates_stored_max`)
- **grid cell max_max** — exceeds A5's ceiling on particle_steps and coordinates_stored at the cell's own step and box; skipped, and the plan's sweep records the empty cell with this reason (grounds: `particle_steps_max_max`, `particle_steps_max`, `coordinates_stored_max_max`, `coordinates_stored_max`)

## Open risks

- The Pe 100, phi 0.01 cell runs by the person's ruling of 2026-09-23 with the step at A1's ceiling and a box of ONE persistence length. The box rests on the box compare's measurement (question 042 of this seat) at Pe 10 and phi 0.1, where one and ten persistence lengths agreed to 3 per cent; at Pe 100 that is an assumption, and this cell is its first test. If its effective diffusivity departs from the free expectation by more than the Pe 10 cells did, the box and not the physics is the first suspect.
- Three of the nine cells are skipped -- the whole Pe 100 row -- because at that level the step is a decade under a millisecond-scale ceiling and the box is five millimetres, so even the dilute cell costs 3e11 particle-steps against a ceiling of 7e10. The S4 refusal card says which single cell would fit at A1's ceiling rather than a decade under it, and why the margin is not owed where the self-propulsion step binds. So this plan characterises Pe 1 and 10 and says nothing about Pe 100 until the person raises a ceiling or accepts the ceiling step.
- The step and the box differ between points along the Peclet axis because A1 and A3 marked those bounds varies_with peclet_number_steric. They are not sweep axes; they are functions of one. The schema's invariant is read here as 'shared except the axes and what the axes determine', and if that reading is refused the plan is wrong and not the invariant.
- The wall-clock estimate rests on A5's assumed rate of ten million particle-steps per second. The small arm of the box compare (question 042 of this seat) measured 8e5 per second at 13 particles and a trial at a thousand particles measured 3.5e6, so the estimates here are three to ten times low and the densest kept cell (Pe 10, phi 0.5, 6000 particles, 4e10 particle-steps) may run three hours against a two-hour ceiling. The operator's gate reads the plan's rate and will not catch it; a_cost_reference's falsifier needs a trajectory-writing run, and gsd is not in the sim environment, so it has not fired. The person should know before the densest cell is started.
- The sparsest cell, Pe 1 and phi 0.01, holds one particle in a box of one persistence length. Its MSD is one particle's, its packing fraction is realised as one particle, and its block error cannot be formed (fewer than two blocks). It is kept because the grid is the question and an empty cell would have to say why; its result card will say what a single particle can and cannot support.
- The free-particle expectation each cell is compared against is D_T + v0^2/(2 D_R), a literature relation applied to this plan's inputs and not a store entry; the librarian holds nothing on active matter yet (kb_gaps). Entering it is the librarian's, and until then the comparison rests on a relation this plan wrote down.
- In the free arm the ballistic slope is not resolvable below Pe_thermal of about 20 (window 3's measurement), which is Pe_steric about 12 in this SED-tied system; the Pe 1 row therefore shows no ballistic regime in the reference and the crossover observables there are about the interacting system alone.
- D_R is tied to D_T through the sphere's rotational drag as a stated assumption; the store holds no rotational diffusivity entry. The persistence time and every window here move with it.
- No plan_approval exists and none is needed at tier 1; each cell runs autonomously once inside the envelope. No trajectory is written while gsd is absent from the sim environment, and each run's meta says so.
