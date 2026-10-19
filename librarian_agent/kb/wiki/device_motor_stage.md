# Device: motor_stage

Every entry in the store about the device motor_stage.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, element of channel stand_ti2e, verbatim:

```json
{
  "id": "motor_stage",
  "lock_group": "stage",
  "source": "operator_read:kyuhwan_20260917",
  "grade": "E3",
  "entry_ref": "stand_ti2e_lock_groups",
  "note": "coarse xy, on the body hub. Stage moves therefore serialise with port and filter changes under one channel, one worker (4.6.8) -- that consequence is design, not a hardware reading, and is not stamped as one."
}
```

## Values

None.

## Claims

### [stand_ti2e_lock_groups](../entries/stand_ti2e_lock_groups.json)

The coarse motorised xy stage is an element of the microscope body channel, on the body hub. The body's optical elements belong to the optical_path lock group while the motor stage belongs to the stage lock group, because the piezo rides on the motor stage. One channel therefore carries two lock groups, and a lock group is a property of an element rather than only of a channel.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260917).

Conditions, verbatim:

> This instrument as configured on 2026-09-17, operator read at the instrument. What is confirmed here is the hardware arrangement and the group each element belongs to. What follows from it under one-channel-one-worker -- that stage moves serialise with port and filter changes, and that the lock a worker waits on is chosen per command rather than per channel -- is a design consequence, not a reading, and is not stamped as one. Falsified by the stage being moved off the body hub or the piezo being mounted elsewhere.

## Disputed and withdrawn

None.

## Reading

None.

## Related

- [device stand_ti2e](../wiki/device_stand_ti2e.md)

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
