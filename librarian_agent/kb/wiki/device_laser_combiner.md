# Device: laser_combiner

Every entry in the store about the device laser_combiner.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, channel, verbatim:

```json
{
  "id": "laser_combiner",
  "role": "confocal excitation, four lines",
  "driver": "lunf, split: blanking and line select over DAQ, per-line power over SPI",
  "driver_note": "The head token names the module and was `split:` until 2026-09-24, which named no file -- the router takes the text before the first comma or space. `lunf` because this store already calls the unit the LUN-F (serial_ports COM8, lunf_per_line_power_is_not_transmittable). The head is a name for the one wrapper over both halves; it says nothing about whether either half is driven -- the power half is deliberately not transmitted.",
  "automatable": "partial",
  "read_back": false,
  "lock_group": "illumination",
  "note": "not one device in the acquisition software: blanking and line select over DAQ, per-line power over SPI. Power is open loop; its output at full level is calibrated for three lines at three objectives (see line_power.calibrated_coverage).",
  "source": "traced in the prior project, driven partially + operator_read:kyuhwan_20260917",
  "grade": "E3",
  "elements": [
    {
      "id": "laser_shutter",
      "source": "operator_read:kyuhwan_20260917",
      "grade": "E3",
      "entry_ref": "laser_shutter_on_the_combiner",
      "note": "a shutter at the source, distinct from csuw1_shutter at the unit's entrance. This row records where it sits and what it gates. Which shutter an abort closes (2.1 interlock 1) is policy and is written by a person in envelope/safety.json -- the store cannot answer it and should not appear to."
    },
    {
      "id": "line_select",
      "entry_ref": "lunf_line_map_and_blanking_polarity",
      "unfilled_on_purpose": "lines, open_level and closed_level are LEFT ABSENT, and that is a guard, not a gap in the extraction. The confocal wrapper refuses without them, and filling them is what would let it open a laser line. The only map this store holds is the entry named here -- E3, the prior project's probe-script constants, corroborated by its live-dialog readout of 2026-09-02, with two of three device-database copies disagreeing about 405 -- and nothing on this bench has confirmed it. Fill these fields from a bench confirmation of each line, by eye, which supersedes the entry; not from the entry. Written 2026-09-24 by librarian-20260924-2 from microscope-20260924-3's findings (a5e7647)."
    },
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
  ],
  "confirmed_by": null,
  "confirmed_by_note": "bulk stamp removed at the channel level; see stamp_audit. The element laser_shutter keeps its stamp, because V5 of the pass did re-affirm that shutter.",
  "elements_note": "what the pass confirmed here is that a shutter exists at the source and what it gates -- not this channel's driver split, automation or read-back."
}
```

## Values

| quantity | value | unit | how it is known | grade and source as recorded | conditions | identifiers | subject | entry |
|---|---|---|---|---|---|---|---|---|
| illumination_power | 7.0 | mW | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-illumination-power-20260909 | illumination_level 1 1 | laser_line: 488 nm; level_percent: 100; light_source: confocal; nominal_magnification: 10x | device laser_combiner, quantity illumination_power | [confocal_power_at_sample_488nm_10x_full_level](../entries/confocal_power_at_sample_488nm_10x_full_level.json) |
| illumination_power | 6.9 | mW | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-illumination-power-20260909 | illumination_level 1 1 | laser_line: 488 nm; level_percent: 100; light_source: confocal; nominal_magnification: 20x | device laser_combiner, quantity illumination_power | [confocal_power_at_sample_488nm_20x_full_level](../entries/confocal_power_at_sample_488nm_20x_full_level.json) |
| illumination_power | 7.0 | mW | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-illumination-power-20260909 | illumination_level 1 1 | laser_line: 488 nm; level_percent: 100; light_source: confocal; nominal_magnification: 4x | device laser_combiner, quantity illumination_power | [confocal_power_at_sample_488nm_4x_full_level](../entries/confocal_power_at_sample_488nm_4x_full_level.json) |
| illumination_power | 6.7 | mW | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-illumination-power-20260909 | illumination_level 1 1 | laser_line: 561 nm; level_percent: 100; light_source: confocal; nominal_magnification: 10x | device laser_combiner, quantity illumination_power | [confocal_power_at_sample_561nm_10x_full_level](../entries/confocal_power_at_sample_561nm_10x_full_level.json) |
| illumination_power | 6.5 | mW | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-illumination-power-20260909 | illumination_level 1 1 | laser_line: 561 nm; level_percent: 100; light_source: confocal; nominal_magnification: 20x | device laser_combiner, quantity illumination_power | [confocal_power_at_sample_561nm_20x_full_level](../entries/confocal_power_at_sample_561nm_20x_full_level.json) |
| illumination_power | 6.9 | mW | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-illumination-power-20260909 | illumination_level 1 1 | laser_line: 561 nm; level_percent: 100; light_source: confocal; nominal_magnification: 4x | device laser_combiner, quantity illumination_power | [confocal_power_at_sample_561nm_4x_full_level](../entries/confocal_power_at_sample_561nm_4x_full_level.json) |
| illumination_power | 10.3 | mW | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-illumination-power-20260909 | illumination_level 1 1 | laser_line: 640 nm; level_percent: 100; light_source: confocal; nominal_magnification: 10x | device laser_combiner, quantity illumination_power | [confocal_power_at_sample_640nm_10x_full_level](../entries/confocal_power_at_sample_640nm_10x_full_level.json) |
| illumination_power | 9.9 | mW | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-illumination-power-20260909 | illumination_level 1 1 | laser_line: 640 nm; level_percent: 100; light_source: confocal; nominal_magnification: 20x | device laser_combiner, quantity illumination_power | [confocal_power_at_sample_640nm_20x_full_level](../entries/confocal_power_at_sample_640nm_20x_full_level.json) |
| illumination_power | 10.6 | mW | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-illumination-power-20260909 | illumination_level 1 1 | laser_line: 640 nm; level_percent: 100; light_source: confocal; nominal_magnification: 4x | device laser_combiner, quantity illumination_power | [confocal_power_at_sample_640nm_4x_full_level](../entries/confocal_power_at_sample_640nm_4x_full_level.json) |
| illumination_power | 7 | mW | computed; computed from other values | E4 · computed:power_scaled_by_objective_transmittance_band | illumination_level 1 1 | laser_line: 488 nm; level_percent: 100; light_source: confocal; nominal_magnification: 100x; part_number: MRD71970 | device laser_combiner, quantity illumination_power | [confocal_power_at_sample_488nm_100x_full_level_rough](../entries/confocal_power_at_sample_488nm_100x_full_level_rough.json) |
| illumination_power | 7 | mW | computed; computed from other values | E4 · computed:power_scaled_by_objective_transmittance_band | illumination_level 1 1 | laser_line: 488 nm; level_percent: 100; light_source: confocal; nominal_magnification: 40x; part_number: MRD77400 | device laser_combiner, quantity illumination_power | [confocal_power_at_sample_488nm_40x_full_level_rough](../entries/confocal_power_at_sample_488nm_40x_full_level_rough.json) |
| illumination_power | 7 | mW | computed; computed from other values | E4 · computed:power_scaled_by_objective_transmittance_band | illumination_level 1 1 | laser_line: 488 nm; level_percent: 100; light_source: confocal; nominal_magnification: 60x; part_number: MRD71670 | device laser_combiner, quantity illumination_power | [confocal_power_at_sample_488nm_60x_full_level_rough](../entries/confocal_power_at_sample_488nm_60x_full_level_rough.json) |
| illumination_power | 6 | mW | computed; computed from other values | E4 · computed:power_scaled_by_objective_transmittance_band | illumination_level 1 1 | laser_line: 561 nm; level_percent: 100; light_source: confocal; nominal_magnification: 100x; part_number: MRD71970 | device laser_combiner, quantity illumination_power | [confocal_power_at_sample_561nm_100x_full_level_rough](../entries/confocal_power_at_sample_561nm_100x_full_level_rough.json) |
| illumination_power | 6 | mW | computed; computed from other values | E4 · computed:power_scaled_by_objective_transmittance_band | illumination_level 1 1 | laser_line: 561 nm; level_percent: 100; light_source: confocal; nominal_magnification: 40x; part_number: MRD77400 | device laser_combiner, quantity illumination_power | [confocal_power_at_sample_561nm_40x_full_level_rough](../entries/confocal_power_at_sample_561nm_40x_full_level_rough.json) |
| illumination_power | 6 | mW | computed; computed from other values | E4 · computed:power_scaled_by_objective_transmittance_band | illumination_level 1 1 | laser_line: 561 nm; level_percent: 100; light_source: confocal; nominal_magnification: 60x; part_number: MRD71670 | device laser_combiner, quantity illumination_power | [confocal_power_at_sample_561nm_60x_full_level_rough](../entries/confocal_power_at_sample_561nm_60x_full_level_rough.json) |
| illumination_power | 10 | mW | computed; computed from other values | E4 · computed:power_scaled_by_objective_transmittance_band | illumination_level 1 1 | laser_line: 640 nm; level_percent: 100; light_source: confocal; nominal_magnification: 100x; part_number: MRD71970 | device laser_combiner, quantity illumination_power | [confocal_power_at_sample_640nm_100x_full_level_rough](../entries/confocal_power_at_sample_640nm_100x_full_level_rough.json) |
| illumination_power | 10 | mW | computed; computed from other values | E4 · computed:power_scaled_by_objective_transmittance_band | illumination_level 1 1 | laser_line: 640 nm; level_percent: 100; light_source: confocal; nominal_magnification: 40x; part_number: MRD77400 | device laser_combiner, quantity illumination_power | [confocal_power_at_sample_640nm_40x_full_level_rough](../entries/confocal_power_at_sample_640nm_40x_full_level_rough.json) |
| illumination_power | 10 | mW | computed; computed from other values | E4 · computed:power_scaled_by_objective_transmittance_band | illumination_level 1 1 | laser_line: 640 nm; level_percent: 100; light_source: confocal; nominal_magnification: 60x; part_number: MRD71670 | device laser_combiner, quantity illumination_power | [confocal_power_at_sample_640nm_60x_full_level_rough](../entries/confocal_power_at_sample_640nm_60x_full_level_rough.json) |

## Claims

### [lunf_blanking_lines_reservable_right_after_nis_kill](../entries/lunf_blanking_lines_reservable_right_after_nis_kill.json)

On the microscope computer, within about 1.6 s of NIS-Elements being force-killed, all four of the laser combiner's blanking lines (Dev1/port0 lines 2, 4, 6 and 8) could be reserved from Python through NI-DAQmx, and level-0 writes to each returned without error. The writes were not read back and no light was produced, so what the lines actually did is not established.

Identifiers: none

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-009).

Conditions, verbatim:

> What the DAQ driver granted, recorded as run events: run-20260924-009's kill at events[7] (t 68.06 s), the lines reported ready at events[8] (t 69.69 s), level-0 writes to all four at events[9] with verification none, and a second close-all at events[12] in the recovery step. run-20260924-010 shows the same at events[7] to [9], 2.2 s after its kill. An observation by this system, not a registered observable's value: E1 from `measured:`, counted by check 85. WHAT IT ADDS. lunf_blanking_port_is_held_by_one_program says the vendor program holds this port exclusively WHILE IT RUNS; this says the port is free about a second and a half after that program is killed, observed here. lunf_fiber_shutter_survives_a_controller_kill implies the same freeing (a line driven from other software after a kill still emitted) in the prior project; this is the first direct observation of it on this instrument. Both stay as they are -- this is a different claim, not the same one re-observed, so it supersedes neither. WHAT IT DOES NOT ESTABLISH. Not the line map or the polarity (both still wait for a lit frame), and not lunf_killed_writer_may_leave_a_line_open: these writes set level 0 and were not read back, so nothing here tells whether a line's level survives its writer dying. Not a safety statement and not a limit: that the lines can be written after a kill says nothing about whether the beam is blocked, and the fiber shutter is not reached by these lines at all. Falsified by a reservation refused with NIS killed and no other program holding the port. Delivered as item blanking_lines_free_right_after_nis_kill of microscope_agent/findings/microscope-20260924-3-20260924.json at 0ecf94b.

### [confocal_488_excites_the_red_arm](../entries/confocal_488_excites_the_red_arm.json)

On the confocal path, 488 nm excitation produced signal in the red camera arm about as strongly as 561 nm did, and the red arm's signal was additive across the two lines. So assigning species on the red arm requires the lines to be strobed, not run together.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/kb/decisions/2026-09-02-lunf-first-light).

Conditions, verbatim:

> Ruled TRANSFER, passed 10.3 rules 1 and 3: the finding crosses, its contrast figures and additivity sum do not. Measured in another project on 2026-09-07 at 20x on its own sample, so the strength of the leak belongs to that sample's dye; this is an E3 fact about the path, not about any tracer here. Slot: A1 (background) and A4 (whether two lines may run at once for a two-colour plan). Falsified by a two-line confocal frame on the red arm with no 488 contribution. Delivered as item `confocal_488_leaks_into_red_arm` of microscope_agent/findings/microscope-20260924-3-20260924.json at a5e7647 (card 044); the source was opened at fbedef0 and its sha256 matched before this was ruled.

### [laser_shutter_on_the_combiner](../entries/laser_shutter_on_the_combiner.json)

A second shutter exists on the laser combiner, distinct from the shutter inside the confocal unit. Two shutters sit in the confocal excitation chain: one at the source and one at the unit's entrance.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260917).

Conditions, verbatim:

> This instrument as configured on 2026-09-17, operator read at the instrument. The store records that both exist and where each sits; it does not record which one anything closes, because that is policy written by a person in envelope/safety.json (4.3.2). Falsified by either shutter being removed or re-sited.

### [lunf_analog_outputs_are_not_cabled_to_the_combiner](../entries/lunf_analog_outputs_are_not_cabled_to_the_combiner.json)

The DAQ's four analog outputs are not cabled to the combiner's power inputs. Driving them, together and one at a time, stepped and at speed, with the blanking line held open, changed nothing in the emitted light.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/kb/decisions/2026-09-02-lunf-first-light).

Conditions, verbatim:

> Ruled TRANSFER, passed 10.3 rule 1 (E3, tested in another project on 2026-09-02). A negative result carried so the route is not proposed again. Slot: A4 (automatability of line_power) -- it removes one candidate path and adds none. The drive voltages of the test are in prose and are not carried (10.3 rule 3). Falsified by an analog output that modulates a line, which would also mean the cabling changed. Delivered as item `combiner_ao_route_not_cabled` of microscope_agent/findings/microscope-20260924-3-20260924.json at a5e7647 (card 044); the source was opened at fbedef0 and its sha256 matched before this was ruled.

### [lunf_blanking_port_is_held_by_one_program](../entries/lunf_blanking_port_is_held_by_one_program.json)

While the vendor acquisition program runs, it holds exclusively the DAQ port that carries the combiner's blanking lines, and the combiner's SPI interfaces. Another program asking for a blanking line is refused by the DAQ driver with error -200587 (lines reserved by another task). So the blanking lines and the per-line levels, which only the vendor program reaches, cannot be held by two programs at once.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/kb/decisions/2026-09-02-lunf-first-light).

Conditions, verbatim:

> Ruled TRANSFER, passed 10.3 rule 1 (E3, observed in another project on 2026-09-02). The error code is a driver identifier, not a measured figure. Slot: A4 (device exclusivity) and O1 preflight -- a session that finds the port reserved knows which program holds it. Falsified by a blanking line taken while the vendor program is running. Delivered as item `nis_holds_blanking_lines_exclusively` of microscope_agent/findings/microscope-20260924-3-20260924.json at a5e7647 (card 044); the source was opened at fbedef0 and its sha256 matched before this was ruled.

### [lunf_fiber_shutter_survives_a_controller_kill](../entries/lunf_fiber_shutter_survives_a_controller_kill.json)

The laser combiner's fiber shutter stays open when the vendor acquisition program that opened it is force-killed: only that program's clean shutdown closes it, and the combiner has no watchdog that shuts the fiber when its controlling link drops. After a kill, a line driven from other software still emitted.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/kb/decisions/2026-09-02-lunf-first-light).

Conditions, verbatim:

> Ruled TRANSFER under 10.2.1, passed 10.3 rule 1 (E3: measured in another project on 2026-09-02, by a force-kill followed by a line driven from Python, on that project's second attempt -- the first attempt killed nothing and its conclusion was withdrawn in the record's own corrections). Slot: the orchestrator's abort path and O1 preflight -- a controller that dies does not close this shutter, so nothing may count a dead controller as a closed beam. A control-path fact and not a limit; which shutter an abort closes stays policy, in envelope/safety.json. Falsified by a kill after which the fiber is found closed. Delivered as item `fiber_shutter_survives_controller_kill` of microscope_agent/findings/microscope-20260924-3-20260924.json at a5e7647 (card 044); the source was opened at fbedef0 and its sha256 matched before this was ruled.

### [lunf_line_map_and_blanking_polarity](../entries/lunf_line_map_and_blanking_polarity.json)

The combiner's four lines are blanked on DAQ Dev1 port 0 as 405 nm on line2, 488 on line4, 561 on line6 and 640 on line8, with DAC indices 0 to 3 in the same order. Blanking is active-high: writing 1 opens a line and 0 closes it.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/config/lunf).

Conditions, verbatim:

> Ruled TRANSFER, passed 10.3 rules 1 and 3: the map and polarity are machine-readable constants in the prior project's probe script, and that project's record says the map was read off the vendor program's live configuration dialog on 2026-09-02, which outranked three device-database copies of which two put 405 on line1. Polarity was measured by eye that day, on 561 and 640. Slot: a contract field -- the device table's line_select element (lines, open_level, closed_level), which the confocal wrapper reads and refuses without; filling that element is a table edit and goes with the seat that publishes. THIS DECIDES WHICH LASER A COMMAND OPENS, so it is E3 about wiring nothing here has confirmed: confirm each line at the bench, by eye, before a plan relies on it, and that confirmation supersedes this entry. Falsified by any line emitting a different wavelength than mapped, or a line opening on 0. Rewiring the DAQ falsifies it silently. Delivered as item `combiner_line_map_and_polarity` of microscope_agent/findings/microscope-20260924-3-20260924.json at a5e7647 (card 044); the source was opened at fbedef0 and its sha256 matched before this was ruled.

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

### [prior_mm_config_declares_lunf_blanking](../entries/prior_mm_config_declares_lunf_blanking.json)

The prior project's Micro-Manager configuration dualcam_noDMD.cfg declares the combiner's blanking lines as a Micro-Manager device, LUNF-Blanking, an NIDAQ digital-output device on Dev1 port 0 under an NIDAQHub. A session that loads a configuration carrying that declaration has a route to switch a confocal laser line that does not pass through any wrapper written here.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/config/micromanager/dualcam_noDMD.cfg).

Conditions, verbatim:

> Ruled TRANSFER, passed 10.3 rule 1 (E3, a fact about one file at fbedef0). Configurations from that folder are loaded here by path (plan.md 10.2.1), which is why a device declaration inside one is a control-path fact about this instrument's sessions. Slot: O1 preflight -- a loaded configuration can be checked for this device before light. What this repository's code refuses today is not in this entry: that is code state, owned by the microscope and changed by a commit. Falsified for a given configuration by reading it. Delivered as item `mm_second_route_to_blanking` of microscope_agent/findings/microscope-20260924-3-20260924.json at a5e7647 (card 044); the source was opened at fbedef0 and its sha256 matched before this was ruled.

### [single_cam_red_config_can_switch_confocal_lines](../entries/single_cam_red_config_can_switch_confocal_lines.json)

The configuration single_cam_red_noDMD_nocom10.cfg declares the confocal combiner's blanking lines as the Micro-Manager device LUNF-Blanking and defines a LaserLine group whose presets 405, 488, 561 and 640 each set one blanking line to 1 -- line2, line4, line6 and line8 respectively -- and whose AllOff preset sets all four to 0. So a session that loads it can switch a confocal laser line with an ordinary Micro-Manager group call.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/config/micromanager/single_cam_red_noDMD_nocom10.cfg).

Conditions, verbatim:

> A fact about one file: agentic-microscope at fbedef0, config/micromanager/single_cam_red_noDMD_nocom10.cfg, sha256 8184073e31e1a7a63731932a20a622131d4dba04cf839bc9e651bf9abcd53120, lines 90, 103-105, 124 and 218-238, read by this seat. That hash is the one run-20260924-002 recorded for the configuration it loaded (event 8), and that run lists LUNF-Blanking among the loaded devices. E3: a configuration written in another project. The group's line map agrees with lunf_line_map_and_blanking_polarity (405 on line2, 488 on line4, 561 on line6, 640 on line8, 1 opens), which makes two prior records agreeing and still nothing confirmed on this bench. Slot: O1 preflight -- a loaded configuration offers this route before any wrapper written here is involved; whether the microscope's code refuses the group is code state and is not in this entry. Found while checking microscope-20260924-1's findings (bf8f91f); not an item of that file.

### [lunf_killed_writer_may_leave_a_line_open](../entries/lunf_killed_writer_may_leave_a_line_open.json)

If a program that opened a combiner blanking line is killed rather than closed, that line may stay open, with the fiber shutter also open. Unmeasured: this is an inference from two prior observations -- a blanking line kept its level after the task that wrote it was cleared (a blink that created and cleared a task per write still blinked), and the fiber shutter survives a kill -- and whether a line's level survives the writing process dying has not been tested.

Identifiers: none

How it is known: recalled or assumed; an assumption (E5 · assumed:inference_from_prior_lunf_blink_and_shutter_kill).

Conditions, verbatim:

> Ruled DOWNGRADE under 10.2.1: an assertion with no measurement of its own enters at E5 with a falsifier. FALSIFIER: kill the driving process with one line open, and see that line go dark by itself. Slot: O1 preflight and the orchestrator's abort path -- until falsified, a crashed controller is treated as possibly leaving a beam on. The microscope seat's version also said which barriers this repository's code can and cannot reach; that is code state and stays in the microscope's live checklist, not here. Rests on lunf_fiber_shutter_survives_a_controller_kill. Delivered as item `killed_process_can_leave_a_line_unblanked` of microscope_agent/findings/microscope-20260924-3-20260924.json at a5e7647 (card 044); the source was opened at fbedef0 and its sha256 matched before this was ruled.

## Disputed and withdrawn

None.

## Reading

None.

## Related

- [device camera_red](../wiki/device_camera_red.md)
- [device confocal_csuw1](../wiki/device_confocal_csuw1.md)
- [device laser_shutter](../wiki/device_laser_shutter.md)
- [device line_power](../wiki/device_line_power.md)
- [device line_select](../wiki/device_line_select.md)
- [quantity illumination_power](../wiki/quantity_illumination_power.md)
- [safety guide](../guides/safety_laser_combiner.md)

---

Generated from the knowledge store at kbv-d027f44dadc0. Do not edit by hand: correct the store and regenerate.
