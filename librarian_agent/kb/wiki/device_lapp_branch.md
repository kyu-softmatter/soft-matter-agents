# Device: lapp_branch

Every entry in the store about the device lapp_branch.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, element of channel stand_ti2e, verbatim:

```json
{
  "id": "lapp_branch",
  "gap_ref": "lapp_branch_assignment",
  "note": "selects which widefield source reaches the sample. WHICH engine each state selects is not confirmed. This is also the one element on this instrument with a recorded history of an inverted label-to-state mapping -- see label_warning in optical_paths.v0.json, where a branch selector read back consistently wrong for weeks and only an image showed which position passed light. The element with that history is the element whose engine assignment is unverified, and those two facts are worth reading together rather than one at a time."
}
```

## Values

None.

## Claims

### [single_cam_red_config_startup_puts_the_lapp_mirror_in](../entries/single_cam_red_config_startup_puts_the_lapp_mirror_in.json)

Loading single_cam_red_noDMD_nocom10.cfg moves the Lapp main-branch mirror: its System/Startup preset sets LappMainBranch1 State to 1, and after the load LappMainBranch1 reads State 1 (mirror_in).

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-002).

Conditions, verbatim:

> Read back in a preparatory run -- the first real acquisition on this computer, with no plan, the person having placed the 20x and moved the microscope by hand, software moving nothing. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system: E1 from `measured:`. Not a value of any registered observable. The preset line is in the configuration file (line 261 at agentic-microscope fbedef0, sha256 8184073e..., which this seat read); the read-back is the run's. A LOAD IS NOT A READ: loading this configuration writes to a device. The person accepted that move for today's runs, which is a decision and is not in this entry. Slot: O1 preflight and A4. Delivered as item lapp_mirror_state_1_after_startup_preset of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042). Checked by this seat against microscope_agent/runs/run-20260924-002/log.json read at bf8f91f (unchanged since): event 12.

### [stand_state_read_20260924_20x_in_place](../entries/stand_state_read_20260924_20x_in_place.json)

On 2026-09-24, with the 20x placed by hand, the stand read: Nosepiece state 2, label '3-Plan Apo LmbdD0.8 20x'; LightPath state 3, '4-L100'; FilterTurret1 state 0, '1-MXR00724 -Empty'; FilterTurret2 state 0, '1-Empty'; LappMainBranch1 state 1, 'mirror_in'; CondenserTurret state 0, '1-ND'.

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-002).

Conditions, verbatim:

> Read back in a preparatory run -- the first real acquisition on this computer, with no plan, the person having placed the 20x and moved the microscope by hand, software moving nothing. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system: E1 from `measured:`. Not a value of any registered observable. A STATE, NOT A PROPERTY: every value is falsified by moving that element. The labels are strings from the loaded configuration and are downgraded until a frame confirms each (plan.md 10.2.1); the state integers are what the stand reported. Nosepiece state 2 agrees with nosepiece_objective_assignment, which puts the 20x (MRD70270) at position 2. FilterTurret1's label names both the MXR00724 cube and 'Empty' at state 0, which is ambiguous; filter_turret_1_state_0_blocked_the_confocal_path records that cube at state 0 in the prior project on 2026-09-07. Slot: A4 and A6. Delivered as item stand_read_with_20x_in_place of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042). Checked by this seat against microscope_agent/runs/run-20260924-002/log.json read at bf8f91f (unchanged since): event 15.

### [lapp_state_1_brings_the_aura_to_the_sample](../entries/lapp_state_1_brings_the_aura_to_the_sample.json)

On this stand, with the Lapp main branch at State 1 -- where the device reports the label 'mirror_in' -- the Aura III light engine's light reaches the sample: the person saw particles lit by the Aura in that state and said the position is the Aura's.

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260924_lapp_aura).

Conditions, verbatim:

> The person's reading and observation on the evening of 2026-09-24, recorded verbatim in commit cd09784's message. About the INTEGER 1: branch_selector_is_pinned_by_integer_not_label holds that this selector's labels were inverted relative to its positions on the prior bench, so the label is given only as what the device reports there. Consistent with run-20260924-002, where the Aura lit the particles while LappMainBranch1 read back 1 (stand_state_read_20260924_20x_in_place). NOT established: what the other positions route; whether the Spectra III also reaches the sample in State 1; which of the device table's widefield_source_a and widefield_source_b is the Aura. Neither observation blocked one engine, which is the decisive test the lapp_branch_assignment gap names, so this narrows that gap and does not close it. Delivered as item lapp_main_branch_state_1_is_the_aura_iii_position of microscope_agent/findings/microscope-20260924-5-20260924.json at cd09784 (card 046).

## Disputed and withdrawn

None.

## Reading

None.

## Related

- [device filter_turret_1](../wiki/device_filter_turret_1.md)
- [device filter_turret_2](../wiki/device_filter_turret_2.md)
- [device light_path_port](../wiki/device_light_path_port.md)
- [device nosepiece](../wiki/device_nosepiece.md)
- [device stand_ti2e](../wiki/device_stand_ti2e.md)

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
