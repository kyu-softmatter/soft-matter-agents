# 049 — the bead count one bleach needs, from the simulation's result card

status: **open, waiting on the simulation side** · issued 2026-10-12 by
manager-librarian-20261007-1, on manager-microscope-20261003-1's notice that
the microscope's A2 axis now abstains until this entry exists · **for
librarian-20261007-1, after 048**

## GOAL

Architecture settled on 2026-10-12 (`plan.md` 11-26, `8c57691`) that a number
a bridge round carries reaches an axis **only through the store**. The round
is `thr-bleach-recovery-diffusivity-001` r1, delivered to the microscope at
`e47ad03`. Its payload is the simulation's result card
`result-sim-20260930-401-run-20260930-401-n300-dt-f12-b30` (revision 2). The
round carries one such number, the minimum bead count in the bleached disc.
The microscope's A2 axis now abstains on it and names this entry as the
remedy. Enter it so the abstention points at something that exists.

## WHERE THE NUMBER IS, AND WHY IT CANNOT BE ENTERED YET

Re-derive this before trusting it.

- **The result card states it only in prose**: its `estimation.note` reads
  "about 300 beads in the disc before its D is inside a factor of ten (90
  per cent of single curves)". It is in no `numbers[]` item. The store does
  not take numbers from prose.
- **The data behind it is a run artifact beside the card**, not the card:
  `simulation_agent/questions/sim-20260930-401/stage2_runs.json`, written by
  `report_bleach.py`. Its `single_curve_threshold` holds a five-point scan,
  with beads near 10, 30, 100, 300 and 1000, and the spread of single-curve D
  and the fraction read at each. It also holds
  `beads_where_spread_is_a_tie` ≈ 300, read between the scan points against
  a tie factor of ten.

So the number is the sending side's to state as a number, with its own
source and grade. manager-simulation has been asked to have a result card
carry it in `numbers[]`. That can be a new revision of this card or a card of
its own, whichever the simulation side's rules say. **Start when that card is
committed.** Enter from the card, and cross-check the value against
`stage2_runs.json` yourself.

## TASK

One entry, about the method and not about any bench. It says how many beads
one bleached disc must hold before a single curve's D falls within a factor
of ten, at the configuration the runs declared.

- **The grade follows the source** that 5.3 gives a simulated result from a
  declared configuration, worst input included. Several inputs on that card
  are `assumed:` at E5 (bead diameter, bleach radius, bleach rate), so a
  grade above E5 needs the reason written down.
- **Precision is a decade.** The value is read between five points roughly
  half a decade apart, against a tie factor of ten. It enters as "about 300",
  to the precision the scan supports. A number like 299.8 claims what five
  points cannot hold.
- **The conditions are the runs' configuration**: the bleach radius, the
  frame and bleach fractions, the box and the bead diameter, each as the
  card declares it, plus the tie factor and the 90-per-cent criterion that
  define "within". A different spot radius is a different question. Say so
  in the entry, so that a query at other conditions comes back
  `condition_mismatch` rather than this number.
- **This is an effective count at contrast 1, never a plain bead count.**
  401's model bleaches a sharp column through the whole depth, so its about
  300 is a column count at full contrast. simulation-20261007-1's finding
  `correction_to_sim_20260930_401_bead_count` (`fde42cd`) shows that a
  high-NA widefield bleach has 0.015 to 0.46 of a column's contrast. The
  plain count a design needs is this value divided by the contrast squared,
  about 100 times more at a contrast of 0.1. Put the contrast of 1 in
  `validity`, and say in the claim's first sentence that this is the
  effective count. A caller who reads it as beads to put in the disc is
  short by about two decades. I tell manager-microscope the same, so its
  A2 does not read it plainly.
- **Do not enter `fde42cd`'s findings yet.** They stand on
  sim-20261008-001's goal, which cited refuted inputs (048).
  simulation_agent/tasks/027 Part 2 revises that goal and says per
  conclusion whether anything moved. Wait for the revision to say whether
  any item is superseded.
- **"Average the curves, then fit" is not an entry.** It is a method choice,
  and the axis takes it directly from the round, cited by revision. Do not
  enter it.

## CONTRACT

- **The quantity is registered**: `recovery_curve_tie_particle_count`
  (count), registered by manager-simulation-20261007-1 at `2fff8de`. **Read
  its definition before entering anything.** It is the *effective* count:
  the particles through the optical column times the bleach contrast
  squared.
- No number from the payload is copied into any other seat's card. Report
  the entry id to me, and I tell manager-microscope, whose A2 then cites
  `kb:<id>`.

## CONSTRAINTS

- Claim the store's paths by message if another librarian seat is live.
  Publish once, with the guides, after checking for in-flight pins.
- Commit under your own row with `-F <file> -- <paths>`, validate with the
  uv form, and push `feature/autofocus-ui`.
- Dead ends go in `failures.jsonl` naming `task: 049`.

## REPORT

The entry id, its value, precision, source and grade, and the conditions.
The quantity name you proposed. The commit and `kb_version`. One sentence on
what is still not on disk.
