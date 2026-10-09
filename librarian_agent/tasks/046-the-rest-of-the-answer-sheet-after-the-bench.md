# 046 — the rest of the answer sheet, once the bench has answered

status: **open, waiting on the bench** · issued 2026-10-07 by
manager-librarian-20261007-1 · **for librarian-20261007-1, with 043 and from
the same record**: the bench of Monday 2026-10-12 (moved from 2026-10-08 by the person on 2026-10-09) answers both, and one reader of
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
