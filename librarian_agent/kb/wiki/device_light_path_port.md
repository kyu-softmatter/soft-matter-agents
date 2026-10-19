# Device: light_path_port

Every entry in the store about the device light_path_port.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, element of channel stand_ti2e, verbatim:

```json
{
  "id": "light_path_port",
  "note": "cameras and the confocal unit are on one position only; any other value sends emission where no detector sees it"
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

### [ti2e_optical_path_addresses](../entries/ti2e_optical_path_addresses.json)

On the Ti2-E the light path has four addresses: 1 is the eyepiece observation port; 2 the right side port; 3, with the optical-path split prism, sends 80 per cent to the left side port and 20 per cent to the eyepieces, or is the bottom port on the Ti2-E/B; and 4 is the left side port. So two addresses can put light into the eyepieces. The position the path takes at start-up is a Ti2 Control setting.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:nikon_ti2_control_v2_90_m706_e15).

Conditions, verbatim:

> Read from Nikon Ti2 Control Ver2.90 for Windows, English manual M706 E15 (sha256 5e43517c...): printed page 67 (PDF page 75), printed page 75 (PDF page 83). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. This manual is for the Ti2 Control software; the archive holds no Ti2-E hardware manual. How these addresses map onto Micro-Manager's LightPath state numbers is not stated in the manual; on 2026-09-24 state 3 read back with the label '4-L100' (stand_state_read_20260924_20x_in_place), which fits address = state + 1 and does not establish it. Whether this stand has the split prism is not recorded here. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_microscope_interlock_blocks_the_laser_at_the_eyepieces](../entries/tweez_microscope_interlock_blocks_the_laser_at_the_eyepieces.json)

The Nikon Ti2's own interlock switch is triggered whenever light could enter the eyepieces -- when the light path selector is set to the eyepieces -- and it is wired to the tweezers' optical unit, so that laser operation is disabled in that position. The manufacturer calls it an additional measure: an infrared filter already keeps the laser out of the eyepiece path. If the interlock cable is disconnected, laser operation is disabled. The Ti2's interlock works only while the microscope is powered, and with the microscope off, tweezers laser operation is disabled too.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300LaserSafetyManual_v3_0_2022).

Conditions, verbatim:

> Read from Tweez 305/310 Laser Safety Manual V3.0, November 2022, as installed in C:/Program Files/Aresis/Tweez300/Manuals/ (sha256 264ab54b...): printed page 7 (PDF page 9). Also Tweez 305/310 System Installation Guide, 2021 (sha256 1f664a72..., byte-identical in the installed folder and the lab archive): printed page 12 (PDF page 16). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. Which light-path positions send light to the eyepieces is the open gap light_path_port_eyepiece_states; the Ti2 Control manual's port list narrows it (ti2e_optical_path_addresses). KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

## Disputed and withdrawn

None.

## Reading

None.

## Related

- [device filter_turret_1](../wiki/device_filter_turret_1.md)
- [device filter_turret_2](../wiki/device_filter_turret_2.md)
- [device lapp_branch](../wiki/device_lapp_branch.md)
- [device nosepiece](../wiki/device_nosepiece.md)
- [device optical_tweezers](../wiki/device_optical_tweezers.md)
- [device stand_ti2e](../wiki/device_stand_ti2e.md)

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
