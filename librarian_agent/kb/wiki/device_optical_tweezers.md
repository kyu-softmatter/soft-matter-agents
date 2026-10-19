# Device: optical_tweezers

Every entry in the store about the device optical_tweezers.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, channel, verbatim:

```json
{
  "id": "optical_tweezers",
  "role": "trapping: power, trap count, trap position",
  "driver": "python_tcp",
  "automatable": "partial",
  "read_back": false,
  "lock_group": "trapping",
  "note": "write-only. Several essentials, including its own calibration, are reachable only through the vendor GUI, so anything that needs them goes to a manual instruction sheet.",
  "source": "driven partially in the prior project",
  "grade": "E3"
}
```

## Values

| quantity | value | unit | how it is known | grade and source as recorded | conditions | subject | entry |
|---|---|---|---|---|---|---|---|
| illumination_power | 1050 | mW | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-illumination-power-20260909 | illumination_level 0.8 1 | device optical_tweezers, quantity illumination_power | [trap_laser_power_at_sample_1064nm_10x_80pct](../entries/trap_laser_power_at_sample_1064nm_10x_80pct.json) |
| illumination_power | 1020 | mW | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-illumination-power-20260909 | illumination_level 0.8 1 | device optical_tweezers, quantity illumination_power | [trap_laser_power_at_sample_1064nm_20x_80pct](../entries/trap_laser_power_at_sample_1064nm_20x_80pct.json) |
| illumination_power | 64 | mW | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-illumination-power-20260909 | illumination_level 0.05 to 0.5 1 | device optical_tweezers, quantity illumination_power | [trap_laser_power_at_sample_1064nm_20x_level_sweep](../entries/trap_laser_power_at_sample_1064nm_20x_level_sweep.json) |
| illumination_power | 126 | mW | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-illumination-power-20260909 | illumination_level 0.05 to 0.5 1 | device optical_tweezers, quantity illumination_power | [trap_laser_power_at_sample_1064nm_20x_level_sweep](../entries/trap_laser_power_at_sample_1064nm_20x_level_sweep.json) |
| illumination_power | 380 | mW | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-illumination-power-20260909 | illumination_level 0.05 to 0.5 1 | device optical_tweezers, quantity illumination_power | [trap_laser_power_at_sample_1064nm_20x_level_sweep](../entries/trap_laser_power_at_sample_1064nm_20x_level_sweep.json) |
| illumination_power | 633 | mW | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-illumination-power-20260909 | illumination_level 0.05 to 0.5 1 | device optical_tweezers, quantity illumination_power | [trap_laser_power_at_sample_1064nm_20x_level_sweep](../entries/trap_laser_power_at_sample_1064nm_20x_level_sweep.json) |
| illumination_power | 890 | mW | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-illumination-power-20260909 | illumination_level 0.8 1 | device optical_tweezers, quantity illumination_power | [trap_laser_power_at_sample_1064nm_4x_80pct](../entries/trap_laser_power_at_sample_1064nm_4x_80pct.json) |
| tweez_power_setting_max | 1 | 1 | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Tweez300UserManual | none stated | device optical_tweezers | [tweez_laser_power_is_set_as_a_fraction_of_maximum](../entries/tweez_laser_power_is_set_as_a_fraction_of_maximum.json) |
| tweez_laser_wavelength | 1064 | nm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Tweez300LaserSafetyManual_v3_0_2022 | none stated | device optical_tweezers | [tweez_laser_source_is_a_1064nm_fiber_laser](../entries/tweez_laser_source_is_a_1064nm_fiber_laser.json) |
| tweez_305_rated_output | 5 | W | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Tweez300LaserSafetyManual_v3_0_2022 | none stated | device optical_tweezers | [tweez_laser_source_is_a_1064nm_fiber_laser](../entries/tweez_laser_source_is_a_1064nm_fiber_laser.json) |
| tweez_310_rated_output | 10 | W | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Tweez300LaserSafetyManual_v3_0_2022 | none stated | device optical_tweezers | [tweez_laser_source_is_a_1064nm_fiber_laser](../entries/tweez_laser_source_is_a_1064nm_fiber_laser.json) |
| tweez_operating_temperature_min | 293.15 | K | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Tweez300GeneralHardwareAndSafetyManual_v3_0_2022 | none stated | device optical_tweezers | [tweez_operating_environment](../entries/tweez_operating_environment.json) |
| tweez_operating_temperature_max | 301.15 | K | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Tweez300GeneralHardwareAndSafetyManual_v3_0_2022 | none stated | device optical_tweezers | [tweez_operating_environment](../entries/tweez_operating_environment.json) |
| tweez_operating_humidity_min | 0.2 | 1 | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Tweez300GeneralHardwareAndSafetyManual_v3_0_2022 | none stated | device optical_tweezers | [tweez_operating_environment](../entries/tweez_operating_environment.json) |
| tweez_operating_humidity_max | 0.8 | 1 | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Tweez300GeneralHardwareAndSafetyManual_v3_0_2022 | none stated | device optical_tweezers | [tweez_operating_environment](../entries/tweez_operating_environment.json) |
| tweez_hibernation_delay | 10 | min | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Tweez300GeneralHardwareAndSafetyManual_v3_0_2022 | none stated | device optical_tweezers | [tweez_standby_then_hibernation](../entries/tweez_standby_then_hibernation.json) |
| tweez_power_supply_rated_power | 255 | W | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Tweez300GeneralHardwareAndSafetyManual_v3_0_2022 | none stated | device optical_tweezers | [tweez_use_only_the_original_power_supply](../entries/tweez_use_only_the_original_power_supply.json) |
| wavelength | 1064 | nm | from a document, a reading off the instrument, or another project's record; the person read it off the instrument | E3 · operator_read:kyuhwan_20260919 | none stated | device optical_tweezers, configuration trapping | [trapping_laser_identity](../entries/trapping_laser_identity.json) |
| rated_max_power | 5 | W | from a document, a reading off the instrument, or another project's record; the person read it off the instrument | E3 · operator_read:kyuhwan_20260919 | none stated | device optical_tweezers, configuration trapping | [trapping_laser_identity](../entries/trapping_laser_identity.json) |
| busy_fraction_at_zero_gap | 16 | count | from a document, a reading off the instrument, or another project's record; another project's record | E3 · prior_run:agentic-microscope@fbedef0 | none stated | device optical_tweezers | [tweez300_back_to_back_sends_come_back_busy](../entries/tweez300_back_to_back_sends_come_back_busy.json) |
| smallest_gap_with_no_busy_probe | 2 | ms | from a document, a reading off the instrument, or another project's record; another project's record | E3 · prior_run:agentic-microscope@fbedef0 | none stated | device optical_tweezers | [tweez300_back_to_back_sends_come_back_busy](../entries/tweez300_back_to_back_sends_come_back_busy.json) |
| illumination_power | 1000 | mW | computed; computed from other values | E4 · computed:power_scaled_by_objective_transmittance_band | illumination_level 0.8 1 | device optical_tweezers, quantity illumination_power | [trap_laser_power_at_sample_1064nm_100x_80pct_rough](../entries/trap_laser_power_at_sample_1064nm_100x_80pct_rough.json) |
| illumination_power | 1000 | mW | computed; computed from other values | E4 · computed:power_scaled_by_objective_transmittance_band | illumination_level 0.8 1 | device optical_tweezers, quantity illumination_power | [trap_laser_power_at_sample_1064nm_40x_80pct_rough](../entries/trap_laser_power_at_sample_1064nm_40x_80pct_rough.json) |
| illumination_power | 1000 | mW | computed; computed from other values | E4 · computed:power_scaled_by_objective_transmittance_band | illumination_level 0.8 1 | device optical_tweezers, quantity illumination_power | [trap_laser_power_at_sample_1064nm_60x_80pct_rough](../entries/trap_laser_power_at_sample_1064nm_60x_80pct_rough.json) |

## Claims

### [trap_laser_emission_is_switchable_over_tcp](../entries/trap_laser_emission_is_switchable_over_tcp.json)

The optical tweezers' trapping laser can be switched on and off from software: the Tweez 300 TCP/IP command set includes LASER_ON (activates the laser) and LASER_OFF (deactivates it). The command set holds no command that sets or reads the laser's power.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300UserManual).

Conditions, verbatim:

> The Tweez 300 as installed on this bench, driven through its TCP/IP external control. Read from the User Manual's Command Reference, printed page 66 (PDF page 72); the whole command list was searched for a power, intensity or laser command and only these two exist. The manual's Laser Control section (printed page 23) adds that the laser activates only if every laser safety component is connected and every interlock is enabled -- stated for the GUI button, and the Command Reference says each command is an exact counterpart of the GUI procedure.  WHY THIS IS HERE. trap_laser_power_has_no_software_path is right about POWER and says nothing about EMISSION, and its name reads as if software has no way to reach the laser at all. It does: software cannot set the level, and it can turn emission on. That is the more dangerous half to leave out, and microscope-20260924-4 reported it on 2026-09-24. Neither command has been sent on this bench; this is the vendor's documentation, not an observation.  NOT A POLICY. Whether any session may send LASER_ON is a person's decision and lives in the envelope, not here.

### [tweez_back_panel_inputs_have_absolute_maxima](../entries/tweez_back_panel_inputs_have_absolute_maxima.json)

Two back-panel inputs have absolute maximum ratings, and exceeding them can permanently damage the input: the 10 MHz reference clock input, 5 volts peak to peak, and the general-purpose GPIO A and B connectors, 5 volts.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300GeneralHardwareAndSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 General Hardware and Safety Manual V3.0, November 2022, as installed (sha256 1c112ed1...): printed page 7 (PDF page 9). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. The voltages are in the claim only: the store's unit registry has no volt. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_calibration_photodiode_needs_the_laser_off](../entries/tweez_calibration_photodiode_needs_the_laser_off.json)

Before setting up the calibration photodiode the laser must be switched off, or it can injure eyes or skin and damage the photodiode. The objective must be fully retracted before the photodiode is placed on the sample holder, and its position adjusted with great care, so as not to damage the objective's front lens.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300UserManual).

Conditions, verbatim:

> Read from Tweez 300 User Manual, 2021 (file date 2022-01-06; sha256 c37027cb..., byte-identical in both places): printed page 28 (PDF page 34), printed page 29 (PDF page 35). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_contains_nickel](../entries/tweez_contains_nickel.json)

The manufacturer warns that the product can expose users to nickel and other chemicals listed by the State of California as causing cancer, and that it must go to electronic-waste recycling at end of life.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300GeneralHardwareAndSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 General Hardware and Safety Manual V3.0, November 2022, as installed (sha256 1c112ed1...): printed page 3 (PDF page 5). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_fibre_is_enclosed_end_to_end](../entries/tweez_fibre_is_enclosed_end_to_end.json)

Between the control laser unit and the optical unit the beam travels in an optical fibre inside a flexible stainless-steel tube, inside a non-removable stainless-steel umbilical, which the manufacturer describes as protection against damage to the fibre and against any leak of laser light.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 3 (PDF page 5). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_filter_cube_shutter_and_blocking_filter](../entries/tweez_filter_cube_shutter_and_blocking_filter.json)

The tweezers are meant to be used with an Aresis-supplied filter cube in the microscope's epi-fluorescence turret. That turret's mechanically actuated shutter blocks the laser from the objective and the eyepieces, and the cube's dichroic and blocking filters attenuate infrared that could reach the eyepiece path to well below the Class 1 limit.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 8 (PDF page 10). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. Which turret and position hold the Aresis cube on this bench is not recorded in this store. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_has_no_user_serviceable_parts](../entries/tweez_has_no_user_serviceable_parts.json)

The tweezers contain no user-serviceable parts; servicing is for qualified personnel only, and the system must not be operated with covers or panels removed. Exposed connections must not be touched while power is on.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300GeneralHardwareAndSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 General Hardware and Safety Manual V3.0, November 2022, as installed (sha256 1c112ed1...): printed page 4 (PDF page 6). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_install_guide_releases_the_safety_switch_counterclockwise](../entries/tweez_install_guide_releases_the_safety_switch_counterclockwise.json)

The 2021 System Installation Guide says the laser safety switch, once pressed, stays in the disabled position until released by turning it counter-clockwise.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300SystemInstallationGuide_2021).

Conditions, verbatim:

> Read from Tweez 305/310 System Installation Guide, 2021 (sha256 1f664a72..., byte-identical in the installed folder and the lab archive): printed page 11 (PDF page 15). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. THIS DISAGREES with the 2022 Laser Safety Manual, which says clockwise (tweez_laser_safety_switch_stops_emission). The person ruled that the safety guide follows the 2022 edition; this entry keeps the other reading so it is not rediscovered as new. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_installation_needs_qualified_personnel](../entries/tweez_installation_needs_qualified_personnel.json)

The tweezers must be installed, or the installation supervised, by qualified personnel; an unauthorised installation voids the warranty and may cause serious injury or damage. The shipping crate is large and heavy and must be handled with care.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300GeneralHardwareAndSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 General Hardware and Safety Manual V3.0, November 2022, as installed (sha256 1c112ed1...): printed page 10 (PDF page 12). Also Tweez 305/310 System Installation Guide, 2021 (sha256 1f664a72..., byte-identical in the installed folder and the lab archive): printed page 3 (PDF page 7). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_interlocks_are_in_hardware](../entries/tweez_interlocks_are_in_hardware.json)

The tweezers' interlocks are built into low-level electronics hardware, independent of the computer and its software, and wherever possible a safety measure is mechanical, such as the shutter, so that it does not depend on electrical power.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 4 (PDF page 6), printed page 9 (PDF page 11). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. So a software failure is not supposed to defeat an interlock; a hardware fault is a different question this manual does not address. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_internal_shutter_closes_by_spring](../entries/tweez_internal_shutter_closes_by_spring.json)

In the optical unit the fibre ends in a fixed collimator followed immediately by a mechanical shutter, which isolates the beam from the exit aperture during start-up and emergency shutdown, and which is spring-loaded to close by itself if the control electronics fail.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 4 (PDF page 6). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_is_a_class_4_laser_device](../entries/tweez_is_a_class_4_laser_device.json)

The manufacturer classifies the laser tweezers as a Class 4 laser device under IEC 60825-1:2014: used inappropriately, it can be a severe hazard to eyes and skin.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 1 (PDF page 3). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. The manual is written for the Tweez 305/310 family; this bench's unit is recorded as a Tweez 300 (trapping_laser_identity), and the family naming is the manufacturer's. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_key_switch_cuts_all_power](../entries/tweez_key_switch_cuts_all_power.json)

A key switch on the front of the control laser unit controls the system's main power. With the key removed the system and the laser are shut down and no emission is possible; the key can be removed only in the OFF position.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 4 (PDF page 6). Also Tweez 305/310 General Hardware and Safety Manual V3.0, November 2022, as installed (sha256 1c112ed1...): printed page 6 (PDF page 8). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_laser_exits_only_at_one_aperture](../entries/tweez_laser_exits_only_at_one_aperture.json)

The tweezers are built so that laser light leaves only through one marked exit aperture on the optical unit; every other point where the beam could be reached is covered by the interlocks.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 9 (PDF page 11). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_laser_safety_glasses_must_be_worn](../entries/tweez_laser_safety_glasses_must_be_worn.json)

The supplied laser safety glasses must be worn during laser operation. One set ships with the system; everyone present where stray laser light could be must wear a pair, and providing the extra sets is the operator's responsibility.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 9 (PDF page 11). Also Tweez 305/310 System Installation Guide, 2021 (sha256 1f664a72..., byte-identical in the installed folder and the lab archive): printed page 22 (PDF page 26). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_laser_safety_switch_stops_emission](../entries/tweez_laser_safety_switch_stops_emission.json)

The laser safety switch, cabled to the optical unit so it sits near the work, is the quick way to shut the laser down. Once pressed it stays engaged and must be released by turning its knob -- clockwise, in this 2022 manual -- before the laser can run again. If it is engaged, or its cable is disconnected or broken, laser operation is disabled and the internal shutter blocks the beam.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 5 (PDF page 7). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. THE RELEASE DIRECTION DISAGREES with the 2021 System Installation Guide, which says counter-clockwise (tweez_install_guide_releases_the_safety_switch_counterclockwise). The person ruled that the safety guide follows the 2022 edition; the disagreement is kept, not resolved. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_laser_safety_training_is_part_of_safety](../entries/tweez_laser_safety_training_is_part_of_safety.json)

The manufacturer treats training as a safety measure: it covers the nature of infrared laser radiation, the hazards, what Class 4 means, the tweezers' safety system, and safe installation and operation.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 10 (PDF page 12). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_microscope_interlock_blocks_the_laser_at_the_eyepieces](../entries/tweez_microscope_interlock_blocks_the_laser_at_the_eyepieces.json)

The Nikon Ti2's own interlock switch is triggered whenever light could enter the eyepieces -- when the light path selector is set to the eyepieces -- and it is wired to the tweezers' optical unit, so that laser operation is disabled in that position. The manufacturer calls it an additional measure: an infrared filter already keeps the laser out of the eyepiece path. If the interlock cable is disconnected, laser operation is disabled. The Ti2's interlock works only while the microscope is powered, and with the microscope off, tweezers laser operation is disabled too.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 7 (PDF page 9). Also Tweez 305/310 System Installation Guide, 2021 (sha256 1f664a72..., byte-identical in the installed folder and the lab archive): printed page 12 (PDF page 16). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. Which light-path positions send light to the eyepieces is the open gap light_path_port_eyepiece_states; the Ti2 Control manual's port list narrows it (ti2e_optical_path_addresses). KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_must_be_grounded_through_its_power_cord](../entries/tweez_must_be_grounded_through_its_power_cord.json)

The tweezers must be earthed through the grounding conductor of the specified, certified power cord before anything else is connected or power applied. The back-panel grounding post is only for additional earthing or equalising potential with the table or microscope.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300GeneralHardwareAndSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 General Hardware and Safety Manual V3.0, November 2022, as installed (sha256 1c112ed1...): printed page 4 (PDF page 6), printed page 9 (PDF page 11). Also Tweez 305/310 General Hardware and Safety Manual V3.0, November 2022, as installed (sha256 1c112ed1...): printed page 8 (PDF page 10). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_optical_unit_cover_must_stay_on](../entries/tweez_optical_unit_cover_must_stay_on.json)

Users should never remove the optical unit's cover: inside, the invisible 1064 nm beam runs through open optics. Removing the cover trips an internal interlock that disables the laser and closes the shutter.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 7 (PDF page 9). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_proprietary_connectors_take_only_aresis_equipment](../entries/tweez_proprietary_connectors_take_only_aresis_equipment.json)

Several tweezers connectors are proprietary and take only Aresis equipment: the LEMO trigger connector only the original Aresis camera cable; the DisplayPort-shaped expansion connector must never go to a monitor or TV, or the tweezers or the monitor may be permanently damaged; and the RJ45 interlock connector only the Aresis laser warning sign.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300GeneralHardwareAndSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 General Hardware and Safety Manual V3.0, November 2022, as installed (sha256 1c112ed1...): printed page 8 (PDF page 10). Also Tweez 305/310 System Installation Guide, 2021 (sha256 1f664a72..., byte-identical in the installed folder and the lab archive): printed page 20 (PDF page 24). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. The Installation Guide adds the camera interface box's DisplayPort sockets and the unit's sync-out connector to the never-a-monitor list. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_sample_safety_shield_goes_on_before_the_laser](../entries/tweez_sample_safety_shield_goes_on_before_the_laser.json)

The sample safety shield blocks laser light scattered off the sample and is to be placed around the sample before the laser is activated. If it gets in the way of other equipment on the stage, the operator must provide a replacement or other protection at least as good.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300SystemInstallationGuide_2021).

Conditions, verbatim:

> Read from Tweez 305/310 System Installation Guide, 2021 (sha256 1f664a72..., byte-identical in the installed folder and the lab archive): printed page 22 (PDF page 26). Also Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 2 (PDF page 4). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. The Laser Safety Manual lists a protective shield as available on request. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_software_shows_laser_power_and_interlocks](../entries/tweez_software_shows_laser_power_and_interlocks.json)

The tweezers software keeps the laser control panel visible, shows whether the laser is on and at what power, gives quick access to an emergency shutdown, and shows the connection and state of every interlock. The laser can be switched on there only if every safety component is connected and every interlock is enabled; its status reads Standby when enabled but off, and Locking or Locked once on.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 9 (PDF page 11). Also Tweez 300 User Manual, 2021 (file date 2022-01-06; sha256 c37027cb..., byte-identical in both places): printed page 23 (PDF page 29), printed page 24 (PDF page 30). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_status_lights_steady_ready_flashing_emitting](../entries/tweez_status_lights_steady_ready_flashing_emitting.json)

The tweezers show laser status the same way on the laser safety switch, the laser warning sign and the control laser unit's front panel: a steady red light means the laser is powered but not emitting, and a flashing red light means it is emitting. A blue light on the front panel means system power is on.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 5 (PDF page 7), printed page 6 (PDF page 8). Also Tweez 305/310 General Hardware and Safety Manual V3.0, November 2022, as installed (sha256 1c112ed1...): printed page 6 (PDF page 8). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_three_independent_ways_to_stop_emission](../entries/tweez_three_independent_ways_to_stop_emission.json)

The manufacturer builds in three independent ways to keep the beam from leaving the exit aperture if one interlock fails: the internal mechanical shutter, an interlock on the laser module that stops emission, and switching off the radio-frequency drive to the acousto-optic deflectors, which then act as a second shutter in series.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 8 (PDF page 10), printed page 9 (PDF page 11). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_ventilation_must_not_be_blocked](../entries/tweez_ventilation_must_not_be_blocked.json)

The ventilation openings on the back panel and underside of the tweezers must not be obstructed, to avoid fire or permanent damage.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300GeneralHardwareAndSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 General Hardware and Safety Manual V3.0, November 2022, as installed (sha256 1c112ed1...): printed page 4 (PDF page 6). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_warning_sign_carries_a_remote_interlock](../entries/tweez_warning_sign_carries_a_remote_interlock.json)

The laser warning sign shows the laser's status to people who would not otherwise know it, such as anyone entering the room, and should be placed where it is clearly visible. It carries a remote interlock connector, meant for a switch or chain of switches -- a door switch, for example -- that disables the laser; disconnecting the sign also disables the laser and closes the internal shutter.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 6 (PDF page 8). Also Tweez 305/310 System Installation Guide, 2021 (sha256 1f664a72..., byte-identical in the installed folder and the lab archive): printed page 13 (PDF page 17). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. The Installation Guide adds that the remote interlock ships short-circuited by default, and that no ordinary network cable may go into the sign's or the unit's RJ45 sockets. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [objective_change_invalidates_trap_calibration](../entries/objective_change_invalidates_trap_calibration.json)

Changing the objective silently invalidates both of the optical tweezers' calibrations -- the GUI's pixel-to-micrometre magnification and the AOD's trapping-field response -- and neither is readable over TCP. Afterwards every commanded trap position in micrometres lands somewhere else and nothing reports it.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@safety-2026-09-03).

Conditions, verbatim:

> Ruled TRANSFER under 10.2.1 and passed 10.3 rule 1, so it caps at E3 -- a run taken in another project is not a run taken here. 10.2's hardware-control-path row is open and says in its own rule that it does not wait for envelope/, because wrapping a control path needs no safety limit. Slot: A4 for the configuration change and O1 preflight for the check it forces, with A7 as the axis that owns commanded motion. It is the specific case of tweez300_reports_nothing_back that bites hardest, because the invalidating action is on a different device from the one that goes wrong. The check is to drive a known amplitude and measure it; the store holds no threshold for what counts as agreement, and that is a caller's judgement recorded in its plan.  NOT THE PIXEL-SIZE CALIBRATION, AND THE STORE NOW SAYS SO AT BOTH ENDS. This entry says an objective change invalidates a pixel-to-micrometre calibration, which reads as covering the twelve pixel_size_\<mag\>_zoom_\<zoom\> rows and does not. What it covers is the tweezers' GUI, which holds ONE such calibration that the swap falsifies; the pixel-size rows are TWELVE, indexed BY objective, so the same action selects among them. The person ruled that directly on 2026-09-21 -- see objective_change_selects_a_pixel_size_row. Written into this entry as well as that one because a cross-reference that lives at one end is found only by whoever arrives at that end, and a reader who reaches this entry first is exactly the reader who would over-apply it.

### [trap_laser_power_has_no_software_path](../entries/trap_laser_power_has_no_software_path.json)

The trapping laser's power is neither readable nor settable from software. The level is set by a hand control and nothing reads it back, so a level used in a run leaves no record unless someone writes it down.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@safety-2026-09-03).

Conditions, verbatim:

> Ruled TRANSFER under 10.2.1 and passed 10.3 rule 1, so it caps at E3 -- a run taken in another project is not a run taken here. 10.2's hardware-control-path row is open and says in its own rule that it does not wait for envelope/, because wrapping a control path needs no safety limit. Slot: A7, which owns the driving term, with the orchestrator second. This is why the detection bound in trap_heating_detection_bound is stated as a dial position and not as a power: there is no path by which the number could have been read back, so a recalled dial setting is the strongest form that fact can take. It also means a run's laser level is not recoverable from any log after the fact.  POWER ONLY, NOT EMISSION (2026-09-24). This entry is about the laser's level. Software CAN switch emission on and off over TCP -- see trap_laser_emission_is_switchable_over_tcp, from the vendor's command list.

### [tweez300_host_streamed_positions_move_smoothly](../entries/tweez300_host_streamed_positions_move_smoothly.json)

Absolute TRAP_POSITION commands streamed from the host at 10 Hz move a Tweez 300 trap smoothly by eye.

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260924_tweezers).

Conditions, verbatim:

> One run of 61 commands tracing a circle and returning to 0 0; the person saw it move smoothly and end at the centre. 'Smoothly' is by eye on the GUI, not a measurement of position or timing; wall time was 6.016 s against 6.0 s planned, on the host clock. Record: D:/soft-matter-agents-frames/tweezers-20260924-001/exchanges.jsonl line 116.  CONDITIONS OF THE SESSION, AND WHAT THEY RULE OUT. 2026-09-24, 12:05-12:33 local, the Tweez 300 GUI driven over TCP by microscope-20260924-4 while the person watched the GUI and said what it showed. The 100x objective was in the path and a sample was mounted -- both stated by the person after the commands. The trapping laser's emission was off -- also stated after the fact, and not logged before the first command. The GUI's calibrations were not stated, so NOTHING HERE IS A MICROMETRE: positions are GUI coordinates and moves are directions on screen. What this is: the person reading the GUI display. What it is not: an observation of light, force or a particle.

### [tweez300_load_pattern_name_first](../entries/tweez300_load_pattern_name_first.json)

LOAD_PATTERN takes the pattern name first and then the file's absolute path, quoted when it contains a space, and the pattern then appears in the Tweez 300 GUI's pattern list.

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260924_tweezers).

Conditions, verbatim:

> One load, of a .tpf file at a path containing a space; the person read the pattern name in the list. Its point count and shape were not read. The argument order is the command that was sent, and the manual's Command Reference says paths are absolute and strings with blanks are quoted. Record: D:/soft-matter-agents-frames/tweezers-20260924-001/exchanges.jsonl line 43.  CONDITIONS OF THE SESSION, AND WHAT THEY RULE OUT. 2026-09-24, 12:05-12:33 local, the Tweez 300 GUI driven over TCP by microscope-20260924-4 while the person watched the GUI and said what it showed. The 100x objective was in the path and a sample was mounted -- both stated by the person after the commands. The trapping laser's emission was off -- also stated after the fact, and not logged before the first command. The GUI's calibrations were not stated, so NOTHING HERE IS A MICROMETRE: positions are GUI coordinates and moves are directions on screen. What this is: the person reading the GUI display. What it is not: an observation of light, force or a particle.

### [tweez300_new_trap_starts_at_strength_zero](../entries/tweez300_new_trap_starts_at_strength_zero.json)

A trap newly created in the Tweez 300 GUI starts at relative strength 0, so switching it on alone leaves it active and delivering nothing until a strength is set.

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260924_tweezers).

Conditions, verbatim:

> t1 was created and switched on with no strength command; after later commands the person read t1's strength as still 0. One trap, one reading. Record: D:/soft-matter-agents-frames/tweezers-20260924-001/exchanges.jsonl line 31.  CONDITIONS OF THE SESSION, AND WHAT THEY RULE OUT. 2026-09-24, 12:05-12:33 local, the Tweez 300 GUI driven over TCP by microscope-20260924-4 while the person watched the GUI and said what it showed. The 100x objective was in the path and a sample was mounted -- both stated by the person after the commands. The trapping laser's emission was off -- also stated after the fact, and not logged before the first command. The GUI's calibrations were not stated, so NOTHING HERE IS A MICROMETRE: positions are GUI coordinates and moves are directions on screen. What this is: the person reading the GUI display. What it is not: an observation of light, force or a particle.

### [tweez300_pattern_runs_on_assignment](../entries/tweez300_pattern_runs_on_assignment.json)

TRAP_ASSIGN_PATTERN starts the pattern at once: the trap moves along it with no separate start command.

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260924_tweezers).

Conditions, verbatim:

> One assignment of a circle pattern; the person saw t2 moving in a circle. Size, roundness and speed were not read. A pattern that runs on assignment means assigning is itself a motion command. Record: D:/soft-matter-agents-frames/tweezers-20260924-001/exchanges.jsonl line 47.  CONDITIONS OF THE SESSION, AND WHAT THEY RULE OUT. 2026-09-24, 12:05-12:33 local, the Tweez 300 GUI driven over TCP by microscope-20260924-4 while the person watched the GUI and said what it showed. The 100x objective was in the path and a sample was mounted -- both stated by the person after the commands. The trapping laser's emission was off -- also stated after the fact, and not logged before the first command. The GUI's calibrations were not stated, so NOTHING HERE IS A MICROMETRE: positions are GUI coordinates and moves are directions on screen. What this is: the person reading the GUI display. What it is not: an observation of light, force or a particle.

### [tweez300_position_origin_is_image_centre](../entries/tweez300_position_origin_is_image_centre.json)

In the Tweez 300 GUI, TRAP_POSITION with coordinates 0 0 places the trap at the centre of the image.

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260924_tweezers).

Conditions, verbatim:

> One command, one reading: the person saw t1 move to the centre of the image. Record: D:/soft-matter-agents-frames/tweezers-20260924-001/exchanges.jsonl line 11.  CONDITIONS OF THE SESSION, AND WHAT THEY RULE OUT. 2026-09-24, 12:05-12:33 local, the Tweez 300 GUI driven over TCP by microscope-20260924-4 while the person watched the GUI and said what it showed. The 100x objective was in the path and a sample was mounted -- both stated by the person after the commands. The trapping laser's emission was off -- also stated after the fact, and not logged before the first command. The GUI's calibrations were not stated, so NOTHING HERE IS A MICROMETRE: positions are GUI coordinates and moves are directions on screen. What this is: the person reading the GUI display. What it is not: an observation of light, force or a particle.

### [tweez300_positive_x_is_right_on_screen](../entries/tweez300_positive_x_is_right_on_screen.json)

In the Tweez 300 GUI, a positive x step moves the trap to the right on screen.

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260924_tweezers).

Conditions, verbatim:

> One relative move of +5 in x, seen once, moving right 'a little'. The size of the step in any length unit was not read, and y's direction was not tested. Record: D:/soft-matter-agents-frames/tweezers-20260924-001/exchanges.jsonl line 15.  CONDITIONS OF THE SESSION, AND WHAT THEY RULE OUT. 2026-09-24, 12:05-12:33 local, the Tweez 300 GUI driven over TCP by microscope-20260924-4 while the person watched the GUI and said what it showed. The 100x objective was in the path and a sample was mounted -- both stated by the person after the commands. The trapping laser's emission was off -- also stated after the fact, and not logged before the first command. The GUI's calibrations were not stated, so NOTHING HERE IS A MICROMETRE: positions are GUI coordinates and moves are directions on screen. What this is: the person reading the GUI display. What it is not: an observation of light, force or a particle.

### [tweez300_readiness_probe_answers_minus_22](../entries/tweez300_readiness_probe_answers_minus_22.json)

On this bench, TRAP_DELETE of a trap name that does not exist answers -22 ('no resource selected') from a working Tweez 300 GUI, not the -25 the Command Reference implies -- so -22 must count as ready in a readiness probe.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0).

Conditions, verbatim:

> Measured in the prior project on the microscope PC on 2026-08-27, same session showing the GUI fully live (a create and a delete of a real trap both answered 0). ALSO SEEN HERE: the same probe answered -22 as the first command of the 2026-09-24 session (D:/soft-matter-agents-frames/tweezers-20260924-001/exchanges.jsonl line 2). That is agreement, not a promotion -- no run_id -- so it stays E3. Ruled TRANSFER; slot: the command path. Without -22 counted as ready, a probe calls a healthy GUI dead.

### [tweez300_reports_nothing_back](../entries/tweez300_reports_nothing_back.json)

The Tweez 300's TCP interface has no readback of any kind -- no position, no force, no trap list, no calibration -- and a return code of 0 means the GUI accepted the command, not that anything happened. Six distinct ways a command can be ignored all return 0: a breakpoint whose enable bits are unset, release bits that do not cover the value, repeat left disabled, a pattern that overruns the calibrated range and is silently clipped to the edge, a GUI calibrated at a different objective so every commanded micrometre is wrong by that ratio, and a named trap that holds no bead.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@safety-2026-09-03).

Conditions, verbatim:

> Ruled TRANSFER under 10.2.1 and passed 10.3 rule 1, so it caps at E3 -- a run taken in another project is not a run taken here. 10.2's hardware-control-path row is open and says in its own rule that it does not wait for envelope/, because wrapping a control path needs no safety limit. Slot: A4, which screens on automatable and read_back, with O1 preflight as the second consumer -- a preflight that reads back to confirm has nothing to read here. This is what read_back: false means on that row, stated rather than left as a flag. Confirmation has to come from outside the interface: by eye in the GUI, or by measuring the result in camera data. Note the contrast with the piezo, which range-checks a trajectory against the travel its controller reports and REFUSES rather than clipping -- two devices on one instrument, opposite behaviours at the same boundary, and only one of them tells you.

### [tweez300_trap_on_shows_active](../entries/tweez300_trap_on_shows_active.json)

TRAP_ON over TCP switches a trap to active as the Tweez 300 GUI displays it.

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260924_tweezers).

Conditions, verbatim:

> One trap, one reading, reported after later commands. Active is the GUI's state and says nothing about output: see tweez300_new_trap_starts_at_strength_zero. Record: D:/soft-matter-agents-frames/tweezers-20260924-001/exchanges.jsonl line 30.  CONDITIONS OF THE SESSION, AND WHAT THEY RULE OUT. 2026-09-24, 12:05-12:33 local, the Tweez 300 GUI driven over TCP by microscope-20260924-4 while the person watched the GUI and said what it showed. The 100x objective was in the path and a sample was mounted -- both stated by the person after the commands. The trapping laser's emission was off -- also stated after the fact, and not logged before the first command. The GUI's calibrations were not stated, so NOTHING HERE IS A MICROMETRE: positions are GUI coordinates and moves are directions on screen. What this is: the person reading the GUI display. What it is not: an observation of light, force or a particle.

### [tweez300_trap_strength_takes_the_last_value](../entries/tweez300_trap_strength_takes_the_last_value.json)

When TRAP_STRENGTH is sent twice to one trap, the Tweez 300 GUI shows the second value; each strength command also shows as sent.

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260924_tweezers).

Conditions, verbatim:

> t2 was sent 0.5 and then 0.2 and read as 0.2 (line 31); t1 was sent 0.3 and read as 0.3 (line 35). The 0.5 itself was not read before it was replaced. Record: D:/soft-matter-agents-frames/tweezers-20260924-001/exchanges.jsonl line 31.  CONDITIONS OF THE SESSION, AND WHAT THEY RULE OUT. 2026-09-24, 12:05-12:33 local, the Tweez 300 GUI driven over TCP by microscope-20260924-4 while the person watched the GUI and said what it showed. The 100x objective was in the path and a sample was mounted -- both stated by the person after the commands. The trapping laser's emission was off -- also stated after the fact, and not logged before the first command. The GUI's calibrations were not stated, so NOTHING HERE IS A MICROMETRE: positions are GUI coordinates and moves are directions on screen. What this is: the person reading the GUI display. What it is not: an observation of light, force or a particle.

### [optical_tweezers_work_with_40x_60x_100x_person_statement](../entries/optical_tweezers_work_with_40x_60x_100x_person_statement.json)

The person states that on this instrument the optical tweezers work with the 40x, 60x and 100x objectives: "OT is working in 40x, 60x, and 100x." (2026-09-25).

How it is known: recalled or assumed; the person's recollection (E5 · operator_recall:person_statement_tweezers_objectives_20260925).

Conditions, verbatim:

> THE PERSON'S WORDS AND ONLY THOSE, at E5 as a statement. WHAT THE QUOTE DOES NOT SAY, and none of it is filled here: (1) that the tweezers do not work with the 4x, 10x and 20x -- it names three objectives and is silent on the rest; the finding's own sentence adds 'not with the others' and that is the seat's reading; (2) why -- that trapping needs a high-NA objective is general knowledge and not the person's statement, so it is not recorded as theirs; (3) which 40x. The nosepiece as entered in nosepiece_objective_assignment holds one 40x (MRD77400, water immersion), one 60x (MRD71670, oil) and one 100x (MRD71970, oil), but the person named magnifications and not parts, so this entry does not join to those parts and a caller that does so adds its own assumption. WHAT IT IS FOR. The microscope seat was settling per-objective position limits for the tweezers; which objectives get limits is policy and belongs to the person, and is not entered. Falsified by a trap that fails at one of the three, or confirmed per objective by a trap observed there. Delivered as item optical_tweezers_work_with_40x_60x_100x of microscope_agent/findings/microscope-20260924-6-20260925.json at 921537b.

### [trap_heating_detection_bound](../entries/trap_heating_detection_bound.json)

The operator recalls not noticing a temperature change in the sample unless the infrared trapping laser was driven above roughly 20 percent on its dial. This records where noticing stopped, by means that were not recorded.

How it is known: recalled or assumed; the person's recollection (E5 · operator_recall:kyuhwan_20260919).

Conditions, verbatim:

> THIS IS NOT A LIMIT AND MAY NOT BE USED AS ONE. 'Keep it under 20 percent' is the sentence someone lifts out of an entry and uses to parameterise a laser, and three separate rules forbid that: safety limits live in a file a person writes and in deterministic code (P0, 2.1 rule 7), they do not transfer (10.3 rule 4), and the grade forbids it on its own -- an E5 may not parameterise an irreversible action without a person's individual approval, and raising laser power onto a sample is irreversible to the sample. Anyone needing a bound writes one in envelope/safety.json after confirming it physically. Three things this says less than it appears to. It is RECALLED, not read, which is why it is E5 while the neighbouring instrument facts are E3. It is a DETECTION BOUND and not a zero: 'did not notice' was measured by unrecorded means, and 'no heating below 20 percent' is a stronger claim than was made. And 20 PERCENT IS A DIAL READING, not a power: a percentage of an unstated maximum is not a quantity, and writing it into numbers[] would not make it one -- the same ruling that keeps a nominal magnification out of numbers[], wearing different clothes. It does not close the heating gap. A measured heating rate is still absent, and a gap that looks satisfied by an E5 recollection is a false absence running backwards. What it does is sharpen what to measure: sweep the dial with a thermometer that has a recorded position, and the bound becomes a curve.

### [tweez300_camera_is_released_so_it_shows_no_image](../entries/tweez300_camera_is_released_so_it_shows_no_image.json)

The person states that in this lab's use the camera is always released from the Tweez 300 software, so nothing can be seen in the tweezers software; frames of a trapped bead come from Micro-Manager after the tweezers software has let the camera go.

How it is known: recalled or assumed; the person's recollection (E5 · operator_recall:kyuhwan_20260924_tweezers_camera).

Conditions, verbatim:

> The person's answer in microscope-20260924-6's window on the evening of 2026-09-24, quoted verbatim in the message of commit 20387f0, which adds microscope_agent/findings/microscope-20260924-6-20260924.json; read by this seat from that message, as the findings item cites. E5, operator_recall: stated from the person's knowledge of the bench, not read off an instrument at the time. The person's words: 'we always release the camera, and you cannot see anything on the tweezer software.' A STATEMENT OF PRACTICE, NOT OF CAPABILITY: the Tweez 300 User Manual describes a live image in the software's master view and video tracking and recording (its calibration chapter, printed pages 36 and 38, refers to 'GUI live image navigation'), so the software can show and record frames when it holds the camera; this lab releases it. Not stated: how the camera is released, whether trap commands over TCP keep working with it released, and whether the software needs the camera at start before releasing it -- the last bears on whether the red body is locked while the tweezers software starts. Delivered as item tweez300_software_records_no_frames.

### [tweez300_does_not_restore_last_project](../entries/tweez300_does_not_restore_last_project.json)

The Tweez 300 program does not reload its last project when it starts, so traps, strengths and patterns left active when it was closed do not come back on their own at the next start.

How it is known: recalled or assumed; the person's recollection (E5 · operator_recall:kyuhwan_20260924).

Conditions, verbatim:

> The Tweez 300 software as installed on this bench on 2026-09-24, started normally. The person's words were "it doesn't restore the last project", relayed by microscope-20260924-4.  WHY IT MATTERS. Loading saved state is a way for output to rise with no output command: on 2026-09-24 the program was closed with two traps active (strengths 0.3 and 0.2) and a pattern loaded. If they came back on start, a session would meet an active trap before sending anything.  WHAT WOULD FALSIFY IT. A start that shows the previous session's traps or pattern. It is a statement of behaviour, not of a setting anyone has read, so a program option, an update, or a start that opens a project file (the TCP command set has LOAD_PROJECT) could change it. At E5 it is a reason to expect an empty project and never a reason to skip checking for one.

### [tweez300_software_opens_the_red_arm_camera](../entries/tweez300_software_opens_the_red_arm_camera.json)

The person states that the Tweez 300 software, when it starts, opens the red-arm Kinetix camera -- the body Micro-Manager reads as serial A24M723015 under the label Kinetix_red.

How it is known: recalled or assumed; the person's recollection (E5 · operator_recall:kyuhwan_20260924_tweezers_camera).

Conditions, verbatim:

> The person's answer in microscope-20260924-6's window on the evening of 2026-09-24, quoted verbatim in the message of commit 20387f0, which adds microscope_agent/findings/microscope-20260924-6-20260924.json; read by this seat from that message, as the findings item cites. E5, operator_recall: stated from the person's knowledge of the bench, not read off an instrument at the time. Asked which of the two bodies the tweezers software opens, with the red arm's serial given in the question, the person chose 'The red-arm body': the arm, not a serial read from the tweezers software. camera_bodies_are_told_apart_by_serial holds that the bodies are told apart by serial, so READING THE SERIAL THE TWEEZERS SOFTWARE OPENS settles this and would supersede it at a higher grade. kinetix_red_label_opens_serial_a24m723015 ties the red arm to that serial in Micro-Manager only. Consistent with the device table making camera_red exclusive with the tweezers software, and not a test of it. Delivered as item tweez300_opens_the_red_arm_kinetix (card from manager-microscope-20260924-1's instruction).

## Disputed and withdrawn

- [tweez_install_guide_releases_the_safety_switch_counterclockwise](../entries/tweez_install_guide_releases_the_safety_switch_counterclockwise.json): in conflict; the other side: [tweez_laser_safety_switch_stops_emission](../entries/tweez_laser_safety_switch_stops_emission.json)
- [tweez_laser_safety_switch_stops_emission](../entries/tweez_laser_safety_switch_stops_emission.json): in conflict; the other side: [tweez_install_guide_releases_the_safety_switch_counterclockwise](../entries/tweez_install_guide_releases_the_safety_switch_counterclockwise.json)

## Reading

None.

## Related

- [configuration trapping](../wiki/configuration_trapping.md)
- [device camera_red](../wiki/device_camera_red.md)
- [device light_path_port](../wiki/device_light_path_port.md)
- [device nosepiece](../wiki/device_nosepiece.md)
- [device stand_ti2e](../wiki/device_stand_ti2e.md)
- [device z_drive](../wiki/device_z_drive.md)
- [quantity illumination_power](../wiki/quantity_illumination_power.md)
- [quantity temperature](../wiki/quantity_temperature.md)
- [safety guide](../guides/safety_optical_tweezers.md)

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
