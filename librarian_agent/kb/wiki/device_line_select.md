# Device: line_select

Every entry in the store about the device line_select.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, element of channel laser_combiner, verbatim:

```json
{
  "id": "line_select",
  "entry_ref": "lunf_line_map_and_blanking_polarity",
  "unfilled_on_purpose": "lines, open_level and closed_level are LEFT ABSENT, and that is a guard, not a gap in the extraction. The confocal wrapper refuses without them, and filling them is what would let it open a laser line. The only map this store holds is the entry named here -- E3, the prior project's probe-script constants, corroborated by its live-dialog readout of 2026-09-02, with two of three device-database copies disagreeing about 405 -- and nothing on this bench has confirmed it. Fill these fields from a bench confirmation of each line, by eye, which supersedes the entry; not from the entry. Written 2026-09-24 by librarian-20260924-2 from microscope-20260924-3's findings (a5e7647)."
}
```

## Values

None.

## Claims

### [lunf_blanking_lines_reservable_right_after_nis_kill](../entries/lunf_blanking_lines_reservable_right_after_nis_kill.json)

On the microscope computer, within about 1.6 s of NIS-Elements being force-killed, all four of the laser combiner's blanking lines (Dev1/port0 lines 2, 4, 6 and 8) could be reserved from Python through NI-DAQmx, and level-0 writes to each returned without error. The writes were not read back and no light was produced, so what the lines actually did is not established.

Identifiers: none

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-009).

Conditions, verbatim:

> What the DAQ driver granted, recorded as run events: run-20260924-009's kill at events[7] (t 68.06 s), the lines reported ready at events[8] (t 69.69 s), level-0 writes to all four at events[9] with verification none, and a second close-all at events[12] in the recovery step. run-20260924-010 shows the same at events[7] to [9], 2.2 s after its kill. An observation by this system, not a registered observable's value: E1 from `measured:`, counted by check 85. WHAT IT ADDS. lunf_blanking_port_is_held_by_one_program says the vendor program holds this port exclusively WHILE IT RUNS; this says the port is free about a second and a half after that program is killed, observed here. lunf_fiber_shutter_survives_a_controller_kill implies the same freeing (a line driven from other software after a kill still emitted) in the prior project; this is the first direct observation of it on this instrument. Both stay as they are -- this is a different claim, not the same one re-observed, so it supersedes neither. WHAT IT DOES NOT ESTABLISH. Not the line map or the polarity (both still wait for a lit frame), and not lunf_killed_writer_may_leave_a_line_open: these writes set level 0 and were not read back, so nothing here tells whether a line's level survives its writer dying. Not a safety statement and not a limit: that the lines can be written after a kill says nothing about whether the beam is blocked, and the fiber shutter is not reached by these lines at all. Falsified by a reservation refused with NIS killed and no other program holding the port. Delivered as item blanking_lines_free_right_after_nis_kill of microscope_agent/findings/microscope-20260924-3-20260924.json at 0ecf94b.

### [lunf_blanking_port_is_held_by_one_program](../entries/lunf_blanking_port_is_held_by_one_program.json)

While the vendor acquisition program runs, it holds exclusively the DAQ port that carries the combiner's blanking lines, and the combiner's SPI interfaces. Another program asking for a blanking line is refused by the DAQ driver with error -200587 (lines reserved by another task). So the blanking lines and the per-line levels, which only the vendor program reaches, cannot be held by two programs at once.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/kb/decisions/2026-09-02-lunf-first-light).

Conditions, verbatim:

> Ruled TRANSFER, passed 10.3 rule 1 (E3, observed in another project on 2026-09-02). The error code is a driver identifier, not a measured figure. Slot: A4 (device exclusivity) and O1 preflight -- a session that finds the port reserved knows which program holds it. Falsified by a blanking line taken while the vendor program is running. Delivered as item `nis_holds_blanking_lines_exclusively` of microscope_agent/findings/microscope-20260924-3-20260924.json at a5e7647 (card 044); the source was opened at fbedef0 and its sha256 matched before this was ruled.

### [lunf_line_map_and_blanking_polarity](../entries/lunf_line_map_and_blanking_polarity.json)

The combiner's four lines are blanked on DAQ Dev1 port 0 as 405 nm on line2, 488 on line4, 561 on line6 and 640 on line8, with DAC indices 0 to 3 in the same order. Blanking is active-high: writing 1 opens a line and 0 closes it.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/config/lunf).

Conditions, verbatim:

> Ruled TRANSFER, passed 10.3 rules 1 and 3: the map and polarity are machine-readable constants in the prior project's probe script, and that project's record says the map was read off the vendor program's live configuration dialog on 2026-09-02, which outranked three device-database copies of which two put 405 on line1. Polarity was measured by eye that day, on 561 and 640. Slot: a contract field -- the device table's line_select element (lines, open_level, closed_level), which the confocal wrapper reads and refuses without; filling that element is a table edit and goes with the seat that publishes. THIS DECIDES WHICH LASER A COMMAND OPENS, so it is E3 about wiring nothing here has confirmed: confirm each line at the bench, by eye, before a plan relies on it, and that confirmation supersedes this entry. Falsified by any line emitting a different wavelength than mapped, or a line opening on 0. Rewiring the DAQ falsifies it silently. Delivered as item `combiner_line_map_and_polarity` of microscope_agent/findings/microscope-20260924-3-20260924.json at a5e7647 (card 044); the source was opened at fbedef0 and its sha256 matched before this was ruled.

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

- [device laser_combiner](../wiki/device_laser_combiner.md)
- [device laser_shutter](../wiki/device_laser_shutter.md)
- [device line_power](../wiki/device_line_power.md)

---

Generated from the knowledge store at kbv-d027f44dadc0. Do not edit by hand: correct the store and regenerate.
