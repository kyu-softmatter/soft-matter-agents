# Operator verification pass — 2026-09-17

**What it was** The operator went row by row over the two flat tables in
`kb/staging/` at the instrument and said, for each row, what he read off the
hardware. The pass is the source `src_operator_read_20260917`; the items he
stated from memory instead are `src_operator_recall_20260917`, and they are E5.

**Its standing decision** Every `confirmed_by` stamp that predated the pass was
treated as unverified until re-affirmed item by item. A stamp applied in bulk
records less than it claims.

## What changed, and why it is worth knowing

**A device existed only because an extractor could not find it.**
`camera_splitter` was recorded as a channel with no driver, no automation and no
read-back, sourced as *absent from every configuration file and from the loaded
device list*. It was absent under that name because it was already present under
another: it is the confocal unit's port. Every field the row asserted was wrong,
and the row had forced a human instruction sheet onto three of the five
configurations. → `csuw1_port_is_the_camera_splitter`,
`csuw1_port_driver_access`

**Two pairs of elements were one mechanism each.** The port with the splitter,
and the confocal/bright-field selector with the disk in/out selector. Both were
predicted by the same asymmetry: the `confocal` configuration named one member
of each pair while the three widefield and transmitted configurations named the
other. One mechanism recorded twice under two names produces exactly that.
→ `csuw1_disk_position_is_the_bright_selector`

**The camera split is spectral, not by intensity.** Three port slots: empty
reaches the red camera only, a 561 nm dichroic reaches both in different bands,
a 100/0 mirror reaches the blue camera only. The old description — *one of:
single camera, or split* — did not constrain which camera got the light, and two
of the three states send none to one of them. → `csuw1_port_slots`

**A channel that was never connected is not a channel.** The temperature stage
exists and has never been driven. It left the channel list and became a claim
plus two gaps, because omitting a thing from a list and erasing it are different
acts. → `sample_temperature_not_actuated`

**The cameras are the same model.** Both Kinetix 22, which closes a discrepancy
the earlier dossier left open between a purchase quote and the current state: a
swap did happen against the quote. `primary` and `second detector` were naming,
not hardware. → `cameras_both_kinetix22`

**The objectives arrived, and their positions count from zero.** Six lenses,
positions 0 through 5. The position-to-lens mapping is an operator reading; the
numerical aperture, working distance and coverglass tolerance are catalog
specifications cited to part numbers. Those are two claims with two sources and
they are two sets of entries, because a lens swap falsifies one and leaves the
other standing. → `nosepiece_position_indexing`,
`nosepiece_objective_assignment`, `objective_*`

## Three things the pass deliberately did not produce

**A grade lifted by corroboration.** The emission-wheel-to-camera mapping was
stated with the word *probably*. A spectral splitter puts one wheel on each
output arm, which is consistent with the mapping — and consistency is not a
reading. It stays E5, and one acquisition settles it: move a wheel, see which
camera's image changes. → `emission_wheel_camera_mapping`

**A number read off a curve.** The catalog publishes transmittance as a graph
with no numeric table. A value a model reads off a rendered plot is E6 and may
enter nothing, so no transmission value is in the store and 1064 nm is a
`condition_mismatch` gap. The same applies to the straight-through and reflected
geometry of the splitter, which is self-consistent and still an inference.

**A safety decision.** Two shutters sit in the confocal excitation chain, one at
the combiner and one at the unit's entrance. The store records what each gates.
Which one an abort closes is policy, written by a person in
`microscope_agent/envelope/safety.json`. → `csuw1_shutter_gates_confocal_excitation`,
`laser_shutter_on_the_combiner`

## What the pass leaves open

The port's slot order; which of two configuration names the driver actually
addresses for each merged pair; the emission wheel mapping as a reading rather
than a recollection; `switch_cost` for the port and the disk; the emission wheel
and filter turret position lists; the calibrated pixel size per objective,
intermediate magnification and binning; 1064 nm transmission per objective; the
ambient sample temperature and its drift band. Each is a gap in one of the two
staging tables, with where it was looked for written down.

**Its own record** `~/Desktop/librarian-verification-2026-09-17.md`, written by
the session that ran the pass. This file is the distillation; that one is the
transcript, and it is outside the repository.
