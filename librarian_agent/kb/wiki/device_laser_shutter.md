# Device: laser_shutter

Every entry in the store about the device laser_shutter.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, element of channel laser_combiner, verbatim:

```json
{
  "id": "laser_shutter",
  "source": "operator_read:kyuhwan_20260917",
  "grade": "E3",
  "entry_ref": "laser_shutter_on_the_combiner",
  "note": "a shutter at the source, distinct from csuw1_shutter at the unit's entrance. This row records where it sits and what it gates. Which shutter an abort closes (2.1 interlock 1) is policy and is written by a person in envelope/safety.json -- the store cannot answer it and should not appear to."
}
```

## Values

None.

## Claims

### [laser_shutter_on_the_combiner](../entries/laser_shutter_on_the_combiner.json)

A second shutter exists on the laser combiner, distinct from the shutter inside the confocal unit. Two shutters sit in the confocal excitation chain: one at the source and one at the unit's entrance.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260917).

Conditions, verbatim:

> This instrument as configured on 2026-09-17, operator read at the instrument. The store records that both exist and where each sits; it does not record which one anything closes, because that is policy written by a person in envelope/safety.json (4.3.2). Falsified by either shutter being removed or re-sited.

### [lunf_fiber_shutter_survives_a_controller_kill](../entries/lunf_fiber_shutter_survives_a_controller_kill.json)

The laser combiner's fiber shutter stays open when the vendor acquisition program that opened it is force-killed: only that program's clean shutdown closes it, and the combiner has no watchdog that shuts the fiber when its controlling link drops. After a kill, a line driven from other software still emitted.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/kb/decisions/2026-09-02-lunf-first-light).

Conditions, verbatim:

> Ruled TRANSFER under 10.2.1, passed 10.3 rule 1 (E3: measured in another project on 2026-09-02, by a force-kill followed by a line driven from Python, on that project's second attempt -- the first attempt killed nothing and its conclusion was withdrawn in the record's own corrections). Slot: the orchestrator's abort path and O1 preflight -- a controller that dies does not close this shutter, so nothing may count a dead controller as a closed beam. A control-path fact and not a limit; which shutter an abort closes stays policy, in envelope/safety.json. Falsified by a kill after which the fiber is found closed. Delivered as item `fiber_shutter_survives_controller_kill` of microscope_agent/findings/microscope-20260924-3-20260924.json at a5e7647 (card 044); the source was opened at fbedef0 and its sha256 matched before this was ruled.

### [lunf_reports_nothing_back](../entries/lunf_reports_nothing_back.json)

Nothing about the laser combiner can be read back. Its DAC is write-only; reading back a blanking line returns the writer's own output, not the shutter's state; no combiner monitor signal is wired to any of the DAQ's analog inputs, which float; and the vendor library exports no shutter or status entry point.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/kb/decisions/2026-09-02-lunf-first-light).

Conditions, verbatim:

> Ruled TRANSFER, passed 10.3 rule 1 (E3, checked in another project on 2026-09-02). It is the evidence behind the device table's read_back false on laser_combiner, stated out loud the way tweez300_reports_nothing_back states it for the trap. The echo point matters most: a digital-output read-back looks like confirmation and is not. The floating-input voltages are prose and are not carried. Slot: A4 (read-back availability) and the orchestrator's verify step, which cannot verify this device. Falsified by any read path that reports a state the software did not write. Delivered as item `combiner_reports_nothing_back` of microscope_agent/findings/microscope-20260924-3-20260924.json at a5e7647 (card 044); the source was opened at fbedef0 and its sha256 matched before this was ruled.

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

- [device laser_combiner](../wiki/device_laser_combiner.md)
- [device line_power](../wiki/device_line_power.md)
- [device line_select](../wiki/device_line_select.md)

---

Generated from the knowledge store at kbv-d027f44dadc0. Do not edit by hand: correct the store and regenerate.
