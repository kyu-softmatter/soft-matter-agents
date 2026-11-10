# 066 — rule the 2026-11-09 drag-run findings, including what piezo_stage can be commanded to do

Written by `manager-librarian-scope-20261105-1` on 2026-11-09. You read this;
you do not edit it.

**For a librarian execution seat on the microscope computer**
(`librarian-scope-20261105-1`, or whichever librarian seat the person opens
next). No librarian session was running when this was written, so it waits
for one. If you are not a librarian seat, take nothing from this card and
report up.

## Why

The person asked a wall-effect question: how a trapped bead's drag changes
with height above the glass. The microscope's scope screen refused it,
correctly, because no configuration declares the observable
`trapped_particle_drag_offset`. The person told the intake seat "decide it"
(`docs/ideas/20261109-scope.md`, I-20261109-scope-02, `e7aaa5eb`), and
`manager-microscope-scope-20261105-1` decided it in microscope task 105
(`8624725f`) in three steps:

1. the microscope seat writes the bench's 2026-11-09 drag run up as findings
   (done: `82ace365`, revised at `5a0d928b` and `2a664060`);
2. **you rule the findings** -- this card;
3. the microscope manager then declares the observable in
   `contracts/capabilities/microscope.json`, citing the entries you made, and
   not before.

So step 3 waits on you. The capability table's own note is why: nothing on
disk says either stage moves at a controlled velocity, and declaring the
observable without that would be inventing the capability rather than
reading it.

## The input

`microscope_agent/findings/microscope-scope-20261105-3-20261109.json`, **at
`2a664060`**, not the earlier versions at `82ace365` and `5a0d928b`: the
microscope seat asked for the latest to be ruled. Eight items. Three are
marked `for_store: true`, five `false`. The two added at `5a0d928b` record
the bench session's answers by message, so no file read there shows them.
The one added at `2a664060` is the person's own word, committed in
`docs/ideas/20261109-scope.md` (I-20261109-scope-03 to -05: `7ca24d3b`,
`f8a176a0`, `ffb65fe3`).
No grades are written; deriving them is yours. Every source is a file under
`D:/automeasure/` with a sha256, which is outside this repository: re-hash
what you cite, and if a hash differs, stop on that item and say so.

| item | for_store | what it is |
|---|---|---|
| `piezo_x_ramp_commanded_as_readback_points_not_waveform` | true | how the piezo's x speed was commanded (a 50 points/s staircase of position targets, each read back) and what the read-back says |
| `drag_runs_operating_points_and_height_as_stand_z` | true | speeds, travel, camera settings, and heights, **which are stand Z readings and not a measured gap to the glass** |
| `drag_per_height_values_from_bench_analysis` | false | offsets, stiffness, drag per height: values of an observable |
| `heating_correction_and_wall_formula_have_no_computing_file` | false | three bench numbers with no file that computes them |
| `drag_run_bead_identity_not_in_records` | false | the bead has no recorded identity |
| `drag_run_heights_are_fitted_from_the_drag_data_not_measured` | false | the bead heights came from fitting a wall formula, with an assumed radius, to the drag values themselves; the reference Z is where the bead was first trapped, not a found glass contact |
| `stuck_beads_in_focus_at_z_2957_5_same_coverslip` | true | the person's reading: beads stuck on the glass were in focus, at the bead middle, at stand Z 2957.5 um, on the same coverslip as the drag runs. Which stand's Z it is was not said; the microscope seat's reading of that is its own |
| `drag_run_stage_speed_and_pixel_scale_not_independently_checked` | false | 20 um/s is the controller's nominal value; the 0.0646 um pixel came from walking the trap with the tweezers' own steps; the one check tests their product |

## TASK

1. **Rule each item** as transfer, downgrade, discard or hold, with the
   reason. A `for_store: false` item is the microscope seat's request, not
   your ruling. Rule it anyway, and say so if you disagree.
2. **`piezo_stage`'s commandable elements.** The row in
   `kb/staging/devices.v0.json` today says three axes, travel and command
   quantisation were measured only in the prior project. What item 1 shows is
   narrower than "the stage moves at a controlled velocity": a software clock
   sent position targets and the controller's own reading came back. Nothing
   independent of the controller checked the travel, and the closed-loop range
   query was refused in the same log. Decide whether the row gains an element
   or field for commanded x-velocity, what it may claim, and what its limits
   say. **The form is yours.** Whatever you write has to be citable as an
   entry id by the capability declaration in step 3, so say which id that is.
3. **Height.** Item 2's height is a commanded stand-Z position, and the
   `5a0d928b` item says the heights above the glass were fitted from the
   drag data with a wall formula and an assumed 2.5 um radius. **A height
   derived from the wall formula cannot then test the wall formula**, so
   whatever you enter must not let a later plan use these heights as
   independent of the drag. Do not enter Z readings as heights.
   The `2a664060` item is the first glass reference that does not come from
   the fit, and it is the person's reading, so grade it as one. It is not yet
   a height: turning it into one needs the stuck bead's size (unmeasured,
   about 5 um assumed), the focal shift between oil and water, and the
   assumption that a stuck bead and a trapped bead sit alike. The
   comparison in that item's note, which puts the glass near the fit's, is the
   microscope seat's arithmetic, not a finding. Do not enter it as agreement.
   Write a gap for whatever still separates that reading from a measured
   height, naming what would close it.
   The same goes for speed and pixel scale: both rest on the instrument's own
   commands, so if they enter, they enter as that.
4. **The three unsourced bench numbers** (heating coefficient, free-water
   drag, wall formula). A formula with a published source enters from that
   source (10.3 rule 2), not from the bench files. A coefficient from one
   bead, which the person calls uncertain by about 20 percent, is the person's
   stated assumption if it enters at all. None enters as a measurement.
5. **The bead.** It stays unlinked to the store's 5 um tracer until the
   person says which bottle. If the store needs the question asked, send it
   to the intake seat on this computer, `architecture-scope-20261109-1`.
6. Run the usual ingest sequence and lint (task 065), and `kb_index.py`.

## CONTRACT

- No values of registered observables enter. Item 3's numbers are values of
  the observable this whole sequence is for, and they wait for a plan that
  cites their run.
- Not a safety value. The tracking abort was switched off for these runs on
  the person's word. That is a fact about how the run was done. It is not a
  limit, and nothing here writes one into `envelope/`.
- The 30 um/s note in the pattern file (the bead moved 515 nm and escaped on
  the return ramp) is an observation from one run. If it enters, it enters as
  that and not as a speed limit.

## CONSTRAINTS

Your `CLAUDE.md`. Dead ends go in `failures.jsonl` with `task: 066`.

## REPORT

Send to `manager-librarian-scope-20261105-1`, and the same lines to
`manager-microscope-scope-20261105-1`, which waits on them, 6 lines at most:

- the commit hash;
- each item: entered (entry id), held or excluded, one reason;
- the entry id the drag-offset declaration should cite, or why there is none
  yet;
- the gaps written;
- one sentence: what is not yet on disk.

## Not in this card

`microscope-scope-20261105-1-20261105.json` (`9d0aaa5e`, the 2026-11-05
hardware check and REA findings) is also addressed to you and has no card of
its own yet. It is not this card's scope.
