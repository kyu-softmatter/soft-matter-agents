# Configuration: trapping

Every entry in the store about the configuration trapping.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

No registry text: configurations have no table of their own in the store.

## Values

| quantity | value | unit | how it is known | grade and source as recorded | conditions | subject | entry |
|---|---|---|---|---|---|---|---|
| wavelength | 1064 | nm | from a document, a reading off the instrument, or another project's record; the person read it off the instrument | E3 · operator_read:kyuhwan_20260919 | none stated | device optical_tweezers, configuration trapping | [trapping_laser_identity](../entries/trapping_laser_identity.json) |
| rated_max_power | 5 | W | from a document, a reading off the instrument, or another project's record; the person read it off the instrument | E3 · operator_read:kyuhwan_20260919 | none stated | device optical_tweezers, configuration trapping | [trapping_laser_identity](../entries/trapping_laser_identity.json) |

## Claims

### [objective_change_invalidates_trap_calibration](../entries/objective_change_invalidates_trap_calibration.json)

Changing the objective silently invalidates both of the optical tweezers' calibrations -- the GUI's pixel-to-micrometre magnification and the AOD's trapping-field response -- and neither is readable over TCP. Afterwards every commanded trap position in micrometres lands somewhere else and nothing reports it.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@safety-2026-09-03).

Conditions, verbatim:

> Ruled TRANSFER under 10.2.1 and passed 10.3 rule 1, so it caps at E3 -- a run taken in another project is not a run taken here. 10.2's hardware-control-path row is open and says in its own rule that it does not wait for envelope/, because wrapping a control path needs no safety limit. Slot: A4 for the configuration change and O1 preflight for the check it forces, with A7 as the axis that owns commanded motion. It is the specific case of tweez300_reports_nothing_back that bites hardest, because the invalidating action is on a different device from the one that goes wrong. The check is to drive a known amplitude and measure it; the store holds no threshold for what counts as agreement, and that is a caller's judgement recorded in its plan.  NOT THE PIXEL-SIZE CALIBRATION, AND THE STORE NOW SAYS SO AT BOTH ENDS. This entry says an objective change invalidates a pixel-to-micrometre calibration, which reads as covering the twelve pixel_size_\<mag\>_zoom_\<zoom\> rows and does not. What it covers is the tweezers' GUI, which holds ONE such calibration that the swap falsifies; the pixel-size rows are TWELVE, indexed BY objective, so the same action selects among them. The person ruled that directly on 2026-09-21 -- see objective_change_selects_a_pixel_size_row. Written into this entry as well as that one because a cross-reference that lives at one end is found only by whoever arrives at that end, and a reader who reaches this entry first is exactly the reader who would over-apply it.

### [tweez300_reports_nothing_back](../entries/tweez300_reports_nothing_back.json)

The Tweez 300's TCP interface has no readback of any kind -- no position, no force, no trap list, no calibration -- and a return code of 0 means the GUI accepted the command, not that anything happened. Six distinct ways a command can be ignored all return 0: a breakpoint whose enable bits are unset, release bits that do not cover the value, repeat left disabled, a pattern that overruns the calibrated range and is silently clipped to the edge, a GUI calibrated at a different objective so every commanded micrometre is wrong by that ratio, and a named trap that holds no bead.

How it is known: from a document, a reading off the instrument, or another project's record; another project's record (E3 · prior_run:agentic-microscope@safety-2026-09-03).

Conditions, verbatim:

> Ruled TRANSFER under 10.2.1 and passed 10.3 rule 1, so it caps at E3 -- a run taken in another project is not a run taken here. 10.2's hardware-control-path row is open and says in its own rule that it does not wait for envelope/, because wrapping a control path needs no safety limit. Slot: A4, which screens on automatable and read_back, with O1 preflight as the second consumer -- a preflight that reads back to confirm has nothing to read here. This is what read_back: false means on that row, stated rather than left as a flag. Confirmation has to come from outside the interface: by eye in the GUI, or by measuring the result in camera data. Note the contrast with the piezo, which range-checks a trajectory against the travel its controller reports and REFUSES rather than clipping -- two devices on one instrument, opposite behaviours at the same boundary, and only one of them tells you.

### [trap_heating_detection_bound](../entries/trap_heating_detection_bound.json)

The operator recalls not noticing a temperature change in the sample unless the infrared trapping laser was driven above roughly 20 percent on its dial. This records where noticing stopped, by means that were not recorded.

How it is known: recalled or assumed; the person's recollection (E5 · operator_recall:kyuhwan_20260919).

Conditions, verbatim:

> THIS IS NOT A LIMIT AND MAY NOT BE USED AS ONE. 'Keep it under 20 percent' is the sentence someone lifts out of an entry and uses to parameterise a laser, and three separate rules forbid that: safety limits live in a file a person writes and in deterministic code (P0, 2.1 rule 7), they do not transfer (10.3 rule 4), and the grade forbids it on its own -- an E5 may not parameterise an irreversible action without a person's individual approval, and raising laser power onto a sample is irreversible to the sample. Anyone needing a bound writes one in envelope/safety.json after confirming it physically. Three things this says less than it appears to. It is RECALLED, not read, which is why it is E5 while the neighbouring instrument facts are E3. It is a DETECTION BOUND and not a zero: 'did not notice' was measured by unrecorded means, and 'no heating below 20 percent' is a stronger claim than was made. And 20 PERCENT IS A DIAL READING, not a power: a percentage of an unstated maximum is not a quantity, and writing it into numbers[] would not make it one -- the same ruling that keeps a nominal magnification out of numbers[], wearing different clothes. It does not close the heating gap. A measured heating rate is still absent, and a gap that looks satisfied by an E5 recollection is a false absence running backwards. What it does is sharpen what to measure: sweep the dial with a thermometer that has a recorded position, and the bound becomes a curve.

## Disputed and withdrawn

None.

## Reading

- [what_falsifies_the_49_bench_claims.md](../distilled/what_falsifies_the_49_bench_claims.md)

## Related

- [device nosepiece](../wiki/device_nosepiece.md)
- [device optical_tweezers](../wiki/device_optical_tweezers.md)
- [quantity temperature](../wiki/quantity_temperature.md)

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
