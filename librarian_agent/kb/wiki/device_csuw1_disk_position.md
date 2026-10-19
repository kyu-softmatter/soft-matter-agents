# Device: csuw1_disk_position

Every entry in the store about the device csuw1_disk_position.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, element of channel confocal_csuw1, verbatim:

```json
{
  "id": "csuw1_disk_position",
  "aliases_in_config": [
    "csuw1_bright"
  ],
  "states": {
    "in": "confocal",
    "out": "widefield fluorescence and brightfield"
  },
  "source": "operator_read:kyuhwan_20260917",
  "grade": "E3",
  "entry_ref": [
    "csuw1_disk_position_is_the_bright_selector",
    "csuw1_disk_position_states"
  ],
  "note": "one mechanism, two names in the configuration: the confocal/bright-field selector and the disk in/out selector are the same thing. Disk-out is not a configuration of its own -- it is a required selector value on configurations that already exist. The position labelled bright field is also the widefield-fluorescence position, so the configuration id cannot be recovered from this label."
}
```

## Values

None.

## Claims

### [csuw1_disk_position_is_the_bright_selector](../entries/csuw1_disk_position_is_the_bright_selector.json)

The element the configuration calls csuw1_bright, offered as confocal or bright field, and the element it calls csuw1_disk_position, offered as in or out, are one mechanism recorded twice under two names. Moving the disk in or out is the only thing either name selects.

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260917).

Conditions, verbatim:

> This instrument as configured on 2026-09-17, operator read at the instrument. Which of the two names micromanager actually addresses is not settled by this claim and is recorded as a gap: setting one property and reading back the other would show an agreement that means nothing. Falsified by the two names proving independently settable.

### [csuw1_disk_position_states](../entries/csuw1_disk_position_states.json)

With the spinning disk in, the path is confocal. With the disk out, the same hardware serves both widefield fluorescence and brightfield. Disk-out is therefore not a configuration of its own but a required selector value on configurations that already exist, and one selector position serves two different configurations.

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260917).

Conditions, verbatim:

> This instrument as configured on 2026-09-17, operator read at the instrument. The consequence worth carrying: the position labelled bright field is also the widefield-fluorescence position, so the configuration id cannot be recovered from this selector's label, and a read-back that confirms the label confirms nothing about which configuration is loaded. Falsified by a mechanical change to the disk carrier.

## Disputed and withdrawn

None.

## Reading

None.

## Related

None.

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
