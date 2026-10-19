# Device: stand_ti2e

Every entry in the store about the device stand_ti2e.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, channel, verbatim:

```json
{
  "id": "stand_ti2e",
  "role": "microscope body: objective and filter turrets, output port, intermediate magnification, focus, transmitted lamp",
  "driver": "micromanager",
  "automatable": "full",
  "read_back": true,
  "lock_group": "optical_path",
  "elements": [
    {
      "id": "nosepiece",
      "positions": 6,
      "position_index_base": 0,
      "entry_ref": [
        "nosepiece_position_indexing",
        "nosepiece_objective_assignment"
      ],
      "index_note": "positions run 0 through 5, not 1 through 6. Any command or preflight check that assumes 1-6 is off by one on every position.",
      "id_note": "each objective's id IS its nominal magnification, a string identifier that is exact by definition (5.3). There is deliberately no numeric magnification field: a field for it is where a value back-derived from a calibrated pixel size ends up wearing a nominal name, which is what happened in the prior project's 20.078x.",
      "objectives": [
        {
          "position": 0,
          "id": "4x",
          "product": "CFI Plan Apo Lambda D 4X",
          "part_number": "MRD70040",
          "immersion": "air",
          "na": 0.2,
          "wd_mm": 20,
          "coverglass_um": {
            "min": 0,
            "max": 170
          },
          "entry_ref": "objective_mrd70040"
        },
        {
          "position": 1,
          "id": "10x",
          "product": "CFI Plan Apo Lambda D 10X",
          "part_number": "MRD70170",
          "immersion": "air",
          "na": 0.45,
          "wd_mm": 4,
          "coverglass_um": {
            "min": 170,
            "max": 170
          },
          "entry_ref": "objective_mrd70170"
        },
        {
          "position": 2,
          "id": "20x",
          "product": "CFI Plan Apo Lambda D 20X",
          "part_number": "MRD70270",
          "immersion": "air",
          "na": 0.8,
          "wd_mm": 0.8,
          "coverglass_um": {
            "min": 170,
            "max": 170
          },
          "entry_ref": "objective_mrd70270"
        },
        {
          "position": 3,
          "id": "40x-WI",
          "product": "CFI Apo Lambda S 40XC WI",
          "part_number": "MRD77400",
          "immersion": "water",
          "na": 1.25,
          "wd_mm": null,
          "wd_mm_range": {
            "min": 0.16,
            "max": 0.2
          },
          "wd_note": "quoted as a range because it depends on the correction collar. wd_mm is null rather than a midpoint: with the coverslip fixed at 170 um the collar setting is determined and the working distance IS a single value, but the catalog does not publish it and the librarian does not interpolate inside a quotation (4.3). A null is loud; an interpolated number would be silent. See the gap objective_40x_wd_at_170um.",
          "coverglass_um": {
            "min": 150,
            "max": 190
          },
          "correction_collar": true,
          "entry_ref": "objective_mrd77400"
        },
        {
          "position": 4,
          "id": "60x-oil",
          "product": "CFI Plan Apo Lambda D 60X Oil",
          "part_number": "MRD71670",
          "immersion": "oil",
          "na": 1.42,
          "wd_mm": 0.15,
          "coverglass_um": {
            "min": 170,
            "max": 170
          },
          "entry_ref": "objective_mrd71670"
        },
        {
          "position": 5,
          "id": "100x-oil",
          "product": "CFI Plan Apo Lambda D 100X Oil",
          "part_number": "MRD71970",
          "immersion": "oil",
          "na": 1.45,
          "wd_mm": 0.13,
          "coverglass_um": {
            "min": 170,
            "max": 170
          },
          "entry_ref": "objective_mrd71970"
        }
      ],
      "objectives_source": {
        "position_to_lens": "operator_read:kyuhwan_20260917, confirmed at the instrument",
        "na_wd_coverglass": "spec:<part_number>, Nikon catalog (src_nikon_objective_catalog), accessed 2026-08-10",
        "grade": "E3",
        "two_coverslip_facts": "coverglass_um here is what the lens ACCEPTS. What this laboratory actually mounts is 170 um (entry coverslip_thickness_in_use). They answer different questions and are not merged.",
        "not_here": "transmission at 1064 nm. The catalog publishes a curve and no numeric table, and a number a model reads off a rendered curve is E6, which may enter nothing (5.3). See the gap objective_transmission_1064nm."
      }
    },
    {
      "id": "filter_turret_1"
    },
    {
      "id": "filter_turret_2"
    },
    {
      "id": "light_path_port",
      "note": "cameras and the confocal unit are on one position only; any other value sends emission where no detector sees it"
    },
    {
      "id": "intermediate_magnification",
      "values": [
        "1x",
        "1.5x"
      ],
      "values_note": "nominal designations, so string identifiers rather than numbers (5.3). They were written 1.0 and 1.5, which gave a nominal name a decimal point and an implied precision it does not have."
    },
    {
      "id": "pfs",
      "note": "focus stabilisation; disabled across turret and path changes (2.1 interlock 3)"
    },
    {
      "id": "dia_lamp"
    },
    {
      "id": "lapp_branch",
      "gap_ref": "lapp_branch_assignment",
      "note": "selects which widefield source reaches the sample. WHICH engine each state selects is not confirmed. This is also the one element on this instrument with a recorded history of an inverted label-to-state mapping -- see label_warning in optical_paths.v0.json, where a branch selector read back consistently wrong for weeks and only an image showed which position passed light. The element with that history is the element whose engine assignment is unverified, and those two facts are worth reading together rather than one at a time."
    },
    {
      "id": "z_drive",
      "read_back": true,
      "source": "prior_run:agentic-microscope@34a432c",
      "grade": "E3",
      "gap_ref": "z_drive_lock_group",
      "entry_ref": "mm_label_zdrive_is_the_focus_axis",
      "note": "the focus axis. The channel role said FOCUS and no element was one, while the store asserted at E3 that smaller Z is retracted -- motion claimed and the mover unaddressed. MM label `ZDrive`, read from code positions and not from the relay; it is in the entry rather than here because every id in this table is this store's own name and not a device label. READ_BACK IS THE ELEMENT'S OWN and not the channel's: `core.getPosition(\"ZDrive\")` appears at four call sites, so the position can be read after a move, which is what an interlock requiring verification == readback needs. LOCK_GROUP IS DELIBERATELY ABSENT -- see the gap. WHAT IT MOVES is not claimed: the document does not settle whether the objective or the sample carriage travels, and on an inverted stand that decides which way a collision closes.",
      "ruling": "transfer (10.2.1)",
      "slot": "the device registry element row, plus a KB entry. Consumer: O1 preflight and the turret-rotation interlock.",
      "rule_passed": "10.3 rule 1"
    },
    {
      "id": "motor_stage",
      "lock_group": "stage",
      "source": "operator_read:kyuhwan_20260917",
      "grade": "E3",
      "entry_ref": "stand_ti2e_lock_groups",
      "note": "coarse xy, on the body hub. Stage moves therefore serialise with port and filter changes under one channel, one worker (4.6.8) -- that consequence is design, not a hardware reading, and is not stamped as one."
    }
  ],
  "source": "mm_config + nis_device_manager",
  "grade": "E3",
  "confirmed_by": "operator_read:kyuhwan_20260917",
  "lock_note": "The channel carries two lock groups. Its optical elements belong to optical_path; the motor stage belongs to stage, because the piezo rides on it. A lock group is therefore a property of an element, not only of a channel, and one worker for this channel can be blocked by two different locks: the lock a worker waits on is chosen per command, not per channel.",
  "entry_ref": "stand_ti2e_lock_groups"
}
```

## Values

None.

## Claims

### [intermediate_magnification_is_not_a_state_device](../entries/intermediate_magnification_is_not_a_state_device.json)

In the Micro-Manager NikonTi2 adapter, IntermediateMagnification is not a state device: asking it for a state raises 'is of the wrong type for the requested operation'. Its value has to be read as a property.

Identifiers: none

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-002).

Conditions, verbatim:

> Read back in a preparatory run -- the first real acquisition on this computer, with no plan, the person having placed the 20x and moved the microscope by hand, software moving nothing. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system: E1 from `measured:`. Not a value of any registered observable. A fact about the adapter in the Micro-Manager copy that loaded today (MMCore 12.5.0, device API 75). Slot: A6 -- a pixel size depends on the intermediate magnification, and code that reads it with a state call gets an error, not a value. Delivered as item intermediate_magnification_not_a_state_device of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042). Checked by this seat against microscope_agent/runs/run-20260924-002/log.json read at bf8f91f (unchanged since): event 15.

### [mm_config_load_did_not_return_after_nis_force_kill](../entries/mm_config_load_did_not_return_after_nis_force_kill.json)

On the microscope computer, after NIS-Elements was force-killed, Micro-Manager's configuration load did not return, twice: in run-20260924-009 for about six minutes, and in run-20260924-010, loading a configuration named ti2_only.cfg, until the seat stopped the process after about two minutes. In run-20260924-008, with NIS closed normally, a configuration holding the same stand devices loaded in about 3 s.

Identifiers: none

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-010).

Conditions, verbatim:

> What the control software did, recorded as run events: an observation by this system and not a measurement of any registered observable, so E1 from `measured:` under 11-21 condition 4 as narrowed, and counted by check 85. Cited as run-010 because that run is the sharper one -- a stand-only configuration -- and the source record names all three logs. WHAT THE LOGS SHOW AND WHAT THEY DO NOT. run-009: the kill at events[7], the close-all at events[9], and no load event after it; the seat's stop at events[10] says loadSystemConfiguration had not returned for about six minutes. The log does NOT name which configuration was loading -- the finding calls it the dual-camera configuration without its DAQ devices and startup preset, and that is the seat's word. run-010: the kill at events[7], load_start of ti2_only.cfg at events[10], and the seat's stop at events[11], whose reason says about two minutes; its t_mono of 257 s is a recovery process's wall-clock estimate, not the run's clock. That the file holds the stand alone is the seat's description; the file itself was not read here. run-008 events[2]: the derived dual-camera configuration, which includes the stand's devices, loaded at t 3.0 s with NIS not running. WHERE IT POINTS AND WHY THAT IS AN INFERENCE. That the stand-only load hung too is what places the fault at the stand's own connection rather than at a camera or the confocal unit. Two runs and one comparison support it; nothing tested the stand's controller directly. Untried: reconnecting or power-cycling the stand's controller after a kill. The person restarted NIS after run-009 and NIS then worked normally (the finding's note, not a log event). THE PRIOR PROJECT. The finding says the prior project loaded a configuration of the same shape after a force-kill on 2026-09-07. No entry here holds that report, so nothing is named in conflict_with; if it is wanted it comes in under 10.2.1 like any prior item. Falsified by a configuration load that returns promptly after a NIS force-kill on this computer. Not a safety statement. Delivered as item mm_load_hung_after_nis_force_kill of microscope_agent/findings/microscope-20260924-3-20260924.json at 0ecf94b.

### [single_cam_red_config_startup_puts_the_lapp_mirror_in](../entries/single_cam_red_config_startup_puts_the_lapp_mirror_in.json)

Loading single_cam_red_noDMD_nocom10.cfg moves the Lapp main-branch mirror: its System/Startup preset sets LappMainBranch1 State to 1, and after the load LappMainBranch1 reads State 1 (mirror_in).

Identifiers: none

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-002).

Conditions, verbatim:

> Read back in a preparatory run -- the first real acquisition on this computer, with no plan, the person having placed the 20x and moved the microscope by hand, software moving nothing. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system: E1 from `measured:`. Not a value of any registered observable. The preset line is in the configuration file (line 261 at agentic-microscope fbedef0, sha256 8184073e..., which this seat read); the read-back is the run's. A LOAD IS NOT A READ: loading this configuration writes to a device. The person accepted that move for today's runs, which is a decision and is not in this entry. Slot: O1 preflight and A4. Delivered as item lapp_mirror_state_1_after_startup_preset of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042). Checked by this seat against microscope_agent/runs/run-20260924-002/log.json read at bf8f91f (unchanged since): event 12.

### [stand_state_read_20260924_20x_in_place](../entries/stand_state_read_20260924_20x_in_place.json)

On 2026-09-24, with the 20x placed by hand, the stand read: Nosepiece state 2, label '3-Plan Apo LmbdD0.8 20x'; LightPath state 3, '4-L100'; FilterTurret1 state 0, '1-MXR00724 -Empty'; FilterTurret2 state 0, '1-Empty'; LappMainBranch1 state 1, 'mirror_in'; CondenserTurret state 0, '1-ND'.

Identifiers: none

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-002).

Conditions, verbatim:

> Read back in a preparatory run -- the first real acquisition on this computer, with no plan, the person having placed the 20x and moved the microscope by hand, software moving nothing. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system: E1 from `measured:`. Not a value of any registered observable. A STATE, NOT A PROPERTY: every value is falsified by moving that element. The labels are strings from the loaded configuration and are downgraded until a frame confirms each (plan.md 10.2.1); the state integers are what the stand reported. Nosepiece state 2 agrees with nosepiece_objective_assignment, which puts the 20x (MRD70270) at position 2. FilterTurret1's label names both the MXR00724 cube and 'Empty' at state 0, which is ambiguous; filter_turret_1_state_0_blocked_the_confocal_path records that cube at state 0 in the prior project on 2026-09-07. Slot: A4 and A6. Delivered as item stand_read_with_20x_in_place of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042). Checked by this seat against microscope_agent/runs/run-20260924-002/log.json read at bf8f91f (unchanged since): event 15.

### [ti2_control_usb_must_not_be_unplugged](../entries/ti2_control_usb_must_not_be_unplugged.json)

Ti2 Control must be installed before the microscope is connected to the computer by USB, or the driver may not install and the microscope may not be recognised; and the USB cable to the microscope must not be unplugged once Ti2 Control is running.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:nikon_ti2_control_v2_90_m706_e15).

Conditions, verbatim:

> Read from Nikon Ti2 Control Ver2.90 for Windows, English manual M706 E15 (sha256 5e43517c...): printed page 2 (PDF page 10), printed page 3 (PDF page 11), printed page 6 (PDF page 14). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. This manual is for the Ti2 Control software; the archive holds no Ti2-E hardware manual. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [ti2e_filter_shutter_state_at_startup_is_a_setting](../entries/ti2e_filter_shutter_state_at_startup_is_a_setting.json)

In Ti2 Control, whether the fluorescence turret's shutter is open or closed when the microscope starts is a setting.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:nikon_ti2_control_v2_90_m706_e15).

Conditions, verbatim:

> Read from Nikon Ti2 Control Ver2.90 for Windows, English manual M706 E15 (sha256 5e43517c...): printed page 75 (PDF page 83). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. This manual is for the Ti2 Control software; the archive holds no Ti2-E hardware manual. How this stand is set is not recorded here; a shutter set to open at start-up admits light as soon as a source is on. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [ti2e_objective_escape_is_set_per_nosepiece_address](../entries/ti2e_objective_escape_is_set_per_nosepiece_address.json)

In Ti2 Control, each nosepiece address can be set to move the objective to its escape position before that address passes when the nosepiece rotates, and the escape distance used when changing the specimen is also a setting there.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:nikon_ti2_control_v2_90_m706_e15).

Conditions, verbatim:

> Read from Nikon Ti2 Control Ver2.90 for Windows, English manual M706 E15 (sha256 5e43517c...): printed page 73 (PDF page 81). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. This manual is for the Ti2 Control software; the archive holds no Ti2-E hardware manual. Bears on nosepiece_write_runs_no_escape (the prior project: a Micro-Manager nosepiece write runs no escape): what the stand does is configured in the stand, and how this one is configured is not recorded here. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [ti2e_optical_path_addresses](../entries/ti2e_optical_path_addresses.json)

On the Ti2-E the light path has four addresses: 1 is the eyepiece observation port; 2 the right side port; 3, with the optical-path split prism, sends 80 per cent to the left side port and 20 per cent to the eyepieces, or is the bottom port on the Ti2-E/B; and 4 is the left side port. So two addresses can put light into the eyepieces. The position the path takes at start-up is a Ti2 Control setting.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:nikon_ti2_control_v2_90_m706_e15).

Conditions, verbatim:

> Read from Nikon Ti2 Control Ver2.90 for Windows, English manual M706 E15 (sha256 5e43517c...): printed page 67 (PDF page 75), printed page 75 (PDF page 83). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. This manual is for the Ti2 Control software; the archive holds no Ti2-E hardware manual. How these addresses map onto Micro-Manager's LightPath state numbers is not stated in the manual; on 2026-09-24 state 3 read back with the label '4-L100' (stand_state_read_20260924_20x_in_place), which fits address = state + 1 and does not establish it. Whether this stand has the split prism is not recorded here. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_calibration_photodiode_needs_the_laser_off](../entries/tweez_calibration_photodiode_needs_the_laser_off.json)

Before setting up the calibration photodiode the laser must be switched off, or it can injure eyes or skin and damage the photodiode. The objective must be fully retracted before the photodiode is placed on the sample holder, and its position adjusted with great care, so as not to damage the objective's front lens.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300UserManual).

Conditions, verbatim:

> Read from Tweez 300 User Manual, 2021 (file date 2022-01-06; sha256 c37027cb..., byte-identical in both places): printed page 28 (PDF page 34), printed page 29 (PDF page 35). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_filter_cube_shutter_and_blocking_filter](../entries/tweez_filter_cube_shutter_and_blocking_filter.json)

The tweezers are meant to be used with an Aresis-supplied filter cube in the microscope's epi-fluorescence turret. That turret's mechanically actuated shutter blocks the laser from the objective and the eyepieces, and the cube's dichroic and blocking filters attenuate infrared that could reach the eyepiece path to well below the Class 1 limit.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 8 (PDF page 10). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. Which turret and position hold the Aresis cube on this bench is not recorded in this store. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_microscope_interlock_blocks_the_laser_at_the_eyepieces](../entries/tweez_microscope_interlock_blocks_the_laser_at_the_eyepieces.json)

The Nikon Ti2's own interlock switch is triggered whenever light could enter the eyepieces -- when the light path selector is set to the eyepieces -- and it is wired to the tweezers' optical unit, so that laser operation is disabled in that position. The manufacturer calls it an additional measure: an infrared filter already keeps the laser out of the eyepiece path. If the interlock cable is disconnected, laser operation is disabled. The Ti2's interlock works only while the microscope is powered, and with the microscope off, tweezers laser operation is disabled too.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 7 (PDF page 9). Also Tweez 305/310 System Installation Guide, 2021 (sha256 1f664a72..., byte-identical in the installed folder and the lab archive): printed page 12 (PDF page 16). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. Which light-path positions send light to the eyepieces is the open gap light_path_port_eyepiece_states; the Ti2 Control manual's port list narrows it (ti2e_optical_path_addresses). KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [filter_turret_1_state_0_blocked_the_confocal_path](../entries/filter_turret_1_state_0_blocked_the_confocal_path.json)

On 2026-09-07 in the prior project, filter turret 1 at state 0 held the multiband cube MXR00724 and blocked the confocal path, while states 1, 2 and 3 were empty and passed it.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/config/lunf).

Conditions, verbatim:

> Ruled TRANSFER, passed 10.3 rules 1 and 3: the placement crosses, the contrast figures in the script's help text do not. A PLACEMENT, NOT A PROPERTY: moving a cube falsifies it and nothing in the store records that somebody did, which is why slot numbers are not addressable handles here. Pin a turret by its state integer, never by its label. Slot: A4 (optical-path validity) -- a confocal configuration must not select this state while that cube sits in it. Falsified by any cube change in turret 1, or a confocal frame with signal at state 0. Delivered as item `turret1_state0_blocks_confocal` of microscope_agent/findings/microscope-20260924-3-20260924.json at a5e7647 (card 044); the source was opened at fbedef0 and its sha256 matched before this was ruled.

### [lapp_state_1_brings_the_aura_to_the_sample](../entries/lapp_state_1_brings_the_aura_to_the_sample.json)

On this stand, with the Lapp main branch at State 1 -- where the device reports the label 'mirror_in' -- the Aura III light engine's light reaches the sample: the person saw particles lit by the Aura in that state and said the position is the Aura's.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260924_lapp_aura).

Conditions, verbatim:

> The person's reading and observation on the evening of 2026-09-24, recorded verbatim in commit cd09784's message. About the INTEGER 1: branch_selector_is_pinned_by_integer_not_label holds that this selector's labels were inverted relative to its positions on the prior bench, so the label is given only as what the device reports there. Consistent with run-20260924-002, where the Aura lit the particles while LappMainBranch1 read back 1 (stand_state_read_20260924_20x_in_place). NOT established: what the other positions route; whether the Spectra III also reaches the sample in State 1; which of the device table's widefield_source_a and widefield_source_b is the Aura. Neither observation blocked one engine, which is the decisive test the lapp_branch_assignment gap names, so this narrows that gap and does not close it. Delivered as item lapp_main_branch_state_1_is_the_aura_iii_position of microscope_agent/findings/microscope-20260924-5-20260924.json at cd09784 (card 046).

### [mm_label_zdrive_is_the_focus_axis](../entries/mm_label_zdrive_is_the_focus_axis.json)

On the prior project's configuration the focus axis is the MMCore device label `ZDrive`, moved with setPosition and read with getPosition. Its position is the focus coordinate on this stand.

Identifiers: mm_label: ZDrive; parent_stand: Ti2-E

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@34a432c).

Conditions, verbatim:

> THE LABEL WAS READ FROM CODE POSITIONS AND NOT FROM THE RELAY, which is the whole point of entering it here. It reached this seat as a quotation manager-microscope flagged as unverified -- `ZDrive` in a 28-device list -- and a relayed label is exactly what 10.3 rule 3 keeps out. Verified independently in machine-readable positions: the named constant `Z_DEVICE = "ZDrive"`, the set `COLLISION_DEVICES = frozenset({"Nosepiece", "ZDrive", "PFSOffset"})` in three files, `core.getPosition("ZDrive")` at four call sites, and two tests asserting the name. The relay was right and that is not why it is entered. The same discipline caught the opposite case under 028: a docstring named the light engines `SpectraIII`/`AuraIII` while every call site wrote `LightEngine` and `Aura`. THE MM LABEL IS NOT THE REGISTRY ID. Every element on `stand_ti2e` is named in this store's own snake_case -- `nosepiece` for `Nosepiece`, `motor_stage` for `XYStage`, `lapp_branch` for `LappMainBranch1` -- so the element row added with this entry is `z_drive` and the MM label lives here, in `identifiers.mm_label`, the way 028 filed the camera and the engines. Task 035 asked for the MM label in the row's `id`; the table's own convention says otherwise and the convention wins, because an id that is sometimes a registry name and sometimes a device label is not an id. WHAT IT DRIVES IS NOT ENTERED. The document calls the motion `stage motion` in one place and gives `SAMPLE_Z_WINDOW_UM` as `where the sample sits in ZDrive coordinates`, which does not settle whether the objective or the sample carriage moves. On an inverted stand that distinction decides which way a collision closes, so it is left unclaimed rather than inferred. IT CORROBORATES A CLAIM THIS STORE ALREADY HOLDS AT E3. z_retract_direction_is_measured says smaller Z is retracted; the prior document carries `Z_RETRACT_DIRECTION = -1`, measured by the same operator on 2026-09-05, and records that the configurations have said `FocusDirection,ZDrive,1` since 2026-09-06. Two records of one measurement, agreeing. The grade does not rise -- it is the same operator and the same instrument, not a second measurement -- and the store's entry does not need this one. WHAT WOULD RAISE IT: getLoadedDevices() on this stand. Slot: a KB entry and the device registry's stand_ti2e elements. Rule passed: 10.3 rule 1 for the E3 cap, and the label comes from the configuration it was read in.

### [nosepiece_write_runs_no_escape](../entries/nosepiece_write_runs_no_escape.json)

The stand runs no objective escape when the nosepiece is rotated by a Micro-Manager write: Z does not move, so whatever height the outgoing objective was at is where the incoming one arrives. Rotating at the stand or in NIS does run the Ti2's own escape; the software path does not.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@safety-2026-09-03).

Conditions, verbatim:

> Ruled TRANSFER under 10.2.1 and passed 10.3 rule 1, so it caps at E3 -- a run taken in another project is not a run taken here. 10.2's hardware-control-path row is open and says in its own rule that it does not wait for envelope/, because wrapping a control path needs no safety limit. Slot: O1 preflight, which is the consumer that has to know a write does less than it appears to, with A4 second. Measured in the prior project by rotating between two objectives and reading the Z drive before and after: it moved by zero. The clearance that absorbs the difference is a property of whichever objective is arriving, and this store already holds those working distances per part number. No limit crosses with this: what is transferred is that the escape does not run, not how far anything may travel.

### [stand_ti2e_lock_groups](../entries/stand_ti2e_lock_groups.json)

The coarse motorised xy stage is an element of the microscope body channel, on the body hub. The body's optical elements belong to the optical_path lock group while the motor stage belongs to the stage lock group, because the piezo rides on the motor stage. One channel therefore carries two lock groups, and a lock group is a property of an element rather than only of a channel.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260917).

Conditions, verbatim:

> This instrument as configured on 2026-09-17, operator read at the instrument. What is confirmed here is the hardware arrangement and the group each element belongs to. What follows from it under one-channel-one-worker -- that stage moves serialise with port and filter changes, and that the lock a worker waits on is chosen per command rather than per channel -- is a design consequence, not a reading, and is not stamped as one. Falsified by the stage being moved off the body hub or the piezo being mounted elsewhere.

### [z_retract_direction_is_measured](../entries/z_retract_direction_is_measured.json)

Smaller Z is retracted on this stand -- measured, not inferred. Micro-Manager now carries the same convention in its configurations, so the instrument can answer which way retract is rather than requiring a reader of a memo.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@safety-2026-09-03).

Conditions, verbatim:

> Ruled TRANSFER under 10.2.1 and passed 10.3 rule 1, so it caps at E3 -- a run taken in another project is not a run taken here. 10.2's hardware-control-path row is open and says in its own rule that it does not wait for envelope/, because wrapping a control path needs no safety limit. Slot: O1 preflight and the orchestrator, both of which move Z. It carries no number and no limit -- a direction is not a permission. It is transferred BECAUSE it replaced a guess that ran the other way: the earlier reading had been that larger Z was retracted, taken from the fact that one rotation at a high Z broke nothing, and under the measured convention that rotation drove the incoming lens millimetres PAST the sample plane, so nothing broke because nothing was in the way. Anyone following the old guess would have driven the objective toward the coverslip believing they were retracting. The source document's own open-questions list still says this direction is unmeasured and calls it the most consequential gap in the document; the body of the same document records the measurement two days later. The list is stale, not the measurement -- see the pfs_offset_sign_unmeasured gap for the direction that really is still open.

## Disputed and withdrawn

None.

## Reading

None.

## Related

- [device filter_turret_1](../wiki/device_filter_turret_1.md)
- [device filter_turret_2](../wiki/device_filter_turret_2.md)
- [device intermediate_magnification](../wiki/device_intermediate_magnification.md)
- [device lapp_branch](../wiki/device_lapp_branch.md)
- [device light_path_port](../wiki/device_light_path_port.md)
- [device motor_stage](../wiki/device_motor_stage.md)
- [device nosepiece](../wiki/device_nosepiece.md)
- [device optical_tweezers](../wiki/device_optical_tweezers.md)
- [device z_drive](../wiki/device_z_drive.md)
- [safety guide](../guides/safety_stand_ti2e.md)

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
