# Device: z_drive

Every entry in the store about the device z_drive.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, element of channel stand_ti2e, verbatim:

```json
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
}
```

## Values

None.

## Claims

### [ti2e_objective_escape_is_set_per_nosepiece_address](../entries/ti2e_objective_escape_is_set_per_nosepiece_address.json)

In Ti2 Control, each nosepiece address can be set to move the objective to its escape position before that address passes when the nosepiece rotates, and the escape distance used when changing the specimen is also a setting there.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:nikon_ti2_control_v2_90_m706_e15).

Conditions, verbatim:

> Read from Nikon Ti2 Control Ver2.90 for Windows, English manual M706 E15 (sha256 5e43517c...): printed page 73 (PDF page 81). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. This manual is for the Ti2 Control software; the archive holds no Ti2-E hardware manual. Bears on nosepiece_write_runs_no_escape (the prior project: a Micro-Manager nosepiece write runs no escape): what the stand does is configured in the stand, and how this one is configured is not recorded here. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [tweez_calibration_photodiode_needs_the_laser_off](../entries/tweez_calibration_photodiode_needs_the_laser_off.json)

Before setting up the calibration photodiode the laser must be switched off, or it can injure eyes or skin and damage the photodiode. The objective must be fully retracted before the photodiode is placed on the sample holder, and its position adjusted with great care, so as not to damage the objective's front lens.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:Tweez300UserManual).

Conditions, verbatim:

> Read from Tweez 300 User Manual, 2021 (file date 2022-01-06; sha256 c37027cb..., byte-identical in both places): printed page 28 (PDF page 34), printed page 29 (PDF page 35). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

## Disputed and withdrawn

None.

## Reading

None.

## Related

- [device nosepiece](../wiki/device_nosepiece.md)
- [device optical_tweezers](../wiki/device_optical_tweezers.md)
- [device stand_ti2e](../wiki/device_stand_ti2e.md)

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
