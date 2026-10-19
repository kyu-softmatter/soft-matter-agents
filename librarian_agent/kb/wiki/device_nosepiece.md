# Device: nosepiece

Every entry in the store about the device nosepiece.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, element of channel stand_ti2e, verbatim:

```json
{
  "id": "nosepiece",
  "positions": 6,
  "position_index_base": 0,
  "entry_ref": [
    "nosepiece_position_indexing",
    "nosepiece_objective_assignment"
  ],
  "index_note": "positions run 0 through 5, not 1 through 6. Any command or preflight check that assumes 1-6 is off by one on every position.",
  "id_note": "each objective's id IS its nominal magnification, a string identifier that is exact by definition (5.3). There is deliberately no numeric magnification field: a field for it is where a value back-derived from a calibrated pixel size ends up wearing a nominal name, which is what happened in the prior project's 20.078x.",
  "objectives": [
    {
      "position": 0,
      "id": "4x",
      "product": "CFI Plan Apo Lambda D 4X",
      "part_number": "MRD70040",
      "immersion": "air",
      "na": 0.2,
      "wd_mm": 20,
      "coverglass_um": {
        "min": 0,
        "max": 170
      },
      "entry_ref": "objective_mrd70040"
    },
    {
      "position": 1,
      "id": "10x",
      "product": "CFI Plan Apo Lambda D 10X",
      "part_number": "MRD70170",
      "immersion": "air",
      "na": 0.45,
      "wd_mm": 4,
      "coverglass_um": {
        "min": 170,
        "max": 170
      },
      "entry_ref": "objective_mrd70170"
    },
    {
      "position": 2,
      "id": "20x",
      "product": "CFI Plan Apo Lambda D 20X",
      "part_number": "MRD70270",
      "immersion": "air",
      "na": 0.8,
      "wd_mm": 0.8,
      "coverglass_um": {
        "min": 170,
        "max": 170
      },
      "entry_ref": "objective_mrd70270"
    },
    {
      "position": 3,
      "id": "40x-WI",
      "product": "CFI Apo Lambda S 40XC WI",
      "part_number": "MRD77400",
      "immersion": "water",
      "na": 1.25,
      "wd_mm": null,
      "wd_mm_range": {
        "min": 0.16,
        "max": 0.2
      },
      "wd_note": "quoted as a range because it depends on the correction collar. wd_mm is null rather than a midpoint: with the coverslip fixed at 170 um the collar setting is determined and the working distance IS a single value, but the catalog does not publish it and the librarian does not interpolate inside a quotation (4.3). A null is loud; an interpolated number would be silent. See the gap objective_40x_wd_at_170um.",
      "coverglass_um": {
        "min": 150,
        "max": 190
      },
      "correction_collar": true,
      "entry_ref": "objective_mrd77400"
    },
    {
      "position": 4,
      "id": "60x-oil",
      "product": "CFI Plan Apo Lambda D 60X Oil",
      "part_number": "MRD71670",
      "immersion": "oil",
      "na": 1.42,
      "wd_mm": 0.15,
      "coverglass_um": {
        "min": 170,
        "max": 170
      },
      "entry_ref": "objective_mrd71670"
    },
    {
      "position": 5,
      "id": "100x-oil",
      "product": "CFI Plan Apo Lambda D 100X Oil",
      "part_number": "MRD71970",
      "immersion": "oil",
      "na": 1.45,
      "wd_mm": 0.13,
      "coverglass_um": {
        "min": 170,
        "max": 170
      },
      "entry_ref": "objective_mrd71970"
    }
  ],
  "objectives_source": {
    "position_to_lens": "operator_read:kyuhwan_20260917, confirmed at the instrument",
    "na_wd_coverglass": "spec:<part_number>, Nikon catalog (src_nikon_objective_catalog), accessed 2026-08-10",
    "grade": "E3",
    "two_coverslip_facts": "coverglass_um here is what the lens ACCEPTS. What this laboratory actually mounts is 170 um (entry coverslip_thickness_in_use). They answer different questions and are not merged.",
    "not_here": "transmission at 1064 nm. The catalog publishes a curve and no numeric table, and a number a model reads off a rendered curve is E6, which may enter nothing (5.3). See the gap objective_transmission_1064nm."
  }
}
```

## Values

| quantity | value | unit | how it is known | grade and source as recorded | conditions | subject | entry |
|---|---|---|---|---|---|---|---|
| pixel_size | 0.04333 | um | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-pixel-size-20260919 | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_100x_zoom_1_5x](../entries/pixel_size_100x_zoom_1_5x.json) |
| pixel_size | 0.065 | um | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-pixel-size-20260919 | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_100x_zoom_1x](../entries/pixel_size_100x_zoom_1x.json) |
| pixel_size | 0.43333 | um | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-pixel-size-20260919 | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_10x_zoom_1_5x](../entries/pixel_size_10x_zoom_1_5x.json) |
| pixel_size | 0.65 | um | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-pixel-size-20260919 | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_10x_zoom_1x](../entries/pixel_size_10x_zoom_1x.json) |
| pixel_size | 0.21582 | um | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-pixel-size-20260919 | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_20x_zoom_1_5x](../entries/pixel_size_20x_zoom_1_5x.json) |
| pixel_size | 0.32373 | um | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-pixel-size-20260919 | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_20x_zoom_1x](../entries/pixel_size_20x_zoom_1x.json) |
| pixel_size | 0.10833 | um | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-pixel-size-20260919 | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_40x_zoom_1_5x](../entries/pixel_size_40x_zoom_1_5x.json) |
| pixel_size | 0.1625 | um | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-pixel-size-20260919 | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_40x_zoom_1x](../entries/pixel_size_40x_zoom_1x.json) |
| pixel_size | 1.0833 | um | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-pixel-size-20260919 | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_4x_zoom_1_5x](../entries/pixel_size_4x_zoom_1_5x.json) |
| pixel_size | 1.625 | um | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-pixel-size-20260919 | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_4x_zoom_1x](../entries/pixel_size_4x_zoom_1x.json) |
| pixel_size | 0.07222 | um | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-pixel-size-20260919 | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_60x_zoom_1_5x](../entries/pixel_size_60x_zoom_1_5x.json) |
| pixel_size | 0.10833 | um | calibrated on this instrument; a calibration on this instrument | E2 · calibration:cal-pixel-size-20260919 | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_60x_zoom_1x](../entries/pixel_size_60x_zoom_1x.json) |
| na | 0.2 | 1 | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD70040 | coverslip_um 0 to 170 um | device nosepiece | [objective_mrd70040](../entries/objective_mrd70040.json) |
| working_distance | 20 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD70040 | coverslip_um 0 to 170 um | device nosepiece | [objective_mrd70040](../entries/objective_mrd70040.json) |
| cover_glass_thickness_min | 0.0 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD70040 | none stated | device nosepiece | [objective_mrd70040_selector_properties](../entries/objective_mrd70040_selector_properties.json) |
| cover_glass_thickness_max | 0.17 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD70040 | none stated | device nosepiece | [objective_mrd70040_selector_properties](../entries/objective_mrd70040_selector_properties.json) |
| na | 0.45 | 1 | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD70170 | coverslip_um 170 um | device nosepiece | [objective_mrd70170](../entries/objective_mrd70170.json) |
| working_distance | 4 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD70170 | coverslip_um 170 um | device nosepiece | [objective_mrd70170](../entries/objective_mrd70170.json) |
| cover_glass_thickness_min | 0.17 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD70170 | none stated | device nosepiece | [objective_mrd70170_selector_properties](../entries/objective_mrd70170_selector_properties.json) |
| cover_glass_thickness_max | 0.17 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD70170 | none stated | device nosepiece | [objective_mrd70170_selector_properties](../entries/objective_mrd70170_selector_properties.json) |
| na | 0.8 | 1 | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD70270 | coverslip_um 170 um | device nosepiece | [objective_mrd70270](../entries/objective_mrd70270.json) |
| working_distance | 0.8 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD70270 | coverslip_um 170 um | device nosepiece | [objective_mrd70270](../entries/objective_mrd70270.json) |
| cover_glass_thickness_min | 0.17 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD70270 | none stated | device nosepiece | [objective_mrd70270_selector_properties](../entries/objective_mrd70270_selector_properties.json) |
| cover_glass_thickness_max | 0.17 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD70270 | none stated | device nosepiece | [objective_mrd70270_selector_properties](../entries/objective_mrd70270_selector_properties.json) |
| na | 1.42 | 1 | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD71670 | coverslip_um 170 um | device nosepiece | [objective_mrd71670](../entries/objective_mrd71670.json) |
| working_distance | 0.15 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD71670 | coverslip_um 170 um | device nosepiece | [objective_mrd71670](../entries/objective_mrd71670.json) |
| cover_glass_thickness_min | 0.17 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD71670 | none stated | device nosepiece | [objective_mrd71670_selector_properties](../entries/objective_mrd71670_selector_properties.json) |
| cover_glass_thickness_max | 0.17 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD71670 | none stated | device nosepiece | [objective_mrd71670_selector_properties](../entries/objective_mrd71670_selector_properties.json) |
| na | 1.45 | 1 | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD71970 | coverslip_um 170 um | device nosepiece | [objective_mrd71970](../entries/objective_mrd71970.json) |
| working_distance | 0.13 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD71970 | coverslip_um 170 um | device nosepiece | [objective_mrd71970](../entries/objective_mrd71970.json) |
| cover_glass_thickness_min | 0.17 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD71970 | none stated | device nosepiece | [objective_mrd71970_selector_properties](../entries/objective_mrd71970_selector_properties.json) |
| cover_glass_thickness_max | 0.17 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD71970 | none stated | device nosepiece | [objective_mrd71970_selector_properties](../entries/objective_mrd71970_selector_properties.json) |
| na | 1.25 | 1 | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD77400 | coverslip_um 150 to 190 um | device nosepiece | [objective_mrd77400](../entries/objective_mrd77400.json) |
| working_distance_min | 0.16 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD77400 | coverslip_um 150 to 190 um | device nosepiece | [objective_mrd77400](../entries/objective_mrd77400.json) |
| working_distance_max | 0.2 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD77400 | coverslip_um 150 to 190 um | device nosepiece | [objective_mrd77400](../entries/objective_mrd77400.json) |
| cover_glass_thickness_min | 0.15 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD77400 | none stated | device nosepiece | [objective_mrd77400_selector_properties](../entries/objective_mrd77400_selector_properties.json) |
| cover_glass_thickness_max | 0.19 | mm | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:MRD77400 | none stated | device nosepiece | [objective_mrd77400_selector_properties](../entries/objective_mrd77400_selector_properties.json) |
| nosepiece_positions | 6 | count | from a document, a reading off the instrument, or another project's record; the person read it off the instrument | E3 · operator_read:kyuhwan_20260917 | none stated | device nosepiece | [nosepiece_position_indexing](../entries/nosepiece_position_indexing.json) |
| coverslip_thickness | 170 | um | from a document, a reading off the instrument, or another project's record; the person read it off the instrument | E3 · operator_read:kyuhwan_20260922 | coverslip_um 170 um | device nosepiece | [objective_40x_collar_setting](../entries/objective_40x_collar_setting.json) |
| objective_transmittance_min | 0.5 | 1 | from a document, a reading off the instrument, or another project's record; the person read it off the instrument | E3 · operator_read:kyuhwan_20260924_transmittance_graphs | none stated | device nosepiece | [objective_transmittance_is_between_half_and_all](../entries/objective_transmittance_is_between_half_and_all.json) |
| objective_transmittance_max | 1.0 | 1 | from a document, a reading off the instrument, or another project's record; the person read it off the instrument | E3 · operator_read:kyuhwan_20260924_transmittance_graphs | none stated | device nosepiece | [objective_transmittance_is_between_half_and_all](../entries/objective_transmittance_is_between_half_and_all.json) |
| pixel_size | 0.04333 | um | computed; computed from other values | E4 · computed:pixel_size_from_sensor_pitch | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_100x_zoom_1_5x_computed](../entries/pixel_size_100x_zoom_1_5x_computed.json) |
| pixel_size | 0.065 | um | computed; computed from other values | E4 · computed:pixel_size_from_sensor_pitch | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_100x_zoom_1x_computed](../entries/pixel_size_100x_zoom_1x_computed.json) |
| pixel_size | 0.43333 | um | computed; computed from other values | E4 · computed:pixel_size_from_sensor_pitch | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_10x_zoom_1_5x_computed](../entries/pixel_size_10x_zoom_1_5x_computed.json) |
| pixel_size | 0.65 | um | computed; computed from other values | E4 · computed:pixel_size_from_sensor_pitch | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_10x_zoom_1x_computed](../entries/pixel_size_10x_zoom_1x_computed.json) |
| pixel_size | 0.21582 | um | computed; computed from other values | E4 · computed:pixel_size_20x_at_1_5x_from_20x_at_1x | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_20x_zoom_1_5x_computed](../entries/pixel_size_20x_zoom_1_5x_computed.json) |
| pixel_size | 0.10833 | um | computed; computed from other values | E4 · computed:pixel_size_from_sensor_pitch | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_40x_zoom_1_5x_computed](../entries/pixel_size_40x_zoom_1_5x_computed.json) |
| pixel_size | 0.1625 | um | computed; computed from other values | E4 · computed:pixel_size_from_sensor_pitch | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_40x_zoom_1x_computed](../entries/pixel_size_40x_zoom_1x_computed.json) |
| pixel_size | 1.0833 | um | computed; computed from other values | E4 · computed:pixel_size_from_sensor_pitch | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_4x_zoom_1_5x_computed](../entries/pixel_size_4x_zoom_1_5x_computed.json) |
| pixel_size | 1.625 | um | computed; computed from other values | E4 · computed:pixel_size_from_sensor_pitch | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_4x_zoom_1x_computed](../entries/pixel_size_4x_zoom_1x_computed.json) |
| pixel_size | 0.07222 | um | computed; computed from other values | E4 · computed:pixel_size_from_sensor_pitch | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_60x_zoom_1_5x_computed](../entries/pixel_size_60x_zoom_1_5x_computed.json) |
| pixel_size | 0.10833 | um | computed; computed from other values | E4 · computed:pixel_size_from_sensor_pitch | binning 1 count | device nosepiece, quantity pixel_size | [pixel_size_60x_zoom_1x_computed](../entries/pixel_size_60x_zoom_1x_computed.json) |

## Claims

### [stand_state_read_20260924_20x_in_place](../entries/stand_state_read_20260924_20x_in_place.json)

On 2026-09-24, with the 20x placed by hand, the stand read: Nosepiece state 2, label '3-Plan Apo LmbdD0.8 20x'; LightPath state 3, '4-L100'; FilterTurret1 state 0, '1-MXR00724 -Empty'; FilterTurret2 state 0, '1-Empty'; LappMainBranch1 state 1, 'mirror_in'; CondenserTurret state 0, '1-ND'.

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-002).

Conditions, verbatim:

> Read back in a preparatory run -- the first real acquisition on this computer, with no plan, the person having placed the 20x and moved the microscope by hand, software moving nothing. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system: E1 from `measured:`. Not a value of any registered observable. A STATE, NOT A PROPERTY: every value is falsified by moving that element. The labels are strings from the loaded configuration and are downgraded until a frame confirms each (plan.md 10.2.1); the state integers are what the stand reported. Nosepiece state 2 agrees with nosepiece_objective_assignment, which puts the 20x (MRD70270) at position 2. FilterTurret1's label names both the MXR00724 cube and 'Empty' at state 0, which is ambiguous; filter_turret_1_state_0_blocked_the_confocal_path records that cube at state 0 in the prior project on 2026-09-07. Slot: A4 and A6. Delivered as item stand_read_with_20x_in_place of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042). Checked by this seat against microscope_agent/runs/run-20260924-002/log.json read at bf8f91f (unchanged since): event 15.

### [ti2e_objective_escape_is_set_per_nosepiece_address](../entries/ti2e_objective_escape_is_set_per_nosepiece_address.json)

In Ti2 Control, each nosepiece address can be set to move the objective to its escape position before that address passes when the nosepiece rotates, and the escape distance used when changing the specimen is also a setting there.

How it is known: from a document, a reading off the instrument, or another project's record; manufacturer's specification (E3 · spec:nikon_ti2_control_v2_90_m706_e15).

Conditions, verbatim:

> Read from Nikon Ti2 Control Ver2.90 for Windows, English manual M706 E15 (sha256 5e43517c...): printed page 73 (PDF page 81). E3 vendor_spec: the manufacturer's statement, not an observation on this bench. This manual is for the Ti2 Control software; the archive holds no Ti2-E hardware manual. Bears on nosepiece_write_runs_no_escape (the prior project: a Micro-Manager nosepiece write runs no escape): what the stand does is configured in the stand, and how this one is configured is not recorded here. KNOWLEDGE, NOT POLICY: this is what the manufacturer says. What any session may do, and every limit anyone here acts on, is the person's, written into the envelope after confirming it on the instrument.

### [nosepiece_is_an_mmcore_state_device](../entries/nosepiece_is_an_mmcore_state_device.json)

On the prior project's configuration the objective turret is the MMCore device label `Nosepiece`, a state device: the position is read with getStateLabel and set with setState, and its labels carry the objective designation, for example `6-Plan Apo LmbdD0.13 100x Oil`.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@34a432c).

Conditions, verbatim:

> THE POSITION IS NOT A NAMED PROPERTY. A state device answers getState and getStateLabel; there is no `Position` property to compare against getDevicePropertyNames(), which is what the request assumed. A plan naming one will not find it. THE LABEL IS THE LAB'S OWN STRING AND CARRIES THE OBJECTIVE, so it is also how the prior project recovered which objective is in the path. That makes it a nominal designation and a string (5.3), never a number: the prior project's `20.078x` is the case that rule exists for -- a nominal magnification wearing a value back-calculated from a calibration -- and a magnification must not be parsed back out of this label into a number here. THE LABEL SET IS NOT ENTERED. Which position carries which objective is falsified by one person turning the turret, and nosepiece_objective_assignment already says position-to-lens is the one claim on this device a single swap falsifies. What crosses is the INTERFACE, which a swap does not touch. NOT A SAFETY CLAIM. The prior module marks this device as one of three where a move can collide and records that rotating the turret does not retract Z. That is device behaviour and it is named here so nobody reads its absence as its absence -- but it is not entered as a limit, and 10.3 rule 4 keeps limits out: a person writes those after confirming physically. WHAT WOULD RAISE IT: getLoadedDevices() and getDeviceType() on this stand. Slot: a KB entry and the device registry's nosepiece row. Rule passed: 10.3 rule 1.

### [nosepiece_objective_assignment](../entries/nosepiece_objective_assignment.json)

The six nosepiece positions hold, in order from 0 to 5: MRD70040 (CFI Plan Apo Lambda D 4X), MRD70170 (10X), MRD70270 (20X), MRD77400 (CFI Apo Lambda S 40XC WI), MRD71670 (60X Oil) and MRD71970 (100X Oil). The operator confirmed the whole assignment at the instrument.

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260917).

Conditions, verbatim:

> This instrument on 2026-09-17, operator read at the instrument. The table arrived as an index from an earlier project's dossier under explicit operator authorisation, and every row was then confirmed here; the specifications of each lens are separate entries citing the catalog part number, never the dossier. Position-to-lens mapping is the one claim on this nosepiece that a single lens swap falsifies, and this instrument's paper record has drifted from its hardware before, so it is re-read rather than inherited. A magnification written here -- 4x, 20x -- is a nominal designation and a string identifier, not a number, and nothing may back-derive it from a calibrated pixel size.

### [nosepiece_write_runs_no_escape](../entries/nosepiece_write_runs_no_escape.json)

The stand runs no objective escape when the nosepiece is rotated by a Micro-Manager write: Z does not move, so whatever height the outgoing objective was at is where the incoming one arrives. Rotating at the stand or in NIS does run the Ti2's own escape; the software path does not.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@safety-2026-09-03).

Conditions, verbatim:

> Ruled TRANSFER under 10.2.1 and passed 10.3 rule 1, so it caps at E3 -- a run taken in another project is not a run taken here. 10.2's hardware-control-path row is open and says in its own rule that it does not wait for envelope/, because wrapping a control path needs no safety limit. Slot: O1 preflight, which is the consumer that has to know a write does less than it appears to, with A4 second. Measured in the prior project by rotating between two objectives and reading the Z drive before and after: it moved by zero. The clearance that absorbs the difference is a property of whichever objective is arriving, and this store already holds those working distances per part number. No limit crosses with this: what is transferred is that the escape does not run, not how far anything may travel.

### [objective_change_invalidates_trap_calibration](../entries/objective_change_invalidates_trap_calibration.json)

Changing the objective silently invalidates both of the optical tweezers' calibrations -- the GUI's pixel-to-micrometre magnification and the AOD's trapping-field response -- and neither is readable over TCP. Afterwards every commanded trap position in micrometres lands somewhere else and nothing reports it.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@safety-2026-09-03).

Conditions, verbatim:

> Ruled TRANSFER under 10.2.1 and passed 10.3 rule 1, so it caps at E3 -- a run taken in another project is not a run taken here. 10.2's hardware-control-path row is open and says in its own rule that it does not wait for envelope/, because wrapping a control path needs no safety limit. Slot: A4 for the configuration change and O1 preflight for the check it forces, with A7 as the axis that owns commanded motion. It is the specific case of tweez300_reports_nothing_back that bites hardest, because the invalidating action is on a different device from the one that goes wrong. The check is to drive a known amplitude and measure it; the store holds no threshold for what counts as agreement, and that is a caller's judgement recorded in its plan.  NOT THE PIXEL-SIZE CALIBRATION, AND THE STORE NOW SAYS SO AT BOTH ENDS. This entry says an objective change invalidates a pixel-to-micrometre calibration, which reads as covering the twelve pixel_size_\<mag\>_zoom_\<zoom\> rows and does not. What it covers is the tweezers' GUI, which holds ONE such calibration that the swap falsifies; the pixel-size rows are TWELVE, indexed BY objective, so the same action selects among them. The person ruled that directly on 2026-09-21 -- see objective_change_selects_a_pixel_size_row. Written into this entry as well as that one because a cross-reference that lives at one end is found only by whoever arrives at that end, and a reader who reaches this entry first is exactly the reader who would over-apply it.

### [working_distance_is_measured_to_the_coverslip](../entries/working_distance_is_measured_to_the_coverslip.json)

The catalogue working distances for the objectives on this nosepiece are measured from the front element to the coverslip's lens-facing surface, not to the sample plane. This is inferred from two facts the store already holds; no document was read that says it.

How it is known: computed; computed from other values (E4 · computed:working_distance_versus_coverslip).

Conditions, verbatim:

> THE INFERENCE, AND IT IS AN INFERENCE. Three of the six objectives have a catalogue working distance SHORTER than the coverslip this laboratory mounts on: 60x Oil at 150 um (objective_mrd71670), 100x Oil at 130 um (objective_mrd71970), and 40x WI from 160 um (objective_mrd77400), against coverslip_thickness 170 um (coverslip_thickness_in_use, E3, operator_read). If the catalogue measured to the SAMPLE PLANE, then at focus the front element of those three would sit nearer the sample than the glass is thick -- inside the coverslip. It cannot. So the catalogue measures to the coverslip's lens-facing surface, and the distance from front element to sample is the working distance plus the coverslip thickness.  RECORDED AS AN INFERENCE OR NOT AT ALL, which is how task 021 put it and why this is E4 rather than E3. Nothing was read. Two E3 facts and one impossibility give it, and 5.3 caps a consequence at E4 however good its inputs are. A later reading of the Nikon catalogue that states the convention outright would supersede this at E3; a measurement on this bench would do better still.  WHAT IT IS NOT NEEDED FOR. Not for the focus ceiling. Task 021 recorded the person's correction of an over-built argument: a lens is at its working distance when it is in focus, by definition, so `do not pass the working distance` means `do not pass focus` whichever surface the catalogue measured from. The convention does not enter that rule and the ceiling did not wait on it.  WHAT IT IS NEEDED FOR. Anything computing an absolute Z in stage coordinates from the coverslip geometry -- where the sample plane sits relative to a focused objective, how far a stage may travel before the element meets glass, and any conversion between a focus position and a depth in the sample. Those need the plus-170 and get it wrong silently without this.  WHY THIS ONE DERIVES AND declared_versus_inferred_temperature DOES NOT. Both are conclusions this store reasoned to rather than read, and both are `computed:` at E4. The difference is what they rest on: this rests on two QUANTITIES the store carries as numbers, `working_distance` and `coverslip_thickness`, so `inputs` resolves and check 62 can verify the grade. That entry rests on CLAIMS carrying no numbers, so nothing composes. Same source kind, two different shapes -- which is the gap raised with manager-librarian under task 020.

### [objective_change_selects_a_pixel_size_row](../entries/objective_change_selects_a_pixel_size_row.json)

Changing the objective does not end the twelve per-objective pixel-size calibration rows; it selects which of them applies. A caller that swaps to another objective reads the row naming that objective, at the intermediate magnification in use.

How it is known: recalled or assumed; an assumption (E5 · assumed:person_ruling_20260921).

Conditions, verbatim:

> The twelve entries pixel_size_\<mag\>_zoom_\<zoom\>, at 1x1 binning, on this instrument.  WHY THIS IS AN ENTRY AND NOT SOMETHING A READER COULD WORK OUT. The structure is visible -- each row carries `nominal_magnification` and `intermediate_magnification` in `identifiers` rather than in `validity`, and the rows say themselves that those are nominal designations, exact by definition. What is NOT visible is whether that structure is a claim about the instrument or a filing convention, and the store already holds a sentence pointing the other way: objective_change_invalidates_trap_calibration says, in so many words, that changing the objective silently invalidates a pixel-to-micrometre calibration. A reader meeting both had no way to tell which applies where. This entry is the person answering that, asked directly on 2026-09-21.  THE TWO ARE DIFFERENT AND THE DIFFERENCE IS COUNTABLE. The tweezers hold ONE calibration, and an objective change falsifies it -- worse, neither of the tweezers' two calibrations is readable over TCP, so nothing reports the loss. This calibration holds TWELVE rows INDEXED BY objective, so the same physical action moves the caller between rows instead of destroying one. Both statements are true at once and neither generalises to the other's subject.  WHAT THIS DOES NOT SAY. It does not say that nothing ends these rows. A camera change would end all twelve at once -- pixel size at the sample plane is the sensor pitch over the magnification, and camera_sensor_geometry carries the Kinetix22's 6.5 um pitch -- and so would a change in the optics between objective and camera, which the store holds nothing about. Neither was put to the person, so neither is entered and neither is denied; `valid_until` on the twelve therefore still carries a bare date and no event. See src_person_ruling_20260921 for what was asked and what came back. Looked-for-and-absent and nobody-checked are not the same claim (4.3.1), and that distinction holds outside a gap as well as inside one.  GRADE. E5 because the source is a person's ruling, derived from that and not declared (rule 3). The confidence a reader should put on it is higher than E5 usually signals, because the store's own structure corroborates it -- but corroboration is not a source, and inflating the grade to match a feeling is what the derivation rule exists to prevent.  THE OTHER HALF OF THE SAME RULING IS NOT AN ENTRY, AND THAT IS NOT AN OVERSIGHT. On 2026-09-21 the person also ruled that this calibration will not be repeated. That was filed beside this one for a few minutes and withdrawn: a decision takes no grade (plan.md:1259 @6d587b3 -- P2's four parts attach to a claim about the world), and kb_entry.schema.json requires one, so it cannot be an entry at all. It is recorded in src_person_ruling_20260921 and in src_operator_calibration_20260919's `standing_2026_09_21`. A READER LOOKING FOR IT THROUGH kb_query WILL NOT FIND IT AND SHOULD NOT: the store answers questions about the world, and whether we intend to remeasure is not one.

## Disputed and withdrawn

- [pixel_size_100x_zoom_1_5x](../entries/pixel_size_100x_zoom_1_5x.json): in conflict; the other side: [pixel_size_100x_zoom_1_5x_computed](../entries/pixel_size_100x_zoom_1_5x_computed.json)
- [pixel_size_100x_zoom_1x](../entries/pixel_size_100x_zoom_1x.json): in conflict; the other side: [pixel_size_100x_zoom_1x_computed](../entries/pixel_size_100x_zoom_1x_computed.json)
- [pixel_size_10x_zoom_1_5x](../entries/pixel_size_10x_zoom_1_5x.json): in conflict; the other side: [pixel_size_10x_zoom_1_5x_computed](../entries/pixel_size_10x_zoom_1_5x_computed.json)
- [pixel_size_10x_zoom_1x](../entries/pixel_size_10x_zoom_1x.json): in conflict; the other side: [pixel_size_10x_zoom_1x_computed](../entries/pixel_size_10x_zoom_1x_computed.json)
- [pixel_size_20x_zoom_1_5x](../entries/pixel_size_20x_zoom_1_5x.json): in conflict; the other side: [pixel_size_20x_zoom_1_5x_computed](../entries/pixel_size_20x_zoom_1_5x_computed.json)
- [pixel_size_40x_zoom_1_5x](../entries/pixel_size_40x_zoom_1_5x.json): in conflict; the other side: [pixel_size_40x_zoom_1_5x_computed](../entries/pixel_size_40x_zoom_1_5x_computed.json)
- [pixel_size_40x_zoom_1x](../entries/pixel_size_40x_zoom_1x.json): in conflict; the other side: [pixel_size_40x_zoom_1x_computed](../entries/pixel_size_40x_zoom_1x_computed.json)
- [pixel_size_4x_zoom_1_5x](../entries/pixel_size_4x_zoom_1_5x.json): in conflict; the other side: [pixel_size_4x_zoom_1_5x_computed](../entries/pixel_size_4x_zoom_1_5x_computed.json)
- [pixel_size_4x_zoom_1x](../entries/pixel_size_4x_zoom_1x.json): in conflict; the other side: [pixel_size_4x_zoom_1x_computed](../entries/pixel_size_4x_zoom_1x_computed.json)
- [pixel_size_60x_zoom_1_5x](../entries/pixel_size_60x_zoom_1_5x.json): in conflict; the other side: [pixel_size_60x_zoom_1_5x_computed](../entries/pixel_size_60x_zoom_1_5x_computed.json)
- [pixel_size_60x_zoom_1x](../entries/pixel_size_60x_zoom_1x.json): in conflict; the other side: [pixel_size_60x_zoom_1x_computed](../entries/pixel_size_60x_zoom_1x_computed.json)
- [pixel_size_100x_zoom_1_5x_computed](../entries/pixel_size_100x_zoom_1_5x_computed.json): in conflict; the other side: [pixel_size_100x_zoom_1_5x](../entries/pixel_size_100x_zoom_1_5x.json)
- [pixel_size_100x_zoom_1x_computed](../entries/pixel_size_100x_zoom_1x_computed.json): in conflict; the other side: [pixel_size_100x_zoom_1x](../entries/pixel_size_100x_zoom_1x.json)
- [pixel_size_10x_zoom_1_5x_computed](../entries/pixel_size_10x_zoom_1_5x_computed.json): in conflict; the other side: [pixel_size_10x_zoom_1_5x](../entries/pixel_size_10x_zoom_1_5x.json)
- [pixel_size_10x_zoom_1x_computed](../entries/pixel_size_10x_zoom_1x_computed.json): in conflict; the other side: [pixel_size_10x_zoom_1x](../entries/pixel_size_10x_zoom_1x.json)
- [pixel_size_20x_zoom_1_5x_computed](../entries/pixel_size_20x_zoom_1_5x_computed.json): in conflict; the other side: [pixel_size_20x_zoom_1_5x](../entries/pixel_size_20x_zoom_1_5x.json)
- [pixel_size_40x_zoom_1_5x_computed](../entries/pixel_size_40x_zoom_1_5x_computed.json): in conflict; the other side: [pixel_size_40x_zoom_1_5x](../entries/pixel_size_40x_zoom_1_5x.json)
- [pixel_size_40x_zoom_1x_computed](../entries/pixel_size_40x_zoom_1x_computed.json): in conflict; the other side: [pixel_size_40x_zoom_1x](../entries/pixel_size_40x_zoom_1x.json)
- [pixel_size_4x_zoom_1_5x_computed](../entries/pixel_size_4x_zoom_1_5x_computed.json): in conflict; the other side: [pixel_size_4x_zoom_1_5x](../entries/pixel_size_4x_zoom_1_5x.json)
- [pixel_size_4x_zoom_1x_computed](../entries/pixel_size_4x_zoom_1x_computed.json): in conflict; the other side: [pixel_size_4x_zoom_1x](../entries/pixel_size_4x_zoom_1x.json)
- [pixel_size_60x_zoom_1_5x_computed](../entries/pixel_size_60x_zoom_1_5x_computed.json): in conflict; the other side: [pixel_size_60x_zoom_1_5x](../entries/pixel_size_60x_zoom_1_5x.json)
- [pixel_size_60x_zoom_1x_computed](../entries/pixel_size_60x_zoom_1x_computed.json): in conflict; the other side: [pixel_size_60x_zoom_1x](../entries/pixel_size_60x_zoom_1x.json)

## Reading

- [what_falsifies_the_49_bench_claims.md](../distilled/what_falsifies_the_49_bench_claims.md)

## Related

- [configuration trapping](../wiki/configuration_trapping.md)
- [device filter_turret_1](../wiki/device_filter_turret_1.md)
- [device filter_turret_2](../wiki/device_filter_turret_2.md)
- [device lapp_branch](../wiki/device_lapp_branch.md)
- [device light_path_port](../wiki/device_light_path_port.md)
- [device optical_tweezers](../wiki/device_optical_tweezers.md)
- [device stand_ti2e](../wiki/device_stand_ti2e.md)
- [device z_drive](../wiki/device_z_drive.md)
- [quantity coverslip_thickness](../wiki/quantity_coverslip_thickness.md)
- [quantity na](../wiki/quantity_na.md)
- [quantity pixel_size](../wiki/quantity_pixel_size.md)

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
