# Device: csuw1_port

Every entry in the store about the device csuw1_port.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, element of channel confocal_csuw1, verbatim:

```json
{
  "id": "csuw1_port",
  "aliases_in_config": [
    "camera_splitter"
  ],
  "slots": 3,
  "slot_contents": [
    {
      "content": "empty",
      "reaches": [
        "camera_red"
      ],
      "starves": [
        "camera_blue"
      ]
    },
    {
      "content": "561 dichroic",
      "reaches": [
        "camera_red",
        "camera_blue"
      ],
      "starves": []
    },
    {
      "content": "100/0 mirror",
      "reaches": [
        "camera_blue"
      ],
      "starves": [
        "camera_red"
      ]
    }
  ],
  "slot_order": null,
  "automatable": "full",
  "read_back": true,
  "verify_by": "acquisition",
  "source": "operator_read:kyuhwan_20260917",
  "grade": "E3",
  "entry_ref": [
    "csuw1_port_is_the_camera_splitter",
    "csuw1_port_slots",
    "csuw1_port_driver_access"
  ],
  "note": "the port IS the splitter: one mechanism that the configuration named twice. The split is spectral, not by intensity -- the two cameras see different bands, not the same image at half brightness. Two of the three states send zero light to one camera, so this is a selector that decides whether light arrives at all, and read-back cannot verify it: slot_order is null and commanding position 2 may land the mirror while read-back confirms position 2 and tells you nothing. Verify by acquiring (see label_warning in optical_paths.v0.json).",
  "not_entered": "which arm is straight-through and which is reflected. That is a model's inference from the slot contents, which is E6 and may enter nothing (P2, 5.3). Read the dichroic's orientation or acquire a known emitter."
}
```

## Values

None.

## Claims

### [csuw1_port_driver_access](../entries/csuw1_port_driver_access.json)

The port/splitter is drivable and readable through micromanager: it can be set without a human and its position can be read back. It is an element of a channel that is automatable in full with read-back, and the earlier record of a manual-only splitter with no programming interface was wrong on every field it asserted.

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260917).

Conditions, verbatim:

> This instrument as configured on 2026-09-17, operator read at the instrument. Drivable and readable is not the same as verifiable: read-back returns a position, and which element that position holds is exactly what is unknown (see csuw1_port_slots). Falsified by a driver or configuration change that drops the property.

### [csuw1_port_is_the_camera_splitter](../entries/csuw1_port_is_the_camera_splitter.json)

The element the configuration calls csuw1_port and the emission splitter that sends light to one camera or the other are one mechanism inside the CSU-W1 unit, not two devices. The splitter is the port. There is no standalone camera_splitter device on this instrument.

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260917).

Conditions, verbatim:

> This instrument as configured on 2026-09-17, operator read at the instrument (operator_read:kyuhwan_20260917). No numeric condition applies, so a query's condition_range comes back unconstrained rather than satisfied. Falsified by a second splitting element being fitted, or by the loaded device list showing two independently addressable mechanisms.

### [csuw1_port_slots](../entries/csuw1_port_slots.json)

The port/splitter carries three slots, and the split is spectral rather than by intensity: one slot is empty and sends light to the red camera only, one holds a 561 nm dichroic and sends light to both cameras in different bands, and one holds a 100/0 mirror and sends light to the blue camera only. Two of the three states therefore send zero light to one camera. Which physical slot is at which position number is not known.

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260917).

Conditions, verbatim:

> This instrument as configured on 2026-09-17, operator read at the instrument. 561 carries no numbers[] entry: it is the dichroic's nominal designation, a string identifier that is exact by definition, and the measured edge of its transmission curve is a different quantity that nobody here has measured (5.3). Slot contents only: the slot ORDER is not part of this claim and is recorded as a gap, not estimated. Because two states starve one camera, a position number read back from the driver does not establish which element is in the beam -- that is settled by acquiring, not by read-back. Falsified by re-fitting any slot.

## Disputed and withdrawn

None.

## Reading

None.

## Related

- [device camera_blue](../wiki/device_camera_blue.md)
- [device camera_red](../wiki/device_camera_red.md)

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
