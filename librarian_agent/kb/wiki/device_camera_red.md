# Device: camera_red

Every entry in the store about the device camera_red.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, channel, verbatim:

```json
{
  "id": "camera_red",
  "mm_label": {
    "label": "Kinetix_red",
    "entry_ref": "kinetix_red_label_opens_serial_a24m723015",
    "config_sha256": "8184073e31e1a7a63731932a20a622131d4dba04cf839bc9e651bf9abcd53120"
  },
  "role": "detector on one arm of the spectral port. Named for the arm it sits on, not for a hardware difference.",
  "model": "Kinetix 22",
  "driver": "micromanager_pvcam",
  "automatable": "full",
  "read_back": true,
  "lock_group": "camera_red",
  "exclusive_with": [
    "optical_tweezers_gui"
  ],
  "exclusive_reason": "the driver hands a camera to one process at a time, and the tweezers GUI opens the same body. Whoever opens first locks the other out, in both directions.",
  "source": "mm_config, confirmed there by loading it",
  "grade": "E3",
  "confirmed_by": "operator_read:kyuhwan_20260917",
  "entry_ref": "cameras_both_kinetix22"
}
```

## Values

| quantity | value | unit | how it is known | grade and source as recorded | conditions | identifiers | subject | entry |
|---|---|---|---|---|---|---|---|---|
| quantum_efficiency | 0.95 | 1 | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Kinetix22 | none stated | model: Kinetix 22 | device camera_red | [camera_qe_peak](../entries/camera_qe_peak.json) |
| read_noise | 1.6 | e | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Kinetix22 | none stated | bit_depth_designation: 16-bit; camera_mode: DynamicRange; model: Kinetix 22 | device camera_red | [camera_read_noise_dynamicrange](../entries/camera_read_noise_dynamicrange.json) |
| read_noise | 1.2 | e | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Kinetix22 | none stated | bit_depth_designation: 12-bit; camera_mode: Sensitivity; model: Kinetix 22 | device camera_red | [camera_read_noise_sensitivity](../entries/camera_read_noise_sensitivity.json) |
| read_noise | 2.0 | e | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Kinetix22 | none stated | bit_depth_designation: 8-bit; camera_mode: Speed; model: Kinetix 22 | device camera_red | [camera_read_noise_speed](../entries/camera_read_noise_speed.json) |
| read_noise | 0.7 | e | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Kinetix22 | none stated | bit_depth_designation: 16-bit, 8x CMS; camera_mode: SubElectron; model: Kinetix 22 | device camera_red | [camera_read_noise_subelectron](../entries/camera_read_noise_subelectron.json) |
| sensor_pixels_x | 2400 | count | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Kinetix22 | none stated | chip: GPixel GSense GSENSE6510 CMOS; model: Kinetix 22 | device camera_red | [camera_sensor_geometry](../entries/camera_sensor_geometry.json) |
| sensor_pixels_y | 2400 | count | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Kinetix22 | none stated | chip: GPixel GSense GSENSE6510 CMOS; model: Kinetix 22 | device camera_red | [camera_sensor_geometry](../entries/camera_sensor_geometry.json) |
| pixel_size | 6.5 | um | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Kinetix22 | none stated | chip: GPixel GSense GSENSE6510 CMOS; model: Kinetix 22 | device camera_red | [camera_sensor_geometry](../entries/camera_sensor_geometry.json) |
| quantum_efficiency | 0.96 | 1 | from a document, a reading off the instrument, or another project's record; another project's record | E3 · prior_run:agentic-microscope@34a432c | wavelength 600.0 nm | model: Kinetix 22 | device camera_red | [camera_qe_at_600nm_from_the_kinetix_graph](../entries/camera_qe_at_600nm_from_the_kinetix_graph.json) |
| full_scale_count | 65535 | ADU | recalled or assumed; the person's recollection | E5 · operator_recall:kyuhwan_20261013_cameras_read_the_same | none stated | binning: 1x1; model: Kinetix 22; port: Dynamic Range; readout_rate: 100MHz 16bit | device camera_red, device camera_blue, quantity full_scale_count | [kinetix22_both_bodies_saturate_alike_per_the_person](../entries/kinetix22_both_bodies_saturate_alike_per_the_person.json) |

## Claims

### [kinetix_red_adapter_properties_as_reported_20260924](../entries/kinetix_red_adapter_properties_as_reported_20260924.json)

At load, the PVCAM adapter describes Kinetix_red as BitDepth 16, PixelType 16bit, ReadoutRate '100MHz 16bit' and Binning 1x1. These are the adapter's self-descriptions and not a measurement of the camera's bit depth.

Identifiers: none

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-002).

Conditions, verbatim:

> Read back in a preparatory run -- the first real acquisition on this computer, with no plan, the person having placed the 20x and moved the microscope by hand, software moving nothing. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system: E1 from `measured:`. Not a value of any registered observable. IT DISAGREES WITH pixeltype_misreports_bit_depth, the prior project's record that PixelType reported 12bit while the data were 16-bit: here PixelType reports 16bit. Kept side by side and not reconciled (rule 7). The readout mode, adapter version or camera settings may differ between the two, and neither record is a measurement of bit depth -- which remains a gap here, because no frame today saturated. Slot: A1 and the acquisition wrapper, which must not take a bit depth from either property. Delivered as item kinetix_red_reported_properties of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042). Checked by this seat against microscope_agent/runs/run-20260924-002/log.json read at bf8f91f (unchanged since): event 18.

### [kinetix_red_exposure_and_binning_read_back_exactly](../entries/kinetix_red_exposure_and_binning_read_back_exactly.json)

On Kinetix_red, exposure written as 100 ms read back as 100.0 and 500 ms as 500.0, and binning written as 1x1 read back as 1x1.

Identifiers: none

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-002).

Conditions, verbatim:

> Read back in a preparatory run -- the first real acquisition on this computer, with no plan, the person having placed the 20x and moved the microscope by hand, software moving nothing. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system: E1 from `measured:`. Not a value of any registered observable. Two exposures and one binning, read back after writing: a write-verify path that works for these settings, not a timing measurement -- whether the sensor actually integrates for that long is a different question. Slot: the acquisition wrapper's verify step. Delivered as item kinetix_red_exposure_and_binning_readback of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042). Checked by this seat against microscope_agent/runs/run-20260924-002/log.json read at bf8f91f (unchanged since): event 20, 43 and 19.

### [kinetix_red_label_opens_serial_a24m723015](../entries/kinetix_red_label_opens_serial_a24m723015.json)

With the configuration single_cam_red_noDMD_nocom10.cfg loaded, the camera opened as Micro-Manager label Kinetix_red reports serial number A24M723015, chip TMP-Kinetix, firmware 30.48. That is the serial camera_bodies_are_told_apart_by_serial gives for the red arm, so in this configuration the label Kinetix_red opens the red-arm body.

Identifiers: mm_config_sha256: 8184073e31e1a7a63731932a20a622131d4dba04cf839bc9e651bf9abcd53120; mm_label: Kinetix_red; model: Kinetix 22; serial: A24M723015

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-002).

Conditions, verbatim:

> Read back in a preparatory run -- the first real acquisition on this computer, with no plan, the person having placed the 20x and moved the microscope by hand, software moving nothing. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system: E1 from `measured:`. Not a value of any registered observable. The comparison with the stored serial is this seat's, from two records: the serial here is E1, the red-arm assignment it is compared with is E3 from the prior project, so the conclusion 'this label opens the red-arm body' is only as good as the E3 half. A frame on each arm with the other dark would settle the assignment here. A different configuration may map labels to bodies differently. Delivered as item kinetix_red_serial_a24m723015 of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042). Checked by this seat against microscope_agent/runs/run-20260924-002/log.json read at bf8f91f (unchanged since): event 40 (serial) and 18 (firmware). The identifiers mm_label and mm_config_sha256 were added on 2026-10-27 by librarian-20261007-1 for librarian card 061, from this same run's log, which card 080 moved to microscope_runtime/runs/run-20260924-002/log.json (read at fb5eff40): event 8, configuration_loaded, single_cam_red_noDMD_nocom10.cfg with sha256 and sha256_after_load both 8184073e31e1a7a63731932a20a622131d4dba04cf839bc9e651bf9abcd53120, the run's one configuration load; events 19 to 53 apply to and acquire from the channel Kinetix_red, and event 40 records the serial. The digest is the run's record of which file was loaded, not a hash of any file on disk. The claim is unchanged.

### [kinetix_red_paced_snaps_kept_one_per_second_20260924](../entries/kinetix_red_paced_snaps_kept_one_per_second_20260924.json)

On 2026-09-24, single snaps on Kinetix_red scheduled at one per second from an integer frame index -- 100 ms exposure, the full 2400 by 2400 frame saved to disk each time, the Aura on throughout -- all ran: 300 of 300 frames, none starting more than 50 ms late, the latest 16 ms late.

Identifiers: none

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-006).

Conditions, verbatim:

> Read back in a preparatory run, a device-and-host report of its own timing rather than a value of any registered observable, so it may enter citing the run (11-21 condition 4 as narrowed at 20a688b); E1 from `measured:`. Checked against microscope_agent/runs/run-20260924-006/log.json read at ac20ee4, event 42: wanted 300, received 300, frames_late_over_50ms 0, worst_late_s 0.016. The findings item also gives the period's median and range; those come from a timing file outside the repository (D:/soft-matter-agents-frames/run-20260924-006/particles_paced_timing.json), which is not committed and so not checkable here, and are not entered. Snaps carry no ImageNumber, so the frame count is the loop's integer index, as the log says. One series, one exposure, one frame size, host-timed: evidence that this rate is kept at this size, not a timing guarantee. Delivered as item paced_snaps_one_per_second_on_time of microscope_agent/findings/microscope-20260924-1-20260924.json at ac20ee4 (card 042).

### [kinetix_red_sequences_delivered_every_frame_20260924](../entries/kinetix_red_sequences_delivered_every_frame_20260924.json)

Two sequence acquisitions on Kinetix_red on 2026-09-24 -- 20 dark frames and 600 frames of particles, at 100 ms, 2400 by 2400 uint16 -- delivered every frame, with contiguous ImageNumber from first to last and no circular-buffer overflow.

Identifiers: none

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-002).

Conditions, verbatim:

> Read back in a preparatory run -- the first real acquisition on this computer, with no plan, the person having placed the 20x and moved the microscope by hand, software moving nothing. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system: E1 from `measured:`. Not a value of any registered observable. The check is ImageNumber, because dropped_frames_raise_nothing says a drop raises no error and appears only as a gap in that sequence. Two sequences on one day, at one exposure and one frame size, with the frames streamed to disk: evidence that this configuration can keep up at that rate, not that it always will. Slot: A2 and A5. Delivered as item kinetix_red_sequence_no_dropped_frames of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042). Checked by this seat against microscope_agent/runs/run-20260924-002/log.json read at bf8f91f (unchanged since): event 32 and 53.

### [camera_bodies_are_told_apart_by_serial](../entries/camera_bodies_are_told_apart_by_serial.json)

The two camera bodies are distinguished by serial number rather than by label: A23H723003 is the blue arm and A24M723015 is the red arm.

Identifiers: model: Kinetix 22; serial: A23H723003

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@safety-2026-09-03).

Conditions, verbatim:

> Ruled TRANSFER under 10.2.1 and passed 10.3 rule 1, so it caps at E3 -- a run taken in another project is not a run taken here. 10.2's hardware-control-path row is open and says in its own rule that it does not wait for envelope/, because wrapping a control path needs no safety limit. Slot: O1 preflight, which has to know which body it opened. The labels are the thing not to trust: this store already records that the two bodies are the same model, so nothing about a frame distinguishes them, and it already records one instance of this instrument's paper record diverging from its hardware. A serial is addressable, so either number now finds this entry.

### [camera_red_mm_control_path](../entries/camera_red_mm_control_path.json)

On the prior project's configuration the red Kinetix is the MMCore device label `Kinetix_red`, mapped to the PVCAM camera `Camera-2`. Binning is reached as a device property named `Binning`; exposure and ROI are not device properties at all but core-level calls, setExposure and setROI.

Identifiers: mm_label: Kinetix_red; model: Kinetix 22

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@34a432c).

Conditions, verbatim:

> THE ASK PRESUMED THREE PROPERTY NAMES AND THERE IS ONE. `Binning` is a device property -- `core.getProperty(cam, "Binning")` and `core.setProperty(cam, "Binning", value)` both appear as call sites. Exposure and ROI are reached through the CORE, `core.setExposure(ms)` and `core.setROI(x, y, w, h)`, so they are not names a plan can compare against getLoadedDevices() or getDevicePropertyNames() and a preflight that looks for them there will not find them. That is a fact about the MMCore interface and not about this stand, but it is the answer to what was asked. THE PVCAM MAPPING IS NOT COSMETIC: `Kinetix_blue` is `Camera-1` and `Kinetix_red` is `Camera-2`, from a dict constant, and the two cameras are the same model, so the mapping is the only thing telling them apart in the library. WHAT WOULD RAISE IT: running getLoadedDevices() on this stand. The label is whatever a person loaded, and a configuration read elsewhere is E3 by 10.3 rule 1 for exactly that reason. Slot: a KB entry and the device registry's camera_red row. Rule passed: 10.3 rule 1.

### [cameras_both_kinetix22](../entries/cameras_both_kinetix22.json)

Both cameras are Kinetix 22. They are the same model, so pixel size, quantum efficiency, read noise and full-well capacity are the same on both arms, and the two arms of the splitter are photometrically comparable without a cross-calibration term. The names red and blue, and the roles primary and second detector, are wiring and naming rather than a hardware difference: neither camera is the better one.

Identifiers: model: Kinetix 22

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260917).

Conditions, verbatim:

> This instrument as configured on 2026-09-17, operator read at the instrument. This closes an older discrepancy in which a purchase quote listed one Kinetix 22 and one Prime95B against a current state recorded as two Kinetix, unconfirmed: a swap did happen against the quote. Sensor properties are shared because the model is shared; no sensor number is entered here, and the calibrated pixel size remains a per-configuration gap. Falsified by either camera being replaced.

### [confocal_488_excites_the_red_arm](../entries/confocal_488_excites_the_red_arm.json)

On the confocal path, 488 nm excitation produced signal in the red camera arm about as strongly as 561 nm did, and the red arm's signal was additive across the two lines. So assigning species on the red arm requires the lines to be strobed, not run together.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/kb/decisions/2026-09-02-lunf-first-light).

Conditions, verbatim:

> Ruled TRANSFER, passed 10.3 rules 1 and 3: the finding crosses, its contrast figures and additivity sum do not. Measured in another project on 2026-09-07 at 20x on its own sample, so the strength of the leak belongs to that sample's dye; this is an E3 fact about the path, not about any tracer here. Slot: A1 (background) and A4 (whether two lines may run at once for a two-colour plan). Falsified by a two-line confocal frame on the red arm with no 488 contribution. Delivered as item `confocal_488_leaks_into_red_arm` of microscope_agent/findings/microscope-20260924-3-20260924.json at a5e7647 (card 044); the source was opened at fbedef0 and its sha256 matched before this was ruled.

### [csuw1_port_slots](../entries/csuw1_port_slots.json)

The port/splitter carries three slots, and the split is spectral rather than by intensity: one slot is empty and sends light to the red camera only, one holds a 561 nm dichroic and sends light to both cameras in different bands, and one holds a 100/0 mirror and sends light to the blue camera only. Two of the three states therefore send zero light to one camera. Which physical slot is at which position number is not known.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260917).

Conditions, verbatim:

> This instrument as configured on 2026-09-17, operator read at the instrument. 561 carries no numbers[] entry: it is the dichroic's nominal designation, a string identifier that is exact by definition, and the measured edge of its transmission curve is a different quantity that nobody here has measured (5.3). Slot contents only: the slot ORDER is not part of this claim and is recorded as a gap, not estimated. Because two states starve one camera, a position number read back from the driver does not establish which element is in the beam -- that is settled by acquiring, not by read-back. Falsified by re-fitting any slot.

### [emission_wheel_camera_mapping](../entries/emission_wheel_camera_mapping.json)

The first emission filter wheel serves the red camera and the second serves the blue camera. The operator stated this from memory, with the word probably, and the blue half is the complementary half of the same recalled claim.

Identifiers: none

How it is known: recalled or assumed; the person's recollection (E5 · operator_recall:kyuhwan_20260917).

Conditions, verbatim:

> This instrument as configured on 2026-09-17, stated from memory rather than read (operator_recall:kyuhwan_20260917), which is why this is E5 and not E3 while every neighbouring claim about the unit is E3. Not to be promoted by corroboration: a spectral splitter puts one wheel on each output arm, which is consistent with this mapping but is not a reading of it. If the mapping is inverted, two-colour data is labelled wrong and nothing raises an error. Settled by one acquisition: move one wheel and see which camera's image changes.

### [tweez300_camera_is_released_so_it_shows_no_image](../entries/tweez300_camera_is_released_so_it_shows_no_image.json)

The person states that in this lab's use the camera is always released from the Tweez 300 software, so nothing can be seen in the tweezers software; frames of a trapped bead come from Micro-Manager after the tweezers software has let the camera go.

Identifiers: none

How it is known: recalled or assumed; the person's recollection (E5 · operator_recall:kyuhwan_20260924_tweezers_camera).

Conditions, verbatim:

> The person's answer in microscope-20260924-6's window on the evening of 2026-09-24, quoted verbatim in the message of commit 20387f0, which adds microscope_agent/findings/microscope-20260924-6-20260924.json; read by this seat from that message, as the findings item cites. E5, operator_recall: stated from the person's knowledge of the bench, not read off an instrument at the time. The person's words: 'we always release the camera, and you cannot see anything on the tweezer software.' A STATEMENT OF PRACTICE, NOT OF CAPABILITY: the Tweez 300 User Manual describes a live image in the software's master view and video tracking and recording (its calibration chapter, printed pages 36 and 38, refers to 'GUI live image navigation'), so the software can show and record frames when it holds the camera; this lab releases it. Not stated: how the camera is released, whether trap commands over TCP keep working with it released, and whether the software needs the camera at start before releasing it -- the last bears on whether the red body is locked while the tweezers software starts. Delivered as item tweez300_software_records_no_frames.

### [tweez300_software_opens_the_red_arm_camera](../entries/tweez300_software_opens_the_red_arm_camera.json)

The person states that the Tweez 300 software, when it starts, opens the red-arm Kinetix camera -- the body Micro-Manager reads as serial A24M723015 under the label Kinetix_red.

Identifiers: none

How it is known: recalled or assumed; the person's recollection (E5 · operator_recall:kyuhwan_20260924_tweezers_camera).

Conditions, verbatim:

> The person's answer in microscope-20260924-6's window on the evening of 2026-09-24, quoted verbatim in the message of commit 20387f0, which adds microscope_agent/findings/microscope-20260924-6-20260924.json; read by this seat from that message, as the findings item cites. E5, operator_recall: stated from the person's knowledge of the bench, not read off an instrument at the time. Asked which of the two bodies the tweezers software opens, with the red arm's serial given in the question, the person chose 'The red-arm body': the arm, not a serial read from the tweezers software. camera_bodies_are_told_apart_by_serial holds that the bodies are told apart by serial, so READING THE SERIAL THE TWEEZERS SOFTWARE OPENS settles this and would supersede it at a higher grade. kinetix_red_label_opens_serial_a24m723015 ties the red arm to that serial in Micro-Manager only. Consistent with the device table making camera_red exclusive with the tweezers software, and not a test of it. Delivered as item tweez300_opens_the_red_arm_kinetix (card from manager-microscope-20260924-1's instruction).

## Disputed and withdrawn

- [kinetix_red_adapter_properties_as_reported_20260924](../entries/kinetix_red_adapter_properties_as_reported_20260924.json): in conflict; the other side: [pixeltype_misreports_bit_depth](../entries/pixeltype_misreports_bit_depth.json)

## Reading

None.

## Related

- [device camera_blue](../wiki/device_camera_blue.md)
- [device confocal_csuw1](../wiki/device_confocal_csuw1.md)
- [device csuw1_port](../wiki/device_csuw1_port.md)
- [device filter_wheel_em1](../wiki/device_filter_wheel_em1.md)
- [device filter_wheel_em2](../wiki/device_filter_wheel_em2.md)
- [device laser_combiner](../wiki/device_laser_combiner.md)
- [device optical_tweezers](../wiki/device_optical_tweezers.md)
- [quantity full_scale_count](../wiki/quantity_full_scale_count.md)
- [quantity pixel_size](../wiki/quantity_pixel_size.md)
- [quantity quantum_efficiency](../wiki/quantity_quantum_efficiency.md)
- [quantity read_noise](../wiki/quantity_read_noise.md)
- [safety guide](../guides/safety_camera_red.md)

---

Generated from the knowledge store at kbv-058ce14eea72. Do not edit by hand: correct the store and regenerate.
