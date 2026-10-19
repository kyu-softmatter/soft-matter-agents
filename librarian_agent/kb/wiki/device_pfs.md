# Device: pfs

Every entry in the store about the device pfs.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, element of channel stand_ti2e, verbatim:

```json
{
  "id": "pfs",
  "note": "focus stabilisation; disabled across turret and path changes (2.1 interlock 3)"
}
```

## Values

None.

## Claims

### [pfs_reports_focus_maintenance_status_and_range_in_three_states](../entries/pfs_reports_focus_maintenance_status_and_range_in_three_states.json)

The focus hold, Micro-Manager device PFS on the NikonTi2 adapter, read three properties in three states on 2026-10-13: off and never switched on since load -- FocusMaintenance Off, PFS Status 0000000000000000, PFS in Range 'Out of Range'; on and locked -- FocusMaintenance On, PFS Status 0000001100001010, PFS in Range 'In Range'; off again after being on -- FocusMaintenance Off, PFS Status 0000000100000000, PFS in Range 'In Range'.

Identifiers: mm_adapter: NikonTi2; mm_device: PFS; properties: FocusMaintenance, PFS Status, PFS in Range, PFS LEDIntensity

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20261013_bench_readings).

Conditions, verbatim:

> SETTINGS READ BACK, entered the way 044 entered the stand's self-reports, as strings and not quantities. The person read each value in the Device Property Browser with 'Show read-only' ticked, pressed Refresh after each change of state, and confirmed the 16 digits of PFS Status for the first two states and the third by saying so; the switch was the stand's own, and 'locked' was confirmed on the stand by the person, not inferred from the property. operator_read and not measured: no run of this system recorded it. ALSO READ: PFS LEDIntensity went from 27 to 10 when focus hold was switched on; the person did not change it. NOT READ: the state 'on but still searching' -- the stand locks faster than the person could press Refresh, after several tries -- so nothing here says what any property reads while searching, including whether FocusMaintenance reads On then. NO SINGLE Status STRING MEANS 'NOT ENGAGED': PFS Status read two different strings in the two off states, 0000000000000000 and 0000000100000000, so Status alone does not tell off from not-yet-reached; FocusMaintenance read Off in both off states and On in the locked one. The person's explanation of the two off codes is a separate entry, pfs_status_differs_in_range_and_out_of_range_per_the_person, kept apart so these readings stay what was read. WHICH READING THE ENVELOPE USES IS THE PERSON'S: envelope/safety.json's pfs_not_engaged is written by the person and is not this entry's to judge, and nothing here may be read as a command or a limit.

### [pfs_status_differs_in_range_and_out_of_range_per_the_person](../entries/pfs_status_differs_in_range_and_out_of_range_per_the_person.json)

The person stated on 2026-10-15 that both off readings of PFS Status taken on 2026-10-13, 0000000000000000 and 0000000100000000, are focus hold off, and that the codes differ because one was taken out of range and the other in range.

Identifiers: mm_device: PFS; property: PFS Status

How it is known: recalled or assumed; the person's recollection (E5 · operator_recall:kyuhwan_20261015_pfs_off_codes).

Conditions, verbatim:

> THE PERSON'S READING OF THE READINGS, kept separate from pfs_reports_focus_maintenance_status_and_range_in_three_states so that what was read and what it means are not one claim. It agrees with the record's own PFS in Range column: 'Out of Range' with Status 0000000000000000 and 'In Range' with 0000000100000000. What it says: whether the stand is in range shows in the Status code apart from engagement. What it does NOT say: which bit of Status means engaged, or what the searching state reads, which was not caught. E5 because it is a statement made two days after the bench, not a reading. Which reading the envelope uses as not engaged is the person's and is written in envelope/safety.json; this entry does not judge it, and is not a command or a limit.

## Disputed and withdrawn

None.

## Reading

None.

## Related

None.

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
