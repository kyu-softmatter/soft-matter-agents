# Device: csuw1_disk_speed

Every entry in the store about the device csuw1_disk_speed.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, element of channel confocal_csuw1, verbatim:

```json
{
  "id": "csuw1_disk_speed",
  "source": "operator_read:kyuhwan_20260917",
  "grade": "E3",
  "entry_ref": "csuw1_disk_speed_exposure_constraint",
  "note": "exposure must be an integer multiple of the disk period or stripes remain (axis A1); nothing acquires while the disk is still spinning up. The period itself is not in the store."
}
```

## Values

None.

## Claims

### [csuw1_disk_speed_is_not_exposed_here](../entries/csuw1_disk_speed_is_not_exposed_here.json)

Loaded through Micro-Manager on the microscope computer, the CSU-W1's seven devices (Hub, Shutter, Bright Field, Port, Dichroic and both filter wheels) expose no property that reports the spinning disk's speed. The only Speed properties are the two filter wheels', which is wheel speed.

Identifiers: configuration: dualcam_noDMD_nolaser_nostartup.cfg; micromanager: Micro-Manager 2.0.3 20260806, MMCore 12.5.0, Device API 75

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-008).

Conditions, verbatim:

> A device's report of itself: run-20260924-008 events[4] to [10] list every property of each CSU-W1 device as read back, and none names the disk's speed or period; events[9] and [10] carry Speed 3 on Filter_Red and Filter_Blue, which is the filter wheels'. E1 from `measured:` under 11-21 condition 4, counted by check 85. Checked here against the property lists themselves, not only the run's own disk_related_properties filter. SCOPE: this configuration (derived dual-camera, no DMD, no laser, no startup preset) and this Micro-Manager build, as named in identifiers. A different device adapter could expose the speed and would falsify this for that adapter. SAME FINDING, DIFFERENT CONDITIONS, SO NOT A SUPERSEDE. csuw1_disk_speed_is_not_exposed_in_micromanager says the same of the prior project's configurations as of 2026-09-07, at E3. That entry's scope is those configurations and that adapter version, which this does not re-observe, so it stays valid for its own scope and this is its own entry. Together they say the disk period has no source through Micro-Manager in either; the disk_period gap stays open. Delivered as item csuw1_reports_no_disk_speed_here of microscope_agent/findings/microscope-20260924-3-20260924.json at 0ecf94b.

### [csuw1_disk_speed_exposure_constraint](../entries/csuw1_disk_speed_exposure_constraint.json)

An exposure taken through the spinning disk must last an integer multiple of the disk period, or stripes remain in the image, and nothing may be acquired while the disk is still spinning up to speed.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260917).

Conditions, verbatim:

> This instrument as configured on 2026-09-17, operator read at the instrument. The disk period itself is not in the store: this entry states the relation the exposure must satisfy, not the number it must be a multiple of, and a plan needs the period from the device before it can apply this. Falsified by a disk or controller change.

### [csuw1_disk_speed_is_not_exposed_in_micromanager](../entries/csuw1_disk_speed_is_not_exposed_in_micromanager.json)

In the prior project's Micro-Manager configurations, the spinning-disk unit is reached as Hub, Filter_Red, Filter_Blue, Dichroic, Shutter, Bright Field and Port. No device there reports or sets the disk's rotation, so the disk period cannot be read from Micro-Manager with those configurations.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/kb/decisions/2026-09-02-lunf-first-light).

Conditions, verbatim:

> Ruled TRANSFER, passed 10.3 rule 1 (E3, the device list of that project's configurations as of 2026-09-07). Slot: A1 -- csuw1_disk_speed_exposure_constraint requires an exposure to be an integer multiple of the disk period, and this says no device supplies the period through that route; it bears directly on the `disk_period` gap, asked for from three questions. Scope: those configurations and that adapter version. A different device adapter or configuration could expose the speed, and would falsify this for that configuration. Delivered as item `mm_exposes_no_disk_speed` of microscope_agent/findings/microscope-20260924-3-20260924.json at a5e7647 (card 044); the source was opened at fbedef0 and its sha256 matched before this was ruled.

### [stopped_disk_frame_looks_bright](../entries/stopped_disk_frame_looks_bright.json)

A confocal frame taken with the spinning disk stopped is a stationary pinhole grid at full brightness, so brightness and contrast look normal and nothing seems wrong. The texture gives it away: on the difference of a lit and an unlit frame, the largest off-centre term of the power spectrum over its median is orders of magnitude higher with a stationary grid than with smooth illumination, and a frame with no signal stays low.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/kb/decisions/2026-09-02-lunf-first-light).

Conditions, verbatim:

> Ruled TRANSFER, passed 10.3 rules 1 and 3: the observation and the method cross; the ratios, the grid period and the prior thresholds do not, because they sit in prose and a markdown table and because nobody here chose the thresholds (the microscope seat ruled them discard). Measured in another project on 2026-09-07 at 20x through both camera arms. Slot: A1 (artefacts) and O1 preflight -- the microscope already carries the method in its live checklist. Falsified by a stopped-disk frame whose spectrum is indistinguishable from a spinning one. Delivered as item `stopped_disk_looks_bright` of microscope_agent/findings/microscope-20260924-3-20260924.json at a5e7647 (card 044); the source was opened at fbedef0 and its sha256 matched before this was ruled.

## Disputed and withdrawn

None.

## Reading

None.

## Related

- [device confocal_csuw1](../wiki/device_confocal_csuw1.md)

---

Generated from the knowledge store at kbv-058ce14eea72. Do not edit by hand: correct the store and regenerate.
