# Device: csuw1_shutter

Every entry in the store about the device csuw1_shutter.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, element of channel confocal_csuw1, verbatim:

```json
{
  "id": "csuw1_shutter",
  "mm_label": {
    "label": "CSUW1-Shutter",
    "entry_ref": "csuw1_shutter_state_reads_a_label",
    "config_sha256": "fad5873de9f994c123090ee56feecb1a33c5bb77f31f3afed1eec7522d1c4f89"
  },
  "source": "operator_read:kyuhwan_20260917",
  "grade": "E3",
  "entry_ref": "csuw1_shutter_gates_confocal_excitation",
  "note": "gates the confocal laser into the unit; must be open while the confocal laser is in use. Which shutter an abort closes is policy, not knowledge: it belongs to a person in microscope_agent/envelope/safety.json (4.3.2, 10.3 rule 4). There are two shutters in this chain -- see laser_combiner/laser_shutter."
}
```

## Values

None.

## Claims

### [csuw1_shutter_state_reads_a_label](../entries/csuw1_shutter_state_reads_a_label.json)

The confocal unit's shutter, Micro-Manager device CSUW1-Shutter, reports its State property as a label rather than a position: it read "Open" on 2026-09-24, and asking the core for its numeric state failed because the device is of the wrong type for that call. No closed value has been recorded.

Identifiers: mm_config_sha256: fad5873de9f994c123090ee56feecb1a33c5bb77f31f3afed1eec7522d1c4f89; mm_device: CSUW1-Shutter; property: State; reported_label: Open

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-008).

Conditions, verbatim:

> Events 5 and 21 of the run: a property read returning State "Open", then the state-device query raising a wrong-type error. That the label read "Open" says what the adapter reported, not that light passed; whether the shutter was physically open is not recorded. The label for closed is unknown, which is why the abort may not close this shutter yet even though the person allowed it on 2026-10-04 (35c5d6d). Read back in a preparatory run with no plan, which wrote nothing to any device. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system, E1. Not a value of any registered observable. KNOWLEDGE, NOT POLICY: what the device reports, never a limit and never permission to command it. Checked by this seat against microscope_agent/runs/run-20260924-008/log.json, read by this seat at 144ab62 (last changed at 9c9f598); body sha256 with CRLF normalised to LF f7a8f673fd630b7252b8ec30f10e71abafe0aea58ae12c85cbb2ed4f2e187818. The identifier mm_config_sha256 was added on 2026-10-27 by librarian-20261007-1 for librarian card 061, from this same run's log, which card 080 moved to microscope_runtime/runs/run-20260924-008/log.json (read at fb5eff40; body sha256 with CRLF normalised to LF unchanged, f7a8f673...): event 2, load, dualcam_noDMD_nolaser_nostartup.cfg with sha256 and sha256_after_load both fad5873de9f994c123090ee56feecb1a33c5bb77f31f3afed1eec7522d1c4f89, the run's one configuration load, before events 5 and 21. The digest is the run's record of which file was loaded, not a hash of any file on disk. The claim is unchanged.

### [csuw1_shutter_gates_confocal_excitation](../entries/csuw1_shutter_gates_confocal_excitation.json)

The shutter inside the confocal unit gates the confocal laser into the unit, and it must be open while the confocal laser is in use for excitation to reach the sample.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260917).

Conditions, verbatim:

> This instrument as configured on 2026-09-17, operator read at the instrument. This entry says what the shutter gates and stops there. Which shutter an abort closes is policy, not knowledge: it belongs to a person and to microscope_agent/envelope/safety.json (4.3.2, 10.3 rule 4). Falsified by a re-plumbing of the excitation path.

## Disputed and withdrawn

None.

## Reading

None.

## Related

None.

---

Generated from the knowledge store at kbv-058ce14eea72. Do not edit by hand: correct the store and regenerate.
