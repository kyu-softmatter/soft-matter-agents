# The map of the store

For each subject page: how many of its entries are known each way, how many are disputed, and which pages share entries with it.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

The same relations, as data for the console to draw: [map.json](../wiki/map.json).

## Kinds of evidence

- E1: measured on this instrument
- E2: calibrated on this instrument
- E3: from a document, a reading off the instrument, or another project's record
- E4: computed
- E5: recalled or assumed
- disputed: refuted, superseded or in conflict

## Device pages

| page | E1 | E2 | E3 | E4 | E5 | disputed | shares entries with |
|---|---|---|---|---|---|---|---|
| [camera_blue](../wiki/device_camera_blue.md) | 0 | 0 | 3 | 0 | 2 | 0 | [device camera_red](../wiki/device_camera_red.md), [device csuw1_port](../wiki/device_csuw1_port.md), [device filter_wheel_em1](../wiki/device_filter_wheel_em1.md), [device filter_wheel_em2](../wiki/device_filter_wheel_em2.md), [quantity full_scale_count](../wiki/quantity_full_scale_count.md) |
| [camera_red](../wiki/device_camera_red.md) | 5 | 0 | 12 | 0 | 4 | 1 | [device camera_blue](../wiki/device_camera_blue.md), [device confocal_csuw1](../wiki/device_confocal_csuw1.md), [device csuw1_port](../wiki/device_csuw1_port.md), [device filter_wheel_em1](../wiki/device_filter_wheel_em1.md), [device filter_wheel_em2](../wiki/device_filter_wheel_em2.md), [device laser_combiner](../wiki/device_laser_combiner.md), [device optical_tweezers](../wiki/device_optical_tweezers.md), [quantity full_scale_count](../wiki/quantity_full_scale_count.md), [quantity pixel_size](../wiki/quantity_pixel_size.md), [quantity quantum_efficiency](../wiki/quantity_quantum_efficiency.md), [quantity read_noise](../wiki/quantity_read_noise.md) |
| [confocal_csuw1](../wiki/device_confocal_csuw1.md) | 1 | 0 | 3 | 0 | 0 | 0 | [device camera_red](../wiki/device_camera_red.md), [device csuw1_disk_speed](../wiki/device_csuw1_disk_speed.md), [device laser_combiner](../wiki/device_laser_combiner.md) |
| [csuw1_dichroic](../wiki/device_csuw1_dichroic.md) | 0 | 0 | 1 | 0 | 0 | 0 | none |
| [csuw1_disk_position](../wiki/device_csuw1_disk_position.md) | 0 | 0 | 2 | 0 | 0 | 0 | none |
| [csuw1_disk_speed](../wiki/device_csuw1_disk_speed.md) | 1 | 0 | 3 | 0 | 0 | 0 | [device confocal_csuw1](../wiki/device_confocal_csuw1.md) |
| [csuw1_port](../wiki/device_csuw1_port.md) | 0 | 0 | 3 | 0 | 0 | 0 | [device camera_blue](../wiki/device_camera_blue.md), [device camera_red](../wiki/device_camera_red.md) |
| [csuw1_shutter](../wiki/device_csuw1_shutter.md) | 1 | 0 | 1 | 0 | 0 | 0 | none |
| [dia_lamp](../wiki/device_dia_lamp.md) | 1 | 0 | 0 | 0 | 0 | 0 | none |
| [filter_turret_1](../wiki/device_filter_turret_1.md) | 1 | 0 | 2 | 0 | 1 | 0 | [device filter_turret_2](../wiki/device_filter_turret_2.md), [device lapp_branch](../wiki/device_lapp_branch.md), [device light_path_port](../wiki/device_light_path_port.md), [device nosepiece](../wiki/device_nosepiece.md), [device stand_ti2e](../wiki/device_stand_ti2e.md) |
| [filter_turret_2](../wiki/device_filter_turret_2.md) | 1 | 0 | 1 | 0 | 1 | 0 | [device filter_turret_1](../wiki/device_filter_turret_1.md), [device lapp_branch](../wiki/device_lapp_branch.md), [device light_path_port](../wiki/device_light_path_port.md), [device nosepiece](../wiki/device_nosepiece.md), [device stand_ti2e](../wiki/device_stand_ti2e.md) |
| [filter_wheel_em1](../wiki/device_filter_wheel_em1.md) | 0 | 0 | 0 | 0 | 1 | 0 | [device camera_blue](../wiki/device_camera_blue.md), [device camera_red](../wiki/device_camera_red.md), [device filter_wheel_em2](../wiki/device_filter_wheel_em2.md) |
| [filter_wheel_em2](../wiki/device_filter_wheel_em2.md) | 0 | 0 | 0 | 0 | 1 | 0 | [device camera_blue](../wiki/device_camera_blue.md), [device camera_red](../wiki/device_camera_red.md), [device filter_wheel_em1](../wiki/device_filter_wheel_em1.md) |
| [intermediate_magnification](../wiki/device_intermediate_magnification.md) | 1 | 0 | 0 | 0 | 0 | 0 | [device stand_ti2e](../wiki/device_stand_ti2e.md) |
| [lapp_branch](../wiki/device_lapp_branch.md) | 2 | 0 | 1 | 0 | 0 | 0 | [device filter_turret_1](../wiki/device_filter_turret_1.md), [device filter_turret_2](../wiki/device_filter_turret_2.md), [device light_path_port](../wiki/device_light_path_port.md), [device nosepiece](../wiki/device_nosepiece.md), [device stand_ti2e](../wiki/device_stand_ti2e.md) |
| [laser_combiner](../wiki/device_laser_combiner.md) | 1 | 9 | 10 | 9 | 1 | 0 | [device camera_red](../wiki/device_camera_red.md), [device confocal_csuw1](../wiki/device_confocal_csuw1.md), [device laser_shutter](../wiki/device_laser_shutter.md), [device line_power](../wiki/device_line_power.md), [device line_select](../wiki/device_line_select.md), [quantity illumination_power](../wiki/quantity_illumination_power.md) |
| [laser_shutter](../wiki/device_laser_shutter.md) | 0 | 0 | 3 | 0 | 1 | 0 | [device laser_combiner](../wiki/device_laser_combiner.md), [device line_power](../wiki/device_line_power.md), [device line_select](../wiki/device_line_select.md) |
| [light_path_port](../wiki/device_light_path_port.md) | 1 | 0 | 2 | 0 | 0 | 0 | [device filter_turret_1](../wiki/device_filter_turret_1.md), [device filter_turret_2](../wiki/device_filter_turret_2.md), [device lapp_branch](../wiki/device_lapp_branch.md), [device nosepiece](../wiki/device_nosepiece.md), [device optical_tweezers](../wiki/device_optical_tweezers.md), [device stand_ti2e](../wiki/device_stand_ti2e.md) |
| [line_power](../wiki/device_line_power.md) | 0 | 0 | 3 | 0 | 0 | 0 | [device laser_combiner](../wiki/device_laser_combiner.md), [device laser_shutter](../wiki/device_laser_shutter.md), [device line_select](../wiki/device_line_select.md) |
| [line_select](../wiki/device_line_select.md) | 1 | 0 | 5 | 0 | 1 | 0 | [device laser_combiner](../wiki/device_laser_combiner.md), [device laser_shutter](../wiki/device_laser_shutter.md), [device line_power](../wiki/device_line_power.md) |
| [motor_stage](../wiki/device_motor_stage.md) | 0 | 0 | 1 | 0 | 0 | 0 | [device stand_ti2e](../wiki/device_stand_ti2e.md) |
| [nosepiece](../wiki/device_nosepiece.md) | 1 | 12 | 20 | 12 | 1 | 22 | [configuration trapping](../wiki/configuration_trapping.md), [device filter_turret_1](../wiki/device_filter_turret_1.md), [device filter_turret_2](../wiki/device_filter_turret_2.md), [device lapp_branch](../wiki/device_lapp_branch.md), [device light_path_port](../wiki/device_light_path_port.md), [device optical_tweezers](../wiki/device_optical_tweezers.md), [device stand_ti2e](../wiki/device_stand_ti2e.md), [device z_drive](../wiki/device_z_drive.md), [quantity coverslip_thickness](../wiki/quantity_coverslip_thickness.md), [quantity na](../wiki/quantity_na.md), [quantity pixel_size](../wiki/quantity_pixel_size.md) |
| [optical_tweezers](../wiki/device_optical_tweezers.md) | 0 | 4 | 46 | 3 | 5 | 2 | [configuration trapping](../wiki/configuration_trapping.md), [device camera_red](../wiki/device_camera_red.md), [device light_path_port](../wiki/device_light_path_port.md), [device nosepiece](../wiki/device_nosepiece.md), [device stand_ti2e](../wiki/device_stand_ti2e.md), [device z_drive](../wiki/device_z_drive.md), [quantity illumination_power](../wiki/quantity_illumination_power.md), [quantity temperature](../wiki/quantity_temperature.md) |
| [pfs](../wiki/device_pfs.md) | 0 | 0 | 1 | 0 | 1 | 0 | none |
| [piezo_stage](../wiki/device_piezo_stage.md) | 9 | 0 | 15 | 0 | 1 | 2 | none |
| [stand_ti2e](../wiki/device_stand_ti2e.md) | 4 | 0 | 13 | 0 | 0 | 0 | [device filter_turret_1](../wiki/device_filter_turret_1.md), [device filter_turret_2](../wiki/device_filter_turret_2.md), [device intermediate_magnification](../wiki/device_intermediate_magnification.md), [device lapp_branch](../wiki/device_lapp_branch.md), [device light_path_port](../wiki/device_light_path_port.md), [device motor_stage](../wiki/device_motor_stage.md), [device nosepiece](../wiki/device_nosepiece.md), [device optical_tweezers](../wiki/device_optical_tweezers.md), [device z_drive](../wiki/device_z_drive.md) |
| [temperature_stage](../wiki/device_temperature_stage.md) | 0 | 0 | 1 | 0 | 0 | 0 | none |
| [z_drive](../wiki/device_z_drive.md) | 0 | 0 | 2 | 0 | 0 | 0 | [device nosepiece](../wiki/device_nosepiece.md), [device optical_tweezers](../wiki/device_optical_tweezers.md), [device stand_ti2e](../wiki/device_stand_ti2e.md) |

## Quantity pages

| page | E1 | E2 | E3 | E4 | E5 | disputed | shares entries with |
|---|---|---|---|---|---|---|---|
| [active_energy](../wiki/quantity_active_energy.md) | 0 | 0 | 1 | 0 | 0 | 0 | [quantity active_fraction](../wiki/quantity_active_fraction.md), [quantity packing_fraction](../wiki/quantity_packing_fraction.md), [quantity peclet_number_steric](../wiki/quantity_peclet_number_steric.md) |
| [active_fraction](../wiki/quantity_active_fraction.md) | 0 | 0 | 2 | 0 | 0 | 0 | [quantity active_energy](../wiki/quantity_active_energy.md), [quantity packing_fraction](../wiki/quantity_packing_fraction.md), [quantity peclet_number_steric](../wiki/quantity_peclet_number_steric.md) |
| [ambient_temperature](../wiki/quantity_ambient_temperature.md) | 0 | 0 | 3 | 0 | 2 | 0 | [quantity temperature](../wiki/quantity_temperature.md) |
| [coverslip_thickness](../wiki/quantity_coverslip_thickness.md) | 0 | 0 | 2 | 0 | 0 | 0 | [device nosepiece](../wiki/device_nosepiece.md) |
| [crystallite_particle_count](../wiki/quantity_crystallite_particle_count.md) | 0 | 0 | 2 | 0 | 0 | 0 | [quantity like_to_unlike_attraction_ratio](../wiki/quantity_like_to_unlike_attraction_ratio.md), [quantity reduced_temperature](../wiki/quantity_reduced_temperature.md) |
| [depletant_to_colloid_radius_ratio](../wiki/quantity_depletant_to_colloid_radius_ratio.md) | 0 | 0 | 2 | 0 | 0 | 0 | [quantity depletant_volume_fraction](../wiki/quantity_depletant_volume_fraction.md), [quantity lobe_compression_ratio](../wiki/quantity_lobe_compression_ratio.md), [quantity patch_protrusion_ratio](../wiki/quantity_patch_protrusion_ratio.md) |
| [depletant_volume_fraction](../wiki/quantity_depletant_volume_fraction.md) | 0 | 0 | 2 | 0 | 0 | 0 | [quantity depletant_to_colloid_radius_ratio](../wiki/quantity_depletant_to_colloid_radius_ratio.md), [quantity lobe_compression_ratio](../wiki/quantity_lobe_compression_ratio.md), [quantity patch_protrusion_ratio](../wiki/quantity_patch_protrusion_ratio.md) |
| [depth_of_field](../wiki/quantity_depth_of_field.md) | 0 | 0 | 0 | 1 | 0 | 0 | none |
| [dipolar_coupling_strength](../wiki/quantity_dipolar_coupling_strength.md) | 0 | 0 | 5 | 0 | 0 | 0 | [quantity packing_fraction](../wiki/quantity_packing_fraction.md), [quantity reduced_active_force](../wiki/quantity_reduced_active_force.md) |
| [dna_strand_fraction](../wiki/quantity_dna_strand_fraction.md) | 0 | 0 | 1 | 0 | 0 | 0 | none |
| [emission_peak_wavelength](../wiki/quantity_emission_peak_wavelength.md) | 0 | 0 | 3 | 0 | 0 | 1 | none |
| [excitation_peak_wavelength](../wiki/quantity_excitation_peak_wavelength.md) | 0 | 0 | 3 | 0 | 0 | 1 | none |
| [full_scale_count](../wiki/quantity_full_scale_count.md) | 0 | 0 | 1 | 0 | 1 | 0 | [device camera_blue](../wiki/device_camera_blue.md), [device camera_red](../wiki/device_camera_red.md) |
| [hexatic_correlation_exponent](../wiki/quantity_hexatic_correlation_exponent.md) | 0 | 0 | 1 | 0 | 0 | 0 | [quantity hexatic_order_parameter](../wiki/quantity_hexatic_order_parameter.md) |
| [hexatic_order_parameter](../wiki/quantity_hexatic_order_parameter.md) | 0 | 0 | 3 | 0 | 0 | 0 | [quantity hexatic_correlation_exponent](../wiki/quantity_hexatic_correlation_exponent.md) |
| [illumination_power](../wiki/quantity_illumination_power.md) | 0 | 13 | 2 | 12 | 0 | 0 | [device laser_combiner](../wiki/device_laser_combiner.md), [device optical_tweezers](../wiki/device_optical_tweezers.md) |
| [like_to_unlike_attraction_ratio](../wiki/quantity_like_to_unlike_attraction_ratio.md) | 0 | 0 | 3 | 0 | 0 | 0 | [quantity crystallite_particle_count](../wiki/quantity_crystallite_particle_count.md), [quantity packing_fraction](../wiki/quantity_packing_fraction.md), [quantity reduced_temperature](../wiki/quantity_reduced_temperature.md) |
| [lobe_compression_ratio](../wiki/quantity_lobe_compression_ratio.md) | 0 | 0 | 6 | 0 | 0 | 0 | [quantity depletant_to_colloid_radius_ratio](../wiki/quantity_depletant_to_colloid_radius_ratio.md), [quantity depletant_volume_fraction](../wiki/quantity_depletant_volume_fraction.md), [quantity packing_fraction](../wiki/quantity_packing_fraction.md), [quantity patch_protrusion_ratio](../wiki/quantity_patch_protrusion_ratio.md), [quantity reduced_temperature](../wiki/quantity_reduced_temperature.md) |
| [na](../wiki/quantity_na.md) | 0 | 0 | 6 | 0 | 0 | 0 | [device nosepiece](../wiki/device_nosepiece.md) |
| [packing_fraction](../wiki/quantity_packing_fraction.md) | 0 | 0 | 18 | 0 | 0 | 0 | [quantity active_energy](../wiki/quantity_active_energy.md), [quantity active_fraction](../wiki/quantity_active_fraction.md), [quantity dipolar_coupling_strength](../wiki/quantity_dipolar_coupling_strength.md), [quantity like_to_unlike_attraction_ratio](../wiki/quantity_like_to_unlike_attraction_ratio.md), [quantity lobe_compression_ratio](../wiki/quantity_lobe_compression_ratio.md), [quantity pair_well_depth](../wiki/quantity_pair_well_depth.md), [quantity patch_protrusion_ratio](../wiki/quantity_patch_protrusion_ratio.md), [quantity peclet_number_shear](../wiki/quantity_peclet_number_shear.md), [quantity peclet_number_steric](../wiki/quantity_peclet_number_steric.md), [quantity reduced_active_force](../wiki/quantity_reduced_active_force.md), [quantity reduced_temperature](../wiki/quantity_reduced_temperature.md), [quantity shear_strain](../wiki/quantity_shear_strain.md) |
| [pair_well_depth](../wiki/quantity_pair_well_depth.md) | 0 | 0 | 3 | 0 | 0 | 0 | [quantity packing_fraction](../wiki/quantity_packing_fraction.md), [quantity peclet_number_shear](../wiki/quantity_peclet_number_shear.md) |
| [patch_protrusion_ratio](../wiki/quantity_patch_protrusion_ratio.md) | 0 | 0 | 5 | 0 | 0 | 0 | [quantity depletant_to_colloid_radius_ratio](../wiki/quantity_depletant_to_colloid_radius_ratio.md), [quantity depletant_volume_fraction](../wiki/quantity_depletant_volume_fraction.md), [quantity lobe_compression_ratio](../wiki/quantity_lobe_compression_ratio.md), [quantity packing_fraction](../wiki/quantity_packing_fraction.md), [quantity reduced_temperature](../wiki/quantity_reduced_temperature.md) |
| [peclet_number_shear](../wiki/quantity_peclet_number_shear.md) | 0 | 0 | 2 | 0 | 0 | 0 | [quantity packing_fraction](../wiki/quantity_packing_fraction.md), [quantity pair_well_depth](../wiki/quantity_pair_well_depth.md), [quantity shear_strain](../wiki/quantity_shear_strain.md) |
| [peclet_number_steric](../wiki/quantity_peclet_number_steric.md) | 0 | 0 | 2 | 0 | 0 | 0 | [quantity active_energy](../wiki/quantity_active_energy.md), [quantity active_fraction](../wiki/quantity_active_fraction.md), [quantity packing_fraction](../wiki/quantity_packing_fraction.md) |
| [pixel_size](../wiki/quantity_pixel_size.md) | 0 | 12 | 1 | 11 | 1 | 22 | [device camera_red](../wiki/device_camera_red.md), [device nosepiece](../wiki/device_nosepiece.md) |
| [quantum_efficiency](../wiki/quantity_quantum_efficiency.md) | 0 | 0 | 2 | 0 | 0 | 0 | [device camera_red](../wiki/device_camera_red.md) |
| [read_noise](../wiki/quantity_read_noise.md) | 0 | 0 | 4 | 0 | 0 | 0 | [device camera_red](../wiki/device_camera_red.md) |
| [reduced_active_force](../wiki/quantity_reduced_active_force.md) | 0 | 0 | 5 | 0 | 0 | 0 | [quantity dipolar_coupling_strength](../wiki/quantity_dipolar_coupling_strength.md), [quantity packing_fraction](../wiki/quantity_packing_fraction.md), [quantity reduced_number_density](../wiki/quantity_reduced_number_density.md) |
| [reduced_number_density](../wiki/quantity_reduced_number_density.md) | 0 | 0 | 1 | 0 | 0 | 0 | [quantity reduced_active_force](../wiki/quantity_reduced_active_force.md) |
| [reduced_temperature](../wiki/quantity_reduced_temperature.md) | 0 | 0 | 4 | 0 | 0 | 0 | [quantity crystallite_particle_count](../wiki/quantity_crystallite_particle_count.md), [quantity like_to_unlike_attraction_ratio](../wiki/quantity_like_to_unlike_attraction_ratio.md), [quantity lobe_compression_ratio](../wiki/quantity_lobe_compression_ratio.md), [quantity packing_fraction](../wiki/quantity_packing_fraction.md), [quantity patch_protrusion_ratio](../wiki/quantity_patch_protrusion_ratio.md) |
| [refractive_index](../wiki/quantity_refractive_index.md) | 0 | 0 | 17 | 0 | 0 | 3 | none |
| [shear_strain](../wiki/quantity_shear_strain.md) | 0 | 0 | 1 | 0 | 0 | 0 | [quantity packing_fraction](../wiki/quantity_packing_fraction.md), [quantity peclet_number_shear](../wiki/quantity_peclet_number_shear.md) |
| [storage_temperature_max](../wiki/quantity_storage_temperature_max.md) | 0 | 0 | 2 | 0 | 0 | 0 | [quantity storage_temperature_min](../wiki/quantity_storage_temperature_min.md) |
| [storage_temperature_min](../wiki/quantity_storage_temperature_min.md) | 0 | 0 | 2 | 0 | 0 | 0 | [quantity storage_temperature_max](../wiki/quantity_storage_temperature_max.md) |
| [tau_d](../wiki/quantity_tau_d.md) | 0 | 0 | 0 | 1 | 0 | 0 | none |
| [temperature](../wiki/quantity_temperature.md) | 0 | 0 | 3 | 1 | 3 | 0 | [configuration trapping](../wiki/configuration_trapping.md), [device optical_tweezers](../wiki/device_optical_tweezers.md), [observable tracer_diffusivity](../wiki/observable_tracer_diffusivity.md), [quantity ambient_temperature](../wiki/quantity_ambient_temperature.md) |
| [viscosity](../wiki/quantity_viscosity.md) | 0 | 0 | 1 | 0 | 0 | 0 | none |

## Observable pages

| page | E1 | E2 | E3 | E4 | E5 | disputed | shares entries with |
|---|---|---|---|---|---|---|---|
| [bleach_recovery_diffusivity](../wiki/observable_bleach_recovery_diffusivity.md) | 0 | 0 | 0 | 0 | 0 | 0 | none |
| [bleaching_rate](../wiki/observable_bleaching_rate.md) | 0 | 0 | 0 | 0 | 0 | 0 | none |
| [dynamical_crossover_time](../wiki/observable_dynamical_crossover_time.md) | 0 | 0 | 0 | 0 | 0 | 0 | none |
| [effective_translational_diffusivity](../wiki/observable_effective_translational_diffusivity.md) | 0 | 0 | 0 | 0 | 0 | 0 | none |
| [interwell_barrier_height](../wiki/observable_interwell_barrier_height.md) | 0 | 0 | 0 | 0 | 0 | 0 | none |
| [interwell_transition_rate](../wiki/observable_interwell_transition_rate.md) | 0 | 0 | 0 | 0 | 0 | 0 | none |
| [mean_squared_displacement](../wiki/observable_mean_squared_displacement.md) | 0 | 0 | 0 | 0 | 0 | 0 | none |
| [msd_loglog_slope](../wiki/observable_msd_loglog_slope.md) | 0 | 0 | 0 | 0 | 0 | 0 | none |
| [persistence_length](../wiki/observable_persistence_length.md) | 0 | 0 | 0 | 0 | 0 | 0 | none |
| [persistence_time](../wiki/observable_persistence_time.md) | 0 | 0 | 0 | 0 | 0 | 0 | none |
| [structural_relaxation_time](../wiki/observable_structural_relaxation_time.md) | 0 | 0 | 0 | 0 | 0 | 0 | none |
| [tracer_brightness](../wiki/observable_tracer_brightness.md) | 0 | 0 | 0 | 0 | 0 | 0 | none |
| [tracer_diffusivity](../wiki/observable_tracer_diffusivity.md) | 0 | 0 | 0 | 1 | 0 | 0 | [quantity temperature](../wiki/quantity_temperature.md) |
| [trapped_particle_drag_offset](../wiki/observable_trapped_particle_drag_offset.md) | 0 | 0 | 0 | 0 | 0 | 0 | none |
| [trapped_position_distribution](../wiki/observable_trapped_position_distribution.md) | 0 | 0 | 0 | 0 | 0 | 0 | none |
| [well_occupancy](../wiki/observable_well_occupancy.md) | 0 | 0 | 0 | 0 | 0 | 0 | none |
| [well_residence_time](../wiki/observable_well_residence_time.md) | 0 | 0 | 0 | 0 | 0 | 0 | none |

## Sample pages

| page | E1 | E2 | E3 | E4 | E5 | disputed | shares entries with |
|---|---|---|---|---|---|---|---|
| [particle_suspension_a](../wiki/sample_particle_suspension_a.md) | 0 | 2 | 1 | 0 | 1 | 0 | none |
| [particle_suspension_b](../wiki/sample_particle_suspension_b.md) | 0 | 0 | 0 | 0 | 1 | 0 | none |

## Configuration pages

| page | E1 | E2 | E3 | E4 | E5 | disputed | shares entries with |
|---|---|---|---|---|---|---|---|
| [trapping](../wiki/configuration_trapping.md) | 0 | 0 | 3 | 0 | 1 | 0 | [device nosepiece](../wiki/device_nosepiece.md), [device optical_tweezers](../wiki/device_optical_tweezers.md), [quantity temperature](../wiki/quantity_temperature.md) |

---

Generated from the knowledge store at kbv-058ce14eea72. Do not edit by hand: correct the store and regenerate.
