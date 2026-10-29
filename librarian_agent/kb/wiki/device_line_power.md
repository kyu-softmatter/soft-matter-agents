# Device: line_power

Every entry in the store about the device line_power.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, element of channel laser_combiner, verbatim:

```json
{
  "id": "line_power",
  "read_back": false,
  "note": "open loop: the device reports nothing back. The OUTPUT at full level is calibrated against a power meter for three of the four lines at three objectives (see calibrated_coverage); a commanded level is not, because this system does not transmit the per-line power word. Abort never relies on a commanded power -- it closes a shutter, and which one is policy.",
  "calibrated": true,
  "calibrated_coverage": "488, 561 and 640 nm at 100% level through the 4x, 10x and 20x objectives, measured at the sample plane on 2026-09-09 and valid to 2036-09-24: the nine confocal_power_at_sample_<line>nm_<objective>_full_level entries, E2, source src_illumination_power_worksheet_20260909. NOT covered: 405 nm; 100x for any line; any level other than 100% (the 20x sweeps are partial and are not entered as linearity). A power at an uncovered line, objective or level is not known, and nothing here may stand in for it.",
  "calibrated_resolved": "TRUE AGAIN ON 2026-09-24, from the entries and not from the reading of 2026-09-17. The person said the power had been calibrated and pointed to C:/Users/Takatori lab/Downloads/illumination-power-worksheet.xlsx, which no search of the prior repositories had found, and answered its blank fields: every spot inside the sensor, the wavelength set per line, a Thorlabs PM100A with an S120C or S121C head, valid ten years. The note below is the history that led here and is kept.",
  "calibrated_note": "WAS `true` UNTIL 2026-09-24, and changed to the conservative reading because two records contradict it and a `calibrated` that is not is a power figure someone may trust. (1) The prior project's own record, kb/decisions/2026-09-02-lunf-first-light-measured-limits.md at a7b880b, section 4: every calibration record in the device database is empty, the milliwatt figure the acquisition software can show is a user-entered interpolation table, and volts to milliwatts is listed as still unknown. (2) This store's own entry lunf_per_line_power_is_not_transmittable says the combiner's power was already recorded as write-only and uncalibrated. Against them stands the operator reading of 2026-09-17 that this row was built from. Not resolved by this change: the person has been asked whether a calibration against a power meter exists. If one does, it comes back as a calibration source with its date and validity period, and this returns to true. Reported by manager-microscope-20260924-1 from card 036.",
  "source": "operator_read:kyuhwan_20260917",
  "grade": "E3",
  "grade_note": "the grade is of the row's other facts (open loop, no read-back), from the operator reading of 2026-09-17. The calibration itself is E2 and lives in the nine entries named in calibrated_coverage, not in this row."
}
```

## Values

None.

## Claims

### [lunf_analog_outputs_are_not_cabled_to_the_combiner](../entries/lunf_analog_outputs_are_not_cabled_to_the_combiner.json)

The DAQ's four analog outputs are not cabled to the combiner's power inputs. Driving them, together and one at a time, stepped and at speed, with the blanking line held open, changed nothing in the emitted light.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/kb/decisions/2026-09-02-lunf-first-light).

Conditions, verbatim:

> Ruled TRANSFER, passed 10.3 rule 1 (E3, tested in another project on 2026-09-02). A negative result carried so the route is not proposed again. Slot: A4 (automatability of line_power) -- it removes one candidate path and adds none. The drive voltages of the test are in prose and are not carried (10.3 rule 3). Falsified by an analog output that modulates a line, which would also mean the cabling changed. Delivered as item `combiner_ao_route_not_cabled` of microscope_agent/findings/microscope-20260924-3-20260924.json at a5e7647 (card 044); the source was opened at fbedef0 and its sha256 matched before this was ruled.

### [lunf_per_line_power_is_not_transmittable](../entries/lunf_per_line_power_is_not_transmittable.json)

The confocal combiner's lines are reachable only as blanking, on digital lines through the acquisition software's line-select group. Per-line power is deliberately not transmitted: the vendor does not document the word format the power interface expects, and the transport was left complete but disabled rather than guessing a byte into a laser driver.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@safety-2026-09-03).

Conditions, verbatim:

> Ruled TRANSFER under 10.2.1 and passed 10.3 rule 1, so it caps at E3 -- a run taken in another project is not a run taken here. 10.2's hardware-control-path row is open and says in its own rule that it does not wait for envelope/, because wrapping a control path needs no safety limit. Slot: A4, which screens on automatable, and the orchestrator. It is a refusal that was made on purpose and is worth carrying as such -- an undocumented control word is not a gap in the implementation to be closed by trying values. This store already recorded the combiner's power as write-only and uncalibrated; what is added is WHY it is not driven, which is the part that stops someone finishing the job.

### [lunf_reports_nothing_back](../entries/lunf_reports_nothing_back.json)

Nothing about the laser combiner can be read back. Its DAC is write-only; reading back a blanking line returns the writer's own output, not the shutter's state; no combiner monitor signal is wired to any of the DAQ's analog inputs, which float; and the vendor library exports no shutter or status entry point.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/kb/decisions/2026-09-02-lunf-first-light).

Conditions, verbatim:

> Ruled TRANSFER, passed 10.3 rule 1 (E3, checked in another project on 2026-09-02). It is the evidence behind the device table's read_back false on laser_combiner, stated out loud the way tweez300_reports_nothing_back states it for the trap. The echo point matters most: a digital-output read-back looks like confirmation and is not. The floating-input voltages are prose and are not carried. Slot: A4 (read-back availability) and the orchestrator's verify step, which cannot verify this device. Falsified by any read path that reports a state the software did not write. Delivered as item `combiner_reports_nothing_back` of microscope_agent/findings/microscope-20260924-3-20260924.json at a5e7647 (card 044); the source was opened at fbedef0 and its sha256 matched before this was ruled.

## Disputed and withdrawn

None.

## Reading

None.

## Related

- [device laser_combiner](../wiki/device_laser_combiner.md)
- [device laser_shutter](../wiki/device_laser_shutter.md)
- [device line_select](../wiki/device_line_select.md)

---

Generated from the knowledge store at kbv-d027f44dadc0. Do not edit by hand: correct the store and regenerate.
