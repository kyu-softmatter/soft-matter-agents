# Unfiled entries

Every entry in the store that names no subject, so that none is invisible.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

Not a registry subject: these entries carry no subject field.

## Values

| quantity | value | unit | how it is known | grade and source as recorded | conditions | subject | entry |
|---|---|---|---|---|---|---|---|
| filter_centre_wavelength | 432 | nm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:FF01-432/36-32 | wavelength 414.0 to 450.0 nm | none named | [filter_ff01_432_36_32_passband](../entries/filter_ff01_432_36_32_passband.json) |
| filter_fwhm | 36 | nm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:FF01-432/36-32 | wavelength 414.0 to 450.0 nm | none named | [filter_ff01_432_36_32_passband](../entries/filter_ff01_432_36_32_passband.json) |
| filter_centre_wavelength | 515 | nm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:FF01-515/30-32 | wavelength 500.0 to 530.0 nm | none named | [filter_ff01_515_30_32_passband](../entries/filter_ff01_515_30_32_passband.json) |
| filter_fwhm | 30 | nm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:FF01-515/30-32 | wavelength 500.0 to 530.0 nm | none named | [filter_ff01_515_30_32_passband](../entries/filter_ff01_515_30_32_passband.json) |
| filter_centre_wavelength | 595 | nm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:FF01-595/31-32 | wavelength 579.5 to 610.5 nm | none named | [filter_ff01_595_31_32_passband](../entries/filter_ff01_595_31_32_passband.json) |
| filter_fwhm | 31 | nm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:FF01-595/31-32 | wavelength 579.5 to 610.5 nm | none named | [filter_ff01_595_31_32_passband](../entries/filter_ff01_595_31_32_passband.json) |
| filter_centre_wavelength | 680 | nm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:FF01-680/42-32 | wavelength 659.0 to 701.0 nm | none named | [filter_ff01_680_42_32_passband](../entries/filter_ff01_680_42_32_passband.json) |
| filter_fwhm | 42 | nm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:FF01-680/42-32 | wavelength 659.0 to 701.0 nm | none named | [filter_ff01_680_42_32_passband](../entries/filter_ff01_680_42_32_passband.json) |
| elapsed_time_resolution | 1 | ms | from a document, a reading off the instrument, or another project's record; another project's record | E3 · prior_run:agentic-microscope@safety-2026-09-03 | none stated | none named | [elapsed_time_is_quantised_to_one_ms](../entries/elapsed_time_is_quantised_to_one_ms.json) |
| command_round_trip_quiet | 2.93 | ms | from a document, a reading off the instrument, or another project's record; another project's record | E3 · prior_run:agentic-microscope@safety-2026-09-03 | none stated | none named | [live_view_degrades_timing](../entries/live_view_degrades_timing.json) |
| command_round_trip_with_live_view | 51.4 | ms | from a document, a reading off the instrument, or another project's record; another project's record | E3 · prior_run:agentic-microscope@safety-2026-09-03 | none stated | none named | [live_view_degrades_timing](../entries/live_view_degrades_timing.json) |

## Claims

### [aura_green_intensity_runs_to_1000](../entries/aura_green_intensity_runs_to_1000.json)

The Aura's GREEN_Intensity property has limits, with upper limit 1000, and the value 100 written to it read back as 100.

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-002).

Conditions, verbatim:

> Read back in a preparatory run -- the first real acquisition on this computer, with no plan, the person having placed the 20x and moved the microscope by hand, software moving nothing. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system: E1 from `measured:`. Not a value of any registered observable. Consistent with light_engine_line_intensity_is_per_mille (E3, the prior project, both engines): on a 0 to 1000 scale an operator's 10 per cent is 100. What is measured here is the limit and the read-back, on one line of one engine; that 1000 is full output is the per-mille reading, not something this run tested. Slot: A7 and the light-engine wrapper. Delivered as item aura_green_intensity_is_per_mille of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042). Checked by this seat against microscope_agent/runs/run-20260924-002/log.json read at bf8f91f (unchanged since): event 17 (limit) and 29 (write and read-back).

### [aura_master_state_0_keeps_green_dark](../entries/aura_master_state_0_keeps_green_dark.json)

With the Aura's master State at 0, turning GREEN on at intensity 1000 left the red camera's frame dark: it was indistinguishable from dark frames taken with the line off, within the frame-to-frame noise, at 100 ms exposure through the 20x with the Lapp mirror in.

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-002).

Conditions, verbatim:

> Read back in a preparatory run -- the first real acquisition on this computer, with no plan, the person having placed the 20x and moved the microscope by hand, software moving nothing. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system: E1 from `measured:`. Not a value of any registered observable. A gating check measured in the run rather than a device's statement, and the microscope seat says so itself; it is entered because what it establishes is control-path behaviour -- the master switch gates a line at full intensity -- and not a value of any observable. The frame statistics are the run's and are not carried as numbers. It confirms on this bench, for GREEN on the Aura, what light_engine_master_state_gates_every_line says at E3 for every line of both engines; the other lines and the Spectra III are not tested here. Slot: the orchestrator's abort path and O1 preflight. Falsified by light reaching a camera with State at 0. Delivered as item aura_master_off_keeps_green_dark of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042). Checked by this seat against microscope_agent/runs/run-20260924-002/log.json read at bf8f91f (unchanged since): event 30.

### [aura_reports_five_named_lines](../entries/aura_reports_five_named_lines.json)

The Aura III light engine, opened as Micro-Manager label Aura, exposes five lines named UV, CYAN, GREEN, RED and NIR, each as an on/off property NAME and an intensity property NAME_Intensity, plus a master State property and the descriptive properties Connection, Description, FirmwareVersion, LEModel, Model, Name and SerialNumber.

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-002).

Conditions, verbatim:

> Read back in a preparatory run -- the first real acquisition on this computer, with no plan, the person having placed the 20x and moved the microscope by hand, software moving nothing. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system: E1 from `measured:`. Not a value of any registered observable. Five names agree with the five channels of the vendor designation 5-NII-WA in the device table's light_engines. Names are not wavelengths: this narrows the light_engine_channel_sets gap to what each named line emits, and does not close it. Slot: A4. Delivered as item aura_line_names of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042). Checked by this seat against microscope_agent/runs/run-20260924-002/log.json read at bf8f91f (unchanged since): event 16.

### [pymmcore_plus_micromanager_copy_loads_single_cam_red_config](../entries/pymmcore_plus_micromanager_copy_loads_single_cam_red_config.json)

The Micro-Manager copy that pymmcore-plus installs, Micro-Manager_2.0.3_20260806 (MMCore 12.5.0, device API 75), loads single_cam_red_noDMD_nocom10.cfg with all 21 of its devices: the stand and its elements, the LightEngine and Aura light engines, Kinetix_red, NIDAQHub and LUNF-Blanking, and the Core.

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-002).

Conditions, verbatim:

> Read back in a preparatory run -- the first real acquisition on this computer, with no plan, the person having placed the 20x and moved the microscope by hand, software moving nothing. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system: E1 from `measured:`. Not a value of any registered observable. A fact about that copy and that configuration on this computer; another copy or version may fail differently. LUNF-Blanking being among the loaded devices is what makes prior_mm_config_declares_lunf_blanking a live route today, not a historical one: see single_cam_red_config_can_switch_confocal_lines. The item also said this copy has no MightexPolygon1000 adapter; that rests on a commit message and not on the cited event, and is not entered. Slot: O1 preflight. Delivered as item pymmcore_plus_copy_loads_this_config of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042). Checked by this seat against microscope_agent/runs/run-20260924-002/log.json read at bf8f91f (unchanged since): event 8.

### [single_cam_red_config_arms_autoshutter_on_the_lightengine](../entries/single_cam_red_config_arms_autoshutter_on_the_lightengine.json)

The configuration single_cam_red_noDMD_nocom10.cfg sets the Micro-Manager core shutter to LightEngine and turns AutoShutter on. After the load, setting AutoShutter to 0 as the first call took effect: getAutoShutter returned False and the core AutoShutter property read 0.

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-002).

Conditions, verbatim:

> Read back in a preparatory run -- the first real acquisition on this computer, with no plan, the person having placed the 20x and moved the microscope by hand, software moving nothing. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system: E1 from `measured:`. Not a value of any registered observable. The two settings are lines 171-172 of the configuration at agentic-microscope fbedef0 (sha256 8184073e...), read by this seat; the read-back is the run's. What it means: with AutoShutter on, a snap opens the Spectra III light engine by itself, so anything that loads this configuration and takes a frame before turning AutoShutter off has turned a light on. Slot: O1 preflight and the orchestrator. Delivered as item autoshutter_zero_read_back_after_load of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042). Checked by this seat against microscope_agent/runs/run-20260924-002/log.json read at bf8f91f (unchanged since): event 8.

### [single_cam_red_config_loads_no_nidaq_analogue_output](../entries/single_cam_red_config_loads_no_nidaq_analogue_output.json)

The configuration single_cam_red_noDMD_nocom10.cfg loads no NIDAQ analogue-output device: its NIDAQ devices are NIDAQHub and the digital-output LUNF-Blanking only, so nothing in it addresses an analogue line such as Dev1/ao2.

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-002).

Conditions, verbatim:

> Read back in a preparatory run -- the first real acquisition on this computer, with no plan, the person having placed the 20x and moved the microscope by hand, software moving nothing. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system: E1 from `measured:`. Not a value of any registered observable. What it does NOT establish, and the run says so: whether NIDAQHub's own initialisation writes any analogue line, which happens inside the adapter and is not observable from Micro-Manager -- a gap in the device table. It matters because the piezo controller sums an analogue command with the digital one when its analogue input is enabled (npcd_analogue_and_digital_commands_are_summed); that input was reported disabled on 2026-09-24 (piezo_command_path_as_found_20260924). Slot: O1 preflight. Delivered as item no_nidaq_analogue_output_loaded of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042). Checked by this seat against microscope_agent/runs/run-20260924-002/log.json read at bf8f91f (unchanged since): event 11.

### [hoomd_blue_6_1_0_documents_a_contact_friction_pair_module](../entries/hoomd_blue_6_1_0_documents_a_contact_friction_pair_module.json)

Hofmann et al. state that their frictional-contact force, with its thermodynamically consistent noise, was merged into HOOMD-blue and is documented in HOOMD-blue version 6.1.0 as the module hoomd.md.pair.friction.

How it is known: from a document, a reading off the instrument, or another project's record; published literature (E3 · literature:src_hofmann_2026_frictional_contacts).

Conditions, verbatim:

> A STATEMENT ABOUT SOFTWARE BY THE AUTHORS, as of the article's publication (online 21 April 2026). It names version 6.1.0 and says nothing about later releases. This repository pins HOOMD-blue 7.2.0; whether the module is present and unchanged there is not asserted by this entry and has to be checked against that release before a plan relies on it. The paper's MIPS results were not run in HOOMD but in LAMMPS.

### [rpy_brownian_dynamics_plugin_was_run_on_hoomd_2_4_0](../entries/rpy_brownian_dynamics_plugin_was_run_on_hoomd_2_4_0.json)

Lee and Park ran their Rotne-Prager-Yamakawa Brownian dynamics through the Positively Split Ewald HOOMD-blue plugin of Fiore et al. under HOOMD 2.4.0 with CUDA 9.2, at about 1,500 time steps per hour for 10,648 particles on one NVIDIA GeForce GTX 1070, and report that the plugin has compatibility problems across HOOMD releases and fails unless modified, the current HOOMD release when they wrote being 5.4.0.

How it is known: from a document, a reading off the instrument, or another project's record; published literature (E3 · literature:src_lee_park_2026_gel_normal_stress).

Conditions, verbatim:

> A STATEMENT ABOUT SOFTWARE BY THE AUTHORS, as of their writing (published February 2026). This repository pins HOOMD-blue 7.2.0, three major versions later than 2.4.0; nothing in the source says the plugin runs there, and nothing here asserts it. For reproducibility the authors point to a separate Python Stokesian-dynamics implementation with RPY mobility that avoids the HOOMD dependency. The speed depends on the mean bond number.

### [bangs_flash_red_plain_ps_material](../entries/bangs_flash_red_plain_ps_material.json)

Bangs Laboratories FSFR004 and FSFR005 are polystyrene microspheres with the Flash Red fluorophore embedded within the bead matrix and a plain (non-functionalised) surface.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:bangs_flash_red_plain_ps).

Conditions, verbatim:

> From the category page: the line is 'Fluorescent Plain Polystyrene' and the page states the fluorophores are embedded within the bead matrix. Spherical shape is stated by the product name 'Microspheres'. Plain means no carboxyl or amine surface group is sold on these codes -- which differs from the Abvigen carboxyl particles already in this store, and matters for sticking to glass. The suspension medium and any surfactant are not stated on the page read. Type-level fact about the catalogue product as sold. It says nothing about a bottle on this bench until a person reads the catalogue number and lot off it; no such reading is on record yet. RENAMED 2026-10-07 under task 047, same claim, value, source and grade (rule 8: a rename is not a supersede): identifiers.catalogue_product became catalog_numbers_listed, which is not addressable, because it lists two catalogue numbers and a list is not one; and product_line became product, the addressable class handle, so the entry answers to the vendor's line name 'Fluorescent Plain Polystyrene'.

### [bangs_fluorescent_ps_contains_sodium_azide](../entries/bangs_fluorescent_ps_contains_sodium_azide.json)

Bangs fluorescent microsphere suspensions covered by PDS 731 contain sodium azide.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:bangs_pds731).

Conditions, verbatim:

> The concentration is not given in PDS 731; the Safety Data Sheet would hold it and was not read. The sheet's disposal note: azide can form explosive metal azides with lead or copper plumbing, so flush with a large volume of water. This is knowledge about the product; handling rules are the person's. Azide also matters to any biological sample mixed with these beads. Type-level: about the product as supplied, not about a bottle on this bench until its catalogue and lot numbers are read. RENAMED 2026-10-07 under task 047, same claim, value, source and grade (rule 8: a rename is not a supersede): identifiers.catalogue_product became catalog_numbers_listed, not addressable, because it holds a range or a list and not one catalogue number; the line is addressed instead by product = 'Fluorescent Microspheres', the vendor's own name for it as printed in this entry's source, which is a class handle and not an item.

### [bangs_fluorescent_ps_storage](../entries/bangs_fluorescent_ps_storage.json)

PDS 731 specifies storage at 2-8 C in the supplied opaque bottle, warns that freezing, drying or centrifuging may cause irreversible aggregation, and states stability of 12 months from purchase under the manufacturer's handling.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:bangs_pds731).

Conditions, verbatim:

> Stability is counted from the purchase date, which is not on record here. Opaque storage is against photobleaching. The centrifugation warning matters for any washing step in sample preparation. Type-level: about the product as supplied, not about a bottle on this bench until its catalogue and lot numbers are read. RENAMED 2026-10-07 under task 047, same claim, value, source and grade (rule 8: a rename is not a supersede): identifiers.catalogue_product became catalog_numbers_listed, not addressable, because it holds a range or a list and not one catalogue number; the line is addressed instead by product = 'Fluorescent Microspheres', the vendor's own name for it as printed in this entry's source, which is a class handle and not an item.

### [f8801_material_and_surface](../entries/f8801_material_and_surface.json)

Invitrogen F8801 microspheres are polystyrene, carboxylate-modified on the surface, and loaded with a red fluorescent dye.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:invitrogen_f8801).

Conditions, verbatim:

> Material Polystyrene, Surface Modification Carboxylate and Color Red are the page's own Specifications rows. Polystyrene is the premise a Stokes-Einstein estimate and a refractive index lookup rest on; the carboxylate surface is what governs sticking to glass. The page does NOT state that the beads are spherical in so many words beyond calling them microspheres, nor the suspending medium, nor the density -- none of those is asserted here. The dye is proprietary and unnamed. No quantity subject: nothing here is a number. THIS IS ABOUT THE TYPE, NOT THE BOTTLE. Under the instance/type split, F8801 is a type and its facts are ordinary entries at E3 from the supplier; the beads on the bench are the instance particle_suspension_b, and the claim joining them is particle_suspension_b_identity at E5, because the person named the product by pasting this page and did not read the bottle. Anything here applied to the bench inherits E5. READ BY THIS SEAT, NOT ONLY PASTED. The person's paste (microscope_agent/questions/mic-20260930-001/asked_of_the_person.jsonl at 51c61eb) is what identified the product; the values here were read by this seat off the vendor's own page on 2026-10-01 and agree with the paste on every field, which is why this is spec: at E3 and not a copy of a copy.

### [micromanager_focus_direction_encoding_mmcore_12_5_0](../entries/micromanager_focus_direction_encoding_mmcore_12_5_0.json)

In Micro-Manager with MMCore 12.5.0, a configuration file line 'FocusDirection,\<stage\>,\<n\>' sets that stage's focus direction from the integer n by its sign: any positive n means increasing position brings the objective closer to the sample, any negative n means increasing position moves the objective away from the sample, and n = 0 means the direction is unknown. A value set this way replaces whatever the device adapter reports.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:micromanager_mmcore_12_5_0).

Conditions, verbatim:

> TWO LINKS, BOTH FROM MICRO-MANAGER'S OWN SOURCE, NAMED BY FILE AND LINE AT mmCoreAndDevices bf906ad7 (src_micromanager_mmcore_focus_direction_12_5_0). Link 1, file to core: the loader takes a FocusDirection line of exactly three tokens and calls setFocusDirection(label, atol(third token)); setFocusDirection keeps only the SIGN -- positive is TowardSample, negative is AwayFromSample, zero is Unknown (MMCore.cpp 7760-7768, 2261-2268). So 1 and 2 both mean toward sample, and -1 and -2 both mean away; there is no separate ordinal encoding. Link 2, value to meaning: +1 is 'increasing position brings objective closer to sample', -1 is 'increasing position moves objective away from sample', 0 is unknown (MMCore.cpp 2225-2229; MMDeviceConstants.h 291-295; MMDevice.h 612-624). This claim is about integer tokens; what atol makes of a token that is not an integer is outside it. A line with other than three tokens fails the configuration load. A line naming a label that is not a focus stage is silently ignored -- the code says so, 'for legacy reasons' -- so a misspelt stage label sets nothing and raises nothing. PRECEDENCE: the configuration's value wins. The stage returns the adapter's own report only while nothing has been set, and a FocusDirection line sets it (StageInstance.cpp 40-61). WHAT IS NOT KNOWN, A GAP: what the Nikon Ti2 adapter (library NikonTi2) reports by itself, which is what the core returns when a configuration carries NO FocusDirection line for ZDrive. Its source is not in Micro-Manager's public repository, and nothing here infers it. WHAT THE CORE DOES WITH IT: within MMCore the value is stored, returned by getFocusDirection and written back when a configuration is saved; no other use was found under MMCore/, so the core does not change how it moves because of it. What applications above the core do with it was not searched. THIS ENTRY NAMES NO PHYSICAL DIRECTION FOR THIS STAND -- that is z_retract_direction_is_measured -- and does not say which value this stand's configuration ought to carry; combining the two is the microscope side's check. VERSION: the instrument runs Micro-Manager 2.0.3 20260806 with MMCore 12.5.0 and device interface 75 (pymmcore_plus_micromanager_copy_loads_single_cam_red_config). The exact commit that build came from was not identified; the pin is the last main commit before 2026-08-06, and the logic is byte-identical across the whole 12.5.0 span, so the answer does not depend on which. A FACT USED BY A SAFETY CHECK, NOT A SAFETY LIMIT: nothing here is an envelope value, and it grants no motion. Not taken from the imported .cfg comments, the prior project's notes, any web summary, or memory.

### [pymmcore_plus_instance_holds_its_singleton_weakly](../entries/pymmcore_plus_instance_holds_its_singleton_weakly.json)

In pymmcore-plus 0.18.1, CMMCorePlus.instance() keeps its global singleton through a weak reference. When the last strong reference to a loaded core is dropped the core can be destroyed, which unloads its devices, and a later instance() call returns a new, empty core. Code that loads a configuration has to keep its own strong reference to the core.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:pymmcore_plus_0_18_1_core_mmcore_plus_py).

Conditions, verbatim:

> The mechanism is read in the library's own source as installed on this computer (pymmcore_plus/core/_mmcore_plus.py, which imports weakref and stores the singleton as weakref.ref; sha256 12eef1d98aa1719f7536045cf24c91b876b9326f5f3998c4a5a6c04019b98f54), so this is E3, the library being the document (10.3 rule 2's spirit, though it is software rather than a device). Observed here as its consequence: run-20260924-001 loaded every device and failed moments later with 'No device with label "LappMainBranch1"' (event 12 of that run's log, read at bf8f91f). The microscope seat's account of the cause is in its code at microscope_agent/src/devices/micromanager.py, read at bf8f91f. Slot: the device wrapper. A later pymmcore-plus release may change it. Delivered as item pymmcore_plus_singleton_is_weak of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042).

### [tracer_number_density_from_diameter](../entries/tracer_number_density_from_diameter.json)

The number of Abvigen AFR-0500-COOH particles per millilitre of the as-supplied 10 mg/ml suspension is 6*C/(pi*rho*d**3), where C is the mass concentration, rho the particle density 1.03 g/cm3 and d the particle diameter.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:abvigen_red_ps_cooh).

Conditions, verbatim:

> WHY A FORMULA AND NOT SIXTY ROWS. The data sheet prints Particles/mg and Particles/ml for sixty diameters from 0.05 um to 3000 um, and the obvious filing is sixty calibration entries. That would be false: the table is not sixty measurements. Checked against 6/(pi*rho*d**3) at 0.05, 0.5, 1, 10, 100 and 3000 um, the ratio is 1.0023 at every one of them and 0.9996 at the last -- a constant offset over five decades, which is rounding, not physics. The vendor computed the table from the density and the geometry of a sphere, so what is actually known is the relation, and entering it as data would dress an arithmetic identity as sixty independent facts that could each be refuted separately. THE GRADE IS E3 AND IT IS INHERITED, NOT EARNED BY THE ARITHMETIC. The geometry is exact, but rho is a vendor specification, so the result can be no better than E3 -- and a caller supplying its own measured diameter does not thereby get an E1 answer, because rho is still in the denominator. IT DOES NOT ANSWER WHAT THE CALLER ASKED. Two separate things stand between this and the number density in anybody's sample. First, d is unknown: this is a product-family sheet and nothing records which diameter was bought (gap tracer_diameter_unknown). Until a person says which, the formula has an unbound input and yields nothing. Second, C here is the stock concentration in the bottle, and any dilution the operator made is an unrecorded fact standing between the stock and the coverslip. mic-20260918-001:v1:widefield_inline:a2 and :a3 both asked for tracer_number_density today and both got `absent`; this entry does not make that answer wrong, and it does not on its own make the next one right. NO SUBJECT, AND THAT IS THE HONEST STATE. Check 44 resolves a `quantity` subject against the names actually used in numbers[] somewhere, and refused an earlier draft of this entry with the right instruction attached -- a subject names a registry so that it can be wrong, do not add the id to make this pass. There is no registry id for the tracer particle: `device` is drawn from the channels and elements of kb/staging/devices.v0.json and a sample is not hardware, `configuration` is an optical path, and contracts/observables.json holds two ids, neither of them this. So the field is left off rather than filled with something adjacent. This is the third instance of one structural gap, after `at` having nowhere to point for 'the room' (lab_ambient_temperature) and the per-lens handle in the pixel-size calibrations; it is raised with manager-librarian, who owns contracts/observables.json. Reachability does not depend on the subject here: the server's handles include an entry's `symbol`, so a query for tracer_number_density finds this entry anyway. 015 WAS WITHDRAWN THE SAME DAY IT WAS ISSUED, AND THIS ENTRY IS ABOUT THE TYPE. For a few hours this entry read that the product identification had been withdrawn and that it was not about the bottle on this bench. The person reversed that on 2026-09-19 after the prior project's records were opened: the bottle IS AFR-0500-COOH, and what is wrong is Abvigen's published data. WHAT DECIDED IT WAS AN ASYMMETRY, NOT A MEASUREMENT, and that is worth keeping because the measurement alone did not settle it. Both explanations -- wrong bottle, or wrong data sheet -- predict green-excited particles visible at 605, and 015's own evidence, a label that says nothing, is equally consistent with either. What broke the tie is that the Abvigen page has two documented errors unrelated to any of this (a monoclonal-antibody filing, and the product name printed in the Particle Size field), so `the data sheet is wrong` is far the cheaper explanation. See abvigen_published_data_is_unreliable. AND THE ENTRY IS STILL NOT DIRECTLY ABOUT THE BOTTLE. Under the instance/type split architecture ruled in 6eaee1b, this is a fact about the TYPE `AFR-0500-COOH`, at E3, from the supplier. The bottle is an INSTANCE and lives in the sample table. The claim joining them -- `this bottle is that product` -- carries its own grade and is E5, because the label is still silent and the person's judgement is what stands in for it; it becomes E3 the day somebody reads a label that says. So applying anything here to the particles on the bench inherits E5 by 5.8, worst in the chain. Restored, but not restored to E3. THE `abvigen_` HANDLES STAY, and they are now right for a different reason than the one they were changed for. They were renamed from `tracer_` because the word `tracer` asserted these were ours in a string nothing checks; they keep the name because these are type-level facts and the type is what they should be named for. A query for our tracer should not land here. THE CLAIM SENTENCE WAS CORRECTED TOO, AND IT HAD BEEN THE LAST PLACE THE OLD ASSERTION SURVIVED. The handles were renamed to `abvigen_` hours earlier, and the first words of the claim still read `The tracer particles...` -- so this entry's body said `a query for our tracer should not land here` while its own headline sentence said these were our tracers. Found by librarian-agent-a5 verifying my report against the tree, which is exactly why that verification was handed over: my account came from memory of what I had done. The entry_id still begins `tracer_` and stays that way deliberately -- it is the citation handle, the polystyrene dispersion entries reference it by name, and renaming it is a deletion under rule 8.

### [tracer_particle_material_and_shape](../entries/tracer_particle_material_and_shape.json)

The Abvigen AFR-0500-COOH particles are spherical polystyrene, surface-functionalised with carboxyl (-COOH) groups, supplied as a suspension in deionised water.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:abvigen_red_ps_cooh).

Conditions, verbatim:

> Applies to the product family as supplied, at every diameter it is sold in, and says nothing about which diameter is in use here (gap tracer_diameter_unknown). WHY THIS IS AN ENTRY AND NOT FILING. Spherical and polystyrene are the two premises a Stokes-Einstein estimate rests on, and a caller that assumes them without a source has made an assumption it cannot cite; carboxyl surface is what governs whether the particles stick to glass or to each other, which is an imaging outcome and not chemistry trivia. THE REFRACTIVE INDEX IS NOT HERE. Polystyrene has a well-known one and this document does not print it, so nothing is entered for it from this source -- but the gap changes character: refractive_index was `absent` and is now findable, because the material is established and a real optical reference can be cited against it. Filling it from memory would be E6 and would enter nothing. NO SUBJECT, AND THAT IS THE HONEST STATE. Check 44 resolves a `quantity` subject against the names actually used in numbers[] somewhere, and refused an earlier draft of this entry with the right instruction attached -- a subject names a registry so that it can be wrong, do not add the id to make this pass. There is no registry id for the tracer particle: `device` is drawn from the channels and elements of kb/staging/devices.v0.json and a sample is not hardware, `configuration` is an optical path, and contracts/observables.json holds two ids, neither of them this. So the field is left off rather than filled with something adjacent. This is the third instance of one structural gap, after `at` having nowhere to point for 'the room' (lab_ambient_temperature) and the per-lens handle in the pixel-size calibrations; it is raised with manager-librarian, who owns contracts/observables.json. 015 WAS WITHDRAWN THE SAME DAY IT WAS ISSUED, AND THIS ENTRY IS ABOUT THE TYPE. For a few hours this entry read that the product identification had been withdrawn and that it was not about the bottle on this bench. The person reversed that on 2026-09-19 after the prior project's records were opened: the bottle IS AFR-0500-COOH, and what is wrong is Abvigen's published data. WHAT DECIDED IT WAS AN ASYMMETRY, NOT A MEASUREMENT, and that is worth keeping because the measurement alone did not settle it. Both explanations -- wrong bottle, or wrong data sheet -- predict green-excited particles visible at 605, and 015's own evidence, a label that says nothing, is equally consistent with either. What broke the tie is that the Abvigen page has two documented errors unrelated to any of this (a monoclonal-antibody filing, and the product name printed in the Particle Size field), so `the data sheet is wrong` is far the cheaper explanation. See abvigen_published_data_is_unreliable. AND THE ENTRY IS STILL NOT DIRECTLY ABOUT THE BOTTLE. Under the instance/type split architecture ruled in 6eaee1b, this is a fact about the TYPE `AFR-0500-COOH`, at E3, from the supplier. The bottle is an INSTANCE and lives in the sample table. The claim joining them -- `this bottle is that product` -- carries its own grade and is E5, because the label is still silent and the person's judgement is what stands in for it; it becomes E3 the day somebody reads a label that says. So applying anything here to the particles on the bench inherits E5 by 5.8, worst in the chain. Restored, but not restored to E3. THE `abvigen_` HANDLES STAY, and they are now right for a different reason than the one they were changed for. They were renamed from `tracer_` because the word `tracer` asserted these were ours in a string nothing checks; they keep the name because these are type-level facts and the type is what they should be named for. A query for our tracer should not land here. THE CLAIM SENTENCE WAS CORRECTED TOO, AND IT HAD BEEN THE LAST PLACE THE OLD ASSERTION SURVIVED. The handles were renamed to `abvigen_` hours earlier, and the first words of the claim still read `The tracer particles...` -- so this entry's body said `a query for our tracer should not land here` while its own headline sentence said these were our tracers. Found by librarian-agent-a5 verifying my report against the tree, which is exactly why that verification was handed over: my account came from memory of what I had done. The entry_id still begins `tracer_` and stays that way deliberately -- it is the citation handle, the polystyrene dispersion entries reference it by name, and renaming it is a deletion under rule 8.

### [abvigen_published_data_is_unreliable](../entries/abvigen_published_data_is_unreliable.json)

Abvigen's published product data for the Red PS Fluorescent Particles-COOH line carries documented errors, including a monoclonal-antibody filing and the product name printed in the Particle Size field, in addition to excitation and emission figures that instrument testing has disproved. Nothing on that page should be treated as load-bearing without independent confirmation.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@abvigen-verification-2026-09-06).

Conditions, verbatim:

> ABOUT A PUBLISHER, NOT ABOUT A BOTTLE, which is the whole reason this one crossed when the measurements beside it did not. 10.3 rule 1 caps a run taken elsewhere at E3 and, worse, a value about another laboratory's bottle needs a same-stock E5 assumption before it means anything here. This claim needs neither: it is about a document, and this store holds that document (src_abvigen_red_ps_cooh_datasheet), so it is checkable rather than inherited. THIS IS WHAT REVERSED TASK 015. The observation on this bench -- green-excited particles visible at 605 -- is equally consistent with `the bottle is not the Abvigen product` and with `the bottle is the Abvigen product and the sheet is wrong`, and a label that says nothing does not separate them either. What separates them is that the page is independently known to be careless, which makes the second explanation far cheaper. Kept as an entry rather than left in a commit message because a reversal whose reason is not on disk gets re-reversed by the next person holding the same data sheet. WHAT IT DOES NOT SAY. It does not say every figure on the page is wrong, and it is not a licence to discard a published number because it is inconvenient. The seven entries taken from that sheet remain on disk at E3 about the type; two of them -- the excitation and emission peaks -- are marked disproved, and that marking rests on two independent instrument observations rather than on this entry. This entry lowers how much an unconfirmed figure from that supplier should be trusted; it does not by itself refute any particular one. 10.2.1: TRANSFER, slot KB entry, 10.3 rule 1, capped E3. NO `grade_tag`, following the seven prior_run entries already on disk, all of which carry none -- and that is a gap rather than a convention. 4.3.1 orders within E3 by grade_tag (peer_reviewed -\> textbook -\> vendor_spec -\> preprint) and `prior_run` is not in that enum, so every prior-project item sorts last inside E3 by default rather than by anyone deciding it should. Against this store's own vendor_spec entries that ordering is arguably backwards here: this claim is an instrument verification of a vendor page, and it sorts below the page. Raised with manager-librarian, who owns the enum; not worked around by borrowing a tag that would describe the evidence falsely.

### [branch_selector_is_pinned_by_integer_not_label](../entries/branch_selector_is_pinned_by_integer_not_label.json)

On the prior project's bench the Lapp branch selector's enum names were false and its integer state was true: the configuration declared the label-to-position mapping inverted, so every label the device reported was the wrong name for the position it was in. The discipline that follows is to select that branch by integer and never by name.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@34a432c).

Conditions, verbatim:

> WHAT CROSSES IS THE DISCIPLINE, NOT THE LABEL, AND THE DIFFERENCE IS THE WHOLE ENTRY. Their `mirror_in`/`mirror_out` strings and their State-to-position mapping are DOWNGRADE under 10.2.1 and are not entered: a label that was wrong there is not evidence here, and copying it would import the defect rather than the lesson. WHAT IT COST THEM: following the labels turned the light off, cost a diagnosis session, and the branch stood BOOKED AS FALSIFIED FOR TWO DAYS before the operator's own mapping showed the mislabelled enum was the fault. The record is worse than that: two further sites had been written by name and would have silently selected the BLOCKING position the moment the labels were corrected. Fixing the names would have broken the working config. Their repair was to convert every functional reference to the integer and to leave the `Label` lines in place only because the GUI needs names to show, with nothing selecting a position by one. WHY THIS MATTERS HERE RATHER THAN THERE: lapp_branch_assignment is open in this store and its own status already says it is settled by ACQUIRING and not by read-back. This entry supplies the reason that sentence is true -- this is the selector whose label and state read back consistently with each other for weeks while the mapping between them was inverted, so every signal a caller would normally trust agreed, and agreed wrongly. IT NARROWS lapp_branch_assignment AND DOES NOT CLOSE IT. The open question is which of widefield_source_a and widefield_source_b is which engine on THIS bench. Nothing here answers that: it is another bench's configuration defect, and 10.3 rule 1 caps it at E3 for exactly that reason. What it changes is what would count as an answer -- a label read back from this stand is not one, and a plan that pins the integer is not exposed to the mapping being wrong. That is a narrowing, and manager-microscope should read it as one. ONE DISCREPANCY IN THE RELAY, recorded rather than smoothed: task 029 quotes the source as saying `State 1 is the Aura position`. The document says State 1 is the measured light-passing position, confirmed 2026-09-04 and re-confirmed 2026-09-06, and separately that the operator gave `mirror_in \<-\> State 1` on 2026-09-05. Those may be the same position on that bench; the document does not say so, and neither does this entry. NO NUMBERS AND NO `validity`: this is a claim about how a device must be addressed, not a quantity, so a query's condition_range comes back unconstrained rather than satisfied. Slot: A4, device combination. Rule passed: 10.3 rule 2 -- what is taken is sourced to the operator's measurement and the applied configuration, not to the prior repository's prose about them.

### [dropped_frames_raise_nothing](../entries/dropped_frames_raise_nothing.json)

MMCore raises no error and writes no record when it drops a frame. Gaps in the ImageNumber sequence are the only evidence, and MicroManager's own metadata files do not record the loss.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@safety-2026-09-03).

Conditions, verbatim:

> A SILENT FAILURE WITH EXACTLY ONE WITNESS, and the witness is not where anyone looks -- the metadata file that is supposed to describe the acquisition is the thing that does not record it. So a series with missing frames is indistinguishable from a complete one unless ImageNumber is checked explicitly, and every derived quantity computed from frame count or elapsed span is wrong by an amount nothing reports. IT COMPOUNDS THE OTHER TWO. The rate cannot be taken from the requested interval, the jitter cannot be taken from consecutive timestamps, and the frame count cannot be trusted without a separate check -- three independent defects in the same measurement, none of which announces itself. 10.2.1: TRANSFER. Row: 10.2's hardware-control-path row, whose prerequisite -- the four device-interface functions -- is met, and whose own rule says it does not wait for `envelope/` because wrapping a control path needs no safety limit. Slot: KB entry, named in the 2026-09-18 amendment. Rule: 10.3 rule 1, capped E3. Confirming it on this instrument promotes it to E1 and supersedes this entry.

### [emission_wheel_filter_positions](../entries/emission_wheel_filter_positions.json)

The emission filter wheel holds single-band filters in positions 1 to 4 -- FF01-432/36-32 at 1, FF01-515/30-32 at 2, FF01-595/31-32 at 3, FF01-680/42-32 at 4 -- with a quad-band filter at position 0 whose part number was never supplied. Positions 5 to 8 are blocked by a metal plate.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@filters-2026-09-06).

Conditions, verbatim:

> THE PAIRING IS INFERRED, NOT CONFIRMED, AND THAT IS THE PRIOR PROJECT'S OWN WARNING carried forward verbatim: `The position\<-\>part pairing is INFERRED from the wheel label naming the EXCITATION line, not stated by the operator. Confirm off the engraving.` So the wheel labels read 405/488/555/647, which are EXCITATION lines, and the parts listed are the emission filters someone matched to them. Nobody read a part number off a filter. USE THIS AT E5, NOT E3. The entry's own grade is E3 because 10.3 rule 1 caps a prior run there, but applying it to the wheel on this bench today stacks two assumptions on top: that the pairing was right when written, and that nothing has been swapped since. 5.8 takes the worst of a chain. The second assumption is lighter than it would be for a consumable -- a filter is a part and stays in its slot unless somebody pulls it, where a bottle gets replaced -- but lighter is not absent, and the bead is precisely why: this store spent a day today on a bottle whose continuity nobody had written down. ONE READING OF THE ENGRAVING SETTLES IT and moves this to `spec:\<part\>` at E3. That is the same cheap confirmation 10.2's consumables row describes for a lot number: bring the identifier a person can verify by looking, and let them look. WHAT IS NOT HERE: position 0's part number, which was never supplied. The store's EM-Quad-Multiband record lists bands [[432,36],[515,30],[595,31],[680,42]], exactly the four single-bands combined, which is suggestive and is NOT a part number and is not entered as one.

### [emission_wheel_red_arm_is_position_3](../entries/emission_wheel_red_arm_is_position_3.json)

On the prior project's instrument the red particle's emission was strongest through emission wheel position 3, measured by running the same particle through all four single-band positions on 2026-09-06.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@filters-2026-09-06).

Conditions, verbatim:

> MEASURED RATHER THAN CHOSEN, and the controls are what make it quantitative. The four positions gave 0.1, 1.6, 362.1 and 62.3 ADU. The first two bands sit blueward of the excitation and cannot carry fluorescence, so they read the floor at about 0.4 percent of the signal -- which is what establishes that the 677-701 band at 17.2 percent is real emission from the red tail of one broad emitter rather than bleed, and that position 3 wins by a real margin rather than a preference. The ADU figures themselves are NOT entered: instrument-specific, DISCARD under 10.2.1, and quoted here only as the reasoning behind the ranking. WHAT IT ESTABLISHES IS A BAND, NOT A PEAK, and the prior project says so itself: `Four bandpasses bracket a band, they do not locate a peak`, which is why it named a TRITC stand-in rather than inventing a number. A6 needs the wavelength actually collected and that is the band of position 3, not a peak inside it. CORROBORATED INDEPENDENTLY ON THIS BENCH. Today's E2 observation, particles_show_on_the_green_605_path, puts this bottle's emission in the same band on this instrument. Two observations, two instruments, two projects. The prior project's numbers are not borrowed for that -- the agreement is what makes borrowing unnecessary. WHICH WHEEL is not settled by this. emission_wheel_camera_mapping is E5 `operator_recall:` and says the first wheel serves red, `probably`. This entry is about positions WITHIN a wheel and neither confirms nor contradicts it. THE POSITION IS A STRING, NOT A NUMBER, and the schema caught me writing it as one. 5.3's own examples of a nominal designation are `20x` 대물렌즈, `1.5x` 줌 and 필터 위치 `3` -- this exact case. A slot index names WHICH SLOT and asserts no quantity, so it has no uncertainty and no place in numbers[]. I reached for `precision: exact` to express that, which the enum does not have, and the absence is the argument: a value needing `exact` is a value that should not be in numbers[] at all.

### [filter_cube_mxr00724_is_five_band](../entries/filter_cube_mxr00724_is_five_band.json)

The cube in the Ti2 filter turret is a Nikon MXR00724, LED-DA/FI/TR/Cy5/Cy7-A, a FIVE-band cube, and it sits in FilterTurret1 position 0. Its emitter passes bands centred at 440, 520.5, 606, 694 and 808.5 nm.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@filters-2026-09-06).

Conditions, verbatim:

> FIVE BANDS, AND THE LABEL SAYS THREE. The turret's metadata label reads DA/FI/TR, a three-band set, across all 2312 of the prior project's metadata records -- while 764 frames were shot on 647-Cy5, which a three-band cube passes almost nothing of. The prior project resolved it on 2026-08-10 by reading NIS-Elements Device Manager \> Filter Block Settings: the physical part is MXR00724, five bands. A label disagreeing with the part in the slot, discovered by counting frames that should not have worked. THE POSITION IS 0 AND THE SOFTWARE LABEL SAYS 1. The MicroManager label `1-MXR00724 -Empty` reads as position 1 and is wrong twice over -- the turret numbers from 0, and `Empty` was a display artifact. Corrected 2026-09-09 against three independent records including a contrast measurement: state 0 gave 1.00x against 5.16/5.15/5.13x for states 1/2/3, so 0 holds the cube and the rest are empty slots. Setting the turret to 1 inserts an EMPTY slot, which on the confocal path is the difference between blocked and clear. THE EXCITER AND EMITTER ARE SEPARATELY SWAPPABLE. The prior project's note corrects an earlier assumption that a cube is one monolithic block: exciter and emitter are individual units in the cube frame. So the part number identifies a set that was shipped together, not a guarantee that all three pieces are still the ones listed. WHY THIS MATTERS FOR THE BEAD. The exciter's third band is 554.5/21, i.e. 544-565 nm, and the emitter's third is 606/34, i.e. 589-623 nm. Those are the 555 and 605 the person reported reading -- so the operator's two numbers are this cube's TRITC window pair, which is a more specific account of where they came from than anything this store had. And because the emitter also passes 694/34, a particle emitting in the red is not excluded by this cube; the band is selected downstream in the wheel. E3 AND STILL CARRYING A CONTINUITY ASSUMPTION, like everything else from that repository: it was verified there, not here.

### [focus_frames_over_the_clip_limit_are_not_readable](../entries/focus_frames_over_the_clip_limit_are_not_readable.json)

In dino-autofocus's focus core the metrics read pixels as they come and do not mask clipped ones, so a frame with clipped particle cores under-reads its own sharpness and can move the peak; each frame's clipped-pixel fraction is therefore kept beside its score, and frames whose fraction exceeds the caller's limit are dropped from the sweep as not readable.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:dino-autofocus@fa9790378ea3f06e94b933a2fb65219322f6702a).

Conditions, verbatim:

> A classical sharpness metric of one monochrome widefield frame as read, clipped pixels not masked. It ranks frames of one sweep against each other; it says nothing about which plane holds the sample, and its value is not comparable across metrics or across sweeps taken with different exposure or binning. The clipped-pixel limit is the caller's and is not entered. 10.2.1: TRANSFER. Place: a store entry -- the one place 10.2's 2026-10-03 paragraph opens for dino-autofocus before 11-24 designs the focus search, so that design can cite the method without any code having crossed. Rule: 10.3 rule 1, capped at E3 as a run taken in another project. No figure crosses (rules 3 and 4): every threshold the method uses is its caller's argument and none is entered. It says what the method IS at the pinned commit, not that it works on this stand.

### [focus_metric_brenner_definition](../entries/focus_metric_brenner_definition.json)

In dino-autofocus's focus core, `brenner` is a scale-invariant Brenner sharpness: after the same normalisation as `vollath4`, the mean squared difference between pixels two apart is taken on each image axis and the two are summed; its source notes that it rises on dim, noisy frames.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:dino-autofocus@fa9790378ea3f06e94b933a2fb65219322f6702a).

Conditions, verbatim:

> A classical sharpness metric of one monochrome widefield frame as read, clipped pixels not masked. It ranks frames of one sweep against each other; it says nothing about which plane holds the sample, and its value is not comparable across metrics or across sweeps taken with different exposure or binning. That it rises on dim, noisy frames is the source's caution, recorded as such and not as a measurement. 10.2.1: TRANSFER. Place: a store entry -- the one place 10.2's 2026-10-03 paragraph opens for dino-autofocus before 11-24 designs the focus search, so that design can cite the method without any code having crossed. Rule: 10.3 rule 1, capped at E3 as a run taken in another project. No figure crosses (rules 3 and 4): every threshold the method uses is its caller's argument and none is entered. It says what the method IS at the pinned commit, not that it works on this stand.

### [focus_metric_peak_brightness_definition](../entries/focus_metric_peak_brightness_definition.json)

In dino-autofocus's focus core, `peak_brightness` (registered as `peak`) is the brightest spot of the block-binned frame minus the median of the binned frame, in raw counts; it is deliberately not scale-invariant, being meant for sparse particle fields at high magnification where a whole-frame sharpness barely moves.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:dino-autofocus@fa9790378ea3f06e94b933a2fb65219322f6702a).

Conditions, verbatim:

> A classical sharpness metric of one monochrome widefield frame as read, clipped pixels not masked. It ranks frames of one sweep against each other; it says nothing about which plane holds the sample, and its value is not comparable across metrics or across sweeps taken with different exposure or binning. Because it is in raw counts, a clipped particle caps it at the camera ceiling; the bin size is a structural default of the source and is not entered. 10.2.1: TRANSFER. Place: a store entry -- the one place 10.2's 2026-10-03 paragraph opens for dino-autofocus before 11-24 designs the focus search, so that design can cite the method without any code having crossed. Rule: 10.3 rule 1, capped at E3 as a run taken in another project. No figure crosses (rules 3 and 4): every threshold the method uses is its caller's argument and none is entered. It says what the method IS at the pinned commit, not that it works on this stand.

### [focus_metric_tenengrad_definition](../entries/focus_metric_tenengrad_definition.json)

In dino-autofocus's focus core, `tenengrad` is Sobel gradient energy -- the mean over the frame's valid interior, with no border padding, of the squared horizontal plus squared vertical Sobel responses -- computed after the same normalisation as `vollath4` and `brenner`.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:dino-autofocus@fa9790378ea3f06e94b933a2fb65219322f6702a).

Conditions, verbatim:

> A classical sharpness metric of one monochrome widefield frame as read, clipped pixels not masked. It ranks frames of one sweep against each other; it says nothing about which plane holds the sample, and its value is not comparable across metrics or across sweeps taken with different exposure or binning. 10.2.1: TRANSFER. Place: a store entry -- the one place 10.2's 2026-10-03 paragraph opens for dino-autofocus before 11-24 designs the focus search, so that design can cite the method without any code having crossed. Rule: 10.3 rule 1, capped at E3 as a run taken in another project. No figure crosses (rules 3 and 4): every threshold the method uses is its caller's argument and none is entered. It says what the method IS at the pinned commit, not that it works on this stand.

### [focus_metric_vollath4_definition](../entries/focus_metric_vollath4_definition.json)

In dino-autofocus's focus core, `vollath4` is a scale-invariant Vollath F-four sharpness of one frame: the frame is median-subtracted and divided by its mean absolute deviation, then on each image axis the mean lag-one product minus the mean lag-two product is taken and the two axes are summed, so that a brighter exposure does not read as sharper and uncorrelated noise cancels.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:dino-autofocus@fa9790378ea3f06e94b933a2fb65219322f6702a).

Conditions, verbatim:

> A classical sharpness metric of one monochrome widefield frame as read, clipped pixels not masked. It ranks frames of one sweep against each other; it says nothing about which plane holds the sample, and its value is not comparable across metrics or across sweeps taken with different exposure or binning. 10.2.1: TRANSFER. Place: a store entry -- the one place 10.2's 2026-10-03 paragraph opens for dino-autofocus before 11-24 designs the focus search, so that design can cite the method without any code having crossed. Rule: 10.3 rule 1, capped at E3 as a run taken in another project. No figure crosses (rules 3 and 4): every threshold the method uses is its caller's argument and none is entered. It says what the method IS at the pinned commit, not that it works on this stand.

### [focus_search_is_coarse_then_fine](../entries/focus_search_is_coarse_then_fine.json)

dino-autofocus's focus search is a coarse sweep around a centre; only when the coarse maximum lies inside the span does a fine sweep follow, around the readback z of that maximum, and a maximum at either end gets no fine pass.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:dino-autofocus@fa9790378ea3f06e94b933a2fb65219322f6702a).

Conditions, verbatim:

> Describes the order and layout of spans only. Every span size, centre, floor and ceiling is an argument the caller supplies, and in this repository the floor and ceiling come from the person's per-objective focus limits, not from dino-autofocus. 10.2.1: TRANSFER. Place: a store entry -- the one place 10.2's 2026-10-03 paragraph opens for dino-autofocus before 11-24 designs the focus search, so that design can cite the method without any code having crossed. Rule: 10.3 rule 1, capped at E3 as a run taken in another project. No figure crosses (rules 3 and 4): every threshold the method uses is its caller's argument and none is entered. It says what the method IS at the pinned commit, not that it works on this stand.

### [focus_search_top_end_extension_layout](../entries/focus_search_top_end_extension_layout.json)

When a coarse maximum sits at the top end of its span, dino-autofocus's focus search lays out the next span centred at the old top with a half-width equal to the old span's full width, swept upward from its low end so that z never jumps upward, and stops extending when the ceiling leaves nothing above the old top; a maximum at the low end is reported as re-centre lower.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:dino-autofocus@fa9790378ea3f06e94b933a2fb65219322f6702a).

Conditions, verbatim:

> Describes the order and layout of spans only. Every span size, centre, floor and ceiling is an argument the caller supplies, and in this repository the floor and ceiling come from the person's per-objective focus limits, not from dino-autofocus. The drafted sentence also said the operator is asked before each extension and that extensions are bounded in number; that half is DISCARDED as a procedure of dino-autofocus's own engine, and the count as a figure -- whether and how often to extend is the 11-24 design's and the person's. 10.2.1: TRANSFER. Place: a store entry -- the one place 10.2's 2026-10-03 paragraph opens for dino-autofocus before 11-24 designs the focus search, so that design can cite the method without any code having crossed. Rule: 10.3 rule 1, capped at E3 as a run taken in another project. No figure crosses (rules 3 and 4): every threshold the method uses is its caller's argument and none is entered. It says what the method IS at the pinned commit, not that it works on this stand.

### [focus_search_yields_points_and_moves_nothing](../entries/focus_search_yields_points_and_moves_nothing.json)

dino-autofocus's focus search file yields spans and ascending z points only: the floor and ceiling are arguments, the points are clipped to them and a span lying wholly outside them is refused, nothing in the file moves anything, and no model value takes part.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:dino-autofocus@fa9790378ea3f06e94b933a2fb65219322f6702a).

Conditions, verbatim:

> Describes the order and layout of spans only. Every span size, centre, floor and ceiling is an argument the caller supplies, and in this repository the floor and ceiling come from the person's per-objective focus limits, not from dino-autofocus. The drafted sentence also said every move is checked and read back by the caller; that half is DISCARDED here because it describes the caller, which in this repository is the orchestrator and its run-time gate, not anything this source can assert. 10.2.1: TRANSFER. Place: a store entry -- the one place 10.2's 2026-10-03 paragraph opens for dino-autofocus before 11-24 designs the focus search, so that design can cite the method without any code having crossed. Rule: 10.3 rule 1, capped at E3 as a run taken in another project. No figure crosses (rules 3 and 4): every threshold the method uses is its caller's argument and none is entered. It says what the method IS at the pinned commit, not that it works on this stand.

### [focus_sweep_light_dropouts_are_not_focus_changes](../entries/focus_sweep_light_dropouts_are_not_focus_changes.json)

In dino-autofocus's focus sweep, a frame whose mean brightness departs from the sweep's median frame mean by more than the caller's tolerance, taken as a fraction of that median, is treated as a light dropout rather than a focus change: it is dropped before the peak is located and cannot be chosen.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:dino-autofocus@fa9790378ea3f06e94b933a2fb65219322f6702a).

Conditions, verbatim:

> A classical sharpness metric of one monochrome widefield frame as read, clipped pixels not masked. It ranks frames of one sweep against each other; it says nothing about which plane holds the sample, and its value is not comparable across metrics or across sweeps taken with different exposure or binning. Corrected from the drafted sentence, which did not say the tolerance is relative to the median; the code compares the absolute departure with the tolerance times the median. 10.2.1: TRANSFER. Place: a store entry -- the one place 10.2's 2026-10-03 paragraph opens for dino-autofocus before 11-24 designs the focus search, so that design can cite the method without any code having crossed. Rule: 10.3 rule 1, capped at E3 as a run taken in another project. No figure crosses (rules 3 and 4): every threshold the method uses is its caller's argument and none is entered. It says what the method IS at the pinned commit, not that it works on this stand.

### [focus_verdict_from_a_classical_sweep](../entries/focus_verdict_from_a_classical_sweep.json)

From a classical sweep dino-autofocus decides its focus verdict in this order: if no frame's high-percentile brightness rises above its median by more than the caller's dark-level floor, `no_sample_here`; otherwise, after light-dropout and over-clipped frames are dropped, too few readable frames or a flat curve gives `unsure`; a maximum at the top of the span gives `step_up` and at the bottom `step_down`, each pointing at the frame of the maximum; a maximum inside gives `in_focus`, pointing at the readable frame nearest the vertex of the parabola through the maximum and its neighbours.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:dino-autofocus@fa9790378ea3f06e94b933a2fb65219322f6702a).

Conditions, verbatim:

> A verdict is for display and for the record only: it never sets a motion limit, opens a gate or takes part in a safety decision, which stay with deterministic guards reading encoder readbacks against limits the person wrote. The vertex itself is a computed z and is never the verdict's z. 10.2.1: TRANSFER. Place: a store entry -- the one place 10.2's 2026-10-03 paragraph opens for dino-autofocus before 11-24 designs the focus search, so that design can cite the method without any code having crossed. Rule: 10.3 rule 1, capped at E3 as a run taken in another project. No figure crosses (rules 3 and 4): every threshold the method uses is its caller's argument and none is entered. It says what the method IS at the pinned commit, not that it works on this stand.

### [focus_verdict_returns_a_branch_never_a_z](../entries/focus_verdict_returns_a_branch_never_a_z.json)

A dino-autofocus focus verdict returns a branch and the index of the frame it chose, never a z to move to; it can refuse and cannot permit, carrying no limit, no target and no command.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:dino-autofocus@fa9790378ea3f06e94b933a2fb65219322f6702a).

Conditions, verbatim:

> A verdict is for display and for the record only: it never sets a motion limit, opens a gate or takes part in a safety decision, which stay with deterministic guards reading encoder readbacks against limits the person wrote. 10.2.1: TRANSFER. Place: a store entry -- the one place 10.2's 2026-10-03 paragraph opens for dino-autofocus before 11-24 designs the focus search, so that design can cite the method without any code having crossed. Rule: 10.3 rule 1, capped at E3 as a run taken in another project. No figure crosses (rules 3 and 4): every threshold the method uses is its caller's argument and none is entered. It says what the method IS at the pinned commit, not that it works on this stand.

### [focus_verdict_step_direction](../entries/focus_verdict_step_direction.json)

In dino-autofocus's focus verdict, `step_up` means best focus lies above the current stage z, so the focus drive would move toward larger z readings, and `step_down` means the opposite.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:dino-autofocus@fa9790378ea3f06e94b933a2fb65219322f6702a).

Conditions, verbatim:

> A verdict is for display and for the record only: it never sets a motion limit, opens a gate or takes part in a safety decision, which stay with deterministic guards reading encoder readbacks against limits the person wrote. The drafted sentence also said that at the oil-immersion objective a step up is the operator's call; that half is DISCARDED here as an operating rule about moving toward an immersed lens, which is the person's to write and not knowledge (10.3 rule 4). 10.2.1: TRANSFER. Place: a store entry -- the one place 10.2's 2026-10-03 paragraph opens for dino-autofocus before 11-24 designs the focus search, so that design can cite the method without any code having crossed. Rule: 10.3 rule 1, capped at E3 as a run taken in another project. No figure crosses (rules 3 and 4): every threshold the method uses is its caller's argument and none is entered. It says what the method IS at the pinned commit, not that it works on this stand.

### [focus_verdict_thresholds_are_all_the_callers](../entries/focus_verdict_thresholds_are_all_the_callers.json)

Every threshold dino-autofocus's focus verdict uses is a keyword argument its caller must supply, with no default in the file and no bench number held there.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:dino-autofocus@fa9790378ea3f06e94b933a2fb65219322f6702a).

Conditions, verbatim:

> A verdict is for display and for the record only: it never sets a motion limit, opens a gate or takes part in a safety decision, which stay with deterministic guards reading encoder readbacks against limits the person wrote. Here the caller is an approved plan, so the thresholds are carried in the plan and not taken from dino-autofocus's own bench tables. 10.2.1: TRANSFER. Place: a store entry -- the one place 10.2's 2026-10-03 paragraph opens for dino-autofocus before 11-24 designs the focus search, so that design can cite the method without any code having crossed. Rule: 10.3 rule 1, capped at E3 as a run taken in another project. No figure crosses (rules 3 and 4): every threshold the method uses is its caller's argument and none is entered. It says what the method IS at the pinned commit, not that it works on this stand.

### [focus_verdict_unsure_is_an_abstention](../entries/focus_verdict_unsure_is_an_abstention.json)

In dino-autofocus's focus verdict `unsure` is an abstention, not a direction: from a classical sweep it is returned when the sweep is empty, when fewer frames than the caller's minimum remain readable, or when the readable curve's contrast is below the caller's floor.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:dino-autofocus@fa9790378ea3f06e94b933a2fb65219322f6702a).

Conditions, verbatim:

> A verdict is for display and for the record only: it never sets a motion limit, opens a gate or takes part in a safety decision, which stay with deterministic guards reading encoder readbacks against limits the person wrote. The source's second mapping, from a learned model's reading, also abstains -- no readable tile, a spread above the caller's bound, or a sign it cannot tell -- and is not entered (see the source record). Completed from the drafted sentence, which omitted the empty sweep. 10.2.1: TRANSFER. Place: a store entry -- the one place 10.2's 2026-10-03 paragraph opens for dino-autofocus before 11-24 designs the focus search, so that design can cite the method without any code having crossed. Rule: 10.3 rule 1, capped at E3 as a run taken in another project. No figure crosses (rules 3 and 4): every threshold the method uses is its caller's argument and none is entered. It says what the method IS at the pinned commit, not that it works on this stand.

### [focus_verdict_vocabulary](../entries/focus_verdict_vocabulary.json)

dino-autofocus's focus verdict takes exactly one of five values: `in_focus`, `step_up`, `step_down`, `no_sample_here` and `unsure`.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:dino-autofocus@fa9790378ea3f06e94b933a2fb65219322f6702a).

Conditions, verbatim:

> A verdict is for display and for the record only: it never sets a motion limit, opens a gate or takes part in a safety decision, which stay with deterministic guards reading encoder readbacks against limits the person wrote. The source names these as the branches of this repository's plan.md 13.2. 10.2.1: TRANSFER. Place: a store entry -- the one place 10.2's 2026-10-03 paragraph opens for dino-autofocus before 11-24 designs the focus search, so that design can cite the method without any code having crossed. Rule: 10.3 rule 1, capped at E3 as a run taken in another project. No figure crosses (rules 3 and 4): every threshold the method uses is its caller's argument and none is entered. It says what the method IS at the pinned commit, not that it works on this stand.

### [focus_verdict_z_is_a_taken_frames_readback](../entries/focus_verdict_z_is_a_taken_frames_readback.json)

The z a dino-autofocus focus verdict carries is the encoder readback of a frame that was actually taken, as handed in by its caller, never a model output and never an interpolated z; a parabola vertex or any model number appears only among the verdict's evidence, tagged with the source's own grade word -- measured, computed or model.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:dino-autofocus@fa9790378ea3f06e94b933a2fb65219322f6702a).

Conditions, verbatim:

> A verdict is for display and for the record only: it never sets a motion limit, opens a gate or takes part in a safety decision, which stay with deterministic guards reading encoder readbacks against limits the person wrote. The verdict cannot check that what it was handed is a readback rather than a commanded z; that is the caller's duty. The source's three grade words are its own and are not this store's grades. 10.2.1: TRANSFER. Place: a store entry -- the one place 10.2's 2026-10-03 paragraph opens for dino-autofocus before 11-24 designs the focus search, so that design can cite the method without any code having crossed. Rule: 10.3 rule 1, capped at E3 as a run taken in another project. No figure crosses (rules 3 and 4): every threshold the method uses is its caller's argument and none is entered. It says what the method IS at the pinned commit, not that it works on this stand.

### [host_clock_is_not_the_experiment_clock](../entries/host_clock_is_not_the_experiment_clock.json)

The host clock and MicroManager's frame timestamp series are separate clocks. Mapping host timestamps onto the frame series after the fact is a correlation between two clocks, not a synchronisation of them.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@safety-2026-09-03).

Conditions, verbatim:

> TWO CLOCKS, AND THE JOIN IS AN INFERENCE. Anything stamped by the host -- a stage move, a trigger, an operator action -- sits on a different timebase from the frames, and aligning them afterwards produces an association whose error nobody has measured. It is not that the offset is large; it is that it is unquantified, so a latency derived across the boundary inherits an unknown. THIS IS THE FACT, NOT THE RULE THAT FOLLOWS FROM IT. Whether the orchestrator may cross that boundary, and what it must record when it does, is a decision for the clock design and not something this entry settles. 10.2.1: TRANSFER. Row: 10.2's hardware-control-path row, whose prerequisite -- the four device-interface functions -- is met, and whose own rule says it does not wait for `envelope/` because wrapping a control path needs no safety limit. Slot: KB entry, named in the 2026-09-18 amendment. Rule: 10.3 rule 1, capped E3. Confirming it on this instrument promotes it to E1 and supersedes this entry.

### [immersion_oil_in_use_is_nikon_type_f](../entries/immersion_oil_in_use_is_nikon_type_f.json)

The immersion oil on this bench is Nikon Type F Non-Fluorescing Immersion Oil, 30 ml, PCB-free, as the person read it off the bottle's label at the bench on 2026-10-13.

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20261013_immersion_oil).

Conditions, verbatim:

> THE JOINING CLAIM, filed the way particle_suspension_b_identity was, and graded higher than it for the reason that entry names as what would raise it: here the person READ THE LABEL, at the bench on 2026-10-13, so this is operator_read (E3) and not a statement of which product they have. The reading was reported two days later, on 2026-10-15, in manager-librarian's window, and task 046 at 17368e3 records it with the person's correction that it was a reading and not a recollection. WHAT WAS READ: the product name, 30 ml and PCB-free. Nothing else from the label is on record -- no catalogue number, no lot, no date, and no index printed on the bottle -- so the catalogue number MXA22168 that a reseller and Nikon's safety sheet give for Type F 30 ml is NOT an identifier here: it was not read. The reseller page the person gave as reference is where the type data was read, not evidence of which oil is used. A caller computing a depth of field for the 60x or 100x applies an index to this bench through this entry, so it cites this entry as well as one of the two index entries, and those two disagree (see them). NOT A LIMIT AND NOT A COMMAND: which oil goes on the lens is the person's practice; nothing here may be read as permission or instruction to apply oil.

### [interval_ms_is_ignored_and_frame_period_equals_exposure](../entries/interval_ms_is_ignored_and_frame_period_equals_exposure.json)

startSequenceAcquisition's intervalMs argument is ignored: the frame period equals the exposure exactly, because readout is pipelined. A frame rate cannot be obtained by asking for it.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@safety-2026-09-03).

Conditions, verbatim:

> AN ARGUMENT THAT IS ACCEPTED AND DISCARDED, so a caller that sets it believes it has scheduled something. The consequence is arithmetic rather than approximate: 30.000 fps requires a 33.333 ms exposure, because the period IS the exposure. So frame rate and exposure are one setting wearing two names, and an axis that treats them as independent has one more degree of freedom than the instrument has. THE ACHIEVED RATE IS A SEPARATE FACT FROM THE REQUESTED ONE and only the achieved one is evidence. Reporting a requested rate as though it were measured is how this becomes silent. Note the interaction with elapsed_time_is_quantised_to_one_ms: the obvious way to report the achieved rate is also compromised, so the two have to be read together. 10.2.1: TRANSFER. Row: 10.2's hardware-control-path row, whose prerequisite -- the four device-interface functions -- is met, and whose own rule says it does not wait for `envelope/` because wrapping a control path needs no safety limit. Slot: KB entry, named in the 2026-09-18 amendment. Rule: 10.3 rule 1, capped E3. Confirming it on this instrument promotes it to E1 and supersedes this entry.

### [light_engine_line_intensity_is_per_mille](../entries/light_engine_line_intensity_is_per_mille.json)

On both Lumencor engines each light line is exposed as two MMCore properties, `\<NAME\>` taking 0 or 1 and `\<NAME\>_Intensity` taking 0 to 1000. The intensity scale is per-mille, not per cent: an operator's 10 per cent is 100, and writing 10 sets one per cent.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@34a432c).

Conditions, verbatim:

> THIS IS THE RANGE THE REQUEST ASKED FOR AND IT IS NONE OF THE THREE IT OFFERED. Not 0-100, not 0-1, not 0-255: `intensity_unit: "per-mille (0-1000)"` appears in the `device_reported:` block of each engine, recorded as read live over MMCore on 2026-09-03. SO THE OPERATOR'S 10 PER CENT RESOLVES TO 100. The factor-of-ten error is not hypothetical there: the source records 5 per cent being written as 50, and warns in the same file that typing 5 gives 0.5 per cent. LINES ARE NAMED, NOT NUMERIC. The Spectra III reports VIOLET, BLUE, CYAN, TEAL, GREEN, YELLOW, RED, NIR; the Aura III reports UV, CYAN, GREEN, RED, NIR. So the property is per LINE and there is no device-level intensity: a plan must name which line it is driving. THE CENTRE WAVELENGTHS OF THOSE LINES DID NOT CROSS. The prior file carries two lists of numeric wavelengths and says twice that they were read from NIS-Elements diagram icons and that the device contradicts them. A line NAME is a nominal designation and a string (5.3); a centre wavelength is a measurement, and that one is not made here. A RANGE IS NOT A LIMIT. 0 to 1000 is what the adapter accepts. What may be commanded on this instrument is envelope/safety.json's and a person's, and 10.3 rule 4 keeps limits out of here entirely. WHAT WOULD RAISE IT: getDevicePropertyNames() and getPropertyLowerLimit/UpperLimit on this stand. Slot: a KB entry and the device registry's control-channel columns. Rule passed: 10.3 rule 1.

### [light_engine_master_state_gates_every_line](../entries/light_engine_master_state_gates_every_line.json)

Both Lumencor engines carry a master property `State`, taking 0 or 1, which gates the whole device. With State at 0 no light leaves the engine however a line and its intensity are set, and nothing reports an error or reads back wrongly.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@34a432c).

Conditions, verbatim:

> THREE PROPERTIES, NOT TWO, AND THE THIRD FAILS SILENTLY. Setting `\<NAME\> = 1` and `\<NAME\>_Intensity = 50` is not enough; with the master `State` at 0 the camera returns a frame indistinguishable from a dark frame. There is no exception, and both the line property and the intensity property read back exactly as written, so every signal a caller would normally trust says the light is on. FILED SEPARATELY FROM THE PER-MILLE SCALE UNDER RULE 1: the scale could be right and the master absent, or the reverse, and a stand could be reconfigured to change one without the other. WHAT IT COST THERE, kept as the reason this is worth an entry rather than a note: a run that set only the two line properties produced a field whose median was BELOW the dark frame and a ratio computed almost entirely on the camera's own hot pixels, and it looked like a result. The guard the prior project adopted -- after enabling light, snap through the widest filter and require the median to rise above the dark frame, else refuse -- is a PREFLIGHT SHAPE and belongs to O1 if this system wants it; it is named here and not entered as a rule, because a check is designed and not transferred (10.2.1). COMPOUNDING IT: on that configuration `Core.Shutter` is `LightEngine`, so autoshutter never opens the Aura, and autoshutter is off during a measurement by their own policy. Nothing else opens the engine for you. WHAT WOULD RAISE IT: getDevicePropertyNames() on this stand, plus one acquisition with State at 0 and a line at full to confirm the frame is dark. Slot: a KB entry and the device registry's control-channel columns. Rule passed: 10.3 rule 1.

### [mm_label_aura_is_the_aura_iii](../entries/mm_label_aura_is_the_aura_iii.json)

On the prior project's configuration the MMCore device label `Aura` is the Lumencor Aura III 5-NII-WA on COM7, serial 30859, firmware 3.14.7. The label is not `AuraIII`; that is the product name.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@34a432c).

Conditions, verbatim:

> THE SAME SPLIT AS ITS SIBLING: `AuraIII` is the product name in the prior module's docstring and scope profiles, and every call site writes `Aura`. Filed separately from mm_label_lightengine_is_the_spectra_iii under rule 1, because the two mappings are refutable one at a time -- a stand could have one label renamed and not the other. AND ONE ASYMMETRY THAT IS NOT A NAMING FACT: the prior configuration's `Core.Shutter` is `LightEngine`, not `Aura`, so MMCore's autoshutter never opens this engine. Recorded here rather than in a separate entry because it is a property of this label's relationship to the core on that configuration, and it is the reason a plan that switches engines and keeps its shutter handling gets a dark frame. IT DOES NOT CLOSE lapp_branch_assignment: which channel id is this engine is a different mapping, and this entry carries no device subject for that reason. WHAT WOULD RAISE IT: getLoadedDevices() on this stand. Slot: a KB entry and the device registry. Rule passed: 10.3 rule 1.

### [mm_label_lightengine_is_the_spectra_iii](../entries/mm_label_lightengine_is_the_spectra_iii.json)

On the prior project's configuration the MMCore device label `LightEngine` is the Lumencor Spectra III 8-NII-XS on COM3, serial 28145, firmware 3.5.4. The label is not `SpectraIII`; that is the product name.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@34a432c).

Conditions, verbatim:

> THE MM LABEL AND THE PRODUCT NAME ARE DIFFERENT STRINGS AND ONLY ONE OF THEM IS WHAT getLoadedDevices() RETURNS. `SpectraIII` appears in the prior module's docstring and as a registry name in its scope profiles; every actual call site writes `LightEngine`. A plan naming SpectraIII fails preflight against a stand where the label is LightEngine, and the failure looks like a missing device rather than a wrong name. IT DOES NOT CLOSE lapp_branch_assignment, AND CANNOT. That gap asks which of the channel ids widefield_source_a and widefield_source_b is which ENGINE. This entry maps an MM LABEL to an engine. The two mappings are independent, so knowing LightEngine is the Spectra leaves the channel-id question exactly where it was -- which is why this entry is keyed by model and carries no device subject, the same reasoning devices.v0.json gives for keying its light_engines block by model designation rather than channel id. WHAT IT DOES BUY is a name a plan can use WITHOUT standing on that gap: getLoadedDevices() returns MM labels, so a plan written in MM labels is comparable at preflight and asserts nothing about the branch. WHAT WOULD RAISE IT: getLoadedDevices() on this stand. Slot: a KB entry and the device registry. Rule passed: 10.3 rule 1.

### [pixeltype_misreports_bit_depth](../entries/pixeltype_misreports_bit_depth.json)

MicroManager's PixelType property reports 12bit while the data delivered is 16-bit, so trusting the property scales every count by a factor of sixteen.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@safety-2026-09-03).

Conditions, verbatim:

> A READ-BACK THAT IS WRONG, WHICH IS THE WORST KIND: it answers, so nothing errors. The prior project's evidence was a single 512x512 frame holding 12,441 distinct values with a modal spacing of 1 LSB and a maximum of 34,917 -- and 34,917 cannot occur in 12 bits, whose ceiling is 4,095, so the maximum alone settles it. Those counts are that project's measurement of their frame and are not entered as numbers here; what transfers is that the property lies. WHY IT MATTERS BEYOND SCALING. A bit depth is read to decide saturation, and a sixteenfold error in the ceiling means a frame can be called safe at 85 per cent of a ceiling that is actually sixteen times higher, or clipped without anything noticing. 10.2.1: TRANSFER. Row: 10.2's hardware-control-path row, whose prerequisite -- the four device-interface functions -- is met, and whose own rule says it does not wait for `envelope/` because wrapping a control path needs no safety limit. Slot: KB entry, named in the 2026-09-18 amendment. Rule: 10.3 rule 1, capped E3. Confirming it on this instrument promotes it to E1 and supersedes this entry.

### [trapped_bead_is_the_one_that_does_not_translate](../entries/trapped_bead_is_the_one_that_does_not_translate.json)

In a crowded field, brightness does not identify the trapped bead. The discriminator that works is motion relative to the stage: the trapped bead is the only object that does not translate when the stage moves.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@safety-2026-09-03).

Conditions, verbatim:

> A NEGATIVE AND A POSITIVE, AND THE NEGATIVE IS THE EXPENSIVE HALF. The prior project found six blobs within 27,200 to 29,140 counts producing six plausible-but-wrong fits -- so brightness does not merely fail, it fails while returning a confident answer, which is worse than returning none. The working discriminator is kinematic rather than photometric and needs a stage move to exist, so it is not available from a single static frame. ENTERED AS A METHOD FACT, and its slot is an axis rather than a control path: whoever identifies a trapped bead reads it. The ADU counts are that project's field and are not entered as numbers -- the transferable content is that a brightness discriminator is unreliable in a crowded field and why. 10.2.1: TRANSFER. Row: 10.2's hardware-control-path row, whose prerequisite -- the four device-interface functions -- is met, and whose own rule says it does not wait for `envelope/` because wrapping a control path needs no safety limit. Slot: KB entry, named in the 2026-09-18 amendment. Rule: 10.3 rule 1, capped E3. Confirming it on this instrument promotes it to E1 and supersedes this entry.

### [tracer_diffusivity_expected](../entries/tracer_diffusivity_expected.json)

The expected translational diffusivity of a tracer sphere in a bulk fluid is the Stokes-Einstein value, k_B T over 3 pi eta d. It is a prediction from the viscosity, the temperature and the diameter, not a measurement of how the particles actually move.

How it is known: computed; computed from other values (E4 · computed:stokes_einstein).

Conditions, verbatim:

> A SPHERE IN BULK, WHICH IS WHERE THIS STOPS BEING TRUE FIRST. Stokes-Einstein assumes a rigid sphere, no slip at its surface, a continuum Newtonian fluid, dilute suspension so particles do not feel each other, and low Reynolds number. Near a wall the drag rises and the real diffusivity falls below this value -- the correction is applied separately and is NOT absorbed here, for the reason tau_d gives: fold it in and the quantity changes with stage position and nothing can be compared across runs. A tracer sitting on a coverslip is the case where this entry is most likely to be quietly wrong.  WHY AN ENTRY RATHER THAN EACH CARD COMPUTING IT. plan.md:1295 ruled it: recomputing a quantity the store holds is not estimation, it is a detour. A simulation card cast tau_a = radius**2/D at E5 while kb:tau_d held diameter**2/D at E4 -- a factor of four out and a grade worse. A card citing this gets one name and the better grade; a card computing it gets neither. Filed as a formula rather than a value so that when an input improves the entry improves with it: the diameter went from an E5 recollection to an E2 measurement on 2026-09-19 and nothing here needs rewriting for that.  THE GRADE IS E4 AND THE CHECK DOES NOT DERIVE IT. 5.3 makes a `computed:` source max(E4, worst input). The worst input is E3 -- water_viscosity_293k E3, lab_ambient_temperature E3, tracer_diameter_measured E2 -- so E4. Check 43 does NOT confirm this: its `computed:` branch accepts E4 or E5 and never reads the inputs, so the number above is a reading of 5.3 by two people and not something the run established. Said out loud because 019 asked for the grade as the validator derives it, and the validator derives a range.  THE TEMPERATURE IS THE ROOM'S, NOT THE SAMPLE'S, AND THAT IS AN ASSUMPTION THIS ENTRY CARRIES. lab_ambient_temperature is a thermometer reading of the room; nothing actuates or reads the sample temperature (no_thermometer_at_the_sample, sample_temperature_not_actuated). declared_versus_inferred_temperature records why this is not symmetric between the two agents: the simulation DECLARES its temperature and realises it, so citing one there records a choice; the experiment INFERS it, so citing one there is a claim about the sample. This entry is on the inferring side. Under a trapping laser it is worse -- trap_heating_detection_bound bounds the heating only below about 20 per cent of the IR power and says nothing above it.  UNITS: THE FORMULA IS SI AND THE DECLARED UNIT IS NOT. Evaluate with k_B in J/K, the temperature in K, the viscosity in Pa*s and the diameter in METRES, and the result is m^2/s. The entry declares um^2/s because that is the scale this store and both agents report diffusivity in -- quantities.json records the whole family at um^2/s -- and units.json's si_factor is what converts. Putting the diameter in um while the viscosity is in Pa*s and reading the answer as um^2/s is out by a factor of 10^6, which is six orders and would not look like a slip in a log.  NOT `tracer_diffusivity`, AND NOT `diffusivity`. Three near-names now sit in one family and two of them are already in quantities.json's open_collisions. `tracer_diffusivity` is the REGISTERED OBSERVABLE: what an experiment measures and what the bridge threads between the two agents. `diffusivity` is the name the simulation writes, six uses, colliding with that observable. This one is the PREDICTION -- what Stokes-Einstein says the value should be given the inputs. The distinction is load-bearing rather than pedantic: the whole point of thr-tracer-diffusivity-001 is to compare a measured diffusivity against a modelled one, and an expected value quietly substituted for either side would make the comparison compare a prediction with itself. `_expected` is the word that keeps them apart and it has to survive any later rename.  NO `subject`, AND THE REASON CHANGED ON 2026-09-20 WHILE THE ANSWER DID NOT. What this paragraph said until now: a quantity subject must resolve against check 44's registry -- the names used in numbers[] anywhere, united with those declared in contracts/quantities.json -- and `tracer_diffusivity_expected` was in neither, because this entry is a formula carrying no numbers[] and the two microscope axes that want it name it in `missing[]` and in a gap's `observable`, which the registry does not read. That was a BLOCK and it named manager-librarian as the route out. THE BLOCK IS GONE: the id is now declared in contracts/quantities.json, measured there on 2026-09-20 among sixteen, so a quantity subject would resolve today. Left off anyway, and now for a standing reason rather than a blocked one: `Store.subjects` is a UNION over entry_id, symbol, numbers[].name, subject[].id and the addressable identifiers, and both entry_id and symbol are already this exact string -- so a subject naming it would add no handle that is not already there. Measured and not reasoned: `answers_to` returns this entry for the bare name today, with the field absent. It stays empty because it would be a duplicate, not because anything is waiting on anybody. WRITTEN OUT RATHER THAN DELETED: a sentence saying a landed thing is still owed sends the next reader to raise it a second time, which is the failure this repository keeps recording, and deleting it instead would leave that reader to rediscover that a quantity subject is possible here and wonder why nobody filled it.  ITS INPUTS ARE FORMAL PARAMETERS TOO, AND FOR A WHILE THAT WAS HIDDEN BY A COINCIDENCE. Task 020 ruled that a derived_quantity whose inputs are formal parameters is complete and takes no grade from them -- 5.3's max(E4, worst input) is a rule about a computed VALUE, and a relation composes no numbers. That ruling was argued about tau_d and it applies here identically: this is the same kind, with the same `formula` key, and `ambient_temperature`, `viscosity` and `tracer_diameter` are the arguments of Stokes-Einstein, not references to particular entries. What made check 62 treat the two differently was that these three names HAPPEN to be carried as values in this store while tau_d's `bead_diameter` is the open_collisions synonym of `tracer_diameter` and is carried by nothing. So the grade it derived here was a coincidence of vocabulary, and editing one string inside the formula would have created or destroyed it -- which is option 2 of task 020, refused at the front door, arriving at the side. manager-librarian caught this in the seat that wrote the ruling and reported the derived count as 2. It is 1: the only real derivation in the store is working_distance_is_measured_to_the_coverslip, which is a `claim` whose inputs are genuinely two quantities. This entry's E4 comes from the relation being textbook and would stand in a store holding no diameters at all.

### [focus_metrics_peak_at_best_focus](../entries/focus_metrics_peak_at_best_focus.json)

Each of dino-autofocus's classical focus metrics -- `vollath4`, `brenner`, `tenengrad` and `peak_brightness` -- reaches its maximum over a z sweep at the plane of best focus.

How it is known: recalled or assumed; an assumption (E5 · assumed:dino-autofocus@fa9790378ea3f06e94b933a2fb65219322f6702a).

Conditions, verbatim:

> A classical sharpness metric of one monochrome widefield frame as read, clipped pixels not masked. It ranks frames of one sweep against each other; it says nothing about which plane holds the sample, and its value is not comparable across metrics or across sweeps taken with different exposure or binning. Best focus here means the plane of greatest sharpness, which need not be the plane holding the sample of interest. 10.2.1: DOWNGRADE. The source states this in its module docstring with no measurement attached, so it enters as an assertion without grounds, E5, rather than at the E3 its sibling definitions carry. Falsifier: a sweep on this stand through the person's manual focus in which a metric's maximum is not at the manual focus plane -- most likely `brenner` on a dim frame, which the source itself says rises on noise, or `peak_brightness` on a dense field. Measured here, the claim is promoted per metric and supersedes this entry. Place: a store entry, cited by the 11-24 design as the premise its baseline rests on. The other half of the drafted sentence, that `vollath4` and the synthetic-training variant peak at the same plane with different values, is DISCARDED: it describes a module that has no place here.

## Disputed and withdrawn

- [pixeltype_misreports_bit_depth](../entries/pixeltype_misreports_bit_depth.json): in conflict; the other side: [kinetix_red_adapter_properties_as_reported_20260924](../entries/kinetix_red_adapter_properties_as_reported_20260924.json)

## Reading

None.

## Related

None.

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
