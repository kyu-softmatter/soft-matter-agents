# Plan plan-sim-20260923-042-r2

*Generated from `v2_plan_simulation_sim-20260923-042.json`. The JSON is authoritative; editing this file changes nothing (P3).*

- **question** `sim-20260923-042`, revision 2, status `VALIDATED`
- **purpose** compare · **intent** explore · **compares** `box_length`
- **from** goal `goal-sim-20260923-042-r2` via synthesis `synthesis-sim-20260923-042-r2`
- **degraded** librarian_agent — S4 and S5 make no lookup; the axis cards did

## What is computed

**mean_squared_displacement** — The ensemble- and time-origin-averaged squared displacement of a particle centre as a function of lag time. The reported object is the curve on a declared lag grid; a single number is never this quantity.

*Estimator (from `contracts/observables.json`):* Unwrapped coordinates, so periodic images do not truncate the displacement. Average over particles and over time origins on a DECLARED lag grid. Overlapping time origins are NOT independent samples and an uncertainty that treats them as such is wrong; the count of independent origins is a declared condition. Report the curve, not a fitted scalar -- quantities derived from it are separate ids.

Configuration `abp_wca_2d` on `hoomd_backend`. Model: interacting active Brownian dynamics in two dimensions: one orientation per particle diffusing at D_R, self-propulsion v0 along it, translational noise D_T, WCA pair repulsion, periodic box, undriven.

## The arms

| arm | box_length | particles (derived from the held packing fraction) |
|---|---|---|
| small | 50 um | 10 1 |
| mid | 500 um | 1000 1 |

A third arm at 5000 um (100000 1 particles) was refused: 600,000,000,000 1 particle-steps against a ceiling of 70,000,000,000 1, and 6,000,000,000 1 stored coordinates against 1,000,000,000 1. See the S4 refusal card.

## Conditions held across the arms

| parameter | value | source | grade |
|---|---|---|---|
| `temperature` | 293 K | `kb:lab_ambient_temperature` | E3 |
| `viscosity` | 0.001 Pa*s | `kb:water_viscosity_293k` | E3 |
| `bead_diameter` | 5 um | `kb:tracer_diameter_measured` | E2 |
| `translational_diffusivity` | 0.09 um^2/s | `computed:stokes_einstein` | E4 |
| `rotational_diffusivity` | 0.01 1/s | `computed:stokes_einstein_debye` | E4 |
| `wca_epsilon` | 4e-21 J | `assumed:a_wca_stiffness` | E5 |
| `peclet_number_steric` | 10 1 | `assumed:a_operating_point` | E5 |
| `packing_fraction` | 0.1 1 | `assumed:a_operating_point` | E5 |
| `integration_timestep` | 0.005 s | `computed:decade_under_a1_ceiling` | E5 |
| `total_simulated_time` | 30000 s | `computed:window_over_record_ratio` | E5 |
| `save_interval` | 1 s | `computed:a4_ceiling` | E5 |
| `max_lag_time` | 3000 s | `computed:a4_floor` | E5 |
| `fit_lag_range_lower_bound` | 1000 s | `computed:a4_floor` | E5 |

## The windows

- the MSD curve runs to `max_lag_time` 3000 s, thirty persistence times (100 s each)
- the effective diffusivity is read above `fit_lag_range_lower_bound` 1000 s; read earlier it is D_T under that name
- frames every 1 s, two decades below the persistence time, so the crossover is resolved
- the record is 30000 s, so the longest lag is a share 0.1 1 of it

## Declared before the run

**Stop**

- `simulated_time` >= 30000 s — stop when the run reaches the planned duration; running longer would be a different plan
- `max_single_step_displacement` > 5 um — a particle moving more than its own diameter in one step has passed through a neighbour's core; the WCA force there is enormous and the integration has diverged. Stop and keep the run, because divergence is a result

**Success**

- `relative_block_error_of_effective_translational_diffusivity` <= 0.1 1 — in each arm the block-resampled error on the long-time slope is small enough that the decade is decided by the physics and not by the sampling
- `log10_ratio_of_effective_translational_diffusivity_mid_to_small` <= the target for `effective_translational_diffusivity`: 1 decade — the compare's question: the arm at ten persistence lengths and the arm at one agree within the goal's decade. Meeting it says the box does not matter at decade resolution between these two sizes; failing it says a persistence length of box is too small, and either is the result the question asked for
- `log10_ratio_of_first_half_to_second_half_effective_translational_diffusivity` <= the target for `effective_translational_diffusivity`: 1 decade — the long-time slope agrees with itself across the fit range: if it does not, the lower bound sits inside the crossover and the number is not the plateau under this name

## Envelope

Status **inside**, checked against `simulation_agent/envelope/budget.json`. target local: every cost number of this plan that lines up with a ceiling is under it: wall_clock_estimate against wall_clock_max, storage_estimate against storage_max. Re-confirmed at run time (4.6 O1).

Cost: 10 min of wall clock and 0.5 GB of disk for both arms, at an assumed rate of ten million particle-steps per second (`particle_step_rate`).

## Rejected

- **configuration abp_free** — the person ruled on 2026-09-23 that the repulsion is WCA, so the system is interacting; the free configuration is the closed-form reference and belongs in the store, not in this run. Its intersection is not empty and its cards stand as the record of what a free arm would need (grounds: `wca_epsilon`)
- **box arm 'large' at box_length_largest_arm** — exceeds A5's ceiling on particle_steps and coordinates_stored at the chosen point; dropped with a counterexample in the S4 refusal card, and the compare keeps the arms that fit (grounds: `particle_steps_arm_large`, `particle_steps_max`, `coordinates_stored_arm_large`, `coordinates_stored_max`)

## Open risks

- The compare has two arms and not three: the arm at a hundred persistence lengths exceeds both A5 ceilings at the intersection's operating point and is refused in v2_refusal_s4 with the numbers. So this plan can say whether one persistence length of box already suffices against ten; it cannot say where independence sets in above ten.
- The small arm holds of order ten particles. At that count the packing fraction is realised coarsely and the MSD's particle average is thin; A2's record floor carries its statistics, and the block error is what says whether that was enough.
- At decade resolution a finite-size effect of a few tens of per cent is a tie (P15). The person has not asked for confirm, so a pass on arms_agree_within_decade means the box does not change the decade, not that it changes nothing.
- dynamical_crossover_time is registered but not read by this plan: its window parameter is a slope threshold between 2 and 1 that no card carries, and S4 introduces no numbers. Declaring it is a revision.
- In this system D_R is tied to D_T through the sphere's rotational drag as a stated assumption; the store holds no rotational diffusivity entry. If the person rules D_R an independent axis the persistence time, and with it every window here, moves.
- The temperature is realised exactly by the noise amplitude and is not a measurement; kb:lab_ambient_temperature records why the value was chosen. The experiment's side of any later comparison carries the whole temperature uncertainty.
- Nothing runs until a person writes a plan_approval for this revision, and no backend for the active configuration exists yet: hoomd_backend integrates bd_overdamped. The backend that realises this plan is the next thing this agent writes, and it has to convert nothing -- the plan is already in SI (D7).
