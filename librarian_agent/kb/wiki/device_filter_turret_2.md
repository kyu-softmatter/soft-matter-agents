# Device: filter_turret_2

Every entry in the store about the device filter_turret_2.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, element of channel stand_ti2e, verbatim:

```json
{
  "id": "filter_turret_2"
}
```

## Values

None.

## Claims

### [stand_state_read_20260924_20x_in_place](../entries/stand_state_read_20260924_20x_in_place.json)

On 2026-09-24, with the 20x placed by hand, the stand read: Nosepiece state 2, label '3-Plan Apo LmbdD0.8 20x'; LightPath state 3, '4-L100'; FilterTurret1 state 0, '1-MXR00724 -Empty'; FilterTurret2 state 0, '1-Empty'; LappMainBranch1 state 1, 'mirror_in'; CondenserTurret state 0, '1-ND'.

Identifiers: none

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-002).

Conditions, verbatim:

> Read back in a preparatory run -- the first real acquisition on this computer, with no plan, the person having placed the 20x and moved the microscope by hand, software moving nothing. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system: E1 from `measured:`. Not a value of any registered observable. A STATE, NOT A PROPERTY: every value is falsified by moving that element. The labels are strings from the loaded configuration and are downgraded until a frame confirms each (plan.md 10.2.1); the state integers are what the stand reported. Nosepiece state 2 agrees with nosepiece_objective_assignment, which puts the 20x (MRD70270) at position 2. FilterTurret1's label names both the MXR00724 cube and 'Empty' at state 0, which is ambiguous; filter_turret_1_state_0_blocked_the_confocal_path records that cube at state 0 in the prior project on 2026-09-07. Slot: A4 and A6. Delivered as item stand_read_with_20x_in_place of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042). Checked by this seat against microscope_agent/runs/run-20260924-002/log.json read at bf8f91f (unchanged since): event 15.

### [ti2e_filter_shutter_state_at_startup_is_a_setting](../entries/ti2e_filter_shutter_state_at_startup_is_a_setting.json)

In Ti2 Control, whether the fluorescence turret's shutter is open or closed when the microscope starts is a setting.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:nikon_ti2_control_v2_90_m706_e15).

Conditions, verbatim:

> Read from Nikon Ti2 Control Ver2.90 for Windows, English manual M706 E15 (sha256 5e43517c...): printed page 75 (PDF page 83). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. This manual is for the Ti2 Control software; the archive holds no Ti2-E hardware manual. How this stand is set is not recorded here; a shutter set to open at start-up admits light as soon as a source is on. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [filter_turret_shutters_close_at_state_0](../entries/filter_turret_shutters_close_at_state_0.json)

The person stated on 2026-10-04 that the two filter-turret shutters, Micro-Manager devices Turret1Shutter and Turret2Shutter, are closed when their State property is "0".

Identifiers: closed_value: 0; mm_device: Turret1Shutter, Turret2Shutter; property: State

How it is known: recalled or assumed; the person's recollection (E5 · operator_recall:kyuhwan_20261004).

Conditions, verbatim:

> A recollection, not a reading: no read-back of either shutter in a closed state is recorded on this stand, and the abort that closes them to this value (35c5d6d) has run on mock only. Falsifier: on the stand, a shutter seen closed whose State reads anything but "0". KNOWLEDGE, NOT POLICY: which value means closed is a fact about the device; that software may write it, and only on an abort, is the person's exemption of 2026-10-04 in plan.md 4.6.8 and not this entry's to grant.

## Disputed and withdrawn

None.

## Reading

None.

## Related

- [device filter_turret_1](../wiki/device_filter_turret_1.md)
- [device lapp_branch](../wiki/device_lapp_branch.md)
- [device light_path_port](../wiki/device_light_path_port.md)
- [device nosepiece](../wiki/device_nosepiece.md)
- [device stand_ti2e](../wiki/device_stand_ti2e.md)

---

Generated from the knowledge store at kbv-d027f44dadc0. Do not edit by hand: correct the store and regenerate.
