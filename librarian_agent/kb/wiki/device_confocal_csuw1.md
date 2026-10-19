# Device: confocal_csuw1

Every entry in the store about the device confocal_csuw1.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, channel, verbatim:

```json
{
  "id": "confocal_csuw1",
  "role": "spinning-disk confocal unit: excitation dichroic, disk in/out, spectral port to the two cameras, two emission wheels, shutter",
  "driver": "micromanager",
  "automatable": "full",
  "read_back": true,
  "lock_group": "optical_path",
  "elements": [
    {
      "id": "csuw1_dichroic",
      "slots": 3,
      "slot_contents": "one dichroic fitted, in slot 1; slots 2 and 3 empty",
      "source": "operator_read:kyuhwan_20260917",
      "grade": "E3",
      "entry_ref": "csuw1_dichroic_slots",
      "note": "stays in the path whatever the disk does, which is why this instrument has no unfiltered white-light path. Its own spectral bands are not in the store."
    },
    {
      "id": "csuw1_port",
      "aliases_in_config": [
        "camera_splitter"
      ],
      "slots": 3,
      "slot_contents": [
        {
          "content": "empty",
          "reaches": [
            "camera_red"
          ],
          "starves": [
            "camera_blue"
          ]
        },
        {
          "content": "561 dichroic",
          "reaches": [
            "camera_red",
            "camera_blue"
          ],
          "starves": []
        },
        {
          "content": "100/0 mirror",
          "reaches": [
            "camera_blue"
          ],
          "starves": [
            "camera_red"
          ]
        }
      ],
      "slot_order": null,
      "automatable": "full",
      "read_back": true,
      "verify_by": "acquisition",
      "source": "operator_read:kyuhwan_20260917",
      "grade": "E3",
      "entry_ref": [
        "csuw1_port_is_the_camera_splitter",
        "csuw1_port_slots",
        "csuw1_port_driver_access"
      ],
      "note": "the port IS the splitter: one mechanism that the configuration named twice. The split is spectral, not by intensity -- the two cameras see different bands, not the same image at half brightness. Two of the three states send zero light to one camera, so this is a selector that decides whether light arrives at all, and read-back cannot verify it: slot_order is null and commanding position 2 may land the mirror while read-back confirms position 2 and tells you nothing. Verify by acquiring (see label_warning in optical_paths.v0.json).",
      "not_entered": "which arm is straight-through and which is reflected. That is a model's inference from the slot contents, which is E6 and may enter nothing (P2, 5.3). Read the dichroic's orientation or acquire a known emitter."
    },
    {
      "id": "csuw1_shutter",
      "source": "operator_read:kyuhwan_20260917",
      "grade": "E3",
      "entry_ref": "csuw1_shutter_gates_confocal_excitation",
      "note": "gates the confocal laser into the unit; must be open while the confocal laser is in use. Which shutter an abort closes is policy, not knowledge: it belongs to a person in microscope_agent/envelope/safety.json (4.3.2, 10.3 rule 4). There are two shutters in this chain -- see laser_combiner/laser_shutter."
    },
    {
      "id": "filter_wheel_em1",
      "serves": "camera_red",
      "source": "operator_recall:kyuhwan_20260917",
      "grade": "E5",
      "entry_ref": "emission_wheel_camera_mapping",
      "note": "the operator said probably. Recalled, not read, so E5 while its neighbours are E3 -- and not promoted by the spectral splitter being consistent with it. If inverted, two-colour data is labelled wrong and nothing errors. One acquisition settles it: move one wheel and see which camera's image changes."
    },
    {
      "id": "filter_wheel_em2",
      "serves": "camera_blue",
      "source": "operator_recall:kyuhwan_20260917",
      "grade": "E5",
      "entry_ref": "emission_wheel_camera_mapping",
      "note": "the complementary half of the same recalled claim, so it carries the same grade."
    },
    {
      "id": "csuw1_disk_speed",
      "source": "operator_read:kyuhwan_20260917",
      "grade": "E3",
      "entry_ref": "csuw1_disk_speed_exposure_constraint",
      "note": "exposure must be an integer multiple of the disk period or stripes remain (axis A1); nothing acquires while the disk is still spinning up. The period itself is not in the store."
    },
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
  ],
  "source": "mm_config + nis_device_manager + operator_read:kyuhwan_20260917",
  "grade": "E3",
  "confirmed_by": "operator_read:kyuhwan_20260917",
  "element_count_note": "seven elements. It was nine: two pairs were one mechanism each (port = splitter, disk position = bright), and the extractor had recorded each pair under both of its configuration names."
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

### [confocal_488_excites_the_red_arm](../entries/confocal_488_excites_the_red_arm.json)

On the confocal path, 488 nm excitation produced signal in the red camera arm about as strongly as 561 nm did, and the red arm's signal was additive across the two lines. So assigning species on the red arm requires the lines to be strobed, not run together.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@fbedef0/kb/decisions/2026-09-02-lunf-first-light).

Conditions, verbatim:

> Ruled TRANSFER, passed 10.3 rules 1 and 3: the finding crosses, its contrast figures and additivity sum do not. Measured in another project on 2026-09-07 at 20x on its own sample, so the strength of the leak belongs to that sample's dye; this is an E3 fact about the path, not about any tracer here. Slot: A1 (background) and A4 (whether two lines may run at once for a two-colour plan). Falsified by a two-line confocal frame on the red arm with no 488 contribution. Delivered as item `confocal_488_leaks_into_red_arm` of microscope_agent/findings/microscope-20260924-3-20260924.json at a5e7647 (card 044); the source was opened at fbedef0 and its sha256 matched before this was ruled.

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

- [device camera_red](../wiki/device_camera_red.md)
- [device csuw1_disk_speed](../wiki/device_csuw1_disk_speed.md)
- [device laser_combiner](../wiki/device_laser_combiner.md)
- [safety guide](../guides/safety_confocal_csuw1.md)

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
