# 046 — the rest of the answer sheet, once the bench has answered

status: **open, re-issued 2026-10-15: the bench answered little; see the section below** · issued 2026-10-07 by
manager-librarian-20261007-1 · **for librarian-20261007-1, with 043 and from
the same record**: the bench of Tuesday 2026-10-13 (moved from 2026-10-08 to 2026-10-12 by the person on 2026-10-09, then to 2026-10-13 on 2026-10-12) answers both, and one reader of
one record is better than two

## GOAL

The answer sheet `kb/staging/dino_autofocus_first_questions.v0.json`
(`4df8e5a`) left seven cards that the store partly holds or does not hold,
and whose answers the person gives at or after the bench. 043 takes the
camera ceiling (SMA-01). This task takes the other six, plus L-052, once the
person has confirmed it. When it ends, each card is either an entry, a named
gap with what was searched, or a plain "does not enter" with the reason. The
sheet says which for every card.

| card | what | the gap it closes or keeps |
|---|---|---|
| L-005 | the 40x water objective's working distance at collar 0.17 | `objective_40x_wd_at_170um` |
| L-031 | which per-objective pixel sizes were measured | none; it re-grades rows |
| L-032 | the 4x stage-to-camera scale and rotation | `stage_camera_transform_4x` |
| L-033 | the parfocal offset from 4x to 100x oil | `parfocal_offset_4x_to_100x` |
| L-056 | the camera's readout mode on 2026-09-30 | `kinetix_red_bit_depth` |
| L-057 | the camera's dark offset | `kinetix_red_dark_offset` |
| L-052 | "605 nm" is a path name (already answered by the store) | nothing enters if the person confirms |

Re-derive the table from the sheet before trusting it.

**Two more reads, added 2026-10-07 from 044's report**. Neither is on the
answer sheet. Each is a device's report of itself, and the store does not
hold it:

- **Which PFS reading means "not engaged."** Card 063's mock session refused
  on it. The bench form's `pfs_release` block records `status_text` and
  properties before, during and after the hand switch.
- **The CSUW1 shutter's closed label.** `csuw1_shutter_state_reads_a_label`
  has "Open" and no closed value. Card 060 step 4 reads the shutter's
  allowed values.

**And the immersion oil, added 2026-10-08.** The person said they will check
it at the bench and report it. This closes the gap
`immersion_oil_refractive_index`, which keeps the 60x and 100x from having a
depth of field computed from the store (045). Two separate facts, two
entries:

- which oil is on the bench: the product as the bottle reads, an instance
  the way the bead bottles are;
- its refractive index: the type's specification, at the wavelength and
  temperature the bottle or the vendor states. One index without its
  wavelength is not a fact about the oil.

Grade each by how it was obtained. A label read at the bench is
`operator_read:`. A value the person states from memory is
`operator_recall:`. The vendor's sheet, if you fetch it, is `spec:`.

Enter each self-report the way 044 entered its self-reports, as settings
read back and graded by the record. **Neither becomes a limit or a command.** Whether
software may write the closed label is the person's exemption, not the
entry's.

## WHAT THE 2026-10-13 BENCH ANSWERED (added 2026-10-15)

The record is `microscope_agent/findings/microscope-20261013-1-20261013.json`
at `1104cc6`. dino's forms were not on the computer that day, so there is
no dino record. Its item `C_not_done` says that the hand measurements, the
40x water working distance and the spinning-disk shutter's closed label were
not done. Per card, as the record stands:

- **L-005, L-031, L-032, L-033, L-056, L-057: not answered.** Each keeps its
  gap. Add a `searched` line: asked at the 2026-10-13 bench, not done (cite
  `C_not_done`).
- **The CSUW1 closed label: not read** (`A_csuw1_shutter` saw only "Open").
  The gap stays. The same item read Turret1Shutter and Turret2Shutter at
  State 0. That is a reading at state 0, not a sighting of a closed
  shutter, so it does not lift `filter_turret_shutters_close_at_state_0`
  above a recollection.
- **The PFS readings were answered** (`A_pfs_readings`): three properties
  read in three states (off before ever switched on, on and locked, off
  again), and "on but still searching" was not caught. These are device
  self-reports, to enter as settings read back. The item shows that PFS
  Status reads two different strings in the two off states. So say plainly
  in the entry that no single Status string means "not engaged". **Which
  reading the envelope uses is the person's**, and the person has written
  one; that is not the entry's to judge.
  **The person explained the two off codes on 2026-10-15**, directly in
  manager-librarian's window: both are off, and the codes differ because one
  reading was taken in range and the other out of range. That matches the
  item's own `PFS in Range` column ("Out of Range" with Status
  `0000000000000000`; "In Range" with `0000000100000000`). Enter it as the
  person's statement, graded as one. Keep it separate from the readings, so
  the readings stay what was read and the reading of them stays the
  person's. It says that in range or out of range shows in the Status code
  apart from engagement. It does not say which bit means engaged, and the
  searching state is still unread.
- **The immersion oil: Nikon Type F Non-Fluorescing Immersion Oil, 30 ml,
  PCB-free.** The person read the bottle's label at the bench and reported it on
  2026-10-15, directly in manager-librarian's window, giving as reference the
  reseller's page `https://www.edmundoptics.com/p/Nikon-Type-F-Non-Fluorescing-30ml-PCB-Free-Immersion-Oil/57189`
  (Edmund Optics stock number 57189; the link's tracking parameters were
  dropped). Two entries, as above:
  - **which oil is on the bench**: **a label the person read at the bench**
    (the person's correction, 2026-10-15). So it is `operator_read:`, a
    reading of the bottle, not a recollection. The bench visit was
    2026-10-13. The microscope findings file does not record the reading,
    so cite the person's statement in manager-librarian's window as where
    it is written. **The link is reference material for the oil's data, not
    the evidence of which oil is used.** This line said otherwise for one
    commit (`560a92a`), and that was wrong.
  - **its refractive index**: a type fact. Take it from the manufacturer's
    own published sheet for Type F if you can reach one, and otherwise from
    the reseller's page. Prefer the manufacturer, and say which you used. It
    is `spec:`, with the wavelength and temperature the sheet states, and
    the dispersion values too if the sheet gives them. **Never from memory.**
    A remembered index is a made-up number and does not enter.
- **L-052: confirmed by the person on 2026-10-15**, directly in
  manager-librarian's window: "605" is a path name, not a wavelength. As the
  answer sheet says, nothing enters, because the store already holds it
  (`red_path_605_is_the_ff01_595_31_filter`). Set the card's status to
  answered and cite this line.

**Every item in that file says `for_store: false`.** Enter nothing from it
until the microscope side offers the items you need. **On 2026-10-15 the
person decided that A_pfs_readings goes to the store** (in manager-microscope's
window). microscope-20261007-1 offers it with `for_store: true` in its own
findings file, citing the original. Enter the PFS readings from that
offering, once it is in HEAD. The oil and the person's explanation of the PFS
codes do not wait on it.

## TASK

For each card, read the person's answer: dino-autofocus's filled bench form
(`docs/runs/` on its bench branch, read as data), its statements S1–S6 with
their `confirmed_at_bench` fields, and the microscope seat's findings item
where card 060 asks for one. Then rule it.

- **The source prefix follows what the record shows**, as in 043: a run of
  this system is `measured:`, a reading off the instrument by hand is
  `operator_read:`, and a recollection is `operator_recall:`. A dino-autofocus
  run or record of its own is `prior_run:dino-autofocus@<sha>`, capped at E3,
  and this is the only way a dino-autofocus number enters (`plan.md` 10.3, and
  10.2's 2026-10-03 paragraph). A statement written before the bench and
  confirmed at it is still graded by how it was confirmed, not by the fact
  that it was.
- **L-005 is not a clearance limit.** A working distance is knowledge. The
  focus upper limit is the person's, written into the envelope and never
  derived from a working distance (the person, 2026-10-04). The entry says
  so in its conditions, so no plan reads it as a ceiling.
- **L-033 is a starting centre, never a target.** It enters as what was
  measured. A plan may use it to centre a search, and the search still finds
  focus by walking.
- **L-031 re-grades and does not re-enter.** If only some pixel sizes were
  measured, the others are what their entries already say. Where an entry
  claims more than the answer supports, supersede it under rule 8 with the
  lower grade. Do not edit its grade in place.
- **L-056 and L-057 touch the camera entries 043 writes.** Keep them
  consistent: one readout-mode vocabulary across all three, as the software
  read it back.
- A card with no answer by the end of the visit stays a gap. Add a
  `searched` line saying the bench was asked and did not answer.

Update every card's status in the answer sheet.

## CONTRACT

- No safety limit, from any card. The envelope is the person's.
- No dino-autofocus number enters except as `prior_run:` at E3 at most,
  ruled under 10.2.1 and recorded in a `kb/sources/` record with the
  discards, the way the 17 definitions went in on 2026-10-04.
- One claim per file. A conflict with an existing entry is kept, not merged.

## CONSTRAINTS

- Same as 043: your seat row first, claim the store's paths by message with
  librarian-20261004-1, publish once with the guides after checking for
  in-flight pins, uv-form validator, push `feature/autofocus-ui`. If 043 and
  this task finish together, one publish for both is right.
- Dead ends go in `failures.jsonl` naming `task: 046`.

## REPORT

Per card: entry id, gap kept, or "does not enter", each with its source
prefix and grade. The answer sheet's new state in one line. The commit and
`kb_version`. One sentence on what is still not on disk.
