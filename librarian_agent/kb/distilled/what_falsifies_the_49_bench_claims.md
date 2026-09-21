# What would falsify the 49 — task 033's wide part

Written by `seat:librarian-3` on 2026-09-21 against `kbv-ac042a5c0814`.
The classification below is a **reading of each claim, one at a time**; a script
only counts it. That matters here because the number this replaces —
manager-librarian's 37 — was produced by a keyword match and was handed over
with the instruction not to reproduce it by construction.

## The count

**26, not 37.** The axis is not binary and not ternary: eight kinds.

| kind | n | what would have to change for the claim to stop being true |
|---|---:|---|
| **A** | 26 | the instrument's fitting changes -- a swap, a re-cabling, something installed or removed |
| **B** | 8 | a software or firmware version changes -- true of MMCore or a device, not of this bench's wiring |
| **C** | 2 | a vendor acts on its own artefact -- corrects published data, documents an interface |
| **D** | 2 | a consumable instance is replaced -- the bottle, the box of coverslips |
| **E** | 6 | nothing: the claim is already scoped to a past moment, and the scoping IS the expiry |
| **F** | 2 | nothing: it is a methodological truth, not a claim about this bench |
| **G** | 1 | no event at all: it drifts, and needs a re-read date rather than a trigger |
| **H** | 2 | it is superseded rather than expired -- a stopgap that ends when a better source arrives |

**A is the kind the policy question is about, and it is 26.** The other 23 split
into seven kinds, and three of those — **E, F and their 8 entries** — *cannot
expire at all*, so a rule requiring an expiry of every bench claim would demand
one from claims that have nothing to put in it.

**The three that are not just 'a smaller bucket':**

- **E (6)** — already scoped to a past moment in the claim's own words: *'on the
  prior project's configuration'*, *'measured on 2026-09-06'*. **The scoping IS
  the expiry**, written in prose where no field can read it. These are the
  cheapest to settle and the easiest to mistake for negligence.
- **G (1)** — `lab_ambient_temperature`. A 20 °C reading ages from the moment it
  is taken and **no event ends it**. `valid_until` is the wrong instrument: what
  this wants is a re-read date. A policy written in terms of events has nothing
  to say here, and this is the one entry that shows it.
- **H (2)** — a stopgap that ends when a better source arrives: the borrowed
  Kinetix QE point, the recalled heating bound. Those are **superseded, not
  expired** — rule 8's business, not `valid_until`'s. Filing them as expiries
  would put a date on something whose end is an event in the STORE, not in the world.

## The ten that could not be placed cleanly

Each is doing two jobs, which is rule 1's business. Listed because a claim you
cannot classify is the interesting one.

- **`camera_red_mm_control_path`** — primary E. also B: device labels are a config fact
- **`csuw1_disk_position_is_the_bright_selector`** — primary A. also: it is half a claim about the CONFIGURATION's naming, which a config rewrite ends
- **`csuw1_disk_position_states`** — primary A. also: 'disk-out is not a configuration of its own' is a modelling ruling, not an observation
- **`csuw1_disk_speed_exposure_constraint`** — primary A. content is a property of spinning-disk DESIGN, so the operator_read prefix files it as bench and it is nearer a product fact
- **`csuw1_port_driver_access`** — primary A. also B: 'drivable through micromanager' dies with a driver or config change
- **`filter_cube_mxr00724_is_five_band`** — primary A. also: 'its emitter passes 440/520.5/606/694/808.5' is a PRODUCT spec that outlives any swap
- **`nosepiece_position_indexing`** — primary A. also B: zero-basing is an MMCore convention, not a property of the turret
- **`nosepiece_write_runs_no_escape`** — primary A. also B: the escape behaviour is the stand's firmware under a software write
- **`stand_ti2e_lock_groups`** — primary A. also: the lock-group assignment is a CONTRACT decision, correct by being made
- **`trapping_laser_identity`** — primary A. also: '1064 nm, rated 5 W' is a PRODUCT spec of the Tweez 300 folded into a bench claim

**Three of those ten are one shape: a product specification folded into a bench**
**claim.** `trapping_laser_identity` carries *1064 nm, rated 5 W* (a Tweez 300
spec, true wherever one sits) inside *the trapping laser here is a Tweez 300* (a
bench claim a swap ends). `filter_cube_mxr00724_is_five_band` and
`csuw1_disk_speed_exposure_constraint` do the same. **That is exactly the shape
`camera_sensor_geometry` and `cameras_both_kinetix22` are kept apart to avoid**,
and today's narrow ruling turned on their being two entries. These three are one
entry each, so the same distinction cannot be drawn in them — the spec half would
expire with the bench half.

**And four are a bench fact welded to a software fact** (`camera_red_mm_control_path`,
`csuw1_port_driver_access`, `nosepiece_position_indexing`,
`nosepiece_write_runs_no_escape`), which is the A/B line running through the middle
of an entry instead of between entries.

## Does one event cover many, as one calibration covered twelve?

**No — and that is the answer, not a failure to find one.**

```
kind A:  26 entries
         20 distinct events, largest cluster 6   (at the granularity of the action)
          9 distinct units, largest cluster 8    (at the granularity a person acts at)
```

- **8** — the CSU-W1 unit
- **3** — the emission filter wheels
- **3** — the Ti2 stand and its stage stack
- **3** — the room and its environmental fittings
- **3** — the optical tweezers
- **2** — the two camera bodies
- **2** — the nosepiece
- **1** — the laser combiner
- **1** — the Ti2 filter turret

**The pixel-size case does not repeat.** There, twelve entries shared ONE source
(`cal-pixel-size-20260919`) and one event covered all twelve, which turned twelve
questions into one. Here the largest cluster is 8 of 26 and the tail is long: nine
units, five of them holding one or two entries. **The policy question shrinks by
about three, not to one.**

**What that means for the ruling architecture has to make**: this cannot be closed
by asking the person one question. It can be closed by asking **nine** — one per
unit, *what would have to happen to this for the claims about it to stop holding* —
and eight of the answers cover two or three entries each. Whether that is worth the
bookkeeping is the question; this document is the size of it.

## Method, and what it is not

Every one of the 49 claims was read. The prefix split that produced the 49
(`operator_read`/`operator_recall`/`calibration`/`measured`/`prior_run` = *about
this bench*) is a good filter and **is not the classification** — it puts
`csuw1_disk_speed_exposure_constraint` in the bench set on an `operator_read`
prefix when its content is a property of spinning-disk design, and it puts the six
E-kind entries there when they are scoped to a bench that is not this one.

The assignment lives in `classify49.py`, which asserts its own key set against the
live store before counting, so it fails rather than drifts when the store moves. It
is not committed: it is scaffolding for one count, and a script in the tree would
be a second authority that can disagree with this file.

## The run

```
the 49 as task 033 counted them; 2 have since been given an expiry (033 narrow part), leaving 47 open

classified 49 entries -- the 49 -- against the store at kbv-ac042a5c0814

  A  26   the instrument's fitting changes -- a swap, a re-cabling, something installed or removed
  B   8   a software or firmware version changes -- true of MMCore or a device, not of this bench's wiring
  C   2   a vendor acts on its own artefact -- corrects published data, documents an interface
  D   2   a consumable instance is replaced -- the bottle, the box of coverslips
  E   6   nothing: the claim is already scoped to a past moment, and the scoping IS the expiry
  F   2   nothing: it is a methodological truth, not a claim about this bench
  G   1   no event at all: it drifts, and needs a re-read date rather than a trigger
  H   2   it is superseded rather than expired -- a stopgap that ends when a better source arrives

two jobs in one entry: 10
    camera_red_mm_control_path
        also B: device labels are a config fact
    csuw1_disk_position_is_the_bright_selector
        also: it is half a claim about the CONFIGURATION's naming, which a config rewrite ends
    csuw1_disk_position_states
        also: 'disk-out is not a configuration of its own' is a modelling ruling, not an observation
    csuw1_disk_speed_exposure_constraint
        content is a property of spinning-disk DESIGN, so the operator_read prefix files it as bench and it is nearer a product fact
    csuw1_port_driver_access
        also B: 'drivable through micromanager' dies with a driver or config change
    filter_cube_mxr00724_is_five_band
        also: 'its emitter passes 440/520.5/606/694/808.5' is a PRODUCT spec that outlives any swap
    nosepiece_position_indexing
        also B: zero-basing is an MMCore convention, not a property of the turret
    nosepiece_write_runs_no_escape
        also B: the escape behaviour is the stand's firmware under a software write
    stand_ti2e_lock_groups
        also: the lock-group assignment is a CONTRACT decision, correct by being made
    trapping_laser_identity
        also: '1064 nm, rated 5 W' is a PRODUCT spec of the Tweez 300 folded into a bench claim

kind A, grouped by the event that ends them:
   6  the CSU-W1 is replaced
        csuw1_disk_position_is_the_bright_selector
        csuw1_disk_position_states
        csuw1_disk_speed_exposure_constraint
        csuw1_port_driver_access
        csuw1_port_is_the_camera_splitter
        csuw1_shutter_gates_confocal_excitation
   2  the stand is replaced
        nosepiece_write_runs_no_escape
        z_retract_direction_is_measured
   1  a body is replaced or the two are moved between arms
        camera_bodies_are_told_apart_by_serial
   1  a camera is replaced by a different model
        cameras_both_kinetix22
   1  the CSU-W1 excitation turret is re-loaded
        csuw1_dichroic_slots
   1  the CSU-W1 port is re-loaded
        csuw1_port_slots
   1  the emission wheels are re-cabled
        emission_wheel_camera_mapping
   1  the emission wheel is re-loaded
        emission_wheel_filter_positions
   1  the Ti2 filter turret cube is changed
        filter_cube_mxr00724_is_five_band
   1  the combiner is re-fitted
        laser_shutter_on_the_combiner
   1  a thermometer is installed at the sample
        no_thermometer_at_the_sample
   1  the nosepiece is re-loaded
        nosepiece_objective_assignment
   1  the nosepiece is replaced by one with a different count
        nosepiece_position_indexing
   1  the optical tweezers are replaced
        objective_change_invalidates_trap_calibration
   1  the 595/31 filter is swapped out
        red_path_605_is_the_ff01_595_31_filter
   1  the air conditioning is changed or fails
        room_temperature_is_controlled
   1  the temperature stage is connected
        sample_temperature_not_actuated
   1  the stage stack is re-fitted
        stand_ti2e_lock_groups
   1  the trapping laser gains a software path
        trap_laser_power_has_no_software_path
   1  the trapping laser is replaced
        trapping_laser_identity

A total 26, distinct events 20, largest cluster 6

kind A regrouped by the UNIT that gets touched:
   8  the CSU-W1 unit
   3  the emission filter wheels
   3  the room and its environmental fittings
   3  the Ti2 stand and its stage stack
   3  the optical tweezers
   2  the two camera bodies
   2  the nosepiece
   1  the Ti2 filter turret
   1  the laser combiner

  26 entries / 9 units, largest 8  (vs 20 distinct actions above)
```
