# 105 — the 2026-11-09 drag run enters the store before the capability does

Written by `manager-microscope-scope-20261105-1`. You read this; you do not edit it.

**Assigned to `microscope-scope-20261105-3`, the seat that holds
`mic-20261109-001`.** If you are not that seat, take nothing from this card
and report up.

## Why

S3.0 refused the person's wall-effect question (`f637dd43`): no configuration
declares `trapped_particle_drag_offset`. The person told the intake seat
**"decide it"** (`docs/ideas/20261109-scope.md`, I-20261109-scope-02,
`e7aaa5eb`), and the decision is this seat's. The person confirmed this seat
in its own window on 2026-11-09.

**Decided: all three of your requests, in reverse order.** The capability
table's own note says why declaring the observable today would be wrong:
nothing on disk says either stage moves at a controlled velocity, and
declaring it would be *inventing the capability rather than reading it*.
Today's run is that evidence, but only once it is in the store. So:

1. **This card.** You write the run up as findings for the librarian.
2. **The librarian's.** It rules the findings. That includes whatever it
   enters about `piezo_stage`'s commandable elements, which are its table
   (`librarian_agent/kb/staging/devices.v0.json`), not this seat's and not
   yours. The finding carries what was commanded. The row's form is the
   librarian's call.
3. **This seat's, after 2.** It declares `trapped_particle_drag_offset` in
   `contracts/capabilities/microscope.json` on all four imaging
   configurations with `requires_composition: ["trapping"]`, the same
   placement as `trapped_position_distribution`. The measurement is a bead
   position read against a stage drive, and neither depends on which light
   is used. That is also why the declaration covers more configurations than
   the two widefield ones you asked for. The declaration cites the entries 2
   produced and lands no earlier.

Then you re-run the screen on `mic-20261109-001`. The refusal stays as it
is. It was right when it was made.

## What to write

One findings file, `microscope_agent/findings/<your-seat>-20261109.json`, in
the form of `microscope-scope-20261105-1-20261105.json`, delivered to
`librarian_agent`. Every item names its source file and how it was read.
Grades are the librarian's to derive. Write none.

The source is the bench session's records in `D:\automeasure\runs\`: the
`drag_20261109/` directory and the `*_series*_20261109` scripts and logs
beside it. Open them and say which ones you read. Do not reconstruct what
they do not hold.

At least these, each one item:

- **What moved, and how.** The device (piezo or motor stage) and the axis.
  How the velocity was commanded: the command form or the waveform, read off
  the script that sent it. And whether anything read the motion back. A
  commanded 20 um/s with no read-back is a commanded value and must be
  written as one.
- **The operating points actually run.** Velocities, travel per sweep, and
  heights, as the scripts set them. Where a height is a commanded focus
  offset and not a measured gap to the glass, say so.
- **What was measured.** The offset or drag per height that the logs
  record, with the analysis that produced it named by file. The stiffness
  value, the heating correction and the wall formula used at the bench came
  without a source. Each is either traced to a file that computed it, or
  written as a stated assumption. None is passed on as a measurement.
- **The bead.** Only what the person said (one bead, about 5 um, material
  and dye unknown). Not the store's 5 um tracer unless the person ties it.

Anything the records do not settle, ask the bench session (`Hardware
connection testing`) by message. Write down what was asked and what came
back. If neither can say, the item is a gap.

## Done when

The findings file is committed through the commit tool and the validator
reads `0 failed` on the tree it names. Then send the librarian a message
naming the file, and report to this seat with the commit. This seat does
step 3 when the librarian's ruling commits.

## Not in this card

No hardware. The run is over and this card reads its records. No edit to
`contracts/`, to the librarian's store, or to `mic-20261109-001`'s cards
before the re-screen.
