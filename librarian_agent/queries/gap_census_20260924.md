# Gap census, 2026-09-24

What callers asked the store for and did not get, sorted by what closing it
takes. Written by `librarian-20260924-2` at the person's request.

**Pinned.** Every count here was taken from one run on `queries/log.jsonl` at
1084 lines (last line 2026-09-24T19:01:26Z), with the store at
`kbv-49c19f9565f8`, the entries committed at `440d999`. The counts are true of
that log and store and of nothing later: re-count off a run, not off this
file. "Questions" means distinct qids. Self-test callers are excluded, and so
are names the server correctly answered `in_published_table` (device_registry,
control_channel, read_back, automatable_condition, optical_path_valid_tuples,
immersion) -- those are not gaps, the table exists and the caller was sent to
it.

**What this is not.** It is editorial: it decides what to look for next and
must never shape an answer. `query_log.py` deliberately has no function that
reads the log by observable or count, so the server cannot rank by popularity
(4.3.1 rule 4). This census was a one-off script outside the tree for that
reason. Whether a census tool should exist in `src/` is manager-librarian's
call, not this seat's.

## A. The store holds it, under a name the caller did not use

Cheapest to close: an added `subject` or number on an existing entry, no new
source. Each is an entry edit and so moves `kb_version`.

| asked as | questions / asks | what the store has | the edit |
|---|---|---|---|
| `tracer_number_density` | 3 / 17 | `tracer_number_density_from_diameter`, a formula, answering to its id and `abvigen_product_number_density` | **not a plain subject edit.** Its handles were named `abvigen_` on purpose: it is a fact about the product type, and "this bottle is that product" is a separate claim at E5. A `tracer_` handle would assert the join in a string nothing checks, the same reason the emission row below is refused. The honest fix is for the gap to say `nearest`, or for the join to be its own entry. And it gives the as-supplied stock; the sample's density after dilution is the experiment's |
| `magnification` | 3 / 10 | six objective entries answering to `4x`, `100x`..., carrying `na` and `working_distance` as numbers but no magnification number | add a `magnification` number to each, from the Nikon catalogue already cited |
| `sensor_active_area` | 3 / 10 | `camera_sensor_geometry`, whose prose says 15.6 by 15.6 mm; the number is not in `numbers[]` | add it as a number, **after** confirming the 15.6 mm is the datasheet's statement and not a product computed in prose -- the source record says the PDF itself has not been read |
| `numerical_aperture` | 2 / 7 | objectives answer to `na` | lowest priority: `near` returns `na`, last asked 2026-09-21. A synonym handle is a matching-policy change (case only, by design), so it goes up rather than being done here |
| `sample_heating_rate` | 3 / 8 | `trap_heating_detection_bound`, answering to `temperature` and `trapping` | partial at best: it is a bound on what could be detected, not a rate. A subject would mislead; leave the gap and say `nearest` |

## B. Findable in documents, as new E3 entries

| asked as | questions / asks | where to look |
|---|---|---|
| `disk_period` | 3 / 10 | the store has the constraint (`csuw1_disk_speed_exposure_constraint`, no number) and not the speed. The vendor range is a document; the speed actually set is a device property, so the value in use is read off the instrument, not entered |
| `light_engine_output_power`, `light_engine_channel_sets` | 2 / 2 each | the light engine's own specification sheet. Not `lunf_per_line_power_is_not_transmittable`, which is the laser combiner |
| `mean_squared_displacement` | 3 / 15 | textbook: a formula entry, 2dDt for free diffusion in d dimensions, with its validity (free, overdamped, no confinement) |
| `rotational_diffusivity`, `persistence_time` | 2 / 3, 1 / 1 | textbook: Stokes-Einstein-Debye, and the persistence time that follows from it |
| `trap_potential_width` | 1 / 2 | textbook, harmonic trap width from stiffness and temperature. Useless without a stiffness -- see C |
| `structural_relaxation_time` (2D Yukawa) | 1 / 3 | peer-reviewed simulation literature, conditions named; `condition_mismatch` is the likely honest answer |

## C. Needs a measurement on this instrument or this computer

No document closes these. They arrive as a result card from an execution
agent, or as a person's calibration with a validity period.

| asked as | questions / asks | note |
|---|---|---|
| `trap_stiffness` | **4 / 22, both agents** | the largest gap in the log and the only one both agents are stuck on. It depends on the objective (`objective_change_invalidates_trap_calibration`), so it is a calibration per objective, not one number |
| `particle_step_rate` + `cost_per_particle_step_overdamped` + `cost_per_particle_step_yukawa_2d` | 5 / 17, 1 / 3, 1 / 2 | one question under three names: this computer's simulation throughput. A benchmark run by the simulation agent closes all three |
| `emission_wavelength` | 3 / 11 | **not a naming fix, though it looks like one.** `near` offers `abvigen_product_emission_wavelength`, which is `tracer_emission_peak` -- the supplier's 680 nm, refuted on this bench and in the prior project, and named for the product type precisely so that a query for our tracer does not land on it. Routing this name there would hand a disproved number to the caller most likely to use it. What the store does hold is `particles_show_on_the_green_605_path` (E2): the particles show through a band centred near 605 nm, an instrument band and not a spectrum. The tracer's emission as a number needs a spectral measurement. Whether `emission_wavelength` should reach the E2 observation is a separate question for the next seat to weigh |
| `bleaching_rate`, `tracer_brightness`, `background_rate`, `localisation_error`, `photodamage_threshold` | 3 each; 19, 11, 9, 15, 8 asks | the supplier's own optical figures for the tracer are refuted (`abvigen_published_data_is_unreliable`), so its literature cannot supply these |
| `drift_rate`, `settling_time`, `focus_drift`, `stage_drift`, `thermal_equilibration`, `pfs`/`perfect_focus` | 2-3 each | a stability run on the stand |
| `working_height_above_coverslip` | 2 / 6 | a trap-height measurement, or the person |
| `trap_escape_force`, `trapped_particle_drag_offset` | 1 / 4, 1 / 9 | follow from `trap_stiffness`; they close when it does |

## D. Not knowledge: the asking agent's own choice

The `absent` answers here are correct, and entering a number would put the
caller's judgement into the store as if it were a fact. What the card owes is
an assumption naming the gap (check 39). Worth telling manager-simulation that
most of the simulation's gaps are this kind, because each costs a call and
comes back the same.

`integration_timestep_resolution_factor` (6 questions / 21 asks -- the most
asked name in the log), `plateau_factor`, `lag_coverage_factor`,
`window_span_factor`, `lag_to_record_ratio`, `independent_samples_prefactor`,
`box_margin_factor`, `save_interval_fraction_of_relaxation_time`,
`save_interval_fraction_of_brownian_time`, `psi6_finite_size_margin`,
`psi6_plateau_fraction`, `relaxation_fit_window_frames`,
`statistical_target_confirm`, `statistical_target_explore`,
`mean_spacing_over_diameter`, `noise_step_fraction_of_screening_length`,
`yukawa_coupling_sweep_range`, `packing_fraction` (2 / 25), `flow_speed`
(2 / 26), `driving_velocity`, `camera_exposure_time` (asked by the
simulation), `target_relative_error`, `required_resolution`.

The one exception worth considering: a timestep rule of thumb relative to
the fastest relaxation time is a textbook statement and could enter as one,
with the caller still choosing the factor.

## E. For the person

`schedule`, `session_duration`, `session_time_budget`,
`instrument_availability_window` -- when the instrument is available is not
in any document. `widefield_source_a` and `lapp_branch_assignment` look like
registry questions (which physical source a label means) and should be
checked against the device table before asking.

## Closed since asked

Answered by the store at `kbv-49c19f9565f8` though they came back empty when
asked: `refractive_index`, `read_noise`, `quantum_efficiency`, `pixel_size`,
`tracer_diffusivity_expected`, `tau_d`, `stand_ti2e_lock_groups`,
`temperature_stability`. Nothing to do.
