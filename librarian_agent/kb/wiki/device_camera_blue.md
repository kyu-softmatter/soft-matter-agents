# Device: camera_blue

Every entry in the store about the device camera_blue.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, channel, verbatim:

```json
{
  "id": "camera_blue",
  "role": "detector on the other arm of the spectral port. Same model as camera_red; primary and second were wiring and naming, not a hardware difference, and neither camera is the better one.",
  "model": "Kinetix 22",
  "driver": "micromanager_pvcam",
  "automatable": "full",
  "read_back": true,
  "lock_group": "camera_blue",
  "exclusive_with": [
    "optical_tweezers_gui"
  ],
  "source": "mm_config, confirmed there by loading it",
  "grade": "E3",
  "confirmed_by": "operator_read:kyuhwan_20260917",
  "entry_ref": "cameras_both_kinetix22",
  "note": "identical models, so pixel size, quantum efficiency, read noise and full-well are the same on both arms and the two are photometrically comparable without a cross-calibration term. The 561 dichroic in the port is the only thing making the arms differ, which is why nothing about the cameras themselves can disambiguate the emission-wheel mapping."
}
```

## Values

| quantity | value | unit | how it is known | grade and source as recorded | conditions | subject | entry |
|---|---|---|---|---|---|---|---|
| full_scale_count | 65535 | ADU | recalled or assumed; the person's recollection | E5 · operator_recall:kyuhwan_20261013_cameras_read_the_same | none stated | device camera_red, device camera_blue, quantity full_scale_count | [kinetix22_both_bodies_saturate_alike_per_the_person](../entries/kinetix22_both_bodies_saturate_alike_per_the_person.json) |

## Claims

### [camera_bodies_are_told_apart_by_serial](../entries/camera_bodies_are_told_apart_by_serial.json)

The two camera bodies are distinguished by serial number rather than by label: A23H723003 is the blue arm and A24M723015 is the red arm.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@safety-2026-09-03).

Conditions, verbatim:

> Ruled TRANSFER under 10.2.1 and passed 10.3 rule 1, so it caps at E3 -- a run taken in another project is not a run taken here. 10.2's hardware-control-path row is open and says in its own rule that it does not wait for envelope/, because wrapping a control path needs no safety limit. Slot: O1 preflight, which has to know which body it opened. The labels are the thing not to trust: this store already records that the two bodies are the same model, so nothing about a frame distinguishes them, and it already records one instance of this instrument's paper record diverging from its hardware. A serial is addressable, so either number now finds this entry.

### [cameras_both_kinetix22](../entries/cameras_both_kinetix22.json)

Both cameras are Kinetix 22. They are the same model, so pixel size, quantum efficiency, read noise and full-well capacity are the same on both arms, and the two arms of the splitter are photometrically comparable without a cross-calibration term. The names red and blue, and the roles primary and second detector, are wiring and naming rather than a hardware difference: neither camera is the better one.

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260917).

Conditions, verbatim:

> This instrument as configured on 2026-09-17, operator read at the instrument. This closes an older discrepancy in which a purchase quote listed one Kinetix 22 and one Prime95B against a current state recorded as two Kinetix, unconfirmed: a swap did happen against the quote. Sensor properties are shared because the model is shared; no sensor number is entered here, and the calibrated pixel size remains a per-configuration gap. Falsified by either camera being replaced.

### [csuw1_port_slots](../entries/csuw1_port_slots.json)

The port/splitter carries three slots, and the split is spectral rather than by intensity: one slot is empty and sends light to the red camera only, one holds a 561 nm dichroic and sends light to both cameras in different bands, and one holds a 100/0 mirror and sends light to the blue camera only. Two of the three states therefore send zero light to one camera. Which physical slot is at which position number is not known.

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260917).

Conditions, verbatim:

> This instrument as configured on 2026-09-17, operator read at the instrument. 561 carries no numbers[] entry: it is the dichroic's nominal designation, a string identifier that is exact by definition, and the measured edge of its transmission curve is a different quantity that nobody here has measured (5.3). Slot contents only: the slot ORDER is not part of this claim and is recorded as a gap, not estimated. Because two states starve one camera, a position number read back from the driver does not establish which element is in the beam -- that is settled by acquiring, not by read-back. Falsified by re-fitting any slot.

### [emission_wheel_camera_mapping](../entries/emission_wheel_camera_mapping.json)

The first emission filter wheel serves the red camera and the second serves the blue camera. The operator stated this from memory, with the word probably, and the blue half is the complementary half of the same recalled claim.

How it is known: recalled or assumed; the person's recollection (E5 · operator_recall:kyuhwan_20260917).

Conditions, verbatim:

> This instrument as configured on 2026-09-17, stated from memory rather than read (operator_recall:kyuhwan_20260917), which is why this is E5 and not E3 while every neighbouring claim about the unit is E3. Not to be promoted by corroboration: a spectral splitter puts one wheel on each output arm, which is consistent with this mapping but is not a reading of it. If the mapping is inverted, two-colour data is labelled wrong and nothing raises an error. Settled by one acquisition: move one wheel and see which camera's image changes.

## Disputed and withdrawn

None.

## Reading

None.

## Related

- [device camera_red](../wiki/device_camera_red.md)
- [device csuw1_port](../wiki/device_csuw1_port.md)
- [device filter_wheel_em1](../wiki/device_filter_wheel_em1.md)
- [device filter_wheel_em2](../wiki/device_filter_wheel_em2.md)
- [quantity full_scale_count](../wiki/quantity_full_scale_count.md)
- [safety guide](../guides/safety_camera_blue.md)

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
