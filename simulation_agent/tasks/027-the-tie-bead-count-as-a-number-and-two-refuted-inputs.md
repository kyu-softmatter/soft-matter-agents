# 027 — the bead count one bleach needs, as a number; and two refuted inputs in sim-20261008-001

**For:** `simulation-20261007-1`. Nobody else takes this card.

Written by `manager-simulation-20261007-1`. You read this; you do not edit it
(§6.2-2). Report to me by session message when each part is committed.

## Part 1 — state the tie count as a number

**Why.** The microscope's statistics axis for the bleach-recovery design now
takes the round's minimum bead count **only as a store entry**, and abstains
until one exists (`plan.md` 11-26). Librarian task 049 (`39058bd`) enters it
the moment a card states it. Today it is prose in
`result-sim-20260930-401-run-20260930-401-n300-dt-f12-b30`'s `estimation.note`
and `beads_where_spread_is_a_tie` in
`questions/sim-20260930-401/stage2_runs.json`. It is in no `numbers[]` item,
and the store does not take numbers from prose.

**The quantity is registered** as `recovery_curve_tie_particle_count`
(`2fff8de`). Read its definition whole before you write anything. It is the
**effective** count, column count times contrast squared, so that your own
2026-10-08 correction travels with the number. 401's model bleaches a sharp
column, so its value is the plain column count at contrast 1. The card must say
so, and it must name `correction_to_sim_20260930_401_bead_count` (`fde42cd`) as
the reason a design at high NA needs far more beads than the value reads.

**What the number must carry:**
- **precision.** Decade, `order_of_magnitude`. It is read between five scan
  points (96 and 315 beads bracket it) against a tie factor of ten, so "about
  300" is honest and 299.8 is not.
- **source and grade.** Derivable from the runs, `simulated:` as the declared
  configuration earns it. Remember that `bd_overdamped` declares its output
  dependent on its input for diffusivity. This number is a statistical
  property of the estimator on finite counts, not the diffusivity, so check
  which field and grade the rules put it in, and **say on the card which
  rule you applied**.
- **the configuration it holds at.** Spot radius, bleach and frame fractions,
  box, bead diameter, the tie factor, the spread criterion (95th to 5th
  percentile), and the 90-per-cent criterion the librarian names.

**Which card.** It is your call under the rules, and there are two candidates:
a revision of the 401 result card, whose own run is the 300-bead scan point,
or a card of its own. A revision is a new `v<N>_` file and never an overwrite.
Overwriting a revision at its own path is the record this repository has
already lost once. **If neither form can carry a number read across several
runs without minting a run or a plan, stop and tell me**, as you did on
026. That would be a contract gap and mine to design.

## Part 2 — two refuted inputs in sim-20261008-001

The librarian's read-only sweep (its task 048) found that
`questions/sim-20261008-001/goal.json` cites entries the store had **already
refuted** at the version you pinned, `kbv-b1253d99047e`:

1. **`emission_wavelength_5um` = 680 nm from `kb:tracer_emission_peak`, at
   E3.** That entry is `refuted_by` `particles_show_on_the_green_605_path`: the
   5 µm beads fluoresce under green excitation and show through a 605 band,
   observed on this bench and before it. The vendor's 680 nm is disproved and
   was used as a live input to the diffraction width and depth of field.
2. **`pixel_size_<objective>_zoom_1x`** for 4x to 100x, in `kb_refs`. Each is
   refuted by its own `_computed` entry, which is the calculated pitch at E4,
   not a measurement.

**The fault is shared, and none of it was hidden.** You read the snapshot as a
file on the degraded path, and the server does not yet make a refutation
impossible to miss. The librarian is fixing the server. A session started
before that fix keeps the old behaviour, so **read `refuted_by` yourself on
every entry you cite** until I tell you the fix has landed.

**What to do:**
- Revise the goal. Take the emission from what the bench observed. The store
  holds the 605 path, not a 680 peak, so it is probably a gap with a stated
  assumption. Name the gap. Cite the pixel sizes as the `_computed` entries at
  E4.
- Re-run `src/focus_stage1.py` against the revised inputs, with the same
  interpreter rule as before, and **say for each of the four conclusions
  whether it moved by more than a tie.** A shift from 680 to about 605 nm is
  roughly 10 per cent in a diffraction width, so a tie is the likely answer,
  but the card must show it rather than assume it.
- Revisions are new files beside the old ones, `v2_`, never overwrites.
  If anything in `findings/simulation-20261007-1-20261008.json` stands on a
  refuted input, write today's findings file
  (`findings/simulation-20261007-1-20261012.json`). Say which earlier item it
  supersedes and why, and leave the earlier file as it is.

## Added 2026-10-12, evening: the server fix, and who takes this card

**The server fix landed at `c77226b`** (2026-10-12 18:21 -0700). Refuted
and superseded entries now say so on every row (`status`, `refuted_by`,
`superseded_by`), and an answer lists its `withdrawn` rows. It reaches only a
session **whose server started after that time**. **And on the degraded path
it reaches nothing at all**: a snapshot read as a file carries
`refuted_by` and nothing flags it. On the Office computer the server
cannot start until `sh` is on the Windows PATH (root `CLAUDE.md`). So the rule
is not "until the fix lands". **Read `refuted_by` by hand on every entry you cite
unless the server actually answered this session**, and the `degraded` field
says which case you are in.

**Corrected the same evening: the server does start on the Office computer
now.** The sentence above about `sh` was copied from the root `CLAUDE.md`, and
that paragraph is stale. `Git\bin` is on the PATH and the app was restarted.
`manager-librarian-20261007-1` probed the server from a session here and got
an answer, microscope-20261007-1 logged 26 real calls today, and this session
gained the librarian's tools when it restarted. So a session started after
`c77226b` gets the fix. The rule is unchanged: read `refuted_by` by hand
unless the server answered *this* session.

**`simulation-20261007-1`'s session closed before this card reached it.** A
vacated identity is not inherited, so the card is for **the next simulation
execution seat the person seats**, registered in `contracts/seats.json`. That
seat reads this card as its own, and I tell it so by message.

## What crosses, and how

Unchanged from 026: nothing to the bridge, no push. The person hands results
over. The librarian picks up Part 1's card and today's findings from the tree.
Tell me the card id and commit, and I tell the librarian's manager.

## Done when

Part 1: a committed card carries `recovery_curve_tie_particle_count` in
`numbers[]` with decade precision, a derivable grade, its configuration and
the contrast caveat, and the validator ends `0 failed` on a tree whose digest
you quote. Part 2: the revised goal cites no refuted entry, each conclusion
says whether it moved, and anything superseded is named.
