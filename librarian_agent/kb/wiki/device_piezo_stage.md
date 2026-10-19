# Device: piezo_stage

Every entry in the store about the device piezo_stage.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, channel, verbatim:

```json
{
  "id": "piezo_stage",
  "role": "fine xyz positioning",
  "driver": "python_serial + vendor_dll",
  "automatable": "full",
  "read_back": true,
  "lock_group": "stage",
  "exclusive_with": [
    "piezo_vendor_gui"
  ],
  "exclusive_reason": "the serial port is exclusive; the vendor GUI holds it while a session is open and the connection then fails",
  "vendor_gui": {
    "name": "NanoBench 6000",
    "what_it_is": "the vendor GUI, and the counterparty of exclusive_with: [piezo_vendor_gui] -- the thing that holds COM4. It is NOT a hardware model, and it was recorded as one in the verification log's V14 before V19 corrected it. This store never carried that error; what it lacked was the name of the process the orchestrator has to see closed.",
    "operational_form": "close the NanoBench 6000 session if one is open, before opening the port",
    "ruling": "transfer (10.2.1)",
    "slot": "A4 -- device combination and automatability. Consumer: the orchestrator's exclusivity check.",
    "rule_passed": "10.3 rule 1",
    "source": "prior project control-path record",
    "grade": "E3"
  },
  "note": "three axes, travel and command quantisation were measured in the prior project and need re-measuring here before use as E1",
  "source": "driven end to end in the prior project + operator_read:kyuhwan_20260917",
  "grade": "E3",
  "mounted_on": "stand_ti2e/motor_stage",
  "mount_consequences": [
    "a piezo position is relative to wherever the motor left it, so a recorded position needs both numbers or it cannot be reproduced",
    "the motor must have settled before a piezo move means anything, which orders the two rather than parallelising them",
    "the two sit on different control channels but one mechanical chain, so the lock spans channels"
  ],
  "confirmed_by": null,
  "confirmed_by_note": "bulk stamp removed; see stamp_audit"
}
```

## Values

| quantity | value | unit | how it is known | grade and source as recorded | conditions | subject | entry |
|---|---|---|---|---|---|---|---|
| piezo_calibrated_range_min | 0 | um | measured on this instrument; a recorded run of this system | E1 · measured:run-20260924-004 | none stated | device piezo_stage | [piezo_calibrated_range](../entries/piezo_calibrated_range.json) |
| piezo_calibrated_range_max | 600 | um | measured on this instrument; a recorded run of this system | E1 · measured:run-20260924-004 | none stated | device piezo_stage | [piezo_calibrated_range](../entries/piezo_calibrated_range.json) |
| piezo_rest_position_ch1 | 0.02531508 | um | measured on this instrument; a recorded run of this system | E1 · measured:run-20260924-004 | none stated | device piezo_stage | [piezo_rest_position_as_found_20260924](../entries/piezo_rest_position_as_found_20260924.json) |
| piezo_rest_position_ch2 | 0.00607026 | um | measured on this instrument; a recorded run of this system | E1 · measured:run-20260924-004 | none stated | device piezo_stage | [piezo_rest_position_as_found_20260924](../entries/piezo_rest_position_as_found_20260924.json) |
| piezo_rest_position_ch3 | -0.00172179 | um | measured on this instrument; a recorded run of this system | E1 · measured:run-20260924-004 | none stated | device piezo_stage | [piezo_rest_position_as_found_20260924](../entries/piezo_rest_position_as_found_20260924.json) |
| piezo_device_range_min | -100 | um | recalled or assumed; the person's recollection | E5 · operator_recall:kyuhwan_20260924_piezo_range | none stated | device piezo_stage | [piezo_device_range_as_stated_by_the_person](../entries/piezo_device_range_as_stated_by_the_person.json) |
| piezo_device_range_max | 600 | um | recalled or assumed; the person's recollection | E5 · operator_recall:kyuhwan_20260924_piezo_range | none stated | device piezo_stage | [piezo_device_range_as_stated_by_the_person](../entries/piezo_device_range_as_stated_by_the_person.json) |

## Claims

### [piezo_command_path_as_found_20260924](../entries/piezo_command_path_as_found_20260924.json)

On 2026-09-24 the piezo controller reported, on each of channels 1, 2 and 3: analogue command input disabled, digital command input enabled, and closed-loop operation on. Its raw mode words were 0x0327 on channel 1 and 0x0323 on channels 2 and 3, and its status word 0x0B17 on all three.

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-004).

Conditions, verbatim:

> A device's report of itself, read in a preparatory run -- a read-only first contact that sent only .get commands from a list the person approved by sha256, and moved nothing. 11-21 condition 4 as narrowed at 20a688b lets such a report enter citing the run, graded as an observation by this system; it is not a measurement of any registered observable, and check 85 counts it rather than failing it. E1 from `measured:`. A SETTING, read back as found: anyone with NanoBench can change it, and nothing here records that they did. It matters because the controller sums analogue and digital commands when both are enabled (npcd_analogue_and_digital_commands_are_summed), so with the analogue input off a digital command is the whole command. The mode words are reported raw and not decoded here; channel 1 differs from 2 and 3 in one bit, which is not interpreted. Slot: the device wrapper and O1 preflight. Delivered as items piezo_analogue_command_off_ch1..3, piezo_digital_command_on_ch1..3, piezo_closed_loop_ch1..3 and piezo_mode_word_ch1..3 of microscope_agent/findings/microscope-20260924-2-20260924.json at a0fda99 (card 043). Checked by this seat against microscope_agent/runs/run-20260924-004/log.json read at a0fda99 (committed at 03e0cd2, unchanged since): events 49-57 and 61-63, each the command named and the value stated.

### [piezo_controller_axis_labels](../entries/piezo_controller_axis_labels.json)

The piezo controller labels its channels as axes: channel 1 is x, channel 2 is y and channel 3 is z. These are the controller's own labels, not an observation of which way the image or the sample moves.

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-004).

Conditions, verbatim:

> A device's report of itself, read in a preparatory run -- a read-only first contact that sent only .get commands from a list the person approved by sha256, and moved nothing. 11-21 condition 4 as narrowed at 20a688b lets such a report enter citing the run, graded as an observation by this system; it is not a measurement of any registered observable, and check 85 counts it rather than failing it. E1 from `measured:`. The person's statement to the architecture session on 2026-09-24 (microscope_agent/tasks/035-piezo-then-confocal-laser-then-tweezers.md at be5a848) puts X, Y and Z on channels 1, 2 and 3, which agrees; that statement is the person's and is not what this entry cites. Which way the image moves when a channel is driven is a separate, unmeasured question and a gap in the device table. Slot: A7 (motion) and the device wrapper. Delivered as items piezo_axis_label_ch1..3 of microscope_agent/findings/microscope-20260924-2-20260924.json at a0fda99 (card 043). Checked by this seat against microscope_agent/runs/run-20260924-004/log.json read at a0fda99 (committed at 03e0cd2, unchanged since): events 27-29, each the command named and the value stated.

### [piezo_controller_identity](../entries/piezo_controller_identity.json)

The piezo stage's controller, on COM4, reports itself as hardware part NPC-6330, serial 108564.

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-004).

Conditions, verbatim:

> A device's report of itself, read in a preparatory run -- a read-only first contact that sent only .get commands from a list the person approved by sha256, and moved nothing. 11-21 condition 4 as narrowed at 20a688b lets such a report enter citing the run, graded as an observation by this system; it is not a measurement of any registered observable, and check 85 counts it rather than failing it. E1 from `measured:`. Slot: the device table's piezo_stage row, and O1 preflight -- a session can check it is talking to this controller and not another, or the vendor emulator. A controller swap falsifies it. Delivered as items piezo_controller_part and piezo_controller_serial of microscope_agent/findings/microscope-20260924-2-20260924.json at a0fda99 (card 043). Checked by this seat against microscope_agent/runs/run-20260924-004/log.json read at a0fda99 (committed at 03e0cd2, unchanged since): events 21 and 23, each the command named and the value stated.

### [piezo_controller_software_version](../entries/piezo_controller_software_version.json)

The piezo controller reports its software version as code 101122056, the raw code as reported and not decoded into a release number.

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-004).

Conditions, verbatim:

> A device's report of itself, read in a preparatory run -- a read-only first contact that sent only .get commands from a list the person approved by sha256, and moved nothing. 11-21 condition 4 as narrowed at 20a688b lets such a report enter citing the run, graded as an observation by this system; it is not a measurement of any registered observable, and check 85 counts it rather than failing it. E1 from `measured:`. Slot: O1 preflight -- the vendor library selects commands by controller firmware, so a changed code means a changed command set. A firmware update falsifies it. Delivered as item piezo_controller_software_version of microscope_agent/findings/microscope-20260924-2-20260924.json at a0fda99 (card 043). Checked by this seat against microscope_agent/runs/run-20260924-004/log.json read at a0fda99 (committed at 03e0cd2, unchanged since): events 26, each the command named and the value stated.

### [piezo_interface_library_version_on_this_computer](../entries/piezo_interface_library_version_on_this_computer.json)

The piezo controller's vendor interface library installed on this computer, loaded from the NanoBench 6000 install, reports version 2.8.1.

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-004).

Conditions, verbatim:

> A device's report of itself, read in a preparatory run -- a read-only first contact that sent only .get commands from a list the person approved by sha256, and moved nothing. 11-21 condition 4 as narrowed at 20a688b lets such a report enter citing the run, graded as an observation by this system; it is not a measurement of any registered observable, and check 85 counts it rather than failing it. E1 from `measured:`. A fact about this computer's installation, not about the controller: reinstalling or updating NanoBench falsifies it. The interface-library manual this store holds (src_npcd_interface_library_manual) is for 2.7.9, an earlier release. Slot: O1 preflight. Delivered as item piezo_library_version of microscope_agent/findings/microscope-20260924-2-20260924.json at a0fda99 (card 043). Checked by this seat against microscope_agent/runs/run-20260924-004/log.json read at a0fda99 (committed at 03e0cd2, unchanged since): events 4, each the command named and the value stated.

### [piezo_security_level_as_found_20260924](../entries/piezo_security_level_as_found_20260924.json)

On 2026-09-24 the piezo controller was at security level 'None' -- locked -- and at that level it lists 184 commands. The read-only run left the level where it found it.

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-004).

Conditions, verbatim:

> A device's report of itself, read in a preparatory run -- a read-only first contact that sent only .get commands from a list the person approved by sha256, and moved nothing. 11-21 condition 4 as narrowed at 20a688b lets such a report enter citing the run, graded as an observation by this system; it is not a measurement of any registered observable, and check 85 counts it rather than failing it. E1 from `measured:`. A SETTING: raising the level exposes more commands, and the prior project worked at a higher level than this. Slot: O1 preflight -- a command absent at this level is refused by the controller, not missing from it. Delivered as items piezo_security_level_found and piezo_command_count_locked of microscope_agent/findings/microscope-20260924-2-20260924.json at a0fda99 (card 043). Checked by this seat against microscope_agent/runs/run-20260924-004/log.json read at a0fda99 (committed at 03e0cd2, unchanged since): events 6 and 7, each the command named and the value stated.

### [piezo_stage_identity](../entries/piezo_stage_identity.json)

The piezo controller reports the same stage on all three of its channels: part SP-XYZ-600, serial 107866. So the three axes are one three-axis stage, not three stages.

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-004).

Conditions, verbatim:

> A device's report of itself, read in a preparatory run -- a read-only first contact that sent only .get commands from a list the person approved by sha256, and moved nothing. 11-21 condition 4 as narrowed at 20a688b lets such a report enter citing the run, graded as an observation by this system; it is not a measurement of any registered observable, and check 85 counts it rather than failing it. E1 from `measured:`. This is the stage model the travel-range gap said was recorded nowhere here, and it now comes from the controller rather than from inference. It says nothing by itself about travel: the model name is the controller's string, and reading a travel out of the '600' in it would be inference. Slot: the device table's piezo_stage row. A stage swap falsifies it. Delivered as items piezo_stage_part_ch1..3 and piezo_stage_serial_ch1..3 of microscope_agent/findings/microscope-20260924-2-20260924.json at a0fda99 (card 043). Checked by this seat against microscope_agent/runs/run-20260924-004/log.json read at a0fda99 (committed at 03e0cd2, unchanged since): events 36-41, each the command named and the value stated.

### [nanobench_controller_gives_limited_protection](../entries/nanobench_controller_gives_limited_protection.json)

The piezo controller gives only limited protection against settings that would damage a connected stage; configuring it is for engineers or technicians with enough expertise to do it safely.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:nanobench_6000_user_manual_v1_0_19).

Conditions, verbatim:

> Read from Nanobench 6000 Customer Interface Software User Manual, PS-000006-UM issue 4 / v1.0.19 (sha256 2acb47b5...): printed page 5 (PDF page 5). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. These manuals are for the controller's software; the archive holds no hardware manual for the stage or the controller. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [nanobench_controller_shuts_down_when_hot](../entries/nanobench_controller_shuts_down_when_hot.json)

The piezo controller performs a safety shutdown if parts of its circuit board get hot enough to be damaged, and shows it on an over-temperature light. The first thing to check is that its air vents are not covered; if it recurs with the vents clear, the manufacturer asks to be contacted.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:nanobench_6000_user_manual_v1_0_19).

Conditions, verbatim:

> Read from Nanobench 6000 Customer Interface Software User Manual, PS-000006-UM issue 4 / v1.0.19 (sha256 2acb47b5...): printed page 9 (PDF page 9), printed page 16 (PDF page 16). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. These manuals are for the controller's software; the archive holds no hardware manual for the stage or the controller. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [nanobench_higher_security_levels_expose_damaging_settings](../entries/nanobench_higher_security_levels_expose_damaging_settings.json)

Raising the piezo controller's security level exposes settings that can damage the stage or the controller -- for example, too small an integrator time constant makes the loop unstable and damages the stage. NanoBench warns when a higher level is entered.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:nanobench_6000_user_manual_v1_0_19).

Conditions, verbatim:

> Read from Nanobench 6000 Customer Interface Software User Manual, PS-000006-UM issue 4 / v1.0.19 (sha256 2acb47b5...): printed page 8 (PDF page 8). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. These manuals are for the controller's software; the archive holds no hardware manual for the stage or the controller. The controller was found at its lowest level on 2026-09-24 (piezo_security_level_as_found_20260924). KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [nanobench_stage_presets_can_be_overwritten_or_lost](../entries/nanobench_stage_presets_can_be_overwritten_or_lost.json)

In NanoBench, storing a stage calibration preset overwrites the settings held in it, and deleting a preset from the stage's memory cannot be undone.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:nanobench_6000_user_manual_v1_0_19).

Conditions, verbatim:

> Read from Nanobench 6000 Customer Interface Software User Manual, PS-000006-UM issue 4 / v1.0.19 (sha256 2acb47b5...): printed page 29 (PDF page 29). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. These manuals are for the controller's software; the archive holds no hardware manual for the stage or the controller. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [nanobench_wrong_loop_settings_damage_the_stage](../entries/nanobench_wrong_loop_settings_damage_the_stage.json)

Wrong control-loop settings -- the position, velocity and acceleration loop gains and time constants, and the trajectory limits -- can make the piezo stage unstable and damage it mechanically, and such damage is not covered by the manufacturer's warranty.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:nanobench_6000_user_manual_v1_0_19).

Conditions, verbatim:

> Read from Nanobench 6000 Customer Interface Software User Manual, PS-000006-UM issue 4 / v1.0.19 (sha256 2acb47b5...): printed page 12 (PDF page 12), printed page 30 (PDF page 30), printed page 31 (PDF page 31). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. These manuals are for the controller's software; the archive holds no hardware manual for the stage or the controller. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [nanoflash_interrupted_reprogramming_is_recoverable](../entries/nanoflash_interrupted_reprogramming_is_recoverable.json)

Reprogramming the piezo controller's firmware with NanoFlash cannot damage it even if interrupted, since programming can always be resumed; but the wrong firmware version, while harmless to the controller, may leave it unable to drive stages or missing key features until the right one is loaded.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:nanoflash_user_manual).

Conditions, verbatim:

> Read from NanoFlash Reflash Application User Manual (sha256 98fbdbf6...): printed page 5 (PDF page 5), printed page 13 (PDF page 13). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. These manuals are for the controller's software; the archive holds no hardware manual for the stage or the controller. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [npcd_analogue_and_digital_commands_are_summed](../entries/npcd_analogue_and_digital_commands_are_summed.json)

The piezo controller takes its commanded position from the analogue input, from digital commands from the host, or from both at once, and when both are enabled the two commands are summed.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:nanobench_6000_user_manual_v1_0_19_s1_2).

Conditions, verbatim:

> Vendor specification, read from the manual itself (10.3 rule 2); E3 vendor_spec. Slot: the device wrapper and O1 preflight -- with the analogue input enabled, a digital position command is not the position the stage goes to, so the analogue-command setting has to be known before a digital command means what it says. The microscope seat reports that input as disabled on all three channels today; that report is a separate item this seat has not yet been able to check. The same manual section warns that the controller gives only limited protection against configurations that would damage a connected stage. Falsified by a stage that, with both inputs enabled, follows the digital command alone. Delivered as item `prior_analogue_digital_sum` of microscope_agent/findings/microscope-20260924-2-20260924.json at a0fda99 (card 043); the source was opened and its sha256 recorded before this was ruled.

### [npcd_connectors_are_static_sensitive](../entries/npcd_connectors_are_static_sensitive.json)

The piezo controller's stage and interface connectors are sensitive to electrostatic discharge, so connector covers should be removed and cables connected only with static-safe handling.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:npcd_interface_library_rev6_dll_2_7_9).

Conditions, verbatim:

> Read from NPC-D Series Digital Controller Interface Library manual, revision 6.0, for DLL 2.7.9 (sha256 88da6849...): printed page 2 (PDF page 2). Also NanoFlash Reflash Application User Manual (sha256 98fbdbf6...): printed page 2 (PDF page 2). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. These manuals are for the controller's software; the archive holds no hardware manual for the stage or the controller. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [npcd_controller_covers_must_stay_on](../entries/npcd_controller_covers_must_stay_on.json)

The piezo controller's covers must not be removed: there are no user-serviceable parts inside, and opening it exposes high-voltage hazards and voids the warranty.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:npcd_interface_library_rev6_dll_2_7_9).

Conditions, verbatim:

> Read from NPC-D Series Digital Controller Interface Library manual, revision 6.0, for DLL 2.7.9 (sha256 88da6849...): printed page 2 (PDF page 2). Also NanoFlash Reflash Application User Manual (sha256 98fbdbf6...): printed page 2 (PDF page 2). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. These manuals are for the controller's software; the archive holds no hardware manual for the stage or the controller. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [npcd_controller_generates_hazardous_voltages](../entries/npcd_controller_generates_hazardous_voltages.json)

The piezo controller generates high voltages to drive the piezo actuators and relies on a protective earth, provided through its approved external power supply, to keep accessible parts safe if insulation fails. Only approved stages and cables may be used with it, and it must not be used if it shows any damage or seems faulty.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:npcd_interface_library_rev6_dll_2_7_9).

Conditions, verbatim:

> Read from NPC-D Series Digital Controller Interface Library manual, revision 6.0, for DLL 2.7.9 (sha256 88da6849...): printed page 2 (PDF page 2). Also NanoFlash Reflash Application User Manual (sha256 98fbdbf6...): printed page 2 (PDF page 2). Also Nanobench 6000 Customer Interface Software User Manual, PS-000006-UM issue 4 / v1.0.19 (sha256 2acb47b5...): printed page 5 (PDF page 5). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. These manuals are for the controller's software; the archive holds no hardware manual for the stage or the controller. The NanoBench manual confirms the controller contains a high-voltage amplifier driving the actuator. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [npcd_emulator_returns_zero_for_every_command](../entries/npcd_emulator_returns_zero_for_every_command.json)

The piezo controller's interface library can emulate a controller when none is fitted, addressed as sim:/NPC followed by the controller part number (optionally with a firmware version), and every command sent to the emulator returns zero. It is for testing that an application runs, not for testing what a controller would answer.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:npcd_interface_library_rev6_dll_2_7_9_s4_3_7).

Conditions, verbatim:

> Vendor specification, read from the manual itself (10.3 rule 2); E3 vendor_spec. Slot: O1 preflight and the device wrapper -- a session that finds every read returning zero may be talking to the emulator and not a controller, so a zero read-back is not evidence that a stage is at zero. For the library release the manual documents, 2.7.9; a later release may differ. Whether the emulator opens a serial port is not in the manual and is listed as unmeasured by the microscope seat. Falsified by an emulator command returning non-zero. Delivered as item `prior_simulator_no_controller` of microscope_agent/findings/microscope-20260924-2-20260924.json at a0fda99 (card 043); the source was opened and its sha256 recorded before this was ruled.

### [npcd_network_must_stay_off_wider_networks](../entries/npcd_network_must_stay_off_wider_networks.json)

If the piezo controller is reached over Ethernet through a hub, that hub must connect only to computers meant to talk to the controller, and never to a wider corporate network or the internet.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:npcd_interface_library_rev6_dll_2_7_9).

Conditions, verbatim:

> Read from NPC-D Series Digital Controller Interface Library manual, revision 6.0, for DLL 2.7.9 (sha256 88da6849...): printed page 16 (PDF page 16). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. These manuals are for the controller's software; the archive holds no hardware manual for the stage or the controller. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [npcd_operating_environment](../entries/npcd_operating_environment.json)

The piezo controller is meant for dry, climate-controlled indoor rooms. Significant dust or acoustic or mechanical vibration can cause faults or damage, its fan vents must not be restricted, and humidity is best kept low during long operation.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:npcd_interface_library_rev6_dll_2_7_9).

Conditions, verbatim:

> Read from NPC-D Series Digital Controller Interface Library manual, revision 6.0, for DLL 2.7.9 (sha256 88da6849...): printed page 2 (PDF page 2). Also NanoFlash Reflash Application User Manual (sha256 98fbdbf6...): printed page 2 (PDF page 2). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. These manuals are for the controller's software; the archive holds no hardware manual for the stage or the controller. The temperature and humidity limits are given in a Table 2.1 that this manual refers to and does not contain; that table is in a document the archive does not hold. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [npcd_switch_off_and_unplug_when_not_in_use](../entries/npcd_switch_off_and_unplug_when_not_in_use.json)

The manufacturer says to read the manual before using the piezo controller, because incorrect use can cause injury or damage, and to switch it off and remove the mains plug whenever it is not in use.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:npcd_interface_library_rev6_dll_2_7_9).

Conditions, verbatim:

> Read from NPC-D Series Digital Controller Interface Library manual, revision 6.0, for DLL 2.7.9 (sha256 88da6849...): printed page 2 (PDF page 2). Also NanoFlash Reflash Application User Manual (sha256 98fbdbf6...): printed page 2 (PDF page 2). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. These manuals are for the controller's software; the archive holds no hardware manual for the stage or the controller. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [piezo_waveform_generator_does_not_read_picometres](../entries/piezo_waveform_generator_does_not_read_picometres.json)

The piezo controller's hardware waveform generator does not read its samples in the picometres that the ordinary position command takes. In the prior project a small sine written in picometres and played back swung the axis over a large part of its travel, many times the amplitude asked for, and oscillated far faster than its programmed period; every sample had read back identical to what was written, so the samples were stored correctly and their unit was wrong. What unit the generator does read is not settled.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/kb/decisions/2026-08-27-piezo-first-light).

Conditions, verbatim:

> Ruled DOWNGRADE by the microscope seat and entered at E3, the cap for a measurement taken in another project (10.3 rule 1). The finding crosses; the swing, amplitude and timing figures do not, because they sit in prose (10.3 rule 3). Slot: A7 (driving and motion) and the device wrapper -- it is why the microscope refuses the waveform generator, and the refusal is recorded in that agent's failure record. Measured there on one lateral axis, on that project's controller. The prior record names the experiment that settles the unit: a constant waveform, which cannot oscillate whatever the unit, played on a lateral axis, so wherever the stage parks is the answer. Falsified by a picometre-coded waveform that plays back at the amplitude written. Delivered as item `prior_waveform_313um_swing` of microscope_agent/findings/microscope-20260924-2-20260924.json at a0fda99 (card 043); the source was opened and its sha256 recorded before this was ruled.

## Disputed and withdrawn

- [piezo_calibrated_range](../entries/piezo_calibrated_range.json): in conflict; the other side: [piezo_device_range_as_stated_by_the_person](../entries/piezo_device_range_as_stated_by_the_person.json)
- [piezo_device_range_as_stated_by_the_person](../entries/piezo_device_range_as_stated_by_the_person.json): in conflict; the other side: [piezo_calibrated_range](../entries/piezo_calibrated_range.json)

## Reading

None.

## Related

- [safety guide](../guides/safety_piezo_stage.md)

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
